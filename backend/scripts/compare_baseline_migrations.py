#!/usr/bin/env python3
"""Compare the production baseline against the legacy migration files.

Purpose: decide which legacy migrations may be stamped as "already applied".

``migrations/MIGRATION_VERSIONING.md`` assumed the production schema equals the
result of migrations 001..011. That assumption is only safe if every table
those migrations touch actually exists in production. This script verifies it
instead of trusting it.

Read-only: parses SQL text on disk, never connects to a database.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

CREATE_TABLE_RE = re.compile(r"^CREATE TABLE `([^`]+)`", re.MULTILINE)
VIEW_RE = re.compile(r"\bCREATE\b[^;\n]*\bVIEW\s+`([^`]+)`")

# Statements that require an already existing table.
ALTER_RE = re.compile(r"\bALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?`?(\w+)`?", re.IGNORECASE)
DML_RE = re.compile(r"\b(?:INSERT\s+INTO|DELETE\s+FROM)\s+`?(\w+)`?", re.IGNORECASE)
# `(?<!ON )` keeps `ON UPDATE CURRENT_TIMESTAMP` out of the results.
UPDATE_RE = re.compile(r"(?<!ON )\bUPDATE\s+`?(\w+)`?", re.IGNORECASE)
CREATE_INDEX_RE = re.compile(
    r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+\S+\s+ON\s+`?(\w+)`?", re.IGNORECASE
)
CREATES_RE = re.compile(
    r"\bCREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?\s+`?(\w+)`?", re.IGNORECASE
)

SQL_NOISE_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)

# Tokens that are SQL keywords rather than table names.
STOPWORDS = {"current_timestamp", "if", "set", "table", "into"}


def baseline_objects(path: Path) -> tuple[set[str], set[str]]:
    text = path.read_text(encoding="utf-8")
    views = set(VIEW_RE.findall(text))
    # phpMyAdmin emits a placeholder CREATE TABLE for each view; treat it as a view.
    tables = set(CREATE_TABLE_RE.findall(text)) - views
    return tables, views


def scan_migration(path: Path) -> tuple[set[str], set[str]]:
    raw = SQL_NOISE_RE.sub(" ", path.read_text(encoding="utf-8", errors="replace"))
    creates = {m.lower() for m in CREATES_RE.findall(raw)}
    needs: set[str] = set()
    for pattern in (ALTER_RE, DML_RE, UPDATE_RE, CREATE_INDEX_RE):
        needs |= {m.lower() for m in pattern.findall(raw)}
    needs -= creates
    needs -= STOPWORDS
    return creates, needs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--migrations-dir", required=True)
    args = parser.parse_args()

    baseline_path = Path(args.baseline)
    mig_dir = Path(args.migrations_dir)
    if not baseline_path.is_file():
        print(f"ERROR: baseline not found: {baseline_path}", file=sys.stderr)
        return 2

    tables, views = baseline_objects(baseline_path)
    present = {name.lower() for name in tables | views}
    print(f"baseline: {len(tables)} tables, {len(views)} view(s)")

    files = sorted(
        p for p in mig_dir.glob("*.sql") if not p.name.startswith("000_baseline")
    )
    print(f"legacy migration files: {len(files)}\n")

    applicable: list[str] = []
    stale: list[tuple[str, list[str]]] = []

    for path in files:
        _creates, needs = scan_migration(path)
        missing = sorted(n for n in needs if n not in present)
        if missing:
            stale.append((path.name, missing))
        else:
            applicable.append(path.name)

    print("--- migrations consistent with production (safe to stamp) ---")
    for name in applicable:
        print(f"  OK    {name}")

    print("\n--- migrations referencing tables ABSENT from production ---")
    if not stale:
        print("  none")
    for name, missing in stale:
        print(f"  STALE {name}")
        print(f"          missing: {', '.join(missing)}")

    print(f"\nsummary: {len(applicable)} consistent, {len(stale)} stale")
    if stale:
        print(
            "NOTE: stale migrations reference tables that production does not have. "
            "They must NOT be blindly stamped as applied, and must NOT run on a "
            "clean install created from the baseline."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())