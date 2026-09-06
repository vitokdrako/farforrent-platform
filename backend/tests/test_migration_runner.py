#!/usr/bin/env python3
"""Tests for the versioned migration runner (Завдання №8).

These tests never open a network socket and never read production credentials.
The database is replaced by :class:`FakeBackend`, an in-memory schema that
tracks tables, views and triggers, so the runner's *decisions* can be checked
exactly — including the decisions to refuse.

What is covered:
  * empty DB install (baseline + compatible migrations);
  * existing DB stamp (no DDL, reported as stamped rather than applied);
  * skipped migrations (001_modify_customers_table, add_user_tracking);
  * checksum mismatch detection;
  * failed migration → recorded FAILED, following migrations not attempted;
  * pending migrations after a new file appears.

Run:
    cd backend && python -m pytest tests/test_migration_runner.py -v
    cd backend && python tests/test_migration_runner.py
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from migrations import catalog as catalog_mod  # noqa: E402
from migrations.catalog import discover, split_statements  # noqa: E402
from migrations.history import (  # noqa: E402
    HISTORY_TABLE,
    DatabaseConfig,
    HistoryRecord,
    MigrationStatus,
)
from migrations.runner import (  # noqa: E402
    Action,
    MigrationError,
    Runner,
    State,
    detect_state,
)

# --------------------------------------------------------------------------- #
# Fake database
# --------------------------------------------------------------------------- #

_CREATE_TABLE = re.compile(
    r"^CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`?(\w+)`?", re.IGNORECASE
)
_CREATE_VIEW = re.compile(
    r"^CREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\S+\s+)?"
    r"(?:SQL\s+SECURITY\s+\S+\s+)?VIEW\s+`?(\w+)`?",
    re.IGNORECASE,
)
_CREATE_TRIGGER = re.compile(r"^CREATE\s+TRIGGER\s+`?(\w+)`?", re.IGNORECASE)
_DROP_TRIGGER = re.compile(
    r"^DROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?", re.IGNORECASE
)
_DROP_TABLE = re.compile(r"^DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?", re.IGNORECASE)
_ALTER_TABLE = re.compile(r"^ALTER\s+TABLE\s+`?(\w+)`?", re.IGNORECASE)


class FakeBackend:
    """In-memory stand-in for a MySQL schema.

    Only models what the runner actually reasons about: which tables, views and
    triggers exist, plus the history table. ``executed`` records every statement
    so a test can assert that a stamp performed no schema DDL at all.
    """

    def __init__(self, *, tables=(), views=(), triggers=(), fail_on: str | None = None):
        self._tables: set[str] = set(tables)
        self._views: set[str] = set(views)
        self._triggers: set[str] = set(triggers)
        self._history: list[HistoryRecord] | None = None
        self.executed: list[str] = []
        self.fail_on = fail_on

    label = "fake://memory/test_db"

    def tables(self) -> set[str]:
        tables = set(self._tables)
        if self._history is not None:
            tables.add(HISTORY_TABLE)
        return tables

    def views(self) -> set[str]:
        return set(self._views)

    def triggers(self) -> set[str]:
        return set(self._triggers)

    def execute(self, statement: str) -> None:
        self.executed.append(statement)
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError(f"simulated MySQL failure near {self.fail_on!r}")

        head = statement.lstrip()
        match = _CREATE_VIEW.match(head)
        if match:
            self._views.add(match.group(1).lower())
            return
        match = _CREATE_TABLE.match(head)
        if match:
            self._tables.add(match.group(1).lower())
            return
        match = _CREATE_TRIGGER.match(head)
        if match:
            self._triggers.add(match.group(1).lower())
            return
        match = _DROP_TRIGGER.match(head)
        if match:
            self._triggers.discard(match.group(1).lower())
            return
        match = _DROP_TABLE.match(head)
        if match:
            self._tables.discard(match.group(1).lower())
            return
        match = _ALTER_TABLE.match(head)
        if match:
            name = match.group(1).lower()
            if name not in self._tables:
                # Mirrors real MySQL error 1146; this is exactly what a stale
                # migration does when it reaches a table that never existed.
                raise RuntimeError(f"Table '{name}' doesn't exist")

    def history_exists(self) -> bool:
        return self._history is not None

    def history_create(self) -> None:
        if self._history is None:
            self._history = []

    def history_rows(self) -> list[HistoryRecord]:
        return list(self._history or [])

    def history_insert(self, record: HistoryRecord) -> None:
        assert self._history is not None, "history table missing"
        if any(row.version == record.version for row in self._history):
            raise RuntimeError(f"Duplicate entry '{record.version}' for key PRIMARY")
        self._history.append(record)

    def close(self) -> None:
        pass


# --------------------------------------------------------------------------- #
# Synthetic migration set
# --------------------------------------------------------------------------- #

BASELINE_SQL = """\
-- baseline snapshot (synthetic)
SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
/*!40101 SET NAMES utf8mb4 */;

