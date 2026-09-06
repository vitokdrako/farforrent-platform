"""
Utility для перевірки доступності товарів.

ВАЖЛИВО: сам розрахунок доступності тут більше НЕ дублюється. Числа
беруться з єдиного джерела правди — `services.availability.AvailabilityService`
(канонічні правила: `services/availability/rules.py`, обґрунтування:
`audit/AVAILABILITY_INVENTORY.md` §7).

Цей модуль залишається як стабільний фасад: він зберігає незмінний формат
відповіді (усі поля, включно з `nearby_orders`, попередженнями про часткові
повернення й обробку), бо його вже споживають `routes/orders.py` та UI
(`ZoneAvailabilityGate`). Тут лишається тільки збір інформативних
попереджень, а не друга формула доступності.
"""
from typing import Dict, List, Optional

from sqlalchemy import text

from services.availability import AvailabilityService
from services.availability.rules import (
    ACTIVE_ITEM_STATUS,
    EXCLUDE_ARCHIVED_ORDERS,
    RESERVING_ORDER_STATUSES,
    statuses_placeholder,
)


def _nearby_orders(
    db,
    product_id: int,
    start_date: str,
    end_date: str,
    exclude_order_id: Optional[int] = None,
) -> List[Dict]:
    """
    Замовлення, які перетинаються з періодом або впритул до нього.

    Це інформативний блок для менеджера (щільний графік), він не впливає
    на розрахунок доступності. Перелік статусів і фільтр архіву беруться
    з канонічних правил, щоб попередження не суперечили самій цифрі.
    """
    status_sql, status_params = statuses_placeholder("st", RESERVING_ORDER_STATUSES)

    query = f"""
        SELECT o.order_id, o.order_number, o.status,
               o.rental_start_date, o.rental_end_date, oi.quantity,
               DATEDIFF(:start_date, o.rental_end_date) as days_gap
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
          AND COALESCE(oi.status, '{ACTIVE_ITEM_STATUS}') = :item_status
          AND o.status IN {status_sql}
          AND (
                (o.rental_start_date <= :end_date AND o.rental_end_date >= :start_date)
             OR (o.rental_end_date >= DATE_SUB(:start_date, INTERVAL 1 DAY)
                 AND o.rental_end_date < :start_date)
          )
    """
    if EXCLUDE_ARCHIVED_ORDERS:
        query += " AND COALESCE(o.is_archived, 0) = 0"

    params = {
        "product_id": product_id,
        "item_status": ACTIVE_ITEM_STATUS,
        "start_date": start_date,
        "end_date": end_date,
    }
    params.update(status_params)

    if exclude_order_id:
        query += " AND o.order_id != :exclude_order_id"
        params["exclude_order_id"] = exclude_order_id

    query += " ORDER BY o.rental_start_date"

    result = db.execute(text(query), params)
    orders = []
    for row in result:
        orders.append(
            {
                "order_id": row[0],
                "order_number": row[1],
                "status": row[2],
                "rental_start_date": row[3].isoformat() if row[3] else None,
                "rental_end_date": row[4].isoformat() if row[4] else None,
                "quantity": row[5],
                "days_gap": row[6] if row[6] is not None else None,
            }
        )
    result.close()
    return orders


def _partial_return_warnings(db, product_id: int) -> Dict:
    """
    Товари, що зависли в активних версіях часткових повернень.

    За рішенням власника (§7, питання 2) статус `partial_return` тепер
    резервує товар, тому кількість тут не віднімається повторно — блок
    лишається попередженням із датою прострочки.
    """
    query = """
        SELECT prv.parent_order_id, prv.display_number, prvi.qty,
               prv.rental_end_date,
               DATEDIFF(CURDATE(), prv.rental_end_date) as days_overdue,
               prvi.daily_rate, prv.created_at, prv.version_id
        FROM partial_return_version_items prvi
        JOIN partial_return_versions prv ON prvi.version_id = prv.version_id
        WHERE prvi.product_id = :product_id
          AND prvi.status = 'pending'
          AND prv.status = 'active'
        ORDER BY prv.rental_end_date DESC
    """
    warnings = []
    total_qty = 0
    try:
        result = db.execute(text(query), {"product_id": product_id})
        for row in result:
            days_overdue = row[4] if row[4] else 0
            total_qty += row[2]
            warnings.append(
                {
                    "order_id": row[0],
                    "order_number": row[1],
                    "qty": row[2],
                    "original_end_date": row[3].isoformat() if row[3] else None,
                    "days_overdue": days_overdue,
                    "daily_rate": float(row[5]) if row[5] else 0,
                    "version_id": row[7],
                    "warning": (
                        f"⚠️ Товар ще НЕ ПОВЕРНУТО! Прострочка {days_overdue} дн. "
                        f"Дата повернення невідома."
                    ),
                }
            )
        result.close()
    except Exception:
        # Відсутність таблиць часткових повернень не має ламати перевірку
        # доступності — краще без попередження, ніж 500 на замовленні.
        return {"warnings": [], "qty": 0}

    return {"warnings": warnings, "qty": total_qty}


