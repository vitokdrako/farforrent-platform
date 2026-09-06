"""Read-only завантажувач production-дампа у локальний SQLite для аудиту.

Призначення
-----------
Дає можливість ставити аналітичні запитання до production-даних БЕЗ підняття
MySQL-сервера і БЕЗ жодного контакту з живою базою. Дамп читається тільки на
читання; жоден байт у ньому не змінюється.

Чому це існує
-------------
Аудит доступності (Завдання №11) вимагає повторюваних замірів на реальних
даних. Тримати для цього живий MySQL-сервер у тимчасовому каталозі виявилося
ненадійно: після перезапуску середовища сервер і datadir зникають, а дамп
лишається. Цей скрипт робить доказову базу відтворюваною за одну команду.

Обмеження, які треба знати
--------------------------
* SQLite НЕ підходить для перевірки MySQL-специфічного SQL самого
  ``AvailabilityService`` (інші функції, інша семантика типів). Він придатний
  саме для аудиту даних: "які рядки існують", "скільки їх", "як вони
  співвідносяться".
* Завантажуються лише явно вказані таблиці, щоб не витрачати час і місце на
  всі 64.

Використання
------------
    python scripts/dump_snapshot_loader.py \
        --dump /workspace/uploads/farforre_rentalhub.sql \
        --out /tmp/snapshot.sqlite \
        --tables products,orders,order_items,product_damage_history
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
from typing import Any, Iterator

# Послідовності, які mysqldump екранує зворотним слешем.
_ESCAPES = {
    "0": "\0",
    "b": "\b",
    "n": "\n",
    "r": "\r",
    "t": "\t",
    "Z": "\x1a",
    "\\": "\\",
    "'": "'",
    '"': '"',
}


def read_dump(path: str) -> str:
    """Прочитати дамп у память як текст.

    Помилки декодування замінюються, а не піднімаються: мета — аналітика по
    числах і зв'язках, і одна зіпсована літера в назві товару не має права
    зривати весь аудит.
    """
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def extract_columns(dump: str, wanted: set[str]) -> dict[str, list[str]]:
    """Витягти імена колонок із ``CREATE TABLE`` для потрібних таблиць.

    Рядки визначення колонок у mysqldump завжди починаються з backtick-имені,
    тоді як KEY / PRIMARY KEY / CONSTRAINT — ні. Це і є ознака розрізнення.
    """
    columns: dict[str, list[str]] = {}
    pattern = re.compile(r"CREATE TABLE `([^`]+)` \((.*?)\n\) ENGINE", re.S)
    for match in pattern.finditer(dump):
        table = match.group(1)
        if table not in wanted:
            continue
        names: list[str] = []
        for raw_line in match.group(2).split("\n"):
            line = raw_line.strip()
            column_match = re.match(r"`([^`]+)`\s+\S", line)
            if column_match:
                names.append(column_match.group(1))
        columns[table] = names
    return columns


def _parse_quoted_string(dump: str, index: int) -> tuple[str, int]:
    """Прочитати SQL-рядок у лапках, починаючи з символу після відкривної лапки."""
    parts: list[str] = []
    while True:
        char = dump[index]
        if char == "\\":
            parts.append(_ESCAPES.get(dump[index + 1], dump[index + 1]))
            index += 2
        elif char == "'":
            # Подвоєна лапка ('') також означає літерал лапки.
            if dump[index + 1] == "'":
                parts.append("'")
                index += 2
                continue
            return "".join(parts), index + 1
        else:
            parts.append(char)
            index += 1


def _coerce(token: str | None) -> Any:
    """Привести неквотований токен до int/float, інакше лишити як є."""
    if token is None:
        return None
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        return token


def parse_value_tuples(dump: str, index: int) -> tuple[list[list[Any]], int]:
    """Розібрати список кортежів ``(...),(...);`` після ``VALUES``.

    Парсер знає про стан лапок, тому крапка з комою або дужка всередині
    текстового значення не обриває розбір передчасно.
    """
    rows: list[list[Any]] = []
    length = len(dump)
    while index < length:
        while index < length and dump[index] in " \n\r\t,":
            index += 1
        if index >= length or dump[index] == ";":
            return rows, index + 1
        if dump[index] != "(":
            return rows, index
        index += 1
        row: list[Any] = []
        while True:
            while dump[index] in " \n\r\t":
                index += 1
            if dump[index] == "'":
                value, index = _parse_quoted_string(dump, index + 1)
                row.append(value)
            else:
                end = index
                while dump[end] not in ",)":
                    end += 1
                token = dump[index:end].strip()
                index = end
                row.append(None if token.upper() == "NULL" else _coerce(token))
            if dump[index] == ",":
                index += 1
                continue
            if dump[index] == ")":
                index += 1
                break
        rows.append(row)
    return rows, index


def iter_inserts(dump: str, table: str) -> Iterator[tuple[list[str] | None, list[list[Any]]]]:
    """Пройти всі ``INSERT INTO `table` ... VALUES`` і віддати розібрані рядки.

    mysqldump має дві форми запису: скорочену (``INSERT INTO `t` VALUES``) і
    з явним переліком колонок (``INSERT INTO `t` (`a`, `b`) VALUES``). Друга
    форма важлива: порядок колонок у ній може не збігатися з порядком у
    ``CREATE TABLE``, тому імена беруться саме з самого INSERT, коли вони є.

    Yields:
        Кортеж ``(імена колонок або None, список рядків)``.
    """
    pattern = re.compile(
        r"INSERT INTO `" + re.escape(table) + r"`\s*(?:\(([^)]*)\))?\s*VALUES\s*"
    )
    for match in pattern.finditer(dump):
        raw_columns = match.group(1)
        names: list[str] | None = None
        if raw_columns:
            names = [item.strip().strip("`") for item in raw_columns.split(",")]
        rows, _ = parse_value_tuples(dump, match.end())
        if rows:
            yield names, rows


def load(dump_path: str, out_path: str, tables: list[str]) -> dict[str, int]:
    """Завантажити вказані таблиці дампа у свіжу SQLite-базу."""
    dump = read_dump(dump_path)
    wanted = set(tables)
    columns = extract_columns(dump, wanted)

    missing = wanted - set(columns)
    if missing:
        raise SystemExit(f"У дампі не знайдено CREATE TABLE для: {sorted(missing)}")

    if os.path.exists(out_path):
        os.remove(out_path)
    connection = sqlite3.connect(out_path)
    counts: dict[str, int] = {}
    try:
        for table in tables:
            ddl_names = columns[table]
            quoted_ddl = ", ".join(f'"{name}"' for name in ddl_names)
            connection.execute(f'CREATE TABLE "{table}" ({quoted_ddl})')
            total = 0
            for insert_names, batch in iter_inserts(dump, table):
                names = insert_names or ddl_names
                quoted = ", ".join(f'"{name}"' for name in names)
                placeholders = ", ".join("?" for _ in names)
                statement = (
                    f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})'
                )
                usable = [row for row in batch if len(row) == len(names)]
                connection.executemany(statement, usable)
                total += len(usable)
            counts[table] = total
        connection.commit()
    finally:
        connection.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump", required=True, help="шлях до production-дампа (.sql)")
    parser.add_argument("--out", required=True, help="шлях до SQLite-файлу результату")
    parser.add_argument(
        "--tables",
        required=True,
        help="перелік таблиць через кому, напр. products,orders",
    )
    args = parser.parse_args(argv)

    tables = [name.strip() for name in args.tables.split(",") if name.strip()]
    counts = load(args.dump, args.out, tables)
    for table, count in counts.items():
        print(f"{table}: {count} рядків")
    return 0


if __name__ == "__main__":
    sys.exit(main())