#!/usr/bin/env python3
"""
Schema inventory scanner (Завдання №7).

READ-ONLY статичний аналізатор репозиторію. НЕ підключається до БД,
НЕ виконує SQL, НЕ змінює жодного файлу проєкту.

Точність:
  * У `.py` файлах SQL шукається ЛИШЕ всередині string-літералів, які
    зібрані через `ast` і містять SQL-ключові слова. Це виключає
    false positives типу `from typing import ...` -> "FROM typing".
  * У `.sql` файлах аналізується весь вміст.
  * `oc_*` (OpenCart) виключені — це зовнішня БД, не наша інсталяція.

Що дає:
  1. DDL inventory: object -> source file -> type -> dependencies.
  2. DML inventory: які таблиці/view код реально читає та пише.
  3. GAP: об'єкти, які код використовує, але репозиторій НЕ може
     створити з нуля (потрібна жива БД або dump).

Використання:
    python3 scripts/schema_inventory.py
    python3 scripts/schema_inventory.py --json out.json
    python3 scripts/schema_inventory.py --gap-only
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

SKIP_DIR_PARTS = {
    ".git", "node_modules", "__pycache__", "venv", ".venv",
    "generated_pdfs", "dist", "build", ".atoms", "frontend",
    "event-tool-source", ".emergent",
}

# Літерал вважається SQL, лише якщо містить один із цих маркерів.
SQL_MARKER_RE = re.compile(
    r"\b(SELECT\s|INSERT\s+(?:IGNORE\s+)?INTO\s|UPDATE\s+\w+\s+SET\b|"
    r"DELETE\s+FROM\s|CREATE\s+(?:TABLE|VIEW|TRIGGER|INDEX|UNIQUE)|"
    r"ALTER\s+TABLE\s|DROP\s+(?:TABLE|VIEW|TRIGGER)\s|SHOW\s+TABLES\b)",
    re.I,
)

# ---------------------------------------------------------------- DDL patterns

DDL_PATTERNS = [
    ("table", "create", re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
    ("view", "create", re.compile(
        r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:ALGORITHM\s*=\s*\w+\s+)?"
        r"(?:DEFINER\s*=\s*\S+\s+)?(?:SQL\s+SECURITY\s+\w+\s+)?"
        r"VIEW\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
    ("trigger", "create", re.compile(
        r"CREATE\s+TRIGGER\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
    ("index", "create", re.compile(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
    ("table", "alter", re.compile(
        r"ALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?", re.I)),
    ("table", "drop", re.compile(
        r"DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
    ("view", "drop", re.compile(
        r"DROP\s+VIEW\s+(?:IF\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
    ("trigger", "drop", re.compile(
        r"DROP\s+TRIGGER\s+(?:IF\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?", re.I)),
]

ALTER_STMT_RE = re.compile(
    r"ALTER\s+TABLE\s+[`\"']?(\w+)[`\"']?(.*?)(?:;|$)", re.I | re.S)
ADD_COLUMN_RE = re.compile(
    r"ADD\s+COLUMN\s+[`\"']?(\w+)[`\"']?", re.I)
ADD_INDEX_RE = re.compile(
    r"ADD\s+(?:UNIQUE\s+)?(?:INDEX|KEY)\s+[`\"']?(\w+)[`\"']?", re.I)
REFERENCES_RE = re.compile(r"REFERENCES\s+[`\"']?(\w+)[`\"']?", re.I)
INLINE_INDEX_RE = re.compile(
    r"(?:^|,)\s*(?:UNIQUE\s+)?(?:INDEX|KEY)\s+[`\"']?(\w+)[`\"']?\s*\(", re.I | re.M)

# --------------------------------------------------------- DML (usage) patterns

READ_PATTERNS = [
    re.compile(r"\bFROM\s+[`\"']?(\w+)[`\"']?", re.I),
    re.compile(r"\bJOIN\s+[`\"']?(\w+)[`\"']?", re.I),
]
WRITE_PATTERNS = [
    re.compile(r"\bINSERT\s+(?:IGNORE\s+)?INTO\s+[`\"']?(\w+)[`\"']?", re.I),
    re.compile(r"\bUPDATE\s+[`\"']?(\w+)[`\"']?\s+SET\b", re.I),
    re.compile(r"\bDELETE\s+FROM\s+[`\"']?(\w+)[`\"']?", re.I),
]

SQL_NOISE = {
    "select", "where", "dual", "information_schema", "set", "values", "as",
    "on", "and", "or", "by", "order", "group", "limit", "using", "left",
    "right", "inner", "outer", "cross", "natural", "straight_join", "database",
    "schema", "table", "duplicate", "key", "update", "into", "distinct",
    "count", "sum", "min", "max", "avg", "case", "when", "then", "else",
    "end", "null", "not", "exists", "in", "is", "like", "union", "all",
    "having", "interval", "row_count", "now", "curdate", "unnamed", "if",
    # Аліаси таблиць із тригерів 005 (`[from fp #`, `[from tx #`), які
    # проходять крізь непарні лапки у CONCAT-виразах.
    "fp", "tx",
}

# Сам сканер містить SQL-приклади у docstring — не аналізуємо себе.
SELF_PATH_SUFFIX = "scripts/schema_inventory.py"

# Шум, який приходить із SQL-комментарів та string-літералів.
# Прибирається препроцесингом (split_sql_literals), список — друга лінія захисту.
LINE_COMMENT_RE = re.compile(r"--[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
SQL_STRING_RE = re.compile(r"'(?:[^'\\]|\\.|'')*'")


def split_sql_literals(sql: str) -> tuple[str, list[str]]:
    """Прибрати комментарі та розділити вкладені string-літерали.

    Потрібні обидві поведінки одночасно:

    * Літерал-шум (`'[from fp #'` у CONCAT всередині тригера 005) мусить
      зникнути, інакше regex зчитає "from fp" як назву таблиці.
    * Літерал-DDL мусить залишитися: `001_modify_customers_table.sql`
      тримає `ALTER TABLE customers ADD COLUMN ...` та `CREATE INDEX ...`
      всередині рядка для динамічного PREPARE. Якщо його викинути,
      інвентар втратить реальні об'єкти.

    Тому літерал, який сам містить SQL-маркер, повертається окремо для
    рекурсивного аналізу; решта літералів затираються.

    Returns:
        (clean_sql, nested_sql_literals)
    """
    nested: list[str] = []

    def replace(match: re.Match) -> str:
        inner = match.group(0)[1:-1]
        if len(inner) > 12 and SQL_MARKER_RE.search(inner):
            nested.append(inner)
            return " "
        return "''"

    sql = BLOCK_COMMENT_RE.sub(" ", sql)
    sql = LINE_COMMENT_RE.sub(" ", sql)
    return SQL_STRING_RE.sub(replace, sql), nested


def expand_sql_sources(sources: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Розкрити вкладений SQL рекурсивно, зберігаючи прив'язку до файлу."""
    expanded: list[tuple[str, str]] = []
    for source, raw in sources:
        pending = [raw]
        guard = 0
        while pending and guard < 5000:
            guard += 1
            clean, nested = split_sql_literals(pending.pop())
            expanded.append((source, clean))
            pending.extend(nested)
    return expanded

