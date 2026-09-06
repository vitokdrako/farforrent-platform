"""
Контрольний вимір впливу міграції точки J (Завдання №11).

Точка J — `routes/order_modifications.py`, три перевірки дозамовлення:
додавання позиції, зміна кількості, відновлення відмовленої позиції.
До міграції всі три звірялися з `products.quantity` — загальним залишком
без урахування інших замовлень, заморозки, soft-резервів і періоду аренди.

Скрипт порівнює стару й канонічну формули на знімку production-дампа й
відповідає на єдине важливе питання: наскільки склад був фантомно
«доступним» для дозамовлення.

Читає лише SELECT. Нічого не змінює. Запускається на SQLite-знімку, а не
на live production.

Використання:
    python scripts/measure_order_modifications_impact.py /tmp/snapshot.sqlite
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

from services.availability import AvailabilityService  # noqa: E402

# Статуси, на яких `order_modifications.py` дозволяє редагування
# (`get_order_for_modification`). Тільки ці замовлення проходять точку J.
MODIFIABLE_STATUSES = ("processing", "ready_for_issue")


def _fmt(value):
    if value is None:
        return None
    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")
    return str(value)[:10]


def main(snapshot_path):
    if not os.path.exists(snapshot_path):
        print(f"ПОМИЛКА: знімок не знайдено: {snapshot_path}")
        return 1

    engine = create_engine(f"sqlite:///{snapshot_path}")
    conn = engine.connect()
    service = AvailabilityService(conn)

    orders = conn.execute(
        text(
            """
            SELECT order_id, order_number, status,
                   rental_start_date, rental_end_date
            FROM orders
            WHERE status IN (:s0, :s1)
              AND COALESCE(is_archived, 0) = 0
            """
        ),
        {"s0": MODIFIABLE_STATUSES[0], "s1": MODIFIABLE_STATUSES[1]},
    ).fetchall()

    print("=" * 70)
    print("ТОЧКА J — order_modifications.py: вимір на знімку")
    print("=" * 70)
    print(f"Знімок: {snapshot_path}")
    print(f"Замовлень, доступних для редагування: {len(orders)}")

    checked = 0
    skipped_no_window = 0
    differing = []
    phantom_units = 0
    max_gap = (0, None)

    for order in orders:
        order_id = order[0]
        start = _fmt(order[3])
        end = _fmt(order[4])

        items = conn.execute(
            text(
                """
                SELECT DISTINCT product_id
                FROM order_items
                WHERE order_id = :order_id
                  AND product_id IS NOT NULL
                  AND COALESCE(status, 'active') = 'active'
                """
            ),
            {"order_id": order_id},
        ).fetchall()

        if not items:
            continue

        if not start or not end:
            skipped_no_window += len(items)
            continue

        for (product_id,) in items:
            row = conn.execute(
                text("SELECT quantity FROM products WHERE product_id = :pid"),
                {"pid": product_id},
            ).fetchone()
            if not row:
                continue

            old_available = int(row[0] or 0)
            new_available = int(
                service.get_availability(
                    product_id=product_id,
                    start_date=start,
                    end_date=end,
                )["available_quantity"]
            )
            checked += 1

            if old_available != new_available:
                gap = old_available - new_available
                differing.append(
                    (order[1], product_id, old_available, new_available, gap)
                )
                if gap > 0:
                    phantom_units += gap
                if gap > max_gap[0]:
                    max_gap = (gap, (order[1], product_id, old_available, new_available))

    drops = [d for d in differing if d[4] > 0]
    rises = [d for d in differing if d[4] < 0]

    print(f"Перевірено пар (замовлення, товар): {checked}")
    print(f"Пропущено без періоду аренди: {skipped_no_window}")
    print(f"Розбіжність формул: {len(differing)}")
    print(f"  доступність зменшилась (прибрано фантом): {len(drops)}")
    print(f"  доступність зросла: {len(rises)}")
    print(f"Сумарно фантомних одиниць прибрано: {phantom_units}")

    if max_gap[1]:
        num, pid, old, new = max_gap[1]
        print(f"Найгірший випадок: замовлення {num}, товар {pid}: {old} -> {new}")

    print("-" * 70)
    print("Перші 15 розбіжностей (замовлення, товар, було -> стало):")
    for num, pid, old, new, _gap in differing[:15]:
        print(f"  {num:<12} товар {pid:<6} {old:>5} -> {new:>5}")

    conn.close()
    print("=" * 70)
    print("Записів не змінювалося: виконувалися лише SELECT.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/tmp/snapshot.sqlite"
    sys.exit(main(target))