def _processing_warnings(db, product_id: int, frozen_qty: int) -> List[Dict]:
    """
    Попередження про товар на обробці (мийка/прання/реставрація).

    Кількість береться з `products.frozen_quantity` — це канонічне джерело
    за рішенням 3. `product_damage_history` більше не впливає на цифру,
    але лишається джерелом деталізації для менеджера.
    """
    result = db.execute(
        text("SELECT in_laundry, state FROM products WHERE product_id = :product_id"),
        {"product_id": product_id},
    )
    row = result.fetchone()
    result.close()

    in_laundry_qty = int(row[0]) if row and row[0] else 0
    product_state = row[1] if row else None

    warnings = []

    if in_laundry_qty > 0:
        warnings.append(
            {
                "type": "on_wash",
                "qty": in_laundry_qty,
                "message": (
                    f"⚠️ {in_laundry_qty} шт на мийці/пранні/хімчистці — "
                    f"потрібно поторопитися з обробкою"
                ),
            }
        )
    elif frozen_qty > 0:
        state_messages = {
            "on_repair": ("on_restoration", "на реставрації"),
            "on_wash": ("on_wash", "на мийці"),
            "on_laundry": ("on_laundry", "на хімчистці/пранні"),
            "damaged": ("awaiting_assignment", "очікують розподілу в кабінеті шкоди"),
        }
        wtype, phrase = state_messages.get(
            product_state, ("frozen", "заморожено — перевірте статус в кабінеті шкоди")
        )
        warnings.append(
            {
                "type": wtype,
                "qty": frozen_qty,
                "message": f"⚠️ {frozen_qty} шт {phrase}",
            }
        )

    return warnings


def check_product_availability(
    db,
    product_id: int,
    quantity: int,
    start_date: str,
    end_date: str,
    exclude_order_id: Optional[int] = None,
) -> Dict:
    """
    Перевірити доступність товару на період.

    Розрахунок делегований `AvailabilityService`. Канонічна формула:
        quantity − frozen_quantity − резерв замовлень − soft-резерви

    Резервують статуси: `processing`, `ready_for_issue`, `awaiting_customer`,
    `issued`, `partial_return`. Архівні замовлення не резервують.
    Відмовлені позиції (`order_items.status = 'refused'`) не резервують.

    Формат відповіді збережений незмінним для сумісності з Orders і UI.
    """
    service = AvailabilityService(db)
    core = service.get_availability(
        product_id=product_id,
        start_date=start_date,
        end_date=end_date,
        quantity=quantity,
        exclude_order_id=exclude_order_id,
    )

    nearby_orders = _nearby_orders(
        db, product_id, start_date, end_date, exclude_order_id
    )
    partial = _partial_return_warnings(db, product_id)
    processing_warnings = _processing_warnings(
        db, product_id, core["on_processing_quantity"]
    )

    has_tight_schedule = False
    for order in nearby_orders:
        if order["status"] == "issued":
            has_tight_schedule = True
        if order["days_gap"] is not None and 0 <= order["days_gap"] <= 1:
            has_tight_schedule = True

    return {
        "product_id": product_id,
        "sku": core["sku"],
        "product_name": core["product_name"],
        "total_quantity": core["total_quantity"],
        "reserved_quantity": core["reserved_quantity"],
        "in_rent": core["in_rent"],
        "soft_reserved_quantity": core["soft_reserved_quantity"],
        "available_quantity": core["available_quantity"],
        "ready_quantity": core["ready_quantity"],
        "on_processing_quantity": core["on_processing_quantity"],
        "requested_quantity": quantity,
        "is_available": core["is_available"],
        "has_tight_schedule": has_tight_schedule,
        "nearby_orders": nearby_orders,
        # Часткові повернення
        "has_partial_return_risk": len(partial["warnings"]) > 0,
        "partial_return_qty": partial["qty"],
        "partial_return_warnings": partial["warnings"],
        # Товари на обробці
        "has_processing_warning": len(processing_warnings) > 0,
        "needs_processing_rush": core["needs_processing_rush"],
        "processing_warnings": processing_warnings,
    }


def check_order_availability(
    db,
    items: List[Dict],
    start_date: str,
    end_date: str,
    exclude_order_id: Optional[int] = None,
) -> Dict:
    """
    Перевірити доступність для всіх товарів замовлення.

    Args:
        items: `[{product_id, quantity}, ...]`
        start_date: `YYYY-MM-DD`
        end_date: `YYYY-MM-DD`
        exclude_order_id: ID замовлення для виключення (при оновленні)
    """
    results = []
    unavailable = []

    for item in items:
        result = check_product_availability(
            db,
            product_id=item["product_id"],
            quantity=item["quantity"],
            start_date=start_date,
            end_date=end_date,
            exclude_order_id=exclude_order_id,
        )
        results.append(result)
        if not result["is_available"]:
            unavailable.append(result)

    partial_return_risks = [r for r in results if r.get("has_partial_return_risk")]
    processing_warning_items = [r for r in results if r.get("has_processing_warning")]
    needs_processing_rush_items = [r for r in results if r.get("needs_processing_rush")]

    return {
        "all_available": len(unavailable) == 0,
        "has_partial_return_risks": len(partial_return_risks) > 0,
        "has_processing_warnings": len(processing_warning_items) > 0,
        "needs_processing_rush": len(needs_processing_rush_items) > 0,
        "items": results,
        "unavailable_items": unavailable,
        "partial_return_risk_items": partial_return_risks,
        "processing_warning_items": processing_warning_items,
        "processing_rush_items": needs_processing_rush_items,
    }