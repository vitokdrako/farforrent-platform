#!/usr/bin/env python3
"""Migration catalog: discovery, checksums, skip rules and SQL splitting.

Everything in this module is a pure function over files on disk. Nothing here
opens a database connection, which means it can be unit-tested without MySQL
and without production credentials.

Companion design document: ``migrations/MIGRATION_VERSIONING.md``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent

# The schema snapshot may ship under either name: `000_baseline.sql` is what
# scripts/extract_baseline.py produces, `000_initial.sql` is the name used in
# the original task text. Both are accepted so the file never has to be
# renamed behind anyone's back; whichever exists is used, and having both is
# an error rather than a silent pick.
BASELINE_FILENAMES = ("000_baseline.sql", "000_initial.sql")
BASELINE_VERSION = "000"

#: Single source of truth for applied/stamped/skipped migrations.
HISTORY_TABLE = "schema_migrations"

#: Presence of this table means "the application schema already lives here".
#: Checked instead of row counts or environment variables, because mistaking
#: a live database for an empty one is the one truly destructive error.
SENTINEL_TABLE = "orders"

_VERSION_RE = re.compile(r"^(\d{3})_(.+)$")
_DELIMITER_RE = re.compile(r"^DELIMITER\s+(\S+)\s*$", re.IGNORECASE)

_CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`?(\w+)`?", re.IGNORECASE
)
_CREATE_TRIGGER_RE = re.compile(r"\bCREATE\s+TRIGGER\s+`?(\w+)`?", re.IGNORECASE)
_DROP_TRIGGER_RE = re.compile(
    r"\bDROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?", re.IGNORECASE
)
_DROP_TABLE_RE = re.compile(
    r"\bDROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?", re.IGNORECASE
)
_CREATE_VIEW_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\S+\s+)?"
    r"(?:SQL\s+SECURITY\s+\S+\s+)?VIEW\s+`?(\w+)`?",
    re.IGNORECASE,
)
_ALTER_TABLE_RE = re.compile(
    r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?", re.IGNORECASE
)


class SkipKind(str, Enum):
    """Why a migration must never be executed nor marked as applied."""

    #: Targets objects that belong to a different database entirely.
    INCOMPATIBLE = "incompatible"
    #: Targets an object name that this schema never used.
    OBSOLETE = "obsolete"
    #: A later design replaced this migration's objects with differently named
    #: ones that the application actually uses. Running it would create a table
    #: nobody reads, or fail outright against the real schema.
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class SkipRule:
    """An explicit, documented refusal to run a migration.

    A skip rule is *not* a shortcut for "pretend it ran". Skipped migrations are
    recorded with ``status='skipped'`` and ``statements_executed=0`` so the
    history can never be mistaken for evidence of a schema change.
    """

    kind: SkipKind
    reason: str
    missing_objects: tuple[str, ...]


#: Migrations proven inapplicable by the live production dump
#: (see MIGRATION_VERSIONING.md §11.3). Keyed by migration version.
#:
#: These entries deliberately keep the original filenames. Renaming them or
#: back-dating them as "applied" would hide the fact that their SQL never ran
#: against this database.
SKIP_RULES: dict[str, SkipRule] = {
    "001": SkipRule(
        kind=SkipKind.INCOMPATIBLE,
        reason=(
            "`customers` is an OpenCart table and lives in a different database. "
            "The RentalHub schema has never contained it, so this migration was "
            "never applied here and must not be stamped as applied."
        ),
        missing_objects=("customers",),
    ),
    "add_user_tracking": SkipRule(
        kind=SkipKind.OBSOLETE,
        reason=(
            "targets `finance_transactions`, but the actual production table is "
            "named `fin_transactions`. The name `finance_transactions` exists "
            "only in an ORM model, never in the schema."
        ),
        missing_objects=("finance_transactions",),
    ),
    "004": SkipRule(
        kind=SkipKind.SUPERSEDED,
        reason=(
            "creates `soft_reservations` with `FOREIGN KEY (board_id) REFERENCES "
            "event_boards(board_id)`, but `event_boards` is keyed by "
            "`id varchar(36)` — there is no `board_id` column to point at, so "
            "MySQL 5.7 refuses it with errno 1215 (verified on a clean 5.7.44 "
            "instance). The feature actually ships as `event_soft_reservations` "
            "(varchar(36) keys, FK to `event_boards`.`id`), which is the only "
            "table routes/event_tool.py reads or writes. `soft_reservations` "
            "appears nowhere outside this file."
        ),
        missing_objects=("soft_reservations",),
    ),
    "add_laundry_queue": SkipRule(
        kind=SkipKind.SUPERSEDED,
        reason=(
            "creates `laundry_queue`, which no code path touches. "
            "routes/laundry.py states it outright at line 904 and implements the "
            "queue as `tasks` rows with `task_type='laundry_queue'`, then moves "
            "them into `laundry_batches`/`laundry_items`. Applying it would add "
            "an orphan table to fresh installs that production does not have."
        ),
        missing_objects=("laundry_queue",),
    ),
}

#: Migrations whose result is already contained in the baseline snapshot.
#:
#: The baseline is ``mysqldump`` of production **HEAD**, not of the database as
#: it looked before these migrations ran. Re-executing their SQL on top of it is
#: therefore wrong, and not merely redundant — verified on MySQL 5.7.44:
#:
#: * ``011`` fails with errno 1060 ``Duplicate column name 'company_profile_id'``
#:   because its ``ALTER TABLE orders`` is already part of the snapshot;
#: * ``002``/``003`` succeed while doing *nothing*: ``CREATE TABLE IF NOT EXISTS``
#:   finds the table present, and the migration's own column list
#:   (``board_id INT``, ``event_location``, ``guest_count``) never materialises.
#:
#: The second case is the dangerous one: the SQL "succeeds", so a naive runner
#: records ``applied`` for a change that did not happen. These versions are
#: adopted with ``status='stamped'`` instead, and only after the objects they
#: describe are observed in the schema the baseline just created.
BASELINE_COVERS: frozenset[str] = frozenset(
    {
        "002",  # event_boards
        "003",  # event_board_items
        "005",  # fin_payments triggers (recursion fix)
        "006",  # drop fin_transactions_after_insert
        "007",  # event_favorites
        "008",  # push_subscriptions
        "009",  # order_chat_messages
        "010",  # document_signatures
        "011",  # company_profiles + orders.company_profile_id
        "create_product_damage_history",  # product_damage_history
    }
)


@dataclass(frozen=True)
class Evidence:
    """Schema objects a migration would create, used to verify a stamp.

    ``tables`` and ``triggers`` must be present in the database; ``absent_triggers``
    must not be (a migration whose only effect is dropping a trigger is verified
    by that trigger being gone). Together they turn "this migration is already
    present" into a fact rather than an assumption.

    ``altered`` is recorded for reporting only: an ``ALTER TABLE`` that adds a
    column cannot be confirmed from object names alone.
    """

    tables: frozenset[str]
    triggers: frozenset[str]
    absent_triggers: frozenset[str]
    absent_tables: frozenset[str]
    altered: frozenset[str]

    @property
    def verifiable(self) -> bool:
        """True when a stamp can be backed by observable schema objects."""
        return bool(
            self.tables or self.triggers or self.absent_triggers or self.absent_tables
        )


def split_statements(sql: str) -> list[str]:
    """Split a MySQL script into executable statements.

    Handles the two things a naive ``sql.split(';')`` gets wrong on our files:

    * ``DELIMITER $$`` blocks — trigger bodies contain ``;`` that must not end
      the statement;
    * quoted content — ``'[from fp #1] '`` and backtick-quoted identifiers may
      contain delimiter characters.

    Comments are dropped, so conditional-comment directives such as
    ``/*!40101 SET NAMES utf8mb4 */;`` collapse to nothing. That is intentional:
    they configure a client session, not the schema.
    """
    statements: list[str] = []
    delimiter = ";"
    buf = ""
    in_single = in_double = in_backtick = False
    in_block_comment = False

    for line in sql.splitlines():
        quoted = in_single or in_double or in_backtick or in_block_comment
        if not quoted and not buf.strip():
            match = _DELIMITER_RE.match(line.strip())
            if match:
                delimiter = match.group(1)
                continue

        index = 0
        length = len(line)
        while index < length:
            char = line[index]

            if in_block_comment:
                if line.startswith("*/", index):
                    in_block_comment = False
                    index += 2
                else:
                    index += 1
                continue

            if in_single or in_double or in_backtick:
                buf += char
                # Backslash escapes only apply inside string literals.
                if char == "\\" and (in_single or in_double) and index + 1 < length:
                    buf += line[index + 1]
                    index += 2
                    continue
                if char == "'" and in_single:
                    in_single = False
                elif char == '"' and in_double:
                    in_double = False
                elif char == "`" and in_backtick:
                    in_backtick = False
                index += 1
                continue

            # `--` starts a comment only when followed by whitespace or EOL.
            if line.startswith("--", index) and (
                index + 2 >= length or line[index + 2] in " \t"
            ):
                break
            if char == "#":
                break
            if line.startswith("/*", index):
                in_block_comment = True
                index += 2
                continue

            if char == "'":
                in_single = True
                buf += char
                index += 1
                continue
            if char == '"':
                in_double = True
                buf += char
                index += 1
                continue
            if char == "`":
                in_backtick = True
                buf += char
                index += 1
                continue

            if line.startswith(delimiter, index):
                statement = buf.strip()
                if statement:
                    statements.append(statement)
                buf = ""
                index += len(delimiter)
                continue

            buf += char
            index += 1

        buf += "\n"

    tail = buf.strip()
    if tail:
        statements.append(tail)
    return statements


@dataclass(frozen=True)
class MigrationFile:
    """One migration on disk."""

    version: str
    name: str
    path: Path
    is_baseline: bool = False

    def read_sql(self) -> str:
        """Return the file contents with newlines normalised."""
        return self.path.read_text(encoding="utf-8").replace("\r\n", "\n")

    @property
    def checksum(self) -> str:
        """SHA-256 of the normalised SQL text.

        Line endings are normalised first so a checkout on a different platform
        does not look like a tampered migration.
        """
        return hashlib.sha256(self.read_sql().encode("utf-8")).hexdigest()

    @property
    def skip_rule(self) -> SkipRule | None:
        return SKIP_RULES.get(self.version)

    def statements(self) -> list[str]:
        return split_statements(self.read_sql())

    def evidence(self) -> Evidence:
        """Parse the schema objects this migration would create."""
        body = "\n".join(self.statements())
        views = {name.lower() for name in _CREATE_VIEW_RE.findall(body)}
        tables = {name.lower() for name in _CREATE_TABLE_RE.findall(body)}
        # phpMyAdmin emits a placeholder CREATE TABLE for every view; the real
        # object is the view, so keep it out of the table set.
        tables -= views
        created_triggers = {n.lower() for n in _CREATE_TRIGGER_RE.findall(body)}
        dropped_triggers = {n.lower() for n in _DROP_TRIGGER_RE.findall(body)}
        dropped_tables = {n.lower() for n in _DROP_TABLE_RE.findall(body)}
        return Evidence(
            tables=frozenset(tables | views),
            triggers=frozenset(created_triggers),
            # An object dropped and then re-created is positive evidence, not
            # negative: only the net removals prove the migration ran.
            absent_triggers=frozenset(dropped_triggers - created_triggers),
            # `DROP TABLE IF EXISTS <name>` followed by `CREATE VIEW <name>` is
            # how phpMyAdmin replaces the view placeholder — not a removal.
            absent_tables=frozenset(dropped_tables - tables - views),
            altered=frozenset(n.lower() for n in _ALTER_TABLE_RE.findall(body)),
        )


@dataclass(frozen=True)
class Catalog:
    """The migrations available on disk, in execution order."""

    baseline: MigrationFile | None
    migrations: tuple[MigrationFile, ...]

    def by_version(self) -> dict[str, MigrationFile]:
        items = {m.version: m for m in self.migrations}
        if self.baseline is not None:
            items[self.baseline.version] = self.baseline
        return items

    def versions_in_order(self) -> tuple[str, ...]:
        head = (self.baseline.version,) if self.baseline is not None else ()
        return head + tuple(m.version for m in self.migrations)


def _sort_key(path: Path) -> tuple[int, int, str]:
    """Order numbered migrations first, then the unnumbered legacy ones.

    Deterministic ordering matters more than elegance here: two environments
    must apply the same files in the same sequence.
    """
    match = _VERSION_RE.match(path.stem)
    if match:
        return (0, int(match.group(1)), path.stem)
    return (1, 0, path.stem)


def _parse(path: Path, *, is_baseline: bool = False) -> MigrationFile:
    match = _VERSION_RE.match(path.stem)
    if is_baseline:
        return MigrationFile(
            version=BASELINE_VERSION, name=path.stem, path=path, is_baseline=True
        )
    if match:
        return MigrationFile(version=match.group(1), name=match.group(2), path=path)
    # Legacy files without a numeric prefix keep their stem as the version, so
    # `add_user_tracking` stays addressable by the name used in every document.
    return MigrationFile(version=path.stem, name=path.stem, path=path)


def find_baseline(migrations_dir: Path = MIGRATIONS_DIR) -> Path | None:
    """Locate the schema snapshot, refusing an ambiguous pair of candidates."""
    present = [migrations_dir / name for name in BASELINE_FILENAMES]
    present = [path for path in present if path.is_file()]
    if len(present) > 1:
        names = ", ".join(p.name for p in present)
        raise ValueError(
            f"Ambiguous baseline: {names}. Keep exactly one snapshot file."
        )
    return present[0] if present else None


def discover(migrations_dir: Path = MIGRATIONS_DIR) -> Catalog:
    """Build the ordered catalog of migrations found in ``migrations_dir``."""
    baseline_path = find_baseline(migrations_dir)
    baseline = _parse(baseline_path, is_baseline=True) if baseline_path else None

    files = sorted(
        (
            path
            for path in migrations_dir.glob("*.sql")
            if path.name not in BASELINE_FILENAMES
        ),
        key=_sort_key,
    )
    migrations = tuple(_parse(path) for path in files)

    duplicates = _duplicate_versions(migrations)
    if duplicates:
        raise ValueError(f"Duplicate migration versions: {', '.join(duplicates)}")
    return Catalog(baseline=baseline, migrations=migrations)


def _duplicate_versions(migrations: tuple[MigrationFile, ...]) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for migration in migrations:
        if migration.version in seen:
            duplicates.add(migration.version)
        seen.add(migration.version)
    return sorted(duplicates)