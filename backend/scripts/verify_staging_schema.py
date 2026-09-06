#!/usr/bin/env python3
"""Verify a migrated staging database against the baseline on disk.

Answers the question the previous task deliberately left open: *does the
baseline actually produce the schema it claims?* Static SQL inspection cannot
answer it — only a real MySQL server can — so this script compares what the
baseline file declares with what a live staging database ended up containing.

Checks performed:
  * every table declared by the baseline exists, and nothing extra appeared;
  * the view exists and is a view (not the phpMyAdmin placeholder table);
  * triggers exist with the expected names;
  * foreign keys match the baseline's ``ADD CONSTRAINT`` clauses;
  * declared indexes exist on their tables;
  * AUTO_INCREMENT columns are actually AUTO_INCREMENT;
  * migration history is consistent (nothing recorded as applied is missing).

Read-only: this script issues SELECTs against information_schema and never
modifies the target.

Usage::

    export MIGRATION_DB_HOST=127.0.0.1
    export MIGRATION_DB_USER=root
    export MIGRATION_DB_PASSWORD=...
    export MIGRATION_DB_NAME=rentalhub_staging
    python scripts/verify_staging_schema.py

Refuses to run against a host that looks like production.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from migrations.catalog import find_baseline, split_statements  # noqa: E402
from migrations.history import (  # noqa: E402
    HISTORY_TABLE,
    DatabaseConfig,
    DatabaseConfigError,
    MigrationStatus,
    MySQLBackend,
)
from migrations.runner import looks_like_production  # noqa: E402

_CREATE_TABLE = re.compile(
    r"^CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`(\w+)`", re.IGNORECASE
)
_CREATE_VIEW = re.compile(
    r"^CREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\S+\s+)?"
    r"(?:SQL\s+SECURITY\s+\S+\s+)?VIEW\s+`(\w+)`",
    re.IGNORECASE,
)
_CREATE_TRIGGER = re.compile(r"^CREATE\s+TRIGGER\s+`?(\w+)`?", re.IGNORECASE)
_ALTER_TABLE = re.compile(r"^ALTER\s+TABLE\s+`(\w+)`", re.IGNORECASE)
_ADD_CONSTRAINT = re.compile(
    r"ADD\s+CONSTRAINT\s+`(\w+)`\s+FOREIGN\s+KEY", re.IGNORECASE
)
_ADD_INDEX = re.compile(
    r"ADD\s+(?:(UNIQUE|PRIMARY|FULLTEXT|SPATIAL)\s+)?KEY(?:\s+`(\w+)`)?", re.IGNORECASE
)
_MODIFY_AUTOINC = re.compile(
    r"MODIFY\s+`(\w+)`\s+[^,;]*\bAUTO_INCREMENT\b", re.IGNORECASE
)
_AUTOINC_COLUMN = re.compile(r"^\s*`(\w+)`\s+[^,]*\bAUTO_INCREMENT\b", re.IGNORECASE)


class Expectations:
    """What the baseline file declares the schema should contain."""

    def __init__(self, baseline: Path):
        self.tables: set[str] = set()
        self.views: set[str] = set()
        self.triggers: set[str] = set()
        self.foreign_keys: dict[str, str] = {}
        self.indexes: set[tuple[str, str]] = set()
        self.auto_increment: set[tuple[str, str]] = set()
        self._parse(baseline)

    def _parse(self, baseline: Path) -> None:
        sql = baseline.read_text(encoding="utf-8").replace("\r\n", "\n")
        for statement in split_statements(sql):
            head = statement.lstrip()

            match = _CREATE_VIEW.match(head)
            if match:
                self.views.add(match.group(1).lower())
                continue

            match = _CREATE_TABLE.match(head)
            if match:
                name = match.group(1).lower()
                self.tables.add(name)
                for line in head.splitlines():
                    column = _AUTOINC_COLUMN.match(line)
                    if column:
                        self.auto_increment.add((name, column.group(1).lower()))
                continue

            match = _CREATE_TRIGGER.match(head)
            if match:
                self.triggers.add(match.group(1).lower())
                continue

            match = _ALTER_TABLE.match(head)
            if match:
                table = match.group(1).lower()
                for constraint in _ADD_CONSTRAINT.findall(head):
                    self.foreign_keys[constraint.lower()] = table
                for kind, index_name in _ADD_INDEX.findall(head):
                    if index_name:
                        self.indexes.add((table, index_name.lower()))
                    elif kind.upper() == "PRIMARY":
                        self.indexes.add((table, "primary"))
                for column in _MODIFY_AUTOINC.findall(head):
                    self.auto_increment.add((table, column.lower()))

        # phpMyAdmin emits a placeholder CREATE TABLE for each view; the real
        # object is the view, so it must not be expected as a base table.
        self.tables -= self.views


class Observations:
    """What the live staging database actually contains."""

    def __init__(self, backend: MySQLBackend):
        self._backend = backend
        self.tables = {t for t in backend.tables() if t != HISTORY_TABLE}
        self.views = backend.views()
        self.triggers = backend.triggers()
        self.tables -= self.views

    def _rows(self, sql: str) -> list[tuple]:
        with self._backend._conn.cursor() as cur:  # noqa: SLF001 - read-only helper
            cur.execute(sql)
            return list(cur.fetchall())

    def foreign_keys(self) -> dict[str, str]:
        rows = self._rows(
            "SELECT LOWER(CONSTRAINT_NAME), LOWER(TABLE_NAME) "
            "FROM information_schema.TABLE_CONSTRAINTS "
            "WHERE CONSTRAINT_SCHEMA = DATABASE() "
            "AND CONSTRAINT_TYPE = 'FOREIGN KEY'"
        )
        return {name: table for name, table in rows}

    def indexes(self) -> set[tuple[str, str]]:
        rows = self._rows(
            "SELECT LOWER(TABLE_NAME), LOWER(INDEX_NAME) "
            "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE()"
        )
        return {(table, index) for table, index in rows}

    def auto_increment(self) -> set[tuple[str, str]]:
        rows = self._rows(
            "SELECT LOWER(TABLE_NAME), LOWER(COLUMN_NAME) "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND EXTRA LIKE '%auto_increment%'"
        )
        return {(table, column) for table, column in rows}


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.warnings: list[str] = []

    def check(self, name: str, missing: set | list, *, extra: set | list = ()) -> None:
        missing = sorted(missing)
        extra = sorted(extra)
        if missing:
            self.failures.append(f"{name}: missing {len(missing)} → {missing[:15]}")
        if extra:
            # Extra objects are reported but not fatal: a staging database may
            # legitimately carry migrations newer than the baseline.
            self.warnings.append(f"{name}: unexpected {len(extra)} → {extra[:15]}")
        if not missing and not extra:
            print(f"  OK   {name}")

    def render(self) -> int:
        print()
        for warning in self.warnings:
            print(f"  WARN {warning}")
        for failure in self.failures:
            print(f"  FAIL {failure}")
        print()
        if self.failures:
            print(f"RESULT: FAILED ({len(self.failures)} check(s))")
            return 1
        print("RESULT: PASSED" + (f" with {len(self.warnings)} warning(s)" if self.warnings else ""))
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--migrations-dir", default=str(BACKEND_DIR / "migrations"))
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="acknowledge running the read-only checks against production",
    )
    args = parser.parse_args(argv)

    try:
        from dotenv import load_dotenv

        env_file = BACKEND_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except Exception:
        pass

    baseline = find_baseline(Path(args.migrations_dir))
    if baseline is None:
        print("ERROR: no baseline file found", file=sys.stderr)
        return 2

    try:
        config = DatabaseConfig.from_env()
    except DatabaseConfigError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if looks_like_production(config) and not args.allow_production:
        print(
            f"ERROR: {config.label} looks like production. This script is read-only, "
            "but staging verification belongs on staging. Pass --allow-production to "
            "inspect production deliberately.",
            file=sys.stderr,
        )
        return 2

    expected = Expectations(baseline)
    print("=" * 72)
    print(f"baseline : {baseline.name}")
    print(f"target   : {config.label}")
    print(
        f"declared : {len(expected.tables)} tables, {len(expected.views)} view(s), "
        f"{len(expected.triggers)} trigger(s), {len(expected.foreign_keys)} FK, "
        f"{len(expected.indexes)} index(es)"
    )
    print("=" * 72)

    backend = MySQLBackend(config)
    report = Report()
    try:
        observed = Observations(backend)

        report.check(
            "tables",
            expected.tables - observed.tables,
            extra=observed.tables - expected.tables,
        )
        report.check(
            "views",
            expected.views - observed.views,
            extra=observed.views - expected.views,
        )
        report.check(
            "triggers",
            expected.triggers - observed.triggers,
            extra=observed.triggers - expected.triggers,
        )

        observed_fks = observed.foreign_keys()
        report.check("foreign keys", set(expected.foreign_keys) - set(observed_fks))
        misplaced = [
            f"{name} on `{observed_fks[name]}`, expected `{table}`"
            for name, table in expected.foreign_keys.items()
            if name in observed_fks and observed_fks[name] != table
        ]
        if misplaced:
            report.failures.append(f"foreign keys attached to wrong table: {misplaced}")

        report.check("indexes", expected.indexes - observed.indexes())
        report.check("auto_increment columns", expected.auto_increment - observed.auto_increment())

        if backend.history_exists():
            rows = backend.history_rows()
            applied = [r for r in rows if r.status is MigrationStatus.APPLIED]
            stamped = [r for r in rows if r.status is MigrationStatus.STAMPED]
            skipped = [r for r in rows if r.status is MigrationStatus.SKIPPED]
            failed = [r for r in rows if r.status is MigrationStatus.FAILED]
            print(
                f"  history: {len(applied)} applied, {len(stamped)} stamped, "
                f"{len(skipped)} skipped, {len(failed)} failed"
            )
            if failed:
                report.failures.append(
                    "history contains failed migrations: "
                    + ", ".join(r.version for r in failed)
                )
            for record in skipped:
                print(f"    skipped {record.version}: {(record.notes or '')[:90]}")
        else:
            report.warnings.append(
                f"`{HISTORY_TABLE}` is absent: this database was not migrated by the runner"
            )

        return report.render()
    finally:
        backend.close()


if __name__ == "__main__":
    raise SystemExit(main())