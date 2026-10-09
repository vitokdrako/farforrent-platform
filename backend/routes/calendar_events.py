"""
Universal Calendar Events API
Єдиний endpoint для всіх подій системи - дзеркало операцій
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import List, Optional
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

# ============================================================
# ТИПИ ПОДІЙ
# ============================================================
EVENT_TYPES = {
    # Видача - показується тільки якщо ордер НЕ виданий
    "issue_awaiting": {"label": "Видача (очікує)", "color": "#8b5cf6", "icon": "📤", "group": "orders"},
    "issue_processing": {"label": "Видача (комплектація)", "color": "#f59e0b", "icon": "📤", "group": "orders"},
    "issue_ready": {"label": "Видача (готово)", "color": "#22c55e", "icon": "📤", "group": "orders"},
    
    # Повернення - показується тільки якщо ордер ВЖЕ виданий
    "return_issued": {"label": "Повернення (в оренді)", "color": "#eab308", "icon": "📥", "group": "orders"},
    "return_processing": {"label": "Повернення (обробка)", "color": "#f59e0b", "icon": "📥", "group": "orders"},
    "return_overdue": {"label": "Повернення (прострочено)", "color": "#ef4444", "icon": "🚨", "group": "orders"},
    
    # Обслуговування
    "cleaning": {"label": "Мийка", "color": "#06b6d4", "icon": "🧹", "group": "maintenance"},
    "laundry": {"label": "Прання", "color": "#0ea5e9", "icon": "🧺", "group": "maintenance"},
    "repair": {"label": "Реставрація", "color": "#f97316", "icon": "🔧", "group": "maintenance"},
    
    # Проблеми
    "damage": {"label": "Шкода", "color": "#ef4444", "icon": "⚠️", "group": "issues"},
    
    # Фінанси
    "payment_due": {"label": "Очікується оплата", "color": "#a855f7", "icon": "💰", "group": "finance"},
    "deposit_return": {"label": "Повернення застави", "color": "#14b8a6", "icon": "🔓", "group": "finance"},
    
    # Завдання
    "task": {"label": "Завдання", "color": "#8b5cf6", "icon": "📝", "group": "tasks"},
}

EVENT_GROUPS = {
    "orders": {"label": "Замовлення", "icon": "📦"},
    "maintenance": {"label": "Обслуговування", "icon": "🔧"},
    "issues": {"label": "Проблеми", "icon": "⚠️"},
    "finance": {"label": "Фінанси", "icon": "💰"},
    "tasks": {"label": "Завдання", "icon": "📝"},
}


@router.get("/event-types")
async def get_event_types():
    """Отримати всі типи подій з метаданими"""
    return {
        "types": EVENT_TYPES,
        "groups": EVENT_GROUPS
    }


@router.get("/events")
async def get_calendar_events(
    date_from: str = Query(..., description="Start date YYYY-MM-DD"),
    date_to: str = Query(..., description="End date YYYY-MM-DD"),
    types: Optional[str] = Query(None, description="Comma-separated event types"),
    groups: Optional[str] = Query(None, description="Comma-separated groups"),
    search: Optional[str] = Query(None, description="Search query"),
    db: Session = Depends(get_rh_db)
):
    """
    Універсальний endpoint для всіх подій календаря.
    Агрегує дані з усіх частин системи.
    """
    events = []
    
    # Парсимо фільтри
    type_filter = set(types.split(",")) if types else None
    group_filter = set(groups.split(",")) if groups else None
    
    def should_include(event_type: str) -> bool:
        if type_filter and event_type not in type_filter:
            return False
        if group_filter:
            event_group = EVENT_TYPES.get(event_type, {}).get("group")
            if event_group not in group_filter:
                return False
        return True
    
    # ============================================================
    # 1. ЗАМОВЛЕННЯ - Видача + Повернення (2 події на ордер)
    # Колір визначається статусом ордера
    # ============================================================
    try:
        orders_query = """
            SELECT 
                o.order_id, o.order_number, o.customer_name, o.customer_phone,
                o.status, o.total_price, o.deposit_amount,
                o.rental_start_date, o.rental_end_date, o.rental_days,
                o.issue_date, o.return_date, o.delivery_type, o.city,
                o.event_type as order_event_type, o.created_at
            FROM orders o
            WHERE o.is_archived = 0
            AND o.status NOT IN ('returned', 'completed', 'cancelled', 'rejected')
            AND (
                (o.rental_start_date BETWEEN :date_from AND :date_to)
                OR (o.rental_end_date BETWEEN :date_from AND :date_to)
                OR (o.issue_date BETWEEN :date_from AND :date_to)
                OR (o.return_date BETWEEN :date_from AND :date_to)
                OR (o.rental_start_date <= :date_from AND o.rental_end_date >= :date_to)
            )
            ORDER BY o.rental_start_date
        """
        
        orders_result = db.execute(text(orders_query), {
            "date_from": date_from,
            "date_to": date_to
        })
        
        # Мапінг статусу на тип події
        def get_issue_type(status):
            if status in ('awaiting_customer', 'awaiting', 'pending'):
                return 'issue_awaiting'
            elif status in ('processing', 'packing'):
                return 'issue_processing'
            elif status in ('ready_for_issue', 'ready'):
                return 'issue_ready'
            elif status in ('issued', 'on_rent', 'shipped', 'delivered'):
                return 'issue_issued'
            return 'issue_processing'
        
        def get_return_type(status, return_date_str, today_str):
            if status in ('awaiting_customer', 'awaiting', 'pending'):
                return 'return_awaiting'
            elif status in ('processing', 'packing'):
                return 'return_processing'
            elif status in ('ready_for_issue', 'ready'):
                return 'return_ready'
            elif status in ('issued', 'on_rent', 'shipped', 'delivered'):
                # Перевірка на прострочення
                if return_date_str and return_date_str < today_str:
                    return 'return_overdue'
                return 'return_issued'
            return 'return_processing'
        
        today_str = date_from  # Приблизно сьогодні
        
        # Статуси для логіки відображення
        NOT_ISSUED_STATUSES = ('awaiting_customer', 'awaiting', 'pending', 'processing', 'packing', 'ready_for_issue', 'ready')
        ISSUED_STATUSES = ('issued', 'on_rent', 'shipped', 'delivered', 'returning', 'partial_return')
        
        for row in orders_result:
            order_id = row[0]
            order_number = row[1]
            customer_name = row[2]
            customer_phone = row[3]
            status = row[4]
            total_price = float(row[5] or 0)
            deposit = float(row[6] or 0)
            start_date = row[7]
            end_date = row[8]
            rental_days = row[9]
            issue_date = row[10]
            return_date = row[11]
            delivery_type = row[12]
            city = row[13]
            event_type = row[14]
            created_at = row[15]
            
            base_event = {
                "order_id": order_id,
                "order_number": order_number,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "total_price": total_price,
                "deposit": deposit,
                "delivery_type": delivery_type,
                "city": city,
                "rental_days": rental_days,
                "order_status": status,
                "order_event_type": event_type,
            }
            
            # ВИДАЧА - показуємо ТІЛЬКИ якщо ордер ще НЕ виданий
            # Якщо ордер вже на поверненні - не показуємо видачу
            if status in NOT_ISSUED_STATUSES:
                issue_dt = issue_date or start_date
                if issue_dt:
                    issue_str = str(issue_dt)[:10]
                    if date_from <= issue_str <= date_to:
                        issue_type = get_issue_type(status)
                        if should_include(issue_type) or group_filter is None:
                            events.append({
                                **base_event,
                                "id": f"order-issue-{order_id}",
                                "type": issue_type,
                                "date": issue_str,
                                "title": f"#{order_number} {customer_name}",
                                "subtitle": f"Видача · {delivery_type or 'самовивіз'}",
                                "priority": 2,
                            })
            
            # ПОВЕРНЕННЯ - показуємо ТІЛЬКИ якщо ордер ВЖЕ виданий
            if status in ISSUED_STATUSES:
                return_dt = return_date or end_date
                if return_dt:
                    return_str = str(return_dt)[:10]
                    if date_from <= return_str <= date_to:
                        # Визначаємо тип повернення
                        if status in ('returning', 'partial_return'):
                            return_type = 'return_processing'
                        elif return_str < today_str:
                            return_type = 'return_overdue'
                        else:
                            return_type = 'return_issued'
                        
                        if should_include(return_type) or group_filter is None:
                            events.append({
                                **base_event,
                                "id": f"order-return-{order_id}",
                                "type": return_type,
                                "date": return_str,
                                "title": f"#{order_number} {customer_name}",
                                "subtitle": f"Повернення · {rental_days or '?'} дн.",
                                "priority": 2 if return_type != 'return_overdue' else 1,
                            })
                
    except Exception as e:
        print(f"[Calendar] Error loading orders: {e}")
    
    # ============================================================
    # 2. CLEANING / LAUNDRY - Мийка, Прання, Реставрація
    # ============================================================
    if should_include("cleaning") or should_include("laundry") or should_include("repair"):
        try:
            cleaning_query = """
                SELECT 
                    id, product_id, sku, processing_type, processing_status,
                    created_at, updated_at, note
                FROM product_damage_history
                WHERE COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
                AND processing_type IN ('wash', 'restoration', 'laundry')
                AND (COALESCE(qty, 1) - COALESCE(processed_qty, 0)) > 0
                AND (
                    DATE(created_at) BETWEEN :date_from AND :date_to
                    OR DATE(updated_at) BETWEEN :date_from AND :date_to
                )
            """
            
            cleaning_result = db.execute(text(cleaning_query), {
                "date_from": date_from,
                "date_to": date_to
            })
            
            for row in cleaning_result:
                cleaning_type = row[3]
                event_type = "repair" if cleaning_type == "restoration" else (
                    "laundry" if cleaning_type == "laundry" else "cleaning"
                )
                
                if should_include(event_type):
                    events.append({
                        "id": f"cleaning-{row[0]}",
                        "type": event_type,
                        "date": str(row[5])[:10] if row[5] else date_from,
                        "title": f"{row[2] or row[1]} · {cleaning_type}",
                        "subtitle": f"{row[4]} · {row[7] or ''}",
                        "cleaning_id": row[0],
                        "product_id": row[1],
                        "sku": row[2],
                        "status": row[4],
                        "priority": 3,
                    })
        except Exception as e:
            print(f"[Calendar] Error loading cleaning: {e}")
    
    # ============================================================
    # 4. DAMAGE - Шкода (з product_damage_history)
    # ============================================================
    if should_include("damage"):
        try:
            damage_query = """
                SELECT 
                    pdh.id, pdh.order_id, pdh.damage_type, pdh.fee,
                    pdh.created_at, pdh.note,
                    o.order_number, o.customer_name
                FROM product_damage_history pdh
                LEFT JOIN orders o ON pdh.order_id = o.order_id
                WHERE pdh.fee > 0
                AND DATE(pdh.created_at) BETWEEN :date_from AND :date_to
            """
            
            damage_result = db.execute(text(damage_query), {
                "date_from": date_from,
                "date_to": date_to
            })
            
            for row in damage_result:
                events.append({
                    "id": f"damage-{row[0]}",
                    "type": "damage",
                    "date": str(row[4])[:10] if row[4] else date_from,
                    "title": f"Шкода #{row[6] or row[1]}",
                    "subtitle": f"₴{float(row[3] or 0):,.0f} · {row[2]}",
                    "damage_id": row[0],
                    "order_id": row[1],
                    "order_number": row[6],
                    "customer_name": row[7],
                    "amount": float(row[3] or 0),
                    "damage_type": row[2],
                    "priority": 1,
                })
        except Exception as e:
            print(f"[Calendar] Error loading damage: {e}")
    
    # ============================================================
    # 5. FINANCE - Платежі, Застави
    # ============================================================
    if should_include("payment_due") or should_include("deposit_return"):
        try:
            # Очікувані платежі
            if should_include("payment_due"):
                payments_query = """
                    SELECT 
                        fp.id, fp.order_id, fp.amount, fp.payment_type, fp.status,
                        fp.created_at, o.order_number, o.customer_name
                    FROM fin_payments fp
                    LEFT JOIN orders o ON fp.order_id = o.order_id
                    WHERE fp.status = 'pending'
                    AND DATE(fp.created_at) BETWEEN :date_from AND :date_to
                """
                
                payments_result = db.execute(text(payments_query), {
                    "date_from": date_from,
                    "date_to": date_to
                })
                
                for row in payments_result:
                    events.append({
                        "id": f"payment-{row[0]}",
                        "type": "payment_due",
                        "date": str(row[5])[:10] if row[5] else date_from,
                        "title": f"#{row[6]} {row[7] or ''}",
                        "subtitle": f"Очікується ₴{float(row[2] or 0):,.0f} · {row[3]}",
                        "payment_id": row[0],
                        "order_id": row[1],
                        "amount": float(row[2] or 0),
                        "payment_type": row[3],
                        "priority": 2,
                    })
            
            # Повернення застав
            if should_include("deposit_return"):
                deposits_query = """
                    SELECT 
                        dh.id, dh.order_id, dh.held_amount, dh.status,
                        dh.opened_at, o.order_number, o.customer_name, o.return_date,
                        dh.currency, dh.used_amount, dh.refunded_amount
                    FROM fin_deposit_holds dh
                    LEFT JOIN orders o ON dh.order_id = o.order_id
                    WHERE dh.status = 'holding'
                    AND o.status = 'returned'
                """
                
                deposits_result = db.execute(text(deposits_query))
                
                for row in deposits_result:
                    event_date = row[7] or row[4]  # return_date or opened_at
                    held = float(row[2] or 0)
                    used = float(row[9] or 0)
                    refunded = float(row[10] or 0)
                    available = held - used - refunded
                    
                    if event_date and available > 0:
                        currency_symbol = "$" if row[8] == "USD" else ("€" if row[8] == "EUR" else "₴")
                        events.append({
                            "id": f"deposit-{row[0]}",
                            "type": "deposit_return",
                            "date": str(event_date)[:10],
                            "title": f"#{row[5]} {row[6] or ''}",
                            "subtitle": f"Повернути заставу {currency_symbol}{available:,.0f}",
                            "deposit_id": row[0],
                            "order_id": row[1],
                            "amount": available,
                            "currency": row[8],
                            "priority": 2,
                        })
        except Exception as e:
            print(f"[Calendar] Error loading finance: {e}")
    
    # ============================================================
    # 6. TASKS - Завдання
    # ============================================================
    if should_include("task"):
        try:
            tasks_query = """
                SELECT 
                    id, title, description, status, priority,
                    due_date, created_at, assigned_to
                FROM tasks
                WHERE status NOT IN ('completed', 'cancelled')
                AND (
                    DATE(due_date) BETWEEN :date_from AND :date_to
                    OR DATE(created_at) BETWEEN :date_from AND :date_to
                )
            """
            
            tasks_result = db.execute(text(tasks_query), {
                "date_from": date_from,
                "date_to": date_to
            })
            
            for row in tasks_result:
                task_date = row[5] or row[6]  # due_date or created_at
                if task_date:
                    events.append({
                        "id": f"task-{row[0]}",
                        "type": "task",
                        "date": str(task_date)[:10],
                        "title": row[1] or "Завдання",
                        "subtitle": row[2][:50] if row[2] else row[3],
                        "task_id": row[0],
                        "status": row[3],
                        "priority": row[4] or 3,
                    })
        except Exception as e:
            print(f"[Calendar] Error loading tasks: {e}")
    
    # ============================================================
    # Фільтрація по пошуку
    # ============================================================
    if search:
        search_lower = search.lower()
        events = [
            e for e in events
            if search_lower in (e.get("title", "") or "").lower()
            or search_lower in (e.get("subtitle", "") or "").lower()
            or search_lower in (e.get("order_number", "") or "").lower()
            or search_lower in (e.get("customer_name", "") or "").lower()
        ]
    
    # Сортування по даті та пріоритету
    def get_priority_value(p):
        if p is None:
            return 5
        if isinstance(p, int):
            return p
        priority_map = {'high': 1, 'medium': 3, 'low': 5}
        return priority_map.get(str(p).lower(), 5)
    
    events.sort(key=lambda e: (str(e.get("date", "") or ""), get_priority_value(e.get("priority"))))
    
    # Додаємо метадані до кожної події
    for event in events:
        event_type = event.get("type")
        if event_type in EVENT_TYPES:
            event["_meta"] = EVENT_TYPES[event_type]
    
    return {
        "events": events,
        "total": len(events),
        "date_from": date_from,
        "date_to": date_to,
        "filters": {
            "types": list(type_filter) if type_filter else None,
            "groups": list(group_filter) if group_filter else None,
            "search": search
        }
    }


@router.get("/stats")
async def get_calendar_stats(
    date: str = Query(..., description="Date YYYY-MM-DD"),
    db: Session = Depends(get_rh_db)
):
    """Статистика подій на конкретну дату"""
    stats = {}
    
    for event_type in EVENT_TYPES:
        stats[event_type] = 0
    
    # Отримуємо всі події на цю дату
    events_response = await get_calendar_events(
        date_from=date,
        date_to=date,
        types=None,
        groups=None,
        search=None,
        db=db
    )
    
    for event in events_response.get("events", []):
        event_type = event.get("type")
        if event_type in stats:
            stats[event_type] += 1
    
    return {
        "date": date,
        "stats": stats,
        "total": sum(stats.values())
    }
