"""
Utility для перевірки доступності товарів
Використовується в різних частинах системи для консистентної логіки
"""
from sqlalchemy import text
from typing import List, Dict, Optional

def check_product_availability(
    db,
    product_id: int,
    quantity: int,
    start_date: str,
    end_date: str,
    exclude_order_id: Optional[int] = None
) -> Dict:
    """
    Перевірити доступність товару на період
    
    Логіка заморожування:
    - ЗАМОРОЖЕНО: orders.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent')
    - РОЗМОРОЖЕНО: orders.status IN ('returned', 'cancelled', 'completed')
    
    Returns:
        {
            "product_id": int,
            "sku": str,
            "product_name": str,
            "total_quantity": int,
            "reserved_quantity": int,
            "available_quantity": int,
            "requested_quantity": int,
            "is_available": bool
        }
    """
    # Отримати загальну кількість, SKU та назву
    total_result = db.execute(text("""
        SELECT quantity, sku, name FROM products WHERE product_id = :product_id
    """), {"product_id": product_id})
    total_row = total_result.fetchone()
    total_result.close()  # Закрити результат
    
    total_qty = int(total_row[0]) if total_row else 0
    sku = total_row[1] if total_row else None
    product_name = total_row[2] if total_row else None
    
    # Підрахувати зарезервовані (заморожені) товари
    # Перевірка по ДАТАХ - якщо дати не перетинаються, товар вільний
    query = """
        SELECT COALESCE(SUM(oi.quantity), 0) as reserved
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
        AND o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent')
        AND o.rental_start_date <= :end_date 
        AND o.rental_end_date >= :start_date
    """
    
    params = {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date
    }
    
    # Виключити поточне замовлення (якщо потрібно)
    if exclude_order_id:
        query += " AND o.order_id != :exclude_order_id"
        params["exclude_order_id"] = exclude_order_id
    
    reserved_result = db.execute(text(query), params)
    reserved_qty = int(reserved_result.fetchone()[0])
    reserved_result.close()  # Закрити результат
    
    # Підрахувати кількість товару що саме "в оренді" (статус issued або on_rent)
    # Тільки для того періоду який перевіряємо
    on_rent_query = """
        SELECT COALESCE(SUM(oi.quantity), 0) as on_rent
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
        AND o.status IN ('issued', 'on_rent')
        AND o.rental_start_date <= :end_date 
        AND o.rental_end_date >= :start_date
    """
    
    on_rent_params = {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date
    }
    
    if exclude_order_id:
        on_rent_query += " AND o.order_id != :exclude_order_id"
        on_rent_params["exclude_order_id"] = exclude_order_id
    
    on_rent_result = db.execute(text(on_rent_query), on_rent_params)
    on_rent_qty = int(on_rent_result.fetchone()[0])
    on_rent_result.close()  # Закрити результат
    
    # Отримати близькі замовлення (попередження про можливий конфлікт)
    # Шукаємо замовлення що:
    # 1. Перетинаються з датами (конфлікт)
    # 2. Завершуються за день до початку (мало часу на підготовку)
    # 3. Зараз у статусі issued/on_rent (може запізнитися з поверненням)
    nearby_orders_query = """
        SELECT o.order_id, o.order_number, o.status, o.rental_start_date, o.rental_end_date, oi.quantity,
               DATEDIFF(:start_date, o.rental_end_date) as days_gap
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        WHERE oi.product_id = :product_id
        AND o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent')
        AND (
            (o.rental_start_date <= :end_date AND o.rental_end_date >= :start_date)
            OR (o.rental_end_date >= DATE_SUB(:start_date, INTERVAL 1 DAY) 
                AND o.rental_end_date < :start_date)
        )
        ORDER BY o.rental_start_date
    """
    
    nearby_params = {
        "product_id": product_id,
        "start_date": start_date,
        "end_date": end_date
    }
    
    if exclude_order_id:
        nearby_orders_query += " AND o.order_id != :exclude_order_id"
        nearby_params["exclude_order_id"] = exclude_order_id
    
    nearby_result = db.execute(text(nearby_orders_query), nearby_params)
    nearby_orders = []
    for row in nearby_result:
        nearby_orders.append({
            "order_id": row[0],
            "order_number": row[1],
            "status": row[2],
            "rental_start_date": row[3].isoformat() if row[3] else None,
            "rental_end_date": row[4].isoformat() if row[4] else None,
            "quantity": row[5],
            "days_gap": row[6] if row[6] is not None else None
        })
    nearby_result.close()
    
    # ========== ПЕРЕВІРКА ЧАСТКОВИХ ПОВЕРНЕНЬ ==========
    # Товари в активних версіях часткових повернень (ще не повернуті)
    # Це ПОПЕРЕДЖЕННЯ - товар формально вільний, але фактично ще у клієнта
    # Використовуємо таблиці: partial_return_versions + partial_return_version_items
    partial_return_query = """
        SELECT 
            prv.parent_order_id,
            prv.display_number,
            prvi.qty,
            prv.rental_end_date,
            DATEDIFF(CURDATE(), prv.rental_end_date) as days_overdue,
            prvi.daily_rate,
            prv.created_at,
            prv.version_id
        FROM partial_return_version_items prvi
        JOIN partial_return_versions prv ON prvi.version_id = prv.version_id
        WHERE prvi.product_id = :product_id
        AND prvi.status = 'pending'
        AND prv.status = 'active'
        ORDER BY prv.rental_end_date DESC
    """
    
    partial_return_result = db.execute(text(partial_return_query), {"product_id": product_id})
    partial_return_warnings = []
    partial_return_qty = 0  # Кількість товару що "зависла" в частковому поверненні
    
    for row in partial_return_result:
        days_overdue = row[4] if row[4] else 0
        partial_return_qty += row[2]  # qty
        partial_return_warnings.append({
            "order_id": row[0],
            "order_number": row[1],  # display_number: OC-7304(1)
            "qty": row[2],
            "original_end_date": row[3].isoformat() if row[3] else None,
            "days_overdue": days_overdue,
            "daily_rate": float(row[5]) if row[5] else 0,
            "version_id": row[7],
            "warning": f"⚠️ Товар ще НЕ ПОВЕРНУТО! Прострочка {days_overdue} дн. Дата повернення невідома."
        })
    partial_return_result.close()
    
    has_partial_return_risk = len(partial_return_warnings) > 0
    # ========== КІНЕЦЬ ПЕРЕВІРКИ ЧАСТКОВИХ ПОВЕРНЕНЬ ==========
    
    # ========== ПЕРЕВІРКА ТОВАРІВ НА ОБРОБЦІ (МИЙКА/ПРАННЯ/ХІМЧИСТКА/РЕСТАВРАЦІЯ) ==========
    # Товари на обробці НЕ БЛОКУЮТЬ видачу, але показують ПОПЕРЕДЖЕННЯ
    # Менеджер може видати, але має знати що потрібно поторопитися з обробкою
    
    processing_query = """
        SELECT 
            p.frozen_quantity,
            p.in_laundry,
            p.state
        FROM products p
        WHERE p.product_id = :product_id
    """
    processing_result = db.execute(text(processing_query), {"product_id": product_id})
    processing_row = processing_result.fetchone()
    processing_result.close()
    
    frozen_qty = int(processing_row[0]) if processing_row and processing_row[0] else 0
    in_laundry_qty = int(processing_row[1]) if processing_row and processing_row[1] else 0
    product_state = processing_row[2] if processing_row else None
    
    # Визначаємо кількість на обробці
    on_processing_qty = 0
    processing_warnings = []
    
    # in_laundry - товари відправлені на мийку/прання/хімчистку
    if in_laundry_qty > 0:
        on_processing_qty = in_laundry_qty
        processing_warnings.append({
            "type": "on_wash",
            "qty": in_laundry_qty,
            "message": f"⚠️ {in_laundry_qty} шт на мийці/пранні/хімчистці - потрібно поторопитися з обробкою"
        })
    # frozen_quantity без in_laundry - товари заморожені (можливо на реставрації або очікують розподілу)
    elif frozen_qty > 0:
        on_processing_qty = frozen_qty
        if product_state == 'on_repair':
            processing_warnings.append({
                "type": "on_restoration",
                "qty": frozen_qty,
                "message": f"⚠️ {frozen_qty} шт на реставрації - потрібно поторопитися з обробкою"
            })
        elif product_state == 'on_wash':
            processing_warnings.append({
                "type": "on_wash",
                "qty": frozen_qty,
                "message": f"⚠️ {frozen_qty} шт на мийці - потрібно поторопитися з обробкою"
            })
        elif product_state == 'on_laundry':
            processing_warnings.append({
                "type": "on_laundry", 
                "qty": frozen_qty,
                "message": f"⚠️ {frozen_qty} шт на хімчистці/пранні - потрібно поторопитися з обробкою"
            })
        elif product_state == 'damaged':
            processing_warnings.append({
                "type": "awaiting_assignment",
                "qty": frozen_qty,
                "message": f"⚠️ {frozen_qty} шт очікують розподілу в кабінеті шкоди - потрібно розподілити та обробити"
            })
        else:
            # Інші випадки заморозки
            processing_warnings.append({
                "type": "frozen",
                "qty": frozen_qty,
                "message": f"⚠️ {frozen_qty} шт заморожено - перевірте статус в кабінеті шкоди"
            })
    
    # Також перевіряємо product_damage_history на товари awaiting_assignment
    awaiting_query = """
        SELECT COALESCE(SUM(pdh.qty), 0) as awaiting_qty
        FROM product_damage_history pdh
        WHERE pdh.product_id = :product_id
        AND pdh.processing_type = 'awaiting_assignment'
        AND pdh.processing_status = 'pending'
    """
    awaiting_result = db.execute(text(awaiting_query), {"product_id": product_id})
    awaiting_row = awaiting_result.fetchone()
    awaiting_result.close()
    awaiting_qty = int(awaiting_row[0]) if awaiting_row and awaiting_row[0] else 0
    
    if awaiting_qty > 0 and awaiting_qty != on_processing_qty:
        # Є товари що очікують розподілу в damage history
        if not any(w['type'] == 'awaiting_assignment' for w in processing_warnings):
            processing_warnings.append({
                "type": "awaiting_assignment",
                "qty": awaiting_qty,
                "message": f"⚠️ {awaiting_qty} шт очікують розподілу в кабінеті шкоди"
            })
            on_processing_qty = max(on_processing_qty, awaiting_qty)
    
    has_processing_warning = len(processing_warnings) > 0
    # ========== КІНЕЦЬ ПЕРЕВІРКИ ТОВАРІВ НА ОБРОБЦІ ==========
    
    # Фактично доступна кількість = загальна - зарезервована
    # Товари на обробці НЕ віднімаємо, бо їх можна видати з попередженням
    available_qty = max(0, total_qty - reserved_qty)
    
    # Але рахуємо "реально готову" кількість для інформування
    ready_qty = max(0, total_qty - reserved_qty - on_processing_qty)
    
    is_available = available_qty >= quantity
    
    # Якщо запитують більше ніж "реально готово", але менше ніж "доступно" - це warning
    needs_processing_rush = is_available and (ready_qty < quantity) and on_processing_qty > 0
    
    # Визначити рівень ризику
    has_conflict = not is_available
    has_tight_schedule = False
    
    for order in nearby_orders:
        # Якщо є замовлення з issued/on_rent поруч, це ризик
        if order['status'] in ('issued', 'on_rent'):
            has_tight_schedule = True
        # Якщо між поверненням і видачею 0-1 день, це ризик
        if order['days_gap'] is not None and 0 <= order['days_gap'] <= 1:
            has_tight_schedule = True
    
    return {
        "product_id": product_id,
        "sku": sku,
        "product_name": product_name,
        "total_quantity": total_qty,
        "reserved_quantity": reserved_qty,
        "in_rent": on_rent_qty,
        "available_quantity": available_qty,
        "ready_quantity": ready_qty,  # Кількість готова до видачі (без обробки)
        "on_processing_quantity": on_processing_qty,  # Кількість на обробці
        "requested_quantity": quantity,
        "is_available": is_available,
        "has_tight_schedule": has_tight_schedule,
        "nearby_orders": nearby_orders,
        # Нові поля для часткових повернень
        "has_partial_return_risk": has_partial_return_risk,
        "partial_return_qty": partial_return_qty,
        "partial_return_warnings": partial_return_warnings,
        # Нові поля для товарів на обробці
        "has_processing_warning": has_processing_warning,
        "needs_processing_rush": needs_processing_rush,
        "processing_warnings": processing_warnings
    }


def check_order_availability(
    db,
    items: List[Dict],
    start_date: str,
    end_date: str,
    exclude_order_id: Optional[int] = None
) -> Dict:
    """
    Перевірити доступність для всіх товарів замовлення
    
    Args:
        items: [{product_id, quantity}, ...]
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        exclude_order_id: ID замовлення для виключення (при оновленні)
    
    Returns:
        {
            "all_available": bool,
            "items": [...],
            "unavailable_items": [...]
        }
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
            exclude_order_id=exclude_order_id
        )
        
        results.append(result)
        
        if not result["is_available"]:
            unavailable.append(result)
    
    # Збираємо товари з ризиком часткового повернення
    partial_return_risks = [r for r in results if r.get("has_partial_return_risk")]
    
    # Збираємо товари з попередженням про обробку
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
        "processing_rush_items": needs_processing_rush_items
    }
