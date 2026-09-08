"""
Контрольний вимір впливу міграції точки G (Завдання №11).

Точка G — `routes/inventory.py`, endpoint `POST /api/inventory/send-to-processing`
(відправка товару на мийку / реставрацію / хімчистку).

Стара формула:
    available = products.quantity - products.frozen_quantity

Вона не бачила ні замовлень, ні soft-резервів, ні періоду аренди.

Особливість цієї точки: поріг БЛОКУВАННЯ свідомо залишений фізичним
(`total - frozen`), бо відправка на обробку — операція з фізичним товаром.
Тому скрипт доводить дві різні речі:

1. Поріг блокування не змінився — вердикт «пропустити / відмовити»
   збігається для всіх товарів (регресії немає).
2. Скільком товарам канонічна доступність нижча за фізичну, тобто де
   оператор тепер отримає попередження `conflicts_with_reservations`.

Читає лише SELECT. Нічого не змінює. Працює на SQLite-знімку дампа.

Використання:
    python scripts/measure_inventory_impact.py /tmp/snapshot.sqlite
"""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text  # noqa: E402

from services.availability import AvailabilityService  # noqa: E402

# Кількість, з якою комірник найчастіше працює в кабінеті переобліку.
REQUESTED_QTY = 1


def main(snapshot_path):
    if not os.path.exists(snapshot_path):
        print(f"ПОМИЛКА: знімок не знайдено: {snapshot_path}")
        return 1

    engine = create_engine(f"sqlite:///{snapshot_path}")
    conn = engine.connect()
    service = AvailabilityService(conn)
    today = datetime.now().strftime("%Y-%m-%d")

    products = conn.execute(
        text(
            """
            SELECT product_id, sku, name, quantity, frozen_quantity
            FROM products
            WHERE COALESCE(status, 1) = 1
            """
        )
    ).fetchall()

    print("=" * 72)
    print("ТОЧКА G — inventory.py / send-to-processing: вимір на знімку")
    print("=" * 72)
    print(f"Знімок: {snapshot_path}")
    print(f"Дата розрахунку: {today}")
    print(f"Активних товарів: {len(products)}")

    gate_changed = []
    warned = []
    checked = 0
    max_gap = (0, None)

    for product_id, sku, name, quantity, frozen in products:
        snap = service.get_availability(
            product_id=product_id,
            start_date=today,
            end_date=today,
            quantity=REQUESTED_QTY,
        )
        checked += 1

        old_gate = max(0, int(quantity or 0) - int(frozen or 0))
        new_gate = max(0, snap["total_quantity"] - snap["on_processing_quantity"])

        # 1. Поріг блокування: старий вердикт проти нового.
        old_allows = REQUESTED_QTY <= old_gate
        new_allows = REQUESTED_QTY <= new_gate
        if old_allows != new_allows or old_gate != new_gate:
            gate_changed.append((sku, product_id, old_gate, new_gate))

        # 2. Нове попередження: канонічна доступність нижча за фізичну.
        canonical = snap["available_quantity"]
        if canonical < new_gate:
            gap = new_gate - canonical
            warned.append((sku, name, product_id, new_gate, canonical, gap))
            if gap > max_gap[0]:
                max_gap = (gap, (sku, name, new_gate, canonical))

    print("-" * 72)
    print(f"Перевірено товарів: {checked}")
    print(f"Змінився поріг блокування: {len(gate_changed)}")
    if gate_changed:
        print("  УВАГА: очікувалось 0 — поріг мав залишитися фізичним!")
        for sku, pid, old, new in gate_changed[:10]:
            print(f"    {sku} (id {pid}): {old} -> {new}")
    else:
        print("  (очікувано: операція з фізичним товаром не блокується бронею)")

    print(f"Товарів із новим попередженням про резерв: {len(warned)}")
    if max_gap[1]:
        sku, name, phys, canon = max_gap[1]
        short_name = (name or "")[:34]
        print(f"Найбільший розрив: {sku} «{short_name}» фізично {phys}, канонічно {canon}")

    warned.sort(key=lambda r: r[5], reverse=True)
    print("-" * 72)
    print("Топ-15 попереджень (фізично -> канонічно):")
    for sku, name, pid, phys, canon, gap in warned[:15]:
        short_name = (name or "")[:30]
        print(f"  {str(sku):<12} {short_name:<32} {phys:>5} -> {canon:>5}  (-{gap})")

    conn.close()
    print("=" * 72)
    print("Записів не змінювалося: виконувалися лише SELECT.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "/tmp/snapshot.sqlite"
    sys.exit(main(target))
