"""
Archive API - Архів замовлень
✅ MIGRATED: Using RentalHub DB
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime, timedelta

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/archive", tags=["archive"])

@router.get("")
async def get_archived_orders(
    status: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати архівні замовлення
    ✅ MIGRATED: Using RentalHub DB
    """
    sql = """
        SELECT 
            order_id, order_number, customer_name, customer_phone,
            rental_start_date, rental_end_date, status, total_price,
            created_at
        FROM orders
        WHERE status IN ('returned', 'cancelled', 'completed')
    """
    
    params = {}
    
    if status:
        sql += " AND status = :status"
        params['status'] = status
    
    if from_date:
        sql += " AND rental_start_date >= :from_date"
        params['from_date'] = from_date
    
    if to_date:
        sql += " AND rental_end_date <= :to_date"
        params['to_date'] = to_date
    
    sql += f" ORDER BY created_at DESC LIMIT {limit}"
    
    result = db.execute(text(sql), params)
    
    orders = []
    for row in result:
        orders.append({
            "order_id": row[0],
            "order_number": row[1],
            "customer_name": row[2],
            "customer_phone": row[3],
            "rental_start_date": row[4].isoformat() if row[4] else None,
            "rental_end_date": row[5].isoformat() if row[5] else None,
            "status": row[6],
            "total_price": float(row[7]) if row[7] else 0.0,
            "created_at": row[8].isoformat() if row[8] else None
        })
    
    return orders

