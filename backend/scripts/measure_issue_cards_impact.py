"""
Контрольний вимір впливу міграції точки K (Завдання №11).

Точка K — `routes/issue_cards.py`, функція `parse_issue_card`: поля
`available` / `reserved` / `in_rent` / `in_restore` у картці видачі.

Стара формула:
    reserved  = SUM(oi.quantity) WHERE o.status IN
                ('processing','ready_for_issue','issued','on_rent')
                AND o.is_archived = 0
    available = products.quantity - reserved

Три дефекти, які закриває міграція:
  1. `on_rent` — фантомний статус (0 рядків у production), тоді як реальні
     `awaiting_customer` і `partial_return` не резервували нічого;
  2. заморозка (`frozen_quantity`) не віднімалася — товар на мийці
     показувався комплектувальнику як доступний;
  3. відмовлені позиції (`order_items.status='refused'`) тримали склад.

Скрипт читає лише SELECT. Нічого не змінює. Працює на SQLite-знімку дампа.

Використання:
    python scripts/measure_issue_cards_impact.py /tmp/snapshot.sqlite
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

from services.availability import AvailabilityService  # noqa: E402

# Точний перелік статусів старої формули, включно з фантомним `on_rent`.
OLD_RESERVING_STATUSES = ("processing", "ready_for_issue", "issued", "on_rent")


def main(snapshot_path):
    if not os.path.exists(snapshot_path):
        print(f"ПОМИЛКА: знімок не знайдено: {snapshot_path}")
        return 1

    engine = create_engine(f"sqlite:///{snapshot_path}")
    conn = engine.connect()
    service = AvailabilityService(conn)

    placeholders = ", ".join(f":st_{i}" for i in range(len(OLD_RESERVING_STATUSES)))
    params = {f"st_{i}": s for i, s in enumerate(OLD_RESERVING_STATUSES)}

    # Стара формула цілком, одним запитом — так само, як її бачив роут.
    old_rows = conn.execute(
        text(
            f"""
            SELECT p.product_id, p.sku, p.name, p.quantity,
                   COALESCE((
                       SELECT SUM(oi.quantity)
                       FROM order_items oi
                       JOIN orders o ON oi.order_id = o.order_id
                       WHERE oi.product_id = p.product_id
                         AND o.status IN ({placeholders})
                         AND COALESCE(o.is_archived, 0) = 0
                   ), 0) AS reserved_old
            FROM products p
            WHERE COALESCE(p.status, 1) = 1
            """
        ),
        params,
    ).fetchall()

    print("=" * 72)
    print("ТОЧКА K — issue_cards.py / parse_issue_card: вимір на знімку")
    print("=" * 72)
    print(f"Знімок: {snapshot_path}")
    print(f"Активних товарів: {len(old_rows)}")

    changed_available = []
    changed_reserved = []
    down = up = 0
    phantom_units = 0

    for product_id, sku, name, quantity, reserved_old in old_rows:
        old_available = max(0, int(quantity or 0) - int(reserved_old or 0))

        # Картка видачі працює «на зараз», без періоду аренди.
        snap = service.get_availability(
            product_id=product_id,
            start_date=None,
            end_date=None,
            quantity=1,
        )
        new_available = snap["available_quantity"]
        new_reserved = snap["reserved_quantity"]

        if new_available != old_available:
            gap = old_available - new_available
            changed_available.append((sku, name, old_available, new_available, gap))
            if gap > 0:
                down += 1
                phantom_units += gap
            else:
                up += 1

        if new_reserved != int(reserved_old or 0):
            changed_reserved.append((sku, int(reserved_old or 0), new_reserved))

    print("-" * 72)
    print(f"Змінилося `available`: {len(changed_available)}")
    print(f"  з них МЕНШЕ (прибрано фантомну доступність): {down}")
    print(f"  з них БІЛЬШЕ (звільнено зайняте безпідставно): {up}")
    print(f"Сумарно фантомних одиниць прибрано: {phantom_units}")
    print(f"Змінилося `reserved`: {len(changed_reserved)}")

    changed_available.sort(key=lambda r: abs(r[4]), reverse=True)
    print("-" * 72)
    print("Топ-15 змін `available` (стара -> канонічна):")
    for sku, name, old, new, gap in changed_available[:15]:
        short_name = (name or "")[:30]
        arrow = "менше" if gap > 0 else "БІЛЬШЕ"
        print(f"  {str(sku):<12} {short_name:<32} {old:>5} -> {new:>5}  ({arrow} на {abs(gap)})")

    if changed_reserved:
        print("-" * 72)
        print("Топ-10 змін `reserved` (стара -> канонічна):")
        changed_reserved.sort(key=lambda r: abs(r[2] - r[1]), reverse=True)
        for sku, old, new in changed_reserved[:10]:
            print(f"  {str(sku):<12} {old:>5} -> {new:>5}")

    conn.close()
    print("=" * 72)
    print("Записів не змінювалося: виконувалися лише SELECT.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/tmp/snapshot.sqlite"
    sys.exit(main(target))
