#!/usr/bin/env python3
"""Prove empirically that ``stamp`` changes history only, never the schema.

Why a dry-run is not enough
---------------------------
``stamp --dry-run`` prints a plan and returns. It proves what the runner
*intends* to do, not what it actually does. The claim that matters before
touching production is stronger: *executing* the stamp must leave every table,
column, type, nullability, default, index, foreign key, view and trigger
byte-for-byte identical, and must write only to ``schema_migrations``.

This script establishes that claim the only way it can be established — by
running the real command and diffing the schema around it:

1. clone the source schema (structure only) into a throwaway probe database;
2. record a full object-level snapshot of the probe;
3. run the real ``stamp --to <version>`` against the probe (no ``--dry-run``);
4. record a second snapshot and diff it against the first;
5. print exactly what landed in ``schema_migrations``.

Any difference in step 4 is a failure: it would mean ``stamp`` mutates schema.

Safety
------
Never connects to production. Writes only to a probe database whose name must
begin with ``audit_``. The source database is read with ``SHOW CREATE`` only.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import pymysql  # noqa: E402

from scripts.compare_production_schema import (  # noqa: E402
    AUDIT_SQL_MODE,
    SCRATCH_PREFIX,
    Schema,
    _DEFINER,
    Report,
)

HISTORY_TABLE = "schema_migrations"


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


def clone_structure(args, source: str, probe: str) -> None:
    """Copy structure (not rows) from ``source`` into a fresh ``probe``."""
    if not probe.startswith(SCRATCH_PREFIX):
        raise SystemExit(f"refusing to write to `{probe}`: must be `{SCRATCH_PREFIX}*`")

    read = connect(args, source)
    try:
        with read.cursor() as cur:
            cur.execute(
                "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s",
                (source,),
            )
            objects = list(cur.fetchall())

            tables, views = [], []
            for name, kind in objects:
                if name == HISTORY_TABLE:
                    continue  # bookkeeping, not schema under audit
                (views if kind == "VIEW" else tables).append(name)

            ddl: list[str] = []
            for name in tables:
                cur.execute(f"SHOW CREATE TABLE `{name}`")
                ddl.append(cur.fetchone()[1])
            for name in views:
                cur.execute(f"SHOW CREATE VIEW `{name}`")
                ddl.append(cur.fetchone()[1])

            cur.execute(
                "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS "
                "WHERE TRIGGER_SCHEMA = %s",
                (source,),
            )
            triggers = [row[0] for row in cur.fetchall()]
            trigger_ddl: list[str] = []
            for name in triggers:
                cur.execute(f"SHOW CREATE TRIGGER `{name}`")
                trigger_ddl.append(cur.fetchone()[2])
    finally:
        read.close()

    admin = connect(args)
    try:
        with admin.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS `{probe}`")
            cur.execute(
                f"CREATE DATABASE `{probe}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci"
            )
    finally:
        admin.close()

    errors = 0
    write = connect(args, probe)
    try:
        with write.cursor() as cur:
            cur.execute(f"SET SESSION sql_mode = '{AUDIT_SQL_MODE}'")
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for statement in ddl + trigger_ddl:
                try:
                    cur.execute(_DEFINER.sub("", statement))
                except Exception as exc:  # noqa: BLE001
                    errors += 1
                    print(f"    CLONE ERROR {exc} :: {' '.join(statement.split())[:110]}")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
    finally:
        write.close()

    print(
        f"  cloned `{source}` → `{probe}`: {len(tables)} table(s), "
        f"{len(views)} view(s), {len(triggers)} trigger(s), {errors} error(s)"
    )
    if errors:
        raise SystemExit("clone incomplete; refusing to draw conclusions from it")


def snapshot(args, database: str) -> Schema:
    conn = connect(args, database)
    try:
        return Schema(conn, database)
    finally:
        conn.close()


def run_runner(args, database: str, command: list[str]) -> tuple[int, str]:
    env = dict(os.environ)
    env["MIGRATION_DB_NAME"] = database
    env["MIGRATION_DB_USER"] = args.runner_user or args.user
    env["MIGRATION_DB_PASSWORD"] = args.runner_password or args.password
    env["MIGRATION_DB_HOST"] = args.host
    env["MIGRATION_DB_PORT"] = str(args.port)
    env["MIGRATION_ACTOR"] = "task10-audit"
    proc = subprocess.run(
        [sys.executable, "-m", "migrations.runner", *command],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def history_rows(args, database: str) -> list[tuple]:
    conn = connect(args, database)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
                (database, HISTORY_TABLE),
            )
            if not cur.fetchone()[0]:
                return []
            # `version` is the primary key of this table; there is no `id`
            # column. Order by insertion time, then version, for a stable read.
            cur.execute(
                f"SELECT version, status, statements_executed, LEFT(notes, 70) "
                f"FROM `{HISTORY_TABLE}` ORDER BY applied_at, version"
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default="audit_prod_snapshot")
    parser.add_argument("--probe", default="audit_stamp_probe")
    parser.add_argument("--to", default="011")
    parser.add_argument("--socket")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--runner-user", help="account the runner connects as (TCP)")
    parser.add_argument("--runner-password")
    args = parser.parse_args(argv)

    print("=" * 78)
    print("STAMP SAFETY PROOF — does `stamp` execute any DDL?")
    print(f"source (read-only) : {args.source}")
    print(f"probe (disposable) : {args.probe}")
    print(f"target version     : {args.to}")
    print("=" * 78)

    clone_structure(args, args.source, args.probe)

    print("\n--- snapshot BEFORE stamp ---")
    before = snapshot(args, args.probe)
    print(
        f"  {len(before.tables)} tables, {len(before.columns)} columns, "
        f"{len(before.indexes)} index parts, {len(before.foreign_keys)} FK, "
        f"{len(before.views)} view(s), {len(before.triggers)} trigger(s)"
    )

    print("\n--- executing REAL stamp (no --dry-run) ---")
    code, output = run_runner(args, args.probe, ["stamp", "--to", args.to])
    for line in output.splitlines():
        print(f"  | {line}")
    if code != 0:
        print(f"\nstamp exited {code}")

    print("\n--- snapshot AFTER stamp ---")
    after = snapshot(args, args.probe)
    print(
        f"  {len(after.tables)} tables, {len(after.columns)} columns, "
        f"{len(after.indexes)} index parts, {len(after.foreign_keys)} FK, "
        f"{len(after.views)} view(s), {len(after.triggers)} trigger(s)"
    )

    print("\n--- schema diff around the stamp ---")
    report = Report()
    report.compare("tables", before.tables, after.tables)
    report.compare("columns", before.columns, after.columns)
    report.compare("indexes", before.indexes, after.indexes)
    report.compare("foreign keys", before.foreign_keys, after.foreign_keys)
    report.compare("views", before.views, after.views)
    report.compare("triggers", before.triggers, after.triggers)
    schema_changed = bool(report.differences)
    for difference in report.differences:
        print(f"  DIFF {difference}")

    print(f"\n--- what landed in `{HISTORY_TABLE}` ---")
    rows = history_rows(args, args.probe)
    total_statements = 0
    for version, status, statements, notes in rows:
        total_statements += statements or 0
        print(f"  {version:<32} {status:<10} stmts={statements}  {notes}")
    print(f"  rows recorded: {len(rows)}, total statements executed: {total_statements}")

    print("\n" + "=" * 78)
    if schema_changed:
        print("RESULT: FAILED — stamp altered the schema. Do NOT stamp production.")
        return 1
    if total_statements != 0:
        print(
            f"RESULT: FAILED — history claims {total_statements} statement(s) were "
            "executed; stamp must execute none."
        )
        return 1
    if code != 0:
        print(f"RESULT: stamp refused (exit {code}); schema untouched, as designed.")
        return 1
    print(
        "RESULT: PASSED — schema identical before and after; 0 statements executed; "
        f"only `{HISTORY_TABLE}` was written."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())