@router.get("/{order_id}/full-history")
async def get_order_full_history(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Повна історія замовлення - всі операції step-by-step
    ✅ MIGRATED: Using RentalHub DB
    """
    timeline = []  # Хронологічний список всіх подій
    
    # Order details
    order_result = db.execute(text("""
        SELECT 
            order_id, order_number, customer_name, customer_phone, customer_email,
            rental_start_date, rental_end_date, status, total_price, deposit_amount,
            created_at, updated_at
        FROM orders
        WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = order_result.fetchone()
    if not order_row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order = {
        "order_id": order_row[0],
        "order_number": order_row[1],
        "customer_name": order_row[2],
        "customer_phone": order_row[3],
        "customer_email": order_row[4],
        "rental_start_date": order_row[5].isoformat() if order_row[5] else None,
        "rental_end_date": order_row[6].isoformat() if order_row[6] else None,
        "status": order_row[7],
        "total_price": float(order_row[8]) if order_row[8] else 0.0,
        "deposit_amount": float(order_row[9]) if order_row[9] else 0.0,
        "created_at": order_row[10].isoformat() if order_row[10] else None
    }
    
    # Add order creation to timeline
    timeline.append({
        "timestamp": order["created_at"],
        "type": "order",
        "action": "created",
        "title": "🛒 Замовлення створено",
        "details": f"Клієнт: {order['customer_name']}, Сума: ₴{order['total_price']}"
    })
    
    # Order items (товари в замовленні)
    items_result = db.execute(text("""
        SELECT 
            oi.id, oi.product_id, oi.product_name, oi.quantity,
            oi.price, oi.total_rental, oi.image_url,
            p.sku, p.category_name
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :order_id AND oi.status = 'active'
        ORDER BY oi.id
    """), {"order_id": order_id})
    
    items = []
    for item_row in items_result:
        image_url = item_row[6]  # from order_items
        # Normalize image URL
        if image_url:
            if not image_url.startswith('http') and not image_url.startswith('/api'):
                image_url = f"/api/{image_url}" if not image_url.startswith('uploads') else f"/api/{image_url}"
        
        items.append({
            "id": item_row[0],
            "product_id": item_row[1],
            "name": item_row[2],
            "quantity": item_row[3],
            "price": float(item_row[4]) if item_row[4] else 0.0,
            "subtotal": float(item_row[5]) if item_row[5] else 0.0,
            "image_url": image_url,
            "sku": item_row[7] or f"P-{item_row[1]}",
            "category": item_row[8]
        })
    
    # Issue cards (збірка та видача)
    issue_result = db.execute(text("""
        SELECT id, status, prepared_by, issued_by, prepared_at, issued_at, created_at
        FROM issue_cards
        WHERE order_id = :order_id
        ORDER BY created_at
    """), {"order_id": order_id})
    
    issue_cards = []
    for i_row in issue_result:
        card = {
            "id": i_row[0],
            "status": i_row[1],
            "prepared_by": i_row[2],
            "issued_by": i_row[3],
            "prepared_at": i_row[4].isoformat() if i_row[4] else None,
            "issued_at": i_row[5].isoformat() if i_row[5] else None,
            "created_at": i_row[6].isoformat() if i_row[6] else None
        }
        issue_cards.append(card)
        
        if card["prepared_at"] and card["prepared_by"]:
            timeline.append({
                "timestamp": card["prepared_at"],
                "type": "issue",
                "action": "prepared",
                "title": "📦 Замовлення зібрано",
                "details": f"Зібрав: {card['prepared_by']}"
            })
        if card["issued_at"] and card["issued_by"]:
            timeline.append({
                "timestamp": card["issued_at"],
                "type": "issue",
                "action": "issued",
                "title": "🚚 Замовлення видано",
                "details": f"Видав: {card['issued_by']}"
            })
    
    # Returns from new system (partial_return_versions + items) — single source of truth
    return_result = db.execute(text("""
        SELECT prv.version_id, prv.status, prv.customer_name, prv.notes,
               prv.created_at, prv.completed_at,
               (SELECT COUNT(*) FROM partial_return_version_items WHERE version_id = prv.version_id AND status = 'returned') AS items_ok,
               (SELECT COUNT(*) FROM partial_return_version_items WHERE version_id = prv.version_id AND status = 'damaged') AS items_damaged,
               (SELECT COUNT(*) FROM partial_return_version_items WHERE version_id = prv.version_id AND status = 'lost') AS items_missing,
               prv.display_number
        FROM partial_return_versions prv
        WHERE prv.parent_order_id = :order_id
        ORDER BY prv.created_at
    """), {"order_id": order_id})

    return_cards = []
    for r_row in return_result:
        card = {
            "id": r_row[0],
            "status": r_row[1],
            "received_by": r_row[2],
            "checked_by": r_row[2],
            "items_ok": int(r_row[6] or 0),
            "items_damaged": int(r_row[7] or 0),
            "items_missing": int(r_row[8] or 0),
            "cleaning_fee": 0.0,
            "late_fee": 0.0,
            "returned_at": r_row[5].isoformat() if r_row[5] else None,
            "checked_at": r_row[5].isoformat() if r_row[5] else None,
            "created_at": r_row[4].isoformat() if r_row[4] else None,
            "display_number": r_row[9],
        }
        return_cards.append(card)
        
        if card["returned_at"]:
            details = f"Прийняв: {card['received_by'] or '—'}"
            if card["items_damaged"]:
                details += f", Пошкоджено: {card['items_damaged']}"
            if card["items_missing"]:
                details += f", Списано: {card['items_missing']}"
            timeline.append({
                "timestamp": card["returned_at"],
                "type": "return",
                "action": "returned",
                "title": "📥 Товар повернено",
                "details": details
            })
        if card["checked_at"] and card["checked_by"]:
            timeline.append({
                "timestamp": card["checked_at"],
                "type": "return",
                "action": "checked",
                "title": "✅ Перевірка завершена",
                "details": f"Перевірив: {card['checked_by']}"
            })
    
    # Payments (фінанси)
    payments_result = db.execute(text("""
        SELECT id, payment_type, method, amount, note, status, occurred_at, accepted_by_name
        FROM fin_payments
        WHERE order_id = :order_id
        ORDER BY occurred_at
    """), {"order_id": order_id})
    
    payments = []
    for p_row in payments_result:
        payment = {
            "id": p_row[0],
            "payment_type": p_row[1],
            "method": p_row[2],
            "amount": float(p_row[3]) if p_row[3] else 0.0,
            "note": p_row[4],
            "status": p_row[5],
            "occurred_at": p_row[6].isoformat() if p_row[6] else None,
            "accepted_by": p_row[7]
        }
        payments.append(payment)
        
        type_labels = {"rent": "Оренда", "damage": "Шкода", "additional": "Донарахування", "deposit": "Застава"}
        method_labels = {"cash": "готівка", "bank": "безготівка", "card": "картка"}
        
        timeline.append({
            "timestamp": payment["occurred_at"],
            "type": "payment",
            "action": payment["payment_type"],
            "title": f"💰 {type_labels.get(payment['payment_type'], payment['payment_type'])}",
            "details": f"₴{payment['amount']} ({method_labels.get(payment['method'], payment['method'])}) · {payment['accepted_by'] or '—'}" + (f" · {payment['note']}" if payment['note'] else "")
        })
    
    # Deposits (застави)
    deposit_result = db.execute(text("""
        SELECT id, held_amount, used_amount, refunded_amount, actual_amount, currency, 
               status, opened_at, closed_at, note
        FROM fin_deposit_holds
        WHERE order_id = :order_id
        ORDER BY opened_at
    """), {"order_id": order_id})
    
    deposits = []
    for d_row in deposit_result:
        deposit = {
            "id": d_row[0],
            "held_amount": float(d_row[1]) if d_row[1] else 0.0,
            "used_amount": float(d_row[2]) if d_row[2] else 0.0,
            "refunded_amount": float(d_row[3]) if d_row[3] else 0.0,
            "actual_amount": float(d_row[4]) if d_row[4] else 0.0,
            "currency": d_row[5] or "UAH",
            "status": d_row[6],
            "created_at": d_row[7].isoformat() if d_row[7] else None,
            "closed_at": d_row[8].isoformat() if d_row[8] else None,
            "note": d_row[9]
        }
        deposits.append(deposit)
        
        symbol = {"USD": "$", "EUR": "€"}.get(deposit["currency"], "₴")
        
        timeline.append({
            "timestamp": deposit["created_at"],
            "type": "deposit",
            "action": "accepted",
            "title": "🔒 Застава прийнята",
            "details": f"{symbol}{deposit['actual_amount']}"
        })
        
        if deposit["used_amount"] > 0:
            timeline.append({
                "timestamp": deposit["closed_at"] or deposit["created_at"],
                "type": "deposit",
                "action": "used",
                "title": "⚠️ Утримано із застави",
                "details": f"₴{deposit['used_amount']} (компенсація шкоди)"
            })
        
        if deposit["refunded_amount"] > 0:
            timeline.append({
                "timestamp": deposit["closed_at"],
                "type": "deposit",
                "action": "refunded",
                "title": "💸 Застава повернена",
                "details": f"{symbol}{deposit['refunded_amount']}"
            })
    
    # Damage history
    damage_result = db.execute(text("""
        SELECT id, sku, note, severity, fee, stage, created_at, damage_type, product_name, qty, fee_per_item, processing_type
        FROM product_damage_history
        WHERE order_id = :order_id
        ORDER BY created_at
    """), {"order_id": order_id})
    
    damages = []
    for dm_row in damage_result:
        qty = dm_row[9] or 1
        fee = float(dm_row[4]) if dm_row[4] else 0.0
        fee_per_item = float(dm_row[10]) if dm_row[10] else (fee / qty if qty > 0 else fee)
        
        damage = {
            "id": dm_row[0],
            "sku": dm_row[1],
            "note": dm_row[2],
            "severity": dm_row[3],
            "fee": fee,
            "fee_per_item": fee_per_item,
            "qty": qty,
            "stage": dm_row[5],
            "created_at": dm_row[6].isoformat() if dm_row[6] else None,
            "damage_type": dm_row[7],
            "product_name": dm_row[8],
            "processing_type": dm_row[11]
        }
        damages.append(damage)
        
        stage_label = "при видачі" if damage["stage"] == "pre_issue" else "при поверненні"
        qty_label = f" x{qty}" if qty > 1 else ""
        timeline.append({
            "timestamp": damage["created_at"],
            "type": "damage",
            "action": damage["stage"],
            "title": f"🔴 Шкода ({stage_label})",
            "details": f"{damage['sku']}{qty_label} · {damage['damage_type'] or damage['note'] or '—'}, Fee: ₴{fee}" + (f" ({qty} шт × ₴{fee_per_item:.0f})" if qty > 1 else "")
        })
    
    # Documents
    doc_result = db.execute(text("""
        SELECT id, doc_type, doc_number, status, created_at
        FROM documents
        WHERE entity_type = 'order' AND entity_id = :order_id
        ORDER BY created_at
    """), {"order_id": str(order_id)})
    
    documents = []
    for doc_row in doc_result:
        doc = {
            "id": doc_row[0],
            "doc_type": doc_row[1],
            "doc_number": doc_row[2],
            "status": doc_row[3],
            "created_at": doc_row[4].isoformat() if doc_row[4] else None
        }
        documents.append(doc)
        
        type_labels = {
            "invoice_offer": "Рахунок-оферта",
            "picking_list": "Лист комплектації",
            "issue_act": "Акт видачі",
            "return_act": "Акт повернення",
            "damage_report": "Акт шкоди",
            "service_act": "Акт виконаних робіт",
            "invoice_legal": "Рахунок",
            "goods_invoice": "Накладна"
        }
        
        timeline.append({
            "timestamp": doc["created_at"],
            "type": "document",
            "action": "generated",
            "title": f"📄 {type_labels.get(doc['doc_type'], doc['doc_type'])}",
            "details": f"#{doc['doc_number']}"
        })
    
    # Order Lifecycle (повна історія всіх змін)
    lifecycle_result = db.execute(text("""
        SELECT id, stage, notes, created_by_name, created_at
        FROM order_lifecycle
        WHERE order_id = :order_id
        ORDER BY created_at
    """), {"order_id": order_id})
    
    lifecycle = []
    stage_labels = {
        "created": "🛒 Замовлення створено",
        "awaiting_customer": "⏳ Очікує підтвердження клієнта",
        "confirmed": "✅ Підтверджено клієнтом",
        "processing": "📋 В обробці",
        "packing": "📦 Комплектація",
        "ready_for_issue": "✅ Готово до видачі",
        "shipped": "🚚 Відправлено",
        "delivered": "📍 Доставлено",
        "issued": "📤 Видано",
        "on_rent": "🔄 В оренді",
        "returning": "📥 Повернення",
        "partial_return": "📦 Часткове повернення",
        "returned": "✅ Повернено",
        "completed": "🎉 Завершено",
        "cancelled": "❌ Скасовано",
        "payment_received": "💰 Оплата отримана",
        "deposit_accepted": "🔒 Застава прийнята",
        "deposit_returned": "💸 Застава повернена",
        "note_added": "📝 Додано нотатку",
        "modified": "✏️ Змінено",
    }
    
    for lc_row in lifecycle_result:
        lc = {
            "id": lc_row[0],
            "stage": lc_row[1],
            "notes": lc_row[2],
            "created_by": lc_row[3],
            "created_at": lc_row[4].isoformat() if lc_row[4] else None
        }
        lifecycle.append(lc)
        
        timeline.append({
            "timestamp": lc["created_at"],
            "type": "lifecycle",
            "action": lc["stage"],
            "title": stage_labels.get(lc["stage"], f"📌 {lc['stage']}"),
            "details": f"{lc['notes'] or ''}" + (f" · {lc['created_by']}" if lc['created_by'] else "")
        })
    
    # Sort timeline by timestamp
    timeline.sort(key=lambda x: x["timestamp"] or "")
    
    return {
        "order": order,
        "items": items,
        "issue_cards": issue_cards,
        "return_cards": return_cards,
        "payments": payments,
        "deposits": deposits,
        "damages": damages,
        "documents": documents,
        "lifecycle": lifecycle,
        "timeline": timeline
    }

@router.get("/stats")
async def get_archive_stats(
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """
    Статистика архіву
    ✅ MIGRATED: Using RentalHub DB
    """
    params = {}
    date_filter = ""
    
    if from_date:
        date_filter += " AND created_at >= :from_date"
        params['from_date'] = from_date
    
    if to_date:
        date_filter += " AND created_at <= :to_date"
        params['to_date'] = to_date
    
    # Total orders
    total_result = db.execute(text(f"""
        SELECT COUNT(*) FROM orders WHERE status IN ('returned', 'cancelled', 'completed') {date_filter}
    """), params)
    total_orders = total_result.scalar() or 0
    
    # By status
    status_result = db.execute(text(f"""
        SELECT status, COUNT(*) as count
        FROM orders
        WHERE status IN ('returned', 'cancelled', 'completed') {date_filter}
        GROUP BY status
    """), params)
    
    by_status = {}
    for s_row in status_result:
        by_status[s_row[0]] = s_row[1]
    
    # Revenue
    revenue_result = db.execute(text(f"""
        SELECT SUM(total_price) FROM orders 
        WHERE status IN ('returned', 'completed') {date_filter}
    """), params)
    total_revenue = revenue_result.scalar() or 0.0
    
    return {
        "total_orders": total_orders,
        "by_status": by_status,
        "total_revenue": float(total_revenue),
        "period": {
            "from": from_date,
            "to": to_date
        }
    }