CREATE TABLE `orders` (
  `order_id` int(11) NOT NULL,
  `note` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `order_log` (
  `id` int(11) NOT NULL,
  `note` text
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

DELIMITER $$
CREATE TRIGGER `orders_after_insert` AFTER INSERT ON `orders` FOR EACH ROW BEGIN
    INSERT INTO order_log (note) VALUES (CONCAT('[from #', NEW.order_id, '] ok'));
END
$$
DELIMITER ;
"""

WIDGETS_SQL = """\
CREATE TABLE IF NOT EXISTS widgets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    label VARCHAR(64) NOT NULL
);
"""

DROP_TRIGGER_SQL = "DROP TRIGGER IF EXISTS orders_after_insert;\n"

GADGETS_SQL = """\
CREATE TABLE IF NOT EXISTS gadgets (
    id INT AUTO_INCREMENT PRIMARY KEY
);
"""

# Real filenames on purpose: these two carry the documented skip rules and must
# stay recognisable by the exact names used in the migration documents.
CUSTOMERS_SQL = """\
ALTER TABLE customers ADD COLUMN password_hash VARCHAR(255) NULL;
"""

USER_TRACKING_SQL = """\
ALTER TABLE finance_transactions ADD COLUMN created_by_id INT NULL;
"""

ALTER_ONLY_SQL = "ALTER TABLE orders ADD COLUMN source VARCHAR(32) NULL;\n"


def make_dir(files: dict[str, str]) -> Path:
    path = Path(tempfile.mkdtemp(prefix="migrations_"))
    for name, content in files.items():
        (path / name).write_text(content, encoding="utf-8")
    return path


def standard_set() -> dict[str, str]:
    return {
        "000_baseline.sql": BASELINE_SQL,
        "001_modify_customers_table.sql": CUSTOMERS_SQL,
        "100_add_widgets.sql": WIDGETS_SQL,
        "101_drop_orders_trigger.sql": DROP_TRIGGER_SQL,
        "add_user_tracking.sql": USER_TRACKING_SQL,
    }


def installed_schema() -> FakeBackend:
    """A database whose contents match a completed install of ``standard_set``."""
    return FakeBackend(tables={"orders", "order_log", "widgets"})


# --------------------------------------------------------------------------- #
# SQL splitting
# --------------------------------------------------------------------------- #


def test_split_statements_keeps_trigger_body_intact():
    statements = split_statements(BASELINE_SQL)
    triggers = [s for s in statements if s.upper().startswith("CREATE TRIGGER")]
    assert len(triggers) == 1, statements
    body = triggers[0]
    # The `;` inside the trigger body must not have ended the statement.
    assert "INSERT INTO order_log" in body
    assert body.rstrip().endswith("END")
    # `DELIMITER` is a client directive, never sent to the server.
    assert not any(s.upper().startswith("DELIMITER") for s in statements)


def test_split_statements_ignores_comments_and_semicolons_in_strings():
    sql = (
        "-- a comment; with a semicolon\n"
        "INSERT INTO t (note) VALUES ('a;b');\n"
        "/* block; comment */\n"
        "SELECT 1;\n"
    )
    statements = split_statements(sql)
    assert len(statements) == 2, statements
    assert statements[0] == "INSERT INTO t (note) VALUES ('a;b')"


def test_real_repository_catalog_marks_the_two_stale_migrations():
    """The documented skip rules must apply to the real files, by their real names."""
    real = discover(BACKEND_DIR / "migrations")
    by_version = {m.version: m for m in real.migrations}

    assert real.baseline is not None, "000_baseline.sql must be present"
    assert by_version["001"].name == "modify_customers_table"
    assert by_version["001"].skip_rule is not None
    assert "customers" in by_version["001"].skip_rule.reason

    assert "add_user_tracking" in by_version
    rule = by_version["add_user_tracking"].skip_rule
    assert rule is not None
    assert "fin_transactions" in rule.reason

    # Every other migration must be applicable; a new skip rule should be a
    # conscious decision, not a side effect.
    unexpected = [
        version
        for version, migration in by_version.items()
        if migration.skip_rule is not None and version not in ("001", "add_user_tracking")
    ]
    assert not unexpected, unexpected


def test_real_baseline_splits_into_executable_statements():
    real = discover(BACKEND_DIR / "migrations")
    assert real.baseline is not None
    statements = real.baseline.statements()
    creates = [s for s in statements if s.upper().startswith("CREATE TABLE")]
    triggers = [s for s in statements if s.upper().startswith("CREATE TRIGGER")]
    views = [s for s in statements if "VIEW `v_order_finance`" in s]
    assert len(creates) >= 60, len(creates)
    assert len(triggers) == 2, len(triggers)
    assert len(views) == 1, len(views)
    assert not any(s.upper().startswith("INSERT INTO") for s in statements)


# --------------------------------------------------------------------------- #
# State detection
# --------------------------------------------------------------------------- #


def test_detect_state_distinguishes_empty_from_legacy():
    assert detect_state(FakeBackend()) is State.EMPTY
    assert detect_state(FakeBackend(tables={"orders"})) is State.LEGACY_UNTRACKED

    tracked = FakeBackend(tables={"orders"})
    tracked.history_create()
    assert detect_state(tracked) is State.TRACKED


# --------------------------------------------------------------------------- #
# Fresh install
# --------------------------------------------------------------------------- #


def test_install_on_empty_database_applies_baseline_and_skips_stale():
    runner = Runner(FakeBackend(), discover(make_dir(standard_set())), log=lambda *_: None)
    report = runner.install()

    assert report.healthy, (report.checksum_mismatch, report.schema_mismatch)
    applied = {r.version for r in report.applied}
    skipped = {r.version for r in report.skipped}
    assert applied == {"000", "100", "101"}
    assert skipped == {"001", "add_user_tracking"}
    assert not report.pending
    assert not report.stamped

    # Skipped rows must carry the reason and prove nothing ran.
    for record in report.skipped:
        assert record.statements_executed == 0
        assert record.notes and ("customers" in record.notes or "fin_transactions" in record.notes)
        assert record.status is MigrationStatus.SKIPPED


def test_install_refuses_a_non_empty_database():
    runner = Runner(installed_schema(), discover(make_dir(standard_set())), log=lambda *_: None)
    try:
        runner.install()
    except MigrationError as exc:
        assert "not empty" in str(exc)
    else:
        raise AssertionError("install must refuse a database that already has tables")


def test_install_dry_run_touches_nothing():
    backend = FakeBackend()
    runner = Runner(
        backend, discover(make_dir(standard_set())), dry_run=True, log=lambda *_: None
    )
    runner.install()
    assert backend.executed == []
    assert not backend.history_exists()


def test_install_without_baseline_is_refused():
    files = standard_set()
    del files["000_baseline.sql"]
    runner = Runner(FakeBackend(), discover(make_dir(files)), log=lambda *_: None)
    try:
        runner.install()
    except MigrationError as exc:
        assert "baseline" in str(exc).lower()
    else:
        raise AssertionError("install without a baseline must be refused")


# --------------------------------------------------------------------------- #
# Existing database: stamp
# --------------------------------------------------------------------------- #


def test_stamp_records_stamped_without_executing_any_ddl():
    backend = installed_schema()
    runner = Runner(backend, discover(make_dir(standard_set())), log=lambda *_: None)
    report = runner.stamp("101")

    assert {r.version for r in report.stamped} == {"000", "100", "101"}
    assert not report.applied, "a stamp must never report anything as applied"
    assert {r.version for r in report.skipped} == {"001"}
    assert report.healthy

    # The only DDL allowed is creating the bookkeeping table itself.
    schema_ddl = [s for s in backend.executed if HISTORY_TABLE not in s]
    assert schema_ddl == [], schema_ddl
    for record in report.stamped:
        assert record.statements_executed == 0
        assert record.schema_fingerprint
        assert "NOT executed" in (record.notes or "")

    # `add_user_tracking` has no numeric prefix, so it sorts after 101 and is
    # outside the requested range. A stamp settles exactly what was asked for
    # and nothing more; the file stays pending and honest.
    assert [m.version for m in report.pending] == ["add_user_tracking"]


def test_a_remote_host_is_treated_as_production_until_declared_staging():
    """The safe default: an undeclared remote target is assumed to be live.

    Production hostnames are intentionally absent from the source tree, so the
    guard cannot rely on recognising a name it was never told about.
    """
    from migrations.runner import looks_like_production

    remote = DatabaseConfig(
        host="db.somewhere.example.com",
        port=3306,
        user="u",
        password="p",
        database="rentalhub",
    )
    local = DatabaseConfig(
        host="127.0.0.1",
        port=3306,
        user="u",
        password="p",
        database="rentalhub_staging",
    )

    for key in ("MIGRATION_PRODUCTION_HOSTS", "MIGRATION_TARGET_IS_STAGING"):
        os.environ.pop(key, None)
    try:
        assert looks_like_production(remote), "an undeclared remote host must be refused"
        assert not looks_like_production(local), "localhost must stay usable"

        # Declaring staging is an explicit, auditable act by the operator.
        os.environ["MIGRATION_TARGET_IS_STAGING"] = "true"
        assert not looks_like_production(remote)

        # An explicitly listed production host wins over that declaration.
        os.environ["MIGRATION_PRODUCTION_HOSTS"] = "db.somewhere.example.com"
        assert looks_like_production(remote)
    finally:
        for key in ("MIGRATION_PRODUCTION_HOSTS", "MIGRATION_TARGET_IS_STAGING"):
            os.environ.pop(key, None)


def test_no_remote_hostname_is_hardcoded_in_the_runner():
    """The baseline was scrubbed of the production host; keep the code clean too.

    Deliberately a *shape* check, not a literal comparison: a test that spelled
    the production hostname out would commit to Git the very string it exists to
    keep out. So it rejects any literal that merely looks like a remote host.
    """
    source = (BACKEND_DIR / "migrations" / "runner.py").read_text(encoding="utf-8")
    literals = re.findall(r"""["']([^"'\s]+)["']""", source)
    hostish = [
        value
        for value in literals
        if re.fullmatch(
            r"[a-z0-9][a-z0-9.-]*\.(?:com|ua|net|org|tools|io|dev|cloud)",
            value,
            re.IGNORECASE,
        )
    ]
    assert hostish == [], f"hardcoded remote host(s) in runner.py: {hostish}"
    assert (
        "MIGRATION_PRODUCTION_HOSTS" in source
    ), "the guard must read live hosts from the environment"


def test_stale_legacy_migration_left_pending_by_stamp_is_skipped_on_upgrade():
    backend = installed_schema()
    directory = make_dir(standard_set())
    Runner(backend, discover(directory), log=lambda *_: None).stamp("101")

    backend.executed.clear()
    report = Runner(backend, discover(directory), log=lambda *_: None).upgrade()

    assert "add_user_tracking" in {r.version for r in report.skipped}
    assert not report.pending
    assert backend.executed == [], "a skipped migration must execute no SQL at all"
    record = next(r for r in report.skipped if r.version == "add_user_tracking")
    assert record.statements_executed == 0
    assert "fin_transactions" in (record.notes or "")


def test_stamp_refuses_when_the_schema_lacks_the_objects():
    # `widgets` was never created here, so migration 100 cannot be claimed.
    backend = FakeBackend(tables={"orders", "order_log"})
    runner = Runner(backend, discover(make_dir(standard_set())), log=lambda *_: None)
    try:
        runner.stamp("101")
    except MigrationError as exc:
        assert "cannot be confirmed" in str(exc)
        assert "widgets" in str(exc)
    else:
        raise AssertionError("stamp must refuse to claim a migration it cannot verify")
    assert not backend.history_exists()


def test_stamp_requires_acknowledgement_for_unverifiable_migrations():
    files = standard_set()
    files["102_alter_orders.sql"] = ALTER_ONLY_SQL
    directory = make_dir(files)

    backend = installed_schema()
    runner = Runner(backend, discover(directory), log=lambda *_: None)
    try:
        runner.stamp("102")
    except MigrationError as exc:
        assert "102" in str(exc)
        assert "--accept-unverifiable" in str(exc)
    else:
        raise AssertionError("an ALTER-only migration cannot be silently stamped")

    report = Runner(
        installed_schema(), discover(directory), log=lambda *_: None
    ).stamp("102", accept_unverifiable=True)
    assert "102" in {r.version for r in report.stamped}


def test_stamp_refuses_an_empty_database():
    runner = Runner(FakeBackend(), discover(make_dir(standard_set())), log=lambda *_: None)
    try:
        runner.stamp("101")
    except MigrationError as exc:
        assert "empty" in str(exc)
    else:
        raise AssertionError("stamp on an empty database must be refused")


def test_stamp_plan_reports_skip_and_stamp_separately():
    runner = Runner(installed_schema(), discover(make_dir(standard_set())), log=lambda *_: None)
    plan = {item.version: item.action for item in runner.plan_stamp("101")}
    assert plan["000"] is Action.STAMP
    assert plan["001"] is Action.SKIP
    assert plan["100"] is Action.STAMP
    assert plan["101"] is Action.STAMP


# --------------------------------------------------------------------------- #
# Upgrade / pending
# --------------------------------------------------------------------------- #


def test_upgrade_applies_only_pending_migrations():
    directory = make_dir(standard_set())
    backend = FakeBackend()
    Runner(backend, discover(directory), log=lambda *_: None).install()

    (directory / "102_add_gadgets.sql").write_text(GADGETS_SQL, encoding="utf-8")
    runner = Runner(backend, discover(directory), log=lambda *_: None)

    before = runner.status()
    assert [m.version for m in before.pending] == ["102"]

    backend.executed.clear()
    report = runner.upgrade()
    assert "102" in {r.version for r in report.applied}
    assert not report.pending
    assert all("gadgets" in s or HISTORY_TABLE in s for s in backend.executed), backend.executed


def test_upgrade_is_a_no_op_when_nothing_is_pending():
    directory = make_dir(standard_set())
    backend = FakeBackend()
    Runner(backend, discover(directory), log=lambda *_: None).install()

    backend.executed.clear()
    report = Runner(backend, discover(directory), log=lambda *_: None).upgrade()
    assert backend.executed == []
    assert report.healthy


def test_upgrade_refuses_an_untracked_schema():
    runner = Runner(installed_schema(), discover(make_dir(standard_set())), log=lambda *_: None)
    try:
        runner.upgrade()
    except MigrationError as exc:
        assert "stamp" in str(exc)
    else:
        raise AssertionError("upgrade must not touch a schema with no history")


def test_reapplying_a_settled_version_is_impossible():
    directory = make_dir(standard_set())
    backend = FakeBackend()
    Runner(backend, discover(directory), log=lambda *_: None).install()

    record = backend.history_rows()[0]
    try:
        backend.history_insert(record)
    except RuntimeError as exc:
        assert "Duplicate entry" in str(exc)
    else:
        raise AssertionError("the primary key must make a second record impossible")


# --------------------------------------------------------------------------- #
# Checksums
# --------------------------------------------------------------------------- #


def test_checksum_mismatch_is_detected_and_blocks_upgrade():
    directory = make_dir(standard_set())
    backend = FakeBackend()
    Runner(backend, discover(directory), log=lambda *_: None).install()

    # Someone edits a migration that already ran here.
    (directory / "100_add_widgets.sql").write_text(
        WIDGETS_SQL + "\nALTER TABLE widgets ADD COLUMN extra INT NULL;\n",
        encoding="utf-8",
    )
    (directory / "102_add_gadgets.sql").write_text(GADGETS_SQL, encoding="utf-8")

    runner = Runner(backend, discover(directory), log=lambda *_: None)
    report = runner.status()
    assert [v for v, _, _ in report.checksum_mismatch] == ["100"]
    assert not report.healthy

    backend.executed.clear()
    try:
        runner.upgrade()
    except MigrationError as exc:
        assert "Checksum mismatch" in str(exc)
    else:
        raise AssertionError("upgrade must stop when history and disk disagree")
    assert backend.executed == [], "no migration may run while history is untrustworthy"


def test_history_without_a_file_on_disk_blocks_upgrade():
    directory = make_dir(standard_set())
    backend = FakeBackend()
    Runner(backend, discover(directory), log=lambda *_: None).install()

    (directory / "100_add_widgets.sql").unlink()
    runner = Runner(backend, discover(directory), log=lambda *_: None)
    assert runner.status().orphan_history == ["100"]
    try:
        runner.upgrade()
    except MigrationError as exc:
        assert "missing from disk" in str(exc)
    else:
        raise AssertionError("a checkout older than the database must not migrate it")


# --------------------------------------------------------------------------- #
# Failure handling
# --------------------------------------------------------------------------- #


def test_failed_migration_is_recorded_as_failed_and_stops_the_run():
    files = standard_set()
    files["102_broken.sql"] = "CREATE TABLE broken_marker (id INT);\n"
    files["103_after_broken.sql"] = GADGETS_SQL
    directory = make_dir(files)

    backend = FakeBackend(fail_on="broken_marker")
    runner = Runner(backend, discover(directory), log=lambda *_: None)
    try:
        runner.install()
    except MigrationError as exc:
        message = str(exc)
        assert "102" in message
        assert "recorded as FAILED" in message
    else:
        raise AssertionError("a failing migration must abort the run")

    history = {row.version: row for row in backend.history_rows()}
    assert history["102"].status is MigrationStatus.FAILED
    assert history["102"].error_message
    assert "103" not in history, "migrations after a failure must not be attempted"
    assert "gadgets" not in backend.tables()

    # And the failure must keep blocking until a human resolves it.
    follow_up = Runner(backend, discover(directory), log=lambda *_: None)
    report = follow_up.status()
    assert [r.version for r in report.failed] == ["102"]
    assert not report.healthy
    try:
        follow_up.upgrade()
    except MigrationError as exc:
        assert "failed migration" in str(exc)
    else:
        raise AssertionError("upgrade must not step over a recorded failure")


def test_stale_migration_would_really_fail_if_it_were_not_skipped():
    """The skip rules are not cosmetic: the SQL genuinely cannot run here.

    Temporarily clearing the rules proves the migration fails against a schema
    without `customers`, which is why marking it "applied" would be a lie.
    """
    directory = make_dir(
        {"000_baseline.sql": BASELINE_SQL, "001_modify_customers_table.sql": CUSTOMERS_SQL}
    )
    saved = dict(catalog_mod.SKIP_RULES)
    catalog_mod.SKIP_RULES.clear()
    try:
        runner = Runner(FakeBackend(), discover(directory), log=lambda *_: None)
        try:
            runner.install()
        except MigrationError as exc:
            assert "customers" in str(exc)
        else:
            raise AssertionError("001 cannot succeed without a `customers` table")
    finally:
        catalog_mod.SKIP_RULES.clear()
        catalog_mod.SKIP_RULES.update(saved)


def main() -> int:
    tests = [
        value
        for name, value in sorted(globals().items())
        if name.startswith("test_") and callable(value)
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"  PASS  {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - report and continue
            failures += 1
            print(f"  FAIL  {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())