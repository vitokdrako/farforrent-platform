"""
Warehouse routes - API для реквізиторів
Dashboard, календар, зони складу
✅ MIGRATED: Using RentalHub DB
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, cast, String, text
from datetime import datetime, timedelta, date
from database_rentalhub import get_rh_db  # ✅ Using RentalHub DB
import json

router = APIRouter(prefix="/api/warehouse", tags=["warehouse"])


@router.get("/dashboard")
async def warehouse_dashboard(
    date: Optional[str] = None,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Dashboard для реквізиторів
    Агрегована інформація на день: видачі, повернення, таски
    ✅ MIGRATED: Using RentalHub DB (issue_cards, return_cards, tasks, damages)
    """
    try:
        target_date = datetime.fromisoformat(date) if date else datetime.now()
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        # ✅ Видачі на сьогодні
        issue_result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM issue_cards
            WHERE created_at >= :start AND created_at < :end
        """), {"start": start_of_day, "end": end_of_day})
        issues_today = issue_result.scalar() or 0
        
        # ✅ Повернення на сьогодні
        return_result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM return_cards
            WHERE created_at >= :start AND created_at < :end
        """), {"start": start_of_day, "end": end_of_day})
        returns_today = return_result.scalar() or 0
        
        # ✅ Таски на сьогодні
        tasks_result = db.execute(text("""
            SELECT status
            FROM tasks
            WHERE status IN ('todo', 'in_progress')
            AND (due_date IS NULL OR due_date <= :end)
        """), {"end": end_of_day})
        tasks_rows = tasks_result.fetchall()
        tasks_pending = len([t for t in tasks_rows if t[0] == 'todo'])
        tasks_progress = len([t for t in tasks_rows if t[0] == 'in_progress'])
        
        # ✅ Активні шкоди (з product_damage_history)
        damages_result = db.execute(text("""
            SELECT COUNT(*) as count
            FROM product_damage_history
            WHERE COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
            AND processing_type IN ('wash', 'restoration', 'laundry')
            AND (COALESCE(qty, 1) - COALESCE(processed_qty, 0)) > 0
        """))
        active_damages = damages_result.scalar() or 0
        
        return {
            "date": target_date.isoformat(),
            "stats": {
                "issues_today": issues_today,
                "returns_today": returns_today,
                "tasks_pending": tasks_pending,
                "tasks_progress": tasks_progress,
                "active_damages": active_damages
            },
            "quick_summary": f"{issues_today} видачі · {returns_today} повернення"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка завантаження dashboard: {str(e)}"
        )


