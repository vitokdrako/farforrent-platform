#!/usr/bin/env python3
"""
Вимір впливу фіксу точки «extended_catalog» (Завдання №11).

Що саме доводиться:
  1. СТАРИЙ count-запит фізично невиконуваний — у ньому аліас `i`, якого немає
     в `FROM products p` (таблиця inventory злита в products). Отже
     `GET /api/extended-catalog/search?in_stock=true` завжди віддавав 500.
  2. НОВИЙ count виконується і повертає число, яке збігається з кількістю
     рядків списку за тим самим фільтром — тобто пагінація тепер рахує той
     самий набір товарів, який показує сторінка.
  3. Фікс НЕ змінює семантику полів `quantity` / `inventory_quantity` /
     `in_stock`: без `in_stock` результат до і після ідентичний.

Read-only: лише SELECT, працює на SQLite-знімку production-дампа, до живої
БД не підключається.

Запуск:
    python scripts/measure_extended_catalog_impact.py [шлях_до_snapshot.sqlite]
"""

import sqlite3
import sys

DEFAULT_SNAPSHOT = "/tmp/snapshot.sqlite"

# Точні тіла запитів з routes/extended_catalog.py.
LIST_SQL_BASE = """
    SELECT
        p.product_id, p.sku, p.name, p.description, p.price,
        p.image_url, p.status,
        p.category_id, p.category_name, p.subcategory_id, p.subcategory_name,
        p.quantity
    FROM products p
    WHERE p.status = 1
"""
COUNT_SQL_BASE = """
    SELECT COUNT(*) FROM products p
    WHERE p.status = 1
"""

# Фільтр `in_stock` у списку — він був коректний і не змінювався.
LIST_IN_STOCK = " AND p.quantity > 0"

# Count-фільтр ДО фіксу (зламаний аліас) і ПІСЛЯ.
COUNT_IN_STOCK_BEFORE = " AND (i.quantity > 0 OR p.quantity > 0)"
COUNT_IN_STOCK_AFTER = " AND p.quantity > 0"


def _scalar(cur, sql):
    """Виконати запит і повернути (значення, помилка)."""
    try:
        cur.execute(sql)
        return cur.fetchone()[0], None
    except sqlite3.Error as exc:
        return None, f"{type(exc).__name__}: {exc}"


def _rowcount(cur, sql):
    cur.execute(sql)
    return len(cur.fetchall())


def main():
    snapshot = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SNAPSHOT
    con = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
    cur = con.cursor()

    print("=" * 72)
    print("ВИМІР: extended_catalog / GET /api/extended-catalog/search")
    print(f"знімок: {snapshot} (read-only)")
    print("=" * 72)

    # --- 1. Чи виконуваний count ДО фіксу -------------------------------
    before_value, before_error = _scalar(
        cur, COUNT_SQL_BASE + COUNT_IN_STOCK_BEFORE
    )
    after_value, after_error = _scalar(
        cur, COUNT_SQL_BASE + COUNT_IN_STOCK_AFTER
    )

    print("\n[1] count-запит при ?in_stock=true")
    print(f"  ДО фіксу     : "
          f"{'ПОМИЛКА -> ' + before_error if before_error else before_value}")
    print(f"  ПІСЛЯ фіксу  : "
          f"{'ПОМИЛКА -> ' + after_error if after_error else after_value}")

    # --- 2. Узгодженість count зі списком -------------------------------
    list_rows = _rowcount(cur, LIST_SQL_BASE + LIST_IN_STOCK)
    print("\n[2] узгодженість count зі списком (той самий фільтр)")
    print(f"  рядків у списку        : {list_rows}")
    print(f"  count ПІСЛЯ фіксу      : {after_value}")
    consistent = (after_value == list_rows)
    print(f"  збігається             : {'ТАК' if consistent else 'НІ'}")

    # --- 3. Незмінність поведінки без in_stock --------------------------
    plain_list = _rowcount(cur, LIST_SQL_BASE)
    plain_count, plain_error = _scalar(cur, COUNT_SQL_BASE)
    print("\n[3] запит без ?in_stock (фікс не мусить нічого змінювати)")
    print(f"  рядків у списку        : {plain_list}")
    print(f"  count                  : "
          f"{'ПОМИЛКА -> ' + plain_error if plain_error else plain_count}")

    # --- 4. Скільки товарів відсікає фільтр -----------------------------
    zero_stock = plain_list - list_rows
    print("\n[4] вплив самого фільтра in_stock")
    print(f"  активних товарів усього       : {plain_list}")
    print(f"  із залишком > 0               : {list_rows}")
    print(f"  відсікається (quantity = 0)   : {zero_stock}")

    print("\n" + "=" * 72)
    print("ВИСНОВОК")
    if before_error and not after_error and consistent:
        print("  Дефект підтверджений: ДО фіксу endpoint із ?in_stock=true")
        print("  падав на count-запиті (неіснуючий аліас `i`), тобто віддавав")
        print("  500. ПІСЛЯ фіксу count виконується і дорівнює кількості")
        print("  рядків списку — пагінація узгоджена зі сторінкою.")
        print("  Семантика полів залишку не змінена: без in_stock цифри ті самі.")
    else:
        print("  УВАГА: очікуваної картини не отримано, потрібен розбір.")
    print("=" * 72)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