OPENCART_PREFIX = "oc_"
ORM_TABLENAME_RE = re.compile(r"__tablename__\s*=\s*['\"](\w+)['\"]")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_DIR))
    except ValueError:
        return str(path)


def iter_files(suffix: str) -> list[Path]:
    out = []
    for path in REPO_DIR.rglob(f"*{suffix}"):
        if not path.is_file() or SKIP_DIR_PARTS & set(path.parts):
            continue
        if path.as_posix().endswith(SELF_PATH_SUFFIX):
            continue
        out.append(path)
    return sorted(out)


def extract_sql_literals(path: Path, text: str) -> list[str]:
    """Зібрати з .py файлу лише ті string-літерали, що є SQL."""
    literals: list[str] = []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return literals
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            value = node.value
            if len(value) > 12 and SQL_MARKER_RE.search(value):
                literals.append(value)
        elif isinstance(node, ast.JoinedStr):
            # f-string: склеїти статичні частини, динамічні замінити плейсхолдером
            parts = []
            for piece in node.values:
                if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                    parts.append(piece.value)
                else:
                    parts.append(" __expr__ ")
            joined = "".join(parts)
            if len(joined) > 12 and SQL_MARKER_RE.search(joined):
                literals.append(joined)
    return literals


def valid_object_name(name: str) -> bool:
    low = name.lower()
    if low in SQL_NOISE:
        return False
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", low):
        return False
    if low.startswith("__"):
        return False
    return True


