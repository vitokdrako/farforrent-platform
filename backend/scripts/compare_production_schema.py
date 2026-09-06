#!/usr/bin/env python3
"""Compare the production schema against ``000_baseline.sql`` object by object.

Why this script exists
----------------------
``000_baseline.sql`` was produced *from* the production dump by
``extract_baseline.py``. Diffing the baseline against that extractor's own
output would therefore prove nothing: any bug in the extractor would be
present on both sides of the comparison and cancel itself out. The schema
fingerprint has the same weakness — it is computed from a normalised object
list, so two schemas can share a fingerprint and still differ in column
types, nullability, defaults or foreign-key actions.

So this script takes a deliberately independent route:

1. it re-parses the **raw** phpMyAdmin dump with its own splitter and its own
   DDL filter, sharing no code with ``extract_baseline.py``;
2. it loads that DDL into a throwaway database (``audit_prod_snapshot``);
3. it loads ``000_baseline.sql`` into a second throwaway database
   (``audit_baseline``);
4. it asks a real MySQL server, through ``information_schema``, what each
   database actually contains, and reports every difference.

A real server is the only authority here. Static SQL comparison cannot tell
you that ``int(11) NOT NULL DEFAULT '0'`` and ``int NOT NULL DEFAULT 0``
describe the same column, nor that two differently-worded index definitions
produce the same index.

Dimensions compared: tables, columns, column types, nullability, defaults,
``EXTRA`` (including AUTO_INCREMENT), collations, indexes, foreign keys
(including ON UPDATE/ON DELETE actions), views and triggers.

Safety
------
This script never connects to production. It reads a dump file from disk and
writes only to scratch databases whose names must begin with ``audit_``;
anything else is refused. Production is not contacted, read or modified.

Usage::

    python scripts/compare_production_schema.py \
        --dump /workspace/uploads/farforre_rentalhub.sql \
        --socket /tmp/my57/run/mysql.sock

Exit codes: 0 = schemas equivalent, 1 = differences found, 2 = setup error.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

try:
    import pymysql
except ImportError:  # pragma: no cover - environment guard
    print("ERROR: pymysql is required", file=sys.stderr)
    raise SystemExit(2)

BACKEND_DIR = Path(__file__).resolve().parent.parent

SCRATCH_PREFIX = "audit_"
PROD_DB = "audit_prod_snapshot"
BASE_DB = "audit_baseline"


# --------------------------------------------------------------------------
# Independent SQL parsing (intentionally shares no code with the extractor)
# --------------------------------------------------------------------------

_DELIMITER = re.compile(r"^DELIMITER\s+(\S+)\s*$", re.IGNORECASE)
_DEFINER = re.compile(r"\s*DEFINER\s*=\s*`[^`]*`@`[^`]*`", re.IGNORECASE)
_SQL_SECURITY = re.compile(r"\s*SQL\s+SECURITY\s+(?:DEFINER|INVOKER)", re.IGNORECASE)
# phpMyAdmin emits the row counter both as a table option
# (``) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=...``) and as a trailing
# clause of an ALTER (``MODIFY `id` int NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=5``).
# The optional leading comma must be consumed too, otherwise removing the
# counter leaves a dangling comma and the ALTER becomes a syntax error.
_AUTOINC_COUNTER = re.compile(r",?\s*AUTO_INCREMENT\s*=\s*\d+", re.IGNORECASE)

# Production runs a permissive sql_mode; the dump contains legacy
# '0000-00-00 00:00:00' defaults that MySQL 5.7's default strict mode rejects.
# Loading with the production-equivalent mode is what makes the snapshot
# faithful rather than silently truncated.
AUDIT_SQL_MODE = "NO_AUTO_VALUE_ON_ZERO,ALLOW_INVALID_DATES"

_DATA_HEADS = (
    "INSERT",
    "REPLACE",
    "LOCK TABLES",
    "UNLOCK TABLES",
    "START TRANSACTION",
    "COMMIT",
    "ROLLBACK",
    "USE ",
    "CREATE DATABASE",
    "DROP DATABASE",
    "SET ",
    "SET@",
    "/*!",
)

_DDL_HEADS = (
    "CREATE TABLE",
    "CREATE TEMPORARY TABLE",
    "CREATE VIEW",
    "CREATE ALGORITHM",
    "CREATE OR REPLACE",
    "CREATE TRIGGER",
    "CREATE INDEX",
    "CREATE UNIQUE",
    "CREATE FULLTEXT",
    "ALTER TABLE",
    "DROP TABLE",
    "DROP VIEW",
    "DROP TRIGGER",
    "RENAME TABLE",
)


def split_sql(sql: str) -> list[str]:
    """Split a dump into statements, honouring ``DELIMITER`` directives.

    Written from scratch rather than reusing ``catalog.split_statements`` so a
    shared parsing bug cannot hide a real schema difference.
    """
    sql = sql.replace("\r\n", "\n")
    delimiter = ";"
    buffer: list[str] = []
    statements: list[str] = []

    for line in sql.split("\n"):
        stripped = line.strip()

        if not buffer and (not stripped or stripped.startswith("--")):
            continue

        match = _DELIMITER.match(stripped)
        if match:
            # A delimiter change can only occur between statements.
            if buffer:
                pending = "\n".join(buffer).strip()
                if pending:
                    statements.append(pending)
                buffer = []
            delimiter = match.group(1)
            continue

        buffer.append(line)
        joined = "\n".join(buffer).rstrip()
        if joined.endswith(delimiter):
            statement = joined[: -len(delimiter)].strip()
            if statement:
                statements.append(statement)
            buffer = []

    tail = "\n".join(buffer).strip()
    if tail:
        statements.append(tail)
    return statements


def is_ddl(statement: str) -> bool:
    head = " ".join(statement.split()).upper()
    if head.startswith(_DATA_HEADS):
        return False
    return head.startswith(_DDL_HEADS)


def normalise_for_load(statement: str) -> str:
    """Remove things that are environment- or data-dependent, not schema.

    * ``DEFINER=`user`@`host``` — the production account does not exist on the
      audit server, and object ownership is not part of the schema contract.
    * ``SQL SECURITY DEFINER`` — follows DEFINER; irrelevant to structure.
    * ``AUTO_INCREMENT=<n>`` — a row counter, i.e. data, not structure.
    """
    statement = _DEFINER.sub("", statement)
    statement = _SQL_SECURITY.sub("", statement)
    statement = _AUTOINC_COUNTER.sub("", statement)
    statement = statement.strip()
    # Defensive: never hand MySQL a statement ending in a separator.
    while statement.endswith(","):
        statement = statement[:-1].rstrip()
    return statement


def extract_ddl(path: Path) -> tuple[list[str], int]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    statements = split_sql(raw)
    ddl = [normalise_for_load(s) for s in statements if is_ddl(s)]
    return [s for s in ddl if s], len(statements)


# --------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------


def connect(args, database: str | None = None):
    kwargs: dict = {"user": args.user, "autocommit": True, "charset": "utf8mb4"}
    if args.password:
        kwargs["password"] = args.password
    if args.socket:
        kwargs["unix_socket"] = args.socket
    else:
        kwargs["host"] = args.host
        kwargs["port"] = args.port
    if database:
        kwargs["database"] = database
    return pymysql.connect(**kwargs)


def rebuild_schema(args, database: str, statements: list[str], label: str) -> list[str]:
    if not database.startswith(SCRATCH_PREFIX):
        raise SystemExit(
            f"refusing to write to `{database}`: audit scratch databases must "
            f"be prefixed `{SCRATCH_PREFIX}`"
        )

    conn = connect(args)
    try:
        with conn.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{database}`")
            cur.execute(
                f"CREATE DATABASE `{database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
    finally:
        conn.close()

    errors: list[str] = []
    conn = connect(args, database)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION sql_mode = '{AUDIT_SQL_MODE}'")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for statement in statements:
                try:
                    cur.execute(statement)
                except Exception as exc:  # noqa: BLE001 - reported, not raised
                    first = " ".join(statement.split())[:120]
                    errors.append(f"{exc} :: {first}")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    finally:
        conn.close()

    print(f"  loaded {label}: {len(statements)} DDL statement(s), {len(errors)} error(s)")
    for error in errors[:20]:
        print(f"    LOAD ERROR {error}")
    return errors


# --------------------------------------------------------------------------
# Observation
# --------------------------------------------------------------------------


def rows(conn, sql: str, params: tuple) -> list[tuple]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def normalise_body(text: str | None, database: str) -> str:
    """Strip schema qualification and whitespace noise from a view/trigger body."""
    if not text:
        return ""
    body = text.replace(f"`{database}`.", "").replace(f"{database}.", "")
    body = _DEFINER.sub("", body)
    return " ".join(body.split()).lower()


class Schema:
    """Everything about a schema that matters for adoption safety."""

    def __init__(self, conn, database: str):
        self.database = database
        self.tables: dict[str, tuple] = {}
        self.columns: dict[str, tuple] = {}
        self.indexes: dict[str, tuple] = {}
        self.foreign_keys: dict[str, tuple] = {}
        self.views: dict[str, str] = {}
        self.triggers: dict[str, tuple] = {}
        self._load(conn, database)

    def _load(self, conn, db: str) -> None:
        for name, engine, collation in rows(
            conn,
            "SELECT LOWER(TABLE_NAME), ENGINE, TABLE_COLLATION "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'",
            (db,),
        ):
            if name == "schema_migrations":
                continue  # runner bookkeeping, never part of the baseline
            self.tables[name] = (engine, collation)

        for (
            table,
            column,
            position,
            col_type,
            nullable,
            default,
            extra,
            collation,
        ) in rows(
            conn,
            "SELECT LOWER(TABLE_NAME), LOWER(COLUMN_NAME), ORDINAL_POSITION, "
            "COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, COLLATION_NAME "
            "FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s",
            (db,),
        ):
            if table == "schema_migrations":
                continue
            self.columns[f"{table}.{column}"] = (
                position,
                (col_type or "").lower(),
                nullable,
                default,
                (extra or "").lower(),
                collation,
            )

        for table, index, seq, column, non_unique, sub_part, index_type in rows(
            conn,
            "SELECT LOWER(TABLE_NAME), LOWER(INDEX_NAME), SEQ_IN_INDEX, "
            "LOWER(COLUMN_NAME), NON_UNIQUE, SUB_PART, INDEX_TYPE "
            "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = %s",
            (db,),
        ):
            if table == "schema_migrations":
                continue
            self.indexes[f"{table}.{index}.{seq}"] = (
                column,
                non_unique,
                sub_part,
                index_type,
            )

        fk_columns: dict[str, list[tuple]] = {}
        for constraint, table, column, position, ref_table, ref_column in rows(
            conn,
            "SELECT LOWER(CONSTRAINT_NAME), LOWER(TABLE_NAME), LOWER(COLUMN_NAME), "
            "ORDINAL_POSITION, LOWER(REFERENCED_TABLE_NAME), LOWER(REFERENCED_COLUMN_NAME) "
            "FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = %s AND REFERENCED_TABLE_NAME IS NOT NULL",
            (db,),
        ):
            fk_columns.setdefault(f"{table}.{constraint}", []).append(
                (position, column, ref_table, ref_column)
            )

        rules = {
            f"{table}.{constraint}": (update_rule, delete_rule)
            for constraint, table, update_rule, delete_rule in rows(
                conn,
                "SELECT LOWER(CONSTRAINT_NAME), LOWER(TABLE_NAME), UPDATE_RULE, DELETE_RULE "
                "FROM information_schema.REFERENTIAL_CONSTRAINTS "
                "WHERE CONSTRAINT_SCHEMA = %s",
                (db,),
            )
        }

        for key, parts in fk_columns.items():
            parts.sort()
            local = tuple(p[1] for p in parts)
            ref_table = parts[0][2]
            ref_cols = tuple(p[3] for p in parts)
            self.foreign_keys[key] = (
                local,
                ref_table,
                ref_cols,
                rules.get(key, ("", "")),
            )

        for name, definition in rows(
            conn,
            "SELECT LOWER(TABLE_NAME), VIEW_DEFINITION FROM information_schema.VIEWS "
            "WHERE TABLE_SCHEMA = %s",
            (db,),
        ):
            self.views[name] = normalise_body(definition, db)

        for name, table, timing, event, action in rows(
            conn,
            "SELECT LOWER(TRIGGER_NAME), LOWER(EVENT_OBJECT_TABLE), ACTION_TIMING, "
            "EVENT_MANIPULATION, ACTION_STATEMENT FROM information_schema.TRIGGERS "
            "WHERE TRIGGER_SCHEMA = %s",
            (db,),
        ):
            self.triggers[name] = (table, timing, event, normalise_body(action, db))


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

FIELD_NAMES = {
    "columns": ("position", "type", "nullable", "default", "extra", "collation"),
    "tables": ("engine", "collation"),
    "indexes": ("column", "non_unique", "sub_part", "index_type"),
    "foreign keys": ("columns", "referenced table", "referenced columns", "rules"),
    "triggers": ("table", "timing", "event", "body"),
}


class Report:
    def __init__(self) -> None:
        self.differences: list[str] = []

    def compare(self, label: str, left: dict, right: dict) -> None:
        only_prod = sorted(set(left) - set(right))
        only_base = sorted(set(right) - set(left))
        changed: list[str] = []

        for key in sorted(set(left) & set(right)):
            if left[key] == right[key]:
                continue
            fields = FIELD_NAMES.get(label)
            if fields and isinstance(left[key], tuple):
                deltas = [
                    f"{fields[i]}: production={left[key][i]!r} baseline={right[key][i]!r}"
                    for i in range(min(len(fields), len(left[key])))
                    if left[key][i] != right[key][i]
                ]
                changed.append(f"{key} → " + "; ".join(deltas))
            else:
                changed.append(
                    f"{key} → production={left[key]!r} baseline={right[key]!r}"
                )

        if not only_prod and not only_base and not changed:
            print(f"  OK   {label}: {len(left)} object(s) identical")
            return

        if only_prod:
            self.differences.append(
                f"{label}: in production but MISSING from baseline "
                f"({len(only_prod)}) → {only_prod[:20]}"
            )
        if only_base:
            self.differences.append(
                f"{label}: in baseline but ABSENT from production "
                f"({len(only_base)}) → {only_base[:20]}"
            )
        if changed:
            self.differences.append(
                f"{label}: {len(changed)} definition mismatch(es) → {changed[:20]}"
            )

    def render(self) -> int:
        print()
        if not self.differences:
            print("RESULT: IDENTICAL — baseline reproduces the production schema exactly")
            return 0
        for difference in self.differences:
            print(f"  DIFF {difference}")
        print()
        print(f"RESULT: {len(self.differences)} DIFFERENCE CATEGORY(IES) FOUND")
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", required=True, help="read-only production dump file")
    parser.add_argument(
        "--baseline", default=str(BACKEND_DIR / "migrations" / "000_baseline.sql")
    )
    parser.add_argument("--socket", help="MySQL unix socket of the audit server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    args = parser.parse_args(argv)

    dump = Path(args.dump)
    baseline = Path(args.baseline)
    for path in (dump, baseline):
        if not path.is_file():
            print(f"ERROR: not a file: {path}", file=sys.stderr)
            return 2

    print("=" * 78)
    print("PRODUCTION SCHEMA ADOPTION AUDIT — schema comparison")
    print(f"production dump : {dump}")
    print(f"baseline        : {baseline}")
    print("note            : the dump is a point-in-time snapshot; production")
    print("                  itself is never contacted or modified by this script")
    print("=" * 78)

    prod_ddl, prod_total = extract_ddl(dump)
    base_ddl, base_total = extract_ddl(baseline)
    print(f"  dump     : {prod_total} statement(s) parsed, {len(prod_ddl)} DDL kept")
    print(f"  baseline : {base_total} statement(s) parsed, {len(base_ddl)} DDL kept")

    load_errors = rebuild_schema(args, PROD_DB, prod_ddl, "production snapshot")
    load_errors += rebuild_schema(args, BASE_DB, base_ddl, "baseline")

    conn = connect(args)
    try:
        production = Schema(conn, PROD_DB)
        base = Schema(conn, BASE_DB)
    finally:
        conn.close()

    print()
    print(
        f"  production snapshot: {len(production.tables)} tables, "
        f"{len(production.columns)} columns, {len(production.views)} view(s), "
        f"{len(production.triggers)} trigger(s), {len(production.foreign_keys)} FK"
    )
    print(
        f"  baseline          : {len(base.tables)} tables, "
        f"{len(base.columns)} columns, {len(base.views)} view(s), "
        f"{len(base.triggers)} trigger(s), {len(base.foreign_keys)} FK"
    )
    print()

    report = Report()
    report.compare("tables", production.tables, base.tables)
    report.compare("columns", production.columns, base.columns)
    report.compare("indexes", production.indexes, base.indexes)
    report.compare("foreign keys", production.foreign_keys, base.foreign_keys)
    report.compare("views", production.views, base.views)
    report.compare("triggers", production.triggers, base.triggers)

    exit_code = report.render()

    if load_errors:
        print()
        print(
            f"WARNING: {len(load_errors)} statement(s) failed to load. The "
            "comparison above is incomplete until they are explained."
        )
        return 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())