@router.get("/calendar")
async def warehouse_calendar(
    from_date: str,
    to_date: str,
    view: str = "day",  # day або week
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Календар подій для реквізиторів
    Видачі та повернення на обраний період
    ✅ MIGRATED: Using RentalHub DB (issue_cards + return_cards + orders)
    """
    try:
        start = datetime.fromisoformat(from_date)
        end = datetime.fromisoformat(to_date)
        
        events = []
        
        # ✅ Issue Cards (Видачі) - using RentalHub DB
        issue_result = db.execute(text("""
            SELECT 
                ic.id, ic.order_number, ic.status, ic.items,
                o.customer_name, o.rental_start_date
            FROM issue_cards ic
            JOIN orders o ON ic.order_id = o.order_id
            WHERE o.rental_start_date >= :start AND o.rental_start_date <= :end
            ORDER BY o.rental_start_date
        """), {"start": start.date(), "end": end.date()})
        
        for row in issue_result:
            card_id, order_number, status, items_json, customer_name, rent_date = row
            
            # Parse items JSON
            items = []
            if items_json:
                try:
                    items = json.loads(items_json) if isinstance(items_json, str) else items_json
                except:
                    items = []
            
            items_count = len(items) if items else 0
            
            # Визначити категорії товарів
            categories = set()
            for item in items:
                name = item.get('name', '').lower() if isinstance(item, dict) else ''
                if 'меблі' in name or 'стіл' in name or 'стілець' in name:
                    categories.add('Меблі')
                elif 'текстиль' in name or 'скатертина' in name or 'серветка' in name:
                    categories.add('текстиль')
                elif 'посуд' in name or 'тарілка' in name or 'келих' in name:
                    categories.add('посуд')
                elif 'ваза' in name or 'свічник' in name or 'декор' in name:
                    categories.add('Вази + свічники')
            
            items_summary = ', '.join(categories) if categories else 'Реквізит'
            
            events.append({
                "id": card_id,
                "order_id": order_number,
                "type": "issue",
                "time": rent_date.strftime("%H:%M") if rent_date else "10:00",
                "date": rent_date.isoformat() if rent_date else None,
                "client": customer_name or "Клієнт",
                "label": "Видача",
                "color": "emerald",
                "status": status,
                "itemsSummary": items_summary,
                "itemsCount": items_count,
                "warehouseZone": "Зона A · Стелаж 3",  # TODO: брати з бази
            })
        
        # ✅ Return Cards (Повернення) - using RentalHub DB
        return_result = db.execute(text("""
            SELECT 
                rc.id, rc.order_number, rc.status, rc.items_returned,
                o.customer_name, o.rental_end_date
            FROM return_cards rc
            JOIN orders o ON rc.order_id = o.order_id
            WHERE o.rental_end_date >= :start AND o.rental_end_date <= :end
            ORDER BY o.rental_end_date
        """), {"start": start.date(), "end": end.date()})
        
        for row in return_result:
            card_id, order_number, status, items_json, customer_name, return_date = row
            
            # Parse items JSON
            items = []
            if items_json:
                try:
                    items = json.loads(items_json) if isinstance(items_json, str) else items_json
                except:
                    items = []
            
            items_count = len(items) if items else 0
            
            categories = set()
            for item in items:
                name = item.get('name', '').lower() if isinstance(item, dict) else ''
                if 'ваза' in name or 'свічник' in name:
                    categories.add('Вази + свічники')
                elif 'посуд' in name:
                    categories.add('посуд')
                elif 'текстиль' in name:
                    categories.add('текстиль')
            
            items_summary = ', '.join(categories) if categories else 'Реквізит'
            
            events.append({
                "id": card_id,
                "order_id": order_number,
                "type": "return",
                "time": return_date.strftime("%H:%M") if return_date else "15:00",
                "date": return_date.isoformat() if return_date else None,
                "client": customer_name or "Клієнт",
                "label": "Повернення",
                "color": "amber",
                "status": status,
                "itemsSummary": items_summary,
                "itemsCount": items_count,
                "warehouseZone": "Зона B · Мийка",  # TODO: брати з бази
            })
        
        # Сортувати по часу
        events.sort(key=lambda x: (x.get('date', ''), x.get('time', '')))
        
        return {
            "from_date": from_date,
            "to_date": to_date,
            "view": view,
            "events": events,
            "total_issues": len([e for e in events if e['type'] == 'issue']),
            "total_returns": len([e for e in events if e['type'] == 'return'])
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка завантаження календаря: {str(e)}"
        )


@router.get("/zones")
async def warehouse_zones(db: Session = Depends(get_rh_db)):  # ✅ MIGRATED
    """
    Список зон складу
    ✅ MIGRATED: Using RentalHub DB (static data, no DB query needed)
    """
    # TODO: Створити таблицю warehouse_zones
    # Поки повертаємо мок
    return [
        {"id": "A", "name": "Зона A", "type": "storage", "description": "Меблі та великогабарит"},
        {"id": "B", "name": "Зона B", "type": "washing", "description": "Мийка та чищення"},
        {"id": "C", "name": "Зона C", "type": "packing", "description": "Комплектація та пакування"},
        {"id": "D", "name": "Зона D", "type": "storage", "description": "Текстиль"},
    ]


@router.put("/calendar/{card_id}/move")
async def move_calendar_event(
    card_id: str,
    move_data: dict,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Перемістити подію в календарі (drag & drop)
    Оновлює дату/час видачі або повернення
    ✅ MIGRATED: Using RentalHub DB (issue_cards, return_cards, orders)
    """
    try:
        card_type = move_data.get('type')  # 'issue' або 'return'
        new_date = move_data.get('date')
        new_time = move_data.get('time')
        
        if card_type == 'issue':
            # ✅ Find issue card
            result = db.execute(text("""
                SELECT order_id FROM issue_cards WHERE id = :card_id
            """), {"card_id": card_id})
            card_row = result.fetchone()
            
            if not card_row:
                raise HTTPException(status_code=404, detail="Issue card не знайдено")
            
            order_id = card_row[0]
            
            # ✅ Update order date
            if new_date:
                new_datetime = datetime.fromisoformat(f"{new_date}T{new_time or '10:00:00'}")
                db.execute(text("""
                    UPDATE orders SET rental_start_date = :new_date WHERE order_id = :order_id
                """), {"new_date": new_datetime, "order_id": order_id})
                
        elif card_type == 'return':
            # ✅ Find return card
            result = db.execute(text("""
                SELECT order_id FROM return_cards WHERE id = :card_id
            """), {"card_id": card_id})
            card_row = result.fetchone()
            
            if not card_row:
                raise HTTPException(status_code=404, detail="Return card не знайдено")
            
            order_id = card_row[0]
            
            # ✅ Update order return date
            if new_date:
                new_datetime = datetime.fromisoformat(f"{new_date}T{new_time or '15:00:00'}")
                db.execute(text("""
                    UPDATE orders SET rental_end_date = :new_date WHERE order_id = :order_id
                """), {"new_date": new_datetime, "order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Подію перенесено",
            "card_id": card_id,
            "new_date": new_date,
            "new_time": new_time
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка переміщення події: {str(e)}"
        )


# ============================================================
# PACKING CABINET (Кабінет комплектації)
# ============================================================

@router.get("/packing-orders")
async def get_packing_orders(
    status: Optional[str] = None,
    zone: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Отримати список замовлень в комплектації
    Статуси: progress (preparation), ready (готово до видачі)
    ✅ MIGRATED: Using RentalHub DB (issue_cards + orders)
    """
    try:
        # ✅ Build SQL query dynamically
        sql_query = """
            SELECT 
                ic.id, ic.order_number, ic.status, ic.items, ic.prepared_by, ic.preparation_notes,
                o.order_id, o.customer_name, o.rental_start_date, o.rental_end_date
            FROM issue_cards ic
            JOIN orders o ON ic.order_id = o.order_id
            WHERE ic.status IN ('preparation', 'ready')
        """
        
        params = {}
        
        # Фільтр по статусу
        if status:
            if status == 'progress':
                sql_query += " AND ic.status = 'preparation'"
            elif status == 'ready':
                sql_query += " AND ic.status = 'ready'"
        
        # Пошук
        if search:
            sql_query += """ AND (
                ic.id LIKE :search OR
                ic.order_number LIKE :search OR
                CAST(o.order_id AS CHAR) LIKE :search OR
                o.customer_name LIKE :search OR
                ic.prepared_by LIKE :search
            )"""
            params['search'] = f"%{search}%"
        
        sql_query += " ORDER BY o.rental_start_date ASC"
        
        result = db.execute(text(sql_query), params)
        
        packing_orders = []
        for row in result:
            (card_id, order_number, card_status, items_json, prepared_by, prep_notes,
             order_id, customer_name, rent_date, return_date) = row
            
            # Parse items JSON
            items = []
            if items_json:
                try:
                    items = json.loads(items_json) if isinstance(items_json, str) else items_json
                except:
                    items = []
            
            items_count = sum(item.get('quantity', 0) for item in items) if items else 0
            sku_count = len(items) if items else 0
            
            # Розрахувати прогрес комплектації
            if card_status == 'ready':
                progress_pack = 100
            else:
                ready_items = [i for i in items if i.get('status') in ['ready', 'prepared']] if items else []
                progress_pack = int((len(ready_items) / len(items) * 100)) if items else 0
            
            warehouse_zone = "Зона C · Комплектація"
            manager = prepared_by or "Не вказано"
            if isinstance(manager, str) and len(manager) > 50:
                manager = "Менеджер"
            
            packing_orders.append({
                "id": card_id,
                "order_id": str(order_id),
                "client": customer_name or "Клієнт",
                "eventDate": rent_date.strftime("%Y-%m-%d") if rent_date else None,
                "issueTime": rent_date.strftime("%H:%M") if rent_date else "10:00",
                "returnTime": f"{return_date.strftime('%d.%m')} · до {return_date.strftime('%H:%M')}" if return_date else "Не вказано",
                "manager": manager,
                "status": "ready" if card_status == "ready" else "progress",
                "itemsCount": items_count,
                "skuCount": sku_count,
                "progressPack": progress_pack,
                "warehouseZone": warehouse_zone,
                "notes": prep_notes or "Без нотаток"
            })
        
        return packing_orders
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка завантаження замовлень: {str(e)}"
        )


@router.get("/packing-orders/{order_id}")
async def get_packing_order_details(
    order_id: str,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Деталі замовлення в комплектації
    ✅ MIGRATED: Using RentalHub DB (issue_cards + orders)
    """
    try:
        # ✅ Find issue card with order details
        result = db.execute(text("""
            SELECT 
                ic.id, ic.order_number, ic.status, ic.items, ic.prepared_by, ic.preparation_notes,
                o.order_id, o.customer_name, o.rental_start_date, o.rental_end_date
            FROM issue_cards ic
            JOIN orders o ON ic.order_id = o.order_id
            WHERE ic.id = :order_id
        """), {"order_id": order_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Issue card не знайдено")
        
        (card_id, order_number, card_status, items_json, prepared_by, prep_notes,
         order_db_id, customer_name, rent_date, return_date) = row
        
        # Parse items JSON
        items = []
        if items_json:
            try:
                items = json.loads(items_json) if isinstance(items_json, str) else items_json
            except:
                items = []
        
        items_count = sum(item.get('quantity', 0) for item in items) if items else 0
        sku_count = len(items) if items else 0
        
        # Прогрес
        if card_status == 'ready':
            progress_pack = 100
        else:
            ready_items = [i for i in items if i.get('status') in ['ready', 'prepared']] if items else []
            progress_pack = int((len(ready_items) / len(items) * 100)) if items else 0
        
        warehouse_zone = "Зона C · Комплектація"
        manager = prepared_by or "Не вказано"
        
        return {
            "id": card_id,
            "order_id": str(order_db_id),
            "client": customer_name or "Клієнт",
            "eventDate": rent_date.strftime("%Y-%m-%d") if rent_date else None,
            "issueTime": rent_date.strftime("%H:%M") if rent_date else "10:00",
            "returnTime": f"{return_date.strftime('%d.%m · до %H:%M')}" if return_date else "Не вказано",
            "manager": manager,
            "status": "ready" if card_status == "ready" else "progress",
            "itemsCount": items_count,
            "skuCount": sku_count,
            "progressPack": progress_pack,
            "warehouseZone": warehouse_zone,
            "notes": prep_notes or "Без нотаток",
            "items": items or []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка завантаження деталей: {str(e)}"
        )


@router.put("/packing-orders/{order_id}/progress")
async def update_packing_progress(
    order_id: str,
    progress_data: dict,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Оновити прогрес комплектації
    Body: {"progressPack": 65, "notes": "..."}
    ✅ MIGRATED: Using RentalHub DB (issue_cards)
    """
    try:
        # ✅ Check if card exists
        result = db.execute(text("""
            SELECT id FROM issue_cards WHERE id = :order_id
        """), {"order_id": order_id})
        
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Issue card не знайдено")
        
        # ✅ Update notes
        if 'notes' in progress_data:
            db.execute(text("""
                UPDATE issue_cards 
                SET preparation_notes = :notes, updated_at = NOW()
                WHERE id = :order_id
            """), {"notes": progress_data['notes'], "order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Прогрес оновлено",
            "order_id": order_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка оновлення прогресу: {str(e)}"
        )


@router.put("/packing-orders/{order_id}/mark-ready")
async def mark_packing_ready(
    order_id: str,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Позначити замовлення як готове до видачі
    ✅ MIGRATED: Using RentalHub DB (issue_cards + orders)
    """
    try:
        # ✅ Get issue card and order_id
        result = db.execute(text("""
            SELECT order_id FROM issue_cards WHERE id = :order_id
        """), {"order_id": order_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Issue card не знайдено")
        
        db_order_id = row[0]
        
        # ✅ Update issue card status
        db.execute(text("""
            UPDATE issue_cards 
            SET status = 'ready', prepared_at = NOW(), updated_at = NOW()
            WHERE id = :order_id
        """), {"order_id": order_id})
        
        # ✅ Update order status
        db.execute(text("""
            UPDATE orders 
            SET status = 'ready_for_issue'
            WHERE order_id = :order_id
        """), {"order_id": db_order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Замовлення готово до видачі",
            "order_id": order_id,
            "status": "ready"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка позначення готовності: {str(e)}"
        )


@router.post("/packing-orders/{order_id}/return-checklist")
async def create_return_checklist(
    order_id: str,
    checklist_data: dict,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Створити чекліст прийому повернення
    ✅ MIGRATED: Using RentalHub DB (issue_cards + return_cards)
    """
    try:
        # ✅ Check if issue card exists
        result = db.execute(text("""
            SELECT id FROM issue_cards WHERE id = :order_id
        """), {"order_id": order_id})
        
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Issue card не знайдено")
        
        # ✅ Find return card
        result = db.execute(text("""
            SELECT id, return_notes FROM return_cards 
            WHERE issue_card_id = :issue_card_id
        """), {"issue_card_id": order_id})
        
        row = result.fetchone()
        return_card_id = None
        
        if row:
            return_card_id, current_notes = row
            # ✅ Update notes
            new_notes = (current_notes or "") + "\n\n" + checklist_data.get('notes', '')
            db.execute(text("""
                UPDATE return_cards 
                SET return_notes = :notes, updated_at = NOW()
                WHERE id = :return_card_id
            """), {"notes": new_notes, "return_card_id": return_card_id})
            db.commit()
        
        return {
            "success": True,
            "message": "Чекліст створено",
            "return_card_id": return_card_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка створення чекліста: {str(e)}"
        )