def scan() -> dict:
    ddl: dict[str, dict] = {}
    reads: dict[str, set[str]] = defaultdict(set)
    writes: dict[str, set[str]] = defaultdict(set)
    added_columns: dict[str, set[str]] = defaultdict(set)
    indexes: dict[str, set[str]] = defaultdict(set)
    orm_tables: dict[str, str] = {}
    sql_sources: list[tuple[str, str]] = []  # (source, sql_text)

    # .sql — весь вміст
    for path in iter_files(".sql"):
        try:
            sql_sources.append((rel(path), path.read_text(encoding="utf-8")))
        except OSError:
            continue

    # .py — лише SQL-літерали + ORM-моделі
    for path in iter_files(".py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        source = rel(path)
        for match in ORM_TABLENAME_RE.finditer(text):
            orm_tables.setdefault(match.group(1), source)
        for literal in extract_sql_literals(path, text):
            sql_sources.append((source, literal))

    sql_sources = expand_sql_sources(sql_sources)

    for source, sql in sql_sources:
        for obj_type, action, pattern in DDL_PATTERNS:
            for match in pattern.finditer(sql):
                name = match.group(1)
                if not valid_object_name(name):
                    continue
                entry = ddl.setdefault(name, {
                    "name": name, "type": obj_type,
                    "creates": [], "alters": [], "drops": [], "depends_on": [],
                })
                if action == "create":
                    entry["type"] = obj_type
                    if source not in entry["creates"]:
                        entry["creates"].append(source)
                elif action == "alter" and source not in entry["alters"]:
                    entry["alters"].append(source)
                elif action == "drop" and source not in entry["drops"]:
                    entry["drops"].append(source)

        # FK deps + inline indexes у межах CREATE TABLE
        for match in re.finditer(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?(\w+)[`\"']?\s*\((.*)",
            sql, re.I | re.S
        ):
            owner, body = match.group(1), match.group(2)
            entry = ddl.get(owner)
            if entry is None:
                continue
            for dep in REFERENCES_RE.finditer(body):
                target = dep.group(1)
                if target != owner and valid_object_name(target) \
                        and target not in entry["depends_on"]:
                    entry["depends_on"].append(target)
            for idx in INLINE_INDEX_RE.finditer(body):
                if valid_object_name(idx.group(1)):
                    indexes[owner].add(idx.group(1))

        # ALTER ... ADD COLUMN / ADD INDEX
        for match in ALTER_STMT_RE.finditer(sql):
            table, body = match.group(1), match.group(2)
            if not valid_object_name(table):
                continue
            for col in ADD_COLUMN_RE.finditer(body):
                col_name = col.group(1)
                # `__expr__` — плейсхолдер динамічної частини f-string:
                # ім'я колонки будується в рантаймі, статично воно невідоме.
                if col_name.startswith("__"):
                    continue
                added_columns[table].add(col_name)
            for idx in ADD_INDEX_RE.finditer(body):
                if valid_object_name(idx.group(1)):
                    indexes[table].add(idx.group(1))

        for pattern in READ_PATTERNS:
            for match in pattern.finditer(sql):
                name = match.group(1)
                if valid_object_name(name):
                    reads[name].add(source)
        for pattern in WRITE_PATTERNS:
            for match in pattern.finditer(sql):
                name = match.group(1)
                if valid_object_name(name):
                    writes[name].add(source)

    creatable = {n for n, e in ddl.items() if e["creates"]}
    used = set(reads) | set(writes) | set(added_columns) | set(orm_tables)

    gap: dict[str, dict] = {}
    opencart: list[str] = []
    for name in sorted(used - creatable):
        if name.startswith(OPENCART_PREFIX):
            opencart.append(name)
            continue
        entry = ddl.get(name, {})
        gap[name] = {
            "name": name,
            "read_by": sorted(reads.get(name, [])),
            "written_by": sorted(writes.get(name, [])),
            "altered_by": sorted(entry.get("alters", [])),
            "columns_added_by_repo": sorted(added_columns.get(name, [])),
            "orm_model": orm_tables.get(name),
        }

    return {
        "ddl": ddl,
        "reads": {k: sorted(v) for k, v in reads.items()},
        "writes": {k: sorted(v) for k, v in writes.items()},
        "added_columns": {k: sorted(v) for k, v in added_columns.items()},
        "indexes": {k: sorted(v) for k, v in indexes.items()},
        "orm_tables": orm_tables,
        "creatable": sorted(creatable),
        "gap": gap,
        "opencart_external": sorted(opencart),
    }


def print_report(data: dict, gap_only: bool = False) -> None:
    ddl, gap = data["ddl"], data["gap"]
    by_type: dict[str, list[str]] = defaultdict(list)
    for name in data["creatable"]:
        by_type[ddl[name]["type"]].append(name)

    print("=" * 78)
    print("SCHEMA INVENTORY — static repository scan (read-only, no DB access)")
    print("=" * 78)

    if not gap_only:
        print("\n[1] KNOWN FROM REPOSITORY — повний CREATE присутній у Git")
        for obj_type in ("table", "view", "trigger", "index"):
            names = sorted(by_type.get(obj_type, []))
            print(f"\n  {obj_type.upper()}S ({len(names)}):")
            for name in names:
                entry = ddl[name]
                deps = f"  deps={','.join(entry['depends_on'])}" if entry["depends_on"] else ""
                print(f"    {name:32s} <- {entry['creates'][0]}{deps}")

    print(f"\n[2] REQUIRES LIVE DB / DUMP — {len(gap)} objects")
    print("    код звертається, але CREATE у репозиторії відсутній\n")
    for name, info in gap.items():
        flags = []
        if info["orm_model"]:
            flags.append("ORM-model")
        if info["altered_by"]:
            flags.append("ALTERed-by-repo")
        if info["written_by"]:
            flags.append("WRITE")
        flag_s = f"  [{', '.join(flags)}]" if flags else ""
        print(f"    {name:32s}{flag_s}")
        srcs = info["read_by"] or info["written_by"] or info["altered_by"]
        if srcs:
            head = ", ".join(srcs[:2])
            more = f" (+{len(srcs) - 2})" if len(srcs) > 2 else ""
            print(f"        used in: {head}{more}")
        if info["columns_added_by_repo"]:
            print(f"        repo adds columns: {', '.join(info['columns_added_by_repo'])}")

    print("\n[3] TOTALS")
    print(f"    creatable from repo ........ {len(data['creatable'])}")
    print(f"      tables ................... {len(by_type.get('table', []))}")
    print(f"      views .................... {len(by_type.get('view', []))}")
    print(f"      triggers ................. {len(by_type.get('trigger', []))}")
    print(f"      standalone indexes ....... {len(by_type.get('index', []))}")
    print(f"    ORM __tablename__ models ... {len(data['orm_tables'])}")
    print(f"    GAP (need live DB) ......... {len(gap)}")
    print(f"    OpenCart external (oc_*) ... {len(data['opencart_external'])}")
    print("=" * 78)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", dest="json_out", default=None)
    parser.add_argument("--gap-only", action="store_true")
    args = parser.parse_args()

    data = scan()
    print_report(data, gap_only=args.gap_only)

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=list),
            encoding="utf-8")
        print(f"\nJSON -> {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())