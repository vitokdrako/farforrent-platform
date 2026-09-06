#!/usr/bin/env python3
"""Versioned migration runner for the RentalHub database.

Commands::

    python -m migrations.runner status
    python -m migrations.runner install                    # empty database only
    python -m migrations.runner stamp --to 011             # adopt existing schema
    python -m migrations.runner upgrade [--to NNN]
    python -m migrations.runner verify

The one rule this runner is built around: **a migration is never recorded as
applied unless its SQL actually executed.** Everything else follows from it.

* ``applied``  — the runner executed the SQL here.
* ``stamped``  — the schema objects were observed to already exist, so the
  migration was adopted *without* running DDL. Never reported as ``applied``.
* ``skipped``  — known inapplicable (``catalog.SKIP_RULES``); no SQL, no claim.
* ``failed``   — execution started and failed. The row stays so the reason
  survives the process, and later migrations are not attempted.

Design document: ``migrations/MIGRATION_VERSIONING.md``.
Staging checklist: ``migrations/STAGING_VERIFICATION.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:  # allow `python migrations/runner.py`
    sys.path.insert(0, str(BACKEND_DIR))

from migrations.catalog import (  # noqa: E402
    BASELINE_VERSION,
    SENTINEL_TABLE,
    Catalog,
    Evidence,
    MigrationFile,
    discover,
)
from migrations.history import (  # noqa: E402
    HISTORY_TABLE,
    Backend,
    DatabaseConfig,
    DatabaseConfigError,
    HistoryRecord,
    MigrationStatus,
    MySQLBackend,
    current_actor,
)

#: Hosts that are unambiguously the developer's own machine. Everything else is
#: treated as potentially live unless explicitly declared staging, so forgetting
#: to declare a remote host errs towards refusing to touch it.
LOCAL_HOST_MARKERS = ("localhost", "127.0.0.1", "::1", "0.0.0.0")


def _production_host_markers() -> tuple[str, ...]:
    """Hostname fragments that identify a live server, from the environment.

    Real production hostnames are deliberately **not** baked into this file.
    The baseline was scrubbed of the production host so it would not live in
    Git; hardcoding it here would put it straight back. Operators supply
    `MIGRATION_PRODUCTION_HOSTS` (comma-separated) instead.
    """
    raw = os.environ.get("MIGRATION_PRODUCTION_HOSTS", "")
    return tuple(part.strip().lower() for part in raw.split(",") if part.strip())


def _declared_staging() -> bool:
    """True only when the operator explicitly vouched for a non-local target."""
    value = os.environ.get("MIGRATION_TARGET_IS_STAGING", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


class MigrationError(RuntimeError):
    """A migration operation was refused or failed. Always actionable."""


class State(str, Enum):
    """What the target database currently is.

    Confusing :data:`EMPTY` with :data:`LEGACY_UNTRACKED` is the one mistake
    that destroys data, so the distinction is made from observable schema
    objects rather than from configuration.
    """

    #: No history table and no application schema.
    EMPTY = "EMPTY"
    #: Application schema present, but no migration history.
    LEGACY_UNTRACKED = "LEGACY_UNTRACKED"
    #: History table present.
    TRACKED = "TRACKED"


class Action(str, Enum):
    """What the runner intends to do with one migration."""

    APPLY = "apply"
    STAMP = "stamp"
    SKIP = "skip"
    ALREADY = "already-settled"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PlanItem:
    version: str
    name: str
    action: Action
    reason: str = ""

    def render(self) -> str:
        suffix = f" — {self.reason}" if self.reason else ""
        return f"{self.action.value:<15} {self.version:<32} {self.name}{suffix}"


@dataclass
class StatusReport:
    """Everything ``status`` prints, and what ``verify`` turns into exit codes."""

    state: State
    target: str
    fingerprint: str
    applied: list[HistoryRecord] = field(default_factory=list)
    stamped: list[HistoryRecord] = field(default_factory=list)
    skipped: list[HistoryRecord] = field(default_factory=list)
    failed: list[HistoryRecord] = field(default_factory=list)
    pending: list[MigrationFile] = field(default_factory=list)
    checksum_mismatch: list[tuple[str, str, str]] = field(default_factory=list)
    schema_mismatch: list[tuple[str, str]] = field(default_factory=list)
    orphan_history: list[str] = field(default_factory=list)

    @property
    def healthy(self) -> bool:
        return not (
            self.checksum_mismatch
            or self.schema_mismatch
            or self.failed
            or self.orphan_history
        )


def schema_fingerprint(backend: Backend) -> str:
    """Stable SHA-256 over the names of tables, views and triggers.

    Deliberately name-only. A column-level fingerprint would change on every
    unrelated ``ALTER``, and an operator who cannot trust the number stops
    reading it. This is enough to tell "the schema I expected" from "an empty
    database" or "somebody else's database".
    """
    tables = {t for t in backend.tables() if t != HISTORY_TABLE}
    parts = (
        ["table:" + name for name in sorted(tables)]
        + ["view:" + name for name in sorted(backend.views())]
        + ["trigger:" + name for name in sorted(backend.triggers())]
    )
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def detect_state(backend: Backend) -> State:
    if backend.history_exists():
        return State.TRACKED
    if SENTINEL_TABLE in backend.tables():
        return State.LEGACY_UNTRACKED
    return State.EMPTY


def looks_like_production(config: DatabaseConfig) -> bool:
    """Best-effort detection of the live database.

    Three signals, in order of confidence:

    1. the host matches `MIGRATION_PRODUCTION_HOSTS`;
    2. the host is remote and nobody declared it staging — the default leans
       towards refusing, because an extra refusal costs a minute while a
       migrated production costs a restore;
    3. the target is exactly the database the application itself runs against
       and it is not local.
    """
    host = config.host.strip().lower()
    if any(marker in host for marker in _production_host_markers()):
        return True
    # A remote host nobody declared as staging is assumed live. The costly
    # mistake is migrating production by accident, not one extra refusal.
    if host and not any(marker in host for marker in LOCAL_HOST_MARKERS):
        if not _declared_staging():
            return True
    app_host = os.environ.get("RH_DB_HOST", "")
    app_db = os.environ.get("RH_DB_DATABASE", "")
    return bool(
        app_host
        and app_db
        and config.host == app_host
        and config.database == app_db
        and not config.is_local
    )


class Runner:
    """Executes and records migrations against one target database."""

    def __init__(
        self,
        backend: Backend,
        catalog: Catalog,
        *,
        actor: str | None = None,
        dry_run: bool = False,
        log=print,
    ):
        self.backend = backend
        self.catalog = catalog
        self.actor = actor or current_actor()
        self.dry_run = dry_run
        self.log = log

    # ---------------------------------------------------------------- reading

    def _history(self) -> dict[str, HistoryRecord]:
        if not self.backend.history_exists():
            return {}
        return {row.version: row for row in self.backend.history_rows()}

    def status(self) -> StatusReport:
        state = detect_state(self.backend)
        history = self._history()
        files = self.catalog.by_version()

        report = StatusReport(
            state=state,
            target=self.backend.label,
            fingerprint=schema_fingerprint(self.backend),
        )

        base_tables = self.backend.tables()
        present = base_tables | self.backend.views()
        triggers = self.backend.triggers()

        for version, record in history.items():
            bucket = {
                MigrationStatus.APPLIED: report.applied,
                MigrationStatus.STAMPED: report.stamped,
                MigrationStatus.SKIPPED: report.skipped,
                MigrationStatus.FAILED: report.failed,
            }[record.status]
            bucket.append(record)

            migration = files.get(version)
            if migration is None:
                # History remembers a migration that no longer exists on disk:
                # either the file was deleted or this checkout is older than the
                # database. Both mean "do not proceed blindly".
                report.orphan_history.append(version)
                continue

            if record.checksum != migration.checksum:
                report.checksum_mismatch.append(
                    (version, record.checksum, migration.checksum)
                )

        # Schema verification runs over the whole settled range rather than file
        # by file. Migration 005 creates a trigger that 006 deliberately drops,
        # so judging 005 in isolation would report a mismatch that is in fact
        # the correct end state.
        settled = [
            version
            for version in self.catalog.versions_in_order()
            if version in history
            and history[version].status
            in (MigrationStatus.APPLIED, MigrationStatus.STAMPED)
        ]
        for version, evidence in self._surviving_evidence(settled).items():
            missing = self._missing_for(evidence, present, base_tables, triggers)
            if missing:
                report.schema_mismatch.append((version, ", ".join(missing)))

        for version in self.catalog.versions_in_order():
            record = history.get(version)
            if record is not None and record.is_settled:
                continue
            candidate = files.get(version)
            if candidate is not None:
                report.pending.append(candidate)

        return report

    def _surviving_evidence(self, versions: list[str]) -> dict[str, Evidence]:
        """Per-migration evidence that survives the rest of the range.

        An object created by one migration and dropped by a later one is no
        longer proof of anything, and demanding it would turn correct history
        into a false alarm.
        """
        files = self.catalog.by_version()
        ordered = [(version, files[version].evidence()) for version in versions if version in files]
        surviving: dict[str, Evidence] = {}
        for index, (version, evidence) in enumerate(ordered):
            later = [item[1] for item in ordered[index + 1 :]]
            dropped_tables: set[str] = set()
            dropped_triggers: set[str] = set()
            created_tables: set[str] = set()
            created_triggers: set[str] = set()
            for future in later:
                dropped_tables |= future.absent_tables
                dropped_triggers |= future.absent_triggers
                created_tables |= future.tables
                created_triggers |= future.triggers
            surviving[version] = Evidence(
                tables=frozenset(evidence.tables - dropped_tables),
                triggers=frozenset(evidence.triggers - dropped_triggers),
                absent_triggers=frozenset(evidence.absent_triggers - created_triggers),
                absent_tables=frozenset(evidence.absent_tables - created_tables),
                altered=evidence.altered,
            )
        return surviving

    @staticmethod
    def _missing_for(
        evidence: Evidence,
        present: set[str],
        base_tables: set[str],
        triggers: set[str],
    ) -> list[str]:
        """Discrepancies between expected and observed schema objects."""
        missing = [f"table `{name}`" for name in sorted(evidence.tables - present)]
        missing += [
            f"trigger `{name}`" for name in sorted(evidence.triggers - triggers)
        ]
        missing += [
            f"trigger `{name}` still present"
            for name in sorted(evidence.absent_triggers & triggers)
        ]
        missing += [
            f"table `{name}` still present"
            for name in sorted(evidence.absent_tables & base_tables)
        ]
        return missing

    # ---------------------------------------------------------------- writing

    def _record(self, record: HistoryRecord) -> None:
        if self.dry_run:
            return
        self.backend.history_insert(record)

    def _ensure_history(self) -> None:
        """Create the history table if absent.

        This is the only DDL a ``stamp`` performs. It creates bookkeeping, not
        application schema, and it is reported explicitly so nobody has to guess.
        """
        if self.backend.history_exists():
            return
        self.log(f"  creating `{HISTORY_TABLE}` (bookkeeping only, no schema change)")
        if not self.dry_run:
            self.backend.history_create()

    def _guard_before_write(self, report: StatusReport) -> None:
        """Refuse to change anything while the recorded history is untrustworthy."""
        if report.checksum_mismatch:
            details = "\n".join(
                f"  {version}: recorded {recorded[:12]}…, on disk {actual[:12]}…"
                for version, recorded, actual in report.checksum_mismatch
            )
            raise MigrationError(
                "Checksum mismatch: already-recorded migrations differ from the "
                "files on disk. This environment has diverged; resolve it before "
                f"migrating.\n{details}"
            )
        if report.failed:
            versions = ", ".join(r.version for r in report.failed)
            raise MigrationError(
                f"Previous run left failed migration(s): {versions}. Inspect the "
                f"error in `{HISTORY_TABLE}`, fix the schema by hand, then delete "
                "the failed row. The runner will not step over a failure."
            )
        if report.orphan_history:
            versions = ", ".join(report.orphan_history)
            raise MigrationError(
                f"History references migrations missing from disk: {versions}. "
                "This checkout is not the one that migrated this database."
            )

    def _apply(self, migration: MigrationFile) -> HistoryRecord:
        """Execute one migration, recording either success or failure."""
        statements = migration.statements()
        self.log(f"  {migration.version:<10} {migration.name} ({len(statements)} stmt)")
        if self.dry_run:
            return HistoryRecord(
                version=migration.version,
                name=migration.name,
                checksum=migration.checksum,
                status=MigrationStatus.APPLIED,
                applied_by=self.actor,
                statements_executed=0,
                notes="dry-run: nothing executed",
            )

        started = time.monotonic()
        executed = 0
        try:
            for statement in statements:
                self.backend.execute(statement)
                executed += 1
        except Exception as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            failure = HistoryRecord(
                version=migration.version,
                name=migration.name,
                checksum=migration.checksum,
                status=MigrationStatus.FAILED,
                applied_by=self.actor,
                execution_ms=elapsed,
                statements_executed=executed,
                error_message=f"statement #{executed + 1}: {exc}"[:4000],
            )
            # Recorded as FAILED, never as APPLIED: the SQL did not complete.
            self.backend.history_insert(failure)
            raise MigrationError(
                f"Migration {migration.version} ({migration.name}) failed at "
                f"statement #{executed + 1}: {exc}\n"
                "It is recorded as FAILED, not applied. MySQL does not roll back "
                "DDL, so the schema may be partially changed — inspect it before "
                "retrying. No further migrations were attempted."
            ) from exc

        record = HistoryRecord(
            version=migration.version,
            name=migration.name,
            checksum=migration.checksum,
            status=MigrationStatus.APPLIED,
            applied_by=self.actor,
            execution_ms=int((time.monotonic() - started) * 1000),
            statements_executed=executed,
        )
        self._record(record)
        return record

    def _skip(self, migration: MigrationFile) -> HistoryRecord:
        rule = migration.skip_rule
        assert rule is not None
        self.log(f"  {migration.version:<10} {migration.name} — SKIPPED ({rule.kind.value})")
        self.log(f"             reason: {rule.reason}")
        record = HistoryRecord(
            version=migration.version,
            name=migration.name,
            checksum=migration.checksum,
            status=MigrationStatus.SKIPPED,
            applied_by=self.actor,
            statements_executed=0,
            notes=f"{rule.kind.value}: {rule.reason} "
            f"(missing: {', '.join(rule.missing_objects)})",
        )
        self._record(record)
        return record

    # --------------------------------------------------------------- commands

    def plan_install(self) -> list[PlanItem]:
        if self.catalog.baseline is None:
            raise MigrationError(
                "Clean install unavailable: no 000_baseline.sql / 000_initial.sql "
                "in the migrations directory. See migrations/SCHEMA_GAP.md."
            )
        items = [
            PlanItem(
                BASELINE_VERSION,
                self.catalog.baseline.name,
                Action.APPLY,
                "schema snapshot",
            )
        ]
        for migration in self.catalog.migrations:
            if migration.skip_rule is not None:
                items.append(
                    PlanItem(
                        migration.version,
                        migration.name,
                        Action.SKIP,
                        migration.skip_rule.kind.value,
                    )
                )
            else:
                items.append(PlanItem(migration.version, migration.name, Action.APPLY))
        return items

    def install(self) -> StatusReport:
        """Create a database from the baseline, then apply compatible migrations.

        Only ever runs against a genuinely empty database. The emptiness check is
        structural (no tables at all), not a promise from the caller.
        """
        state = detect_state(self.backend)
        tables = self.backend.tables()
        if state is not State.EMPTY or tables:
            raise MigrationError(
                f"install refused: target {self.backend.label} is not empty "
                f"(state={state.value}, {len(tables)} table(s) present).\n"
                "Use `stamp` to adopt an existing database, or `upgrade` to apply "
                "pending migrations."
            )

        plan = self.plan_install()
        self.log(f"install → {self.backend.label}")
        for item in plan:
            self.log("  plan: " + item.render())
        if self.dry_run:
            self.log("dry-run: nothing executed")
            return self.status()

        self._ensure_history()
        assert self.catalog.baseline is not None
        self._apply(self.catalog.baseline)
        for migration in self.catalog.migrations:
            if migration.skip_rule is not None:
                self._skip(migration)
            else:
                self._apply(migration)

        report = self.status()
        if report.checksum_mismatch:
            raise MigrationError(
                "Post-install checksum verification failed: "
                f"{[v for v, _, _ in report.checksum_mismatch]}"
            )
        return report

    def plan_stamp(self, to_version: str) -> list[PlanItem]:
        history = self._history()
        versions = self.catalog.versions_in_order()
        if to_version not in versions:
            raise MigrationError(
                f"Unknown version to stamp: {to_version}. "
                f"Known versions: {', '.join(versions)}"
            )
        cutoff = versions.index(to_version)
        files = self.catalog.by_version()
        in_range = list(versions[: cutoff + 1])
        # Skipped migrations never ran, so their objects must not be expected.
        surviving = self._surviving_evidence(
            [version for version in in_range if files[version].skip_rule is None]
        )
        base_tables = self.backend.tables()
        present = base_tables | self.backend.views()
        triggers = self.backend.triggers()

        items: list[PlanItem] = []
        for version in in_range:
            migration = files[version]
            record = history.get(version)
            if record is not None and record.is_settled:
                items.append(
                    PlanItem(version, migration.name, Action.ALREADY, record.status.value)
                )
                continue
            if migration.skip_rule is not None:
                items.append(
                    PlanItem(
                        version,
                        migration.name,
                        Action.SKIP,
                        migration.skip_rule.kind.value,
                    )
                )
                continue
            evidence = surviving[version]
            missing = self._missing_for(evidence, present, base_tables, triggers)
            if missing:
                items.append(
                    PlanItem(
                        version,
                        migration.name,
                        Action.BLOCKED,
                        "not present in schema: " + ", ".join(missing),
                    )
                )
                continue
            reason = "" if evidence.verifiable else "no verifiable objects"
            items.append(PlanItem(version, migration.name, Action.STAMP, reason))
        return items

    def stamp(self, to_version: str, *, accept_unverifiable: bool = False) -> StatusReport:
        """Adopt an existing database into migration history without running DDL.

        Refuses to stamp a migration whose objects are absent: claiming a change
        the schema does not contain is exactly the lie this runner exists to
        prevent. Migrations with nothing observable to check require explicit
        acknowledgement.
        """
        state = detect_state(self.backend)
        if state is State.EMPTY:
            raise MigrationError(
                "stamp refused: the target is empty. An empty database has no "
                "schema to adopt — use `install` instead."
            )

        plan = self.plan_stamp(to_version)
        self.log(f"stamp → {self.backend.label} (up to {to_version})")
        self.log(f"  schema fingerprint: {schema_fingerprint(self.backend)}")
        for item in plan:
            self.log("  plan: " + item.render())

        blocked = [item for item in plan if item.action is Action.BLOCKED]
        if blocked:
            details = "\n".join(f"  {item.version}: {item.reason}" for item in blocked)
            raise MigrationError(
                "stamp refused: these migrations cannot be confirmed against the "
                "current schema, so marking them as applied would be false.\n"
                f"{details}\n"
                "Either the target is not the database you think it is, or those "
                "migrations genuinely never ran here."
            )

        unverifiable = [
            item
            for item in plan
            if item.action is Action.STAMP and item.reason == "no verifiable objects"
        ]
        if unverifiable and not accept_unverifiable:
            versions = ", ".join(item.version for item in unverifiable)
            raise MigrationError(
                f"stamp refused: {versions} create no object the runner can "
                "observe (e.g. ALTER-only migrations), so their presence cannot be "
                "proven. Verify by hand, then re-run with --accept-unverifiable."
            )

        if self.dry_run:
            self.log("dry-run: nothing recorded")
            return self.status()

        self._ensure_history()
        fingerprint = schema_fingerprint(self.backend)
        files = self.catalog.by_version()
        stamped = skipped = 0
        for item in plan:
            migration = files[item.version]
            if item.action is Action.ALREADY:
                continue
            if item.action is Action.SKIP:
                self._skip(migration)
                skipped += 1
                continue
            note = "adopted from existing schema; SQL was NOT executed"
            if item.reason:
                note += f"; {item.reason} (accepted by operator)"
            self._record(
                HistoryRecord(
                    version=migration.version,
                    name=migration.name,
                    checksum=migration.checksum,
                    status=MigrationStatus.STAMPED,
                    applied_by=self.actor,
                    statements_executed=0,
                    schema_fingerprint=fingerprint,
                    notes=note,
                )
            )
            stamped += 1

        self.log(
            f"  STAMPED {stamped} migration(s), skipped {skipped}. "
            "Nothing was applied: no migration SQL was executed."
        )
        return self.status()

    def plan_upgrade(self, to_version: str | None = None) -> list[PlanItem]:
        report = self.status()
        items: list[PlanItem] = []
        for migration in report.pending:
            if to_version is not None and migration.version > to_version:
                continue
            if migration.is_baseline:
                items.append(
                    PlanItem(
                        migration.version,
                        migration.name,
                        Action.BLOCKED,
                        "baseline is applied by `install`, never by `upgrade`",
                    )
                )
                continue
            if migration.skip_rule is not None:
                items.append(
                    PlanItem(
                        migration.version,
                        migration.name,
                        Action.SKIP,
                        migration.skip_rule.kind.value,
                    )
                )
                continue
            items.append(PlanItem(migration.version, migration.name, Action.APPLY))
        return items

    def upgrade(self, to_version: str | None = None) -> StatusReport:
        """Apply migrations that have never run here. Stops at the first failure."""
        state = detect_state(self.backend)
        if state is State.EMPTY:
            raise MigrationError(
                "upgrade refused: the target is empty. Use `install` to create the "
                "schema from the baseline."
            )
        if state is State.LEGACY_UNTRACKED:
            raise MigrationError(
                "upgrade refused: the schema exists but has no migration history. "
                "Adopt it explicitly first: `stamp --to <version>`. Applying "
                "migrations blindly to an untracked schema is how data is lost."
            )

        report = self.status()
        self._guard_before_write(report)

        plan = self.plan_upgrade(to_version)
        self.log(f"upgrade → {self.backend.label}")
        if not plan:
            self.log("  nothing pending")
            return report
        for item in plan:
            self.log("  plan: " + item.render())

        blocked = [item for item in plan if item.action is Action.BLOCKED]
        if blocked:
            details = "\n".join(f"  {item.version}: {item.reason}" for item in blocked)
            raise MigrationError(f"upgrade refused:\n{details}")

        if self.dry_run:
            self.log("dry-run: nothing executed")
            return report

        files = self.catalog.by_version()
        for item in plan:
            migration = files[item.version]
            if item.action is Action.SKIP:
                self._skip(migration)
            else:
                self._apply(migration)
        return self.status()


# ------------------------------------------------------------------ reporting


def render_status(report: StatusReport, log=print) -> None:
    log("=" * 72)
    log(f"target       : {report.target}")
    log(f"state        : {report.state.value}")
    log(f"fingerprint  : {report.fingerprint}")
    log("=" * 72)

    log(f"applied      : {len(report.applied)}")
    for record in report.applied:
        log(f"  {record.version:<32} {record.name}")
    log(f"stamped      : {len(report.stamped)}  (adopted, SQL never executed)")
    for record in report.stamped:
        log(f"  {record.version:<32} {record.name}")
    log(f"skipped      : {len(report.skipped)}")
    for record in report.skipped:
        log(f"  {record.version:<32} {record.name}")
        if record.notes:
            log(f"      {record.notes}")
    log(f"pending      : {len(report.pending)}")
    for migration in report.pending:
        marker = " (will be skipped)" if migration.skip_rule else ""
        log(f"  {migration.version:<32} {migration.name}{marker}")

    log(f"failed       : {len(report.failed)}")
    for record in report.failed:
        log(f"  {record.version:<32} {record.error_message or ''}")
    log(f"checksum mismatch : {len(report.checksum_mismatch)}")
    for version, recorded, actual in report.checksum_mismatch:
        log(f"  {version}: recorded {recorded[:12]}… != on disk {actual[:12]}…")
    log(f"schema mismatch   : {len(report.schema_mismatch)}")
    for version, detail in report.schema_mismatch:
        log(f"  {version}: {detail}")
    if report.orphan_history:
        log(f"history without file : {', '.join(report.orphan_history)}")
    log("=" * 72)
    log("OK" if report.healthy else "PROBLEMS FOUND")


# ------------------------------------------------------------------------ CLI


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        env_file = BACKEND_DIR / ".env"
        if env_file.exists():
            load_dotenv(env_file)
    except Exception:
        pass


def _build_backend(args) -> Backend:
    config = DatabaseConfig.from_env()
    is_production = looks_like_production(config)
    writes = args.command in {"install", "stamp", "upgrade"} and not args.dry_run

    if is_production and args.command == "install":
        raise MigrationError(
            f"install refused: {config.label} looks like the live database. "
            "A clean install is for empty targets only and must never be pointed "
            "at production."
        )
    if is_production and writes and not args.confirm_production:
        raise MigrationError(
            f"{args.command} refused: {config.label} looks like the live database. "
            "Take a backup, then pass --confirm-production if this is intended. "
            "Point MIGRATION_DB_* at staging to work elsewhere."
        )
    if is_production:
        print(f"⚠️  target looks like production: {config.label}")
    return MySQLBackend(config)


def main(argv: list[str] | None = None) -> int:
    _load_env()
    parser = argparse.ArgumentParser(
        prog="python -m migrations.runner", description=__doc__
    )
    parser.add_argument(
        "command", choices=["status", "install", "stamp", "upgrade", "verify"]
    )
    parser.add_argument("--to", help="target version for stamp/upgrade")
    parser.add_argument("--dry-run", action="store_true", help="plan only, no changes")
    parser.add_argument(
        "--accept-unverifiable",
        action="store_true",
        help="allow stamping migrations whose effect cannot be observed",
    )
    parser.add_argument(
        "--confirm-production",
        action="store_true",
        help="required to write to a target that looks like production",
    )
    parser.add_argument(
        "--migrations-dir",
        default=str(Path(__file__).resolve().parent),
    )
    args = parser.parse_args(argv)

    try:
        catalog = discover(Path(args.migrations_dir))
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    backend: Backend | None = None
    try:
        backend = _build_backend(args)
        runner = Runner(backend, catalog, dry_run=args.dry_run)

        if args.command in {"status", "verify"}:
            report = runner.status()
            if args.command == "status":
                render_status(report)
            else:
                render_status(report)
            return 0 if report.healthy else 1

        if args.command == "install":
            report = runner.install()
        elif args.command == "stamp":
            if not args.to:
                print("ERROR: stamp requires --to <version>", file=sys.stderr)
                return 2
            report = runner.stamp(args.to, accept_unverifiable=args.accept_unverifiable)
        else:
            report = runner.upgrade(args.to)

        render_status(report)
        return 0 if report.healthy else 1

    except (MigrationError, DatabaseConfigError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected driver errors
        print(f"\nUNEXPECTED ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        if backend is not None:
            backend.close()


if __name__ == "__main__":
    raise SystemExit(main())