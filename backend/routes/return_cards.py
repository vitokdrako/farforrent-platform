"""
Return Cards routes - Картки повернення

⚠️  DEPRECATED (2026-02): Цей роутер та таблиця `return_cards` є legacy.
    Сучасний потік повернень знаходиться у:
      - routes/return_versions.py    (партіальні повернення з версіями)
      - routes/partial_returns.py    (обробка пошкоджень/списань)

    Ендпойнти `return_cards` залишені тільки для:
      1) Зворотньої сумісності зі старим Admin UI (`archive.py` дивиться сюди)
      2) Читання історичних записів (картки повернень створені до 2025-Q4)
    Не використовуйте у нових фічах. Перед видаленням потрібно мігрувати
    дані `return_cards` → `partial_return_versions`.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid
import json

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/return-cards", tags=["return-cards"])

# Pydantic Models
class ReturnItem(BaseModel):
    sku: str
    name: str
    quantity_expected: int
    quantity_returned: int
    condition: str = "ok"  # ok, dirty, damaged, missing
    photos: List[str] = []
    notes: Optional[str] = None

class ReturnCardCreate(BaseModel):
    order_id: int
    order_number: str
    issue_card_id: str
    items_expected: List[dict]

class ReturnCardUpdate(BaseModel):
    status: Optional[str] = None
    items_returned: Optional[List[dict]] = None
    return_notes: Optional[str] = None
    received_by: Optional[str] = None
    checked_by: Optional[str] = None
    items_ok: Optional[int] = None
    items_dirty: Optional[int] = None
    items_damaged: Optional[int] = None
    items_missing: Optional[int] = None

# Helper to parse return card
def parse_return_card(row, db=None):
    """Parse return card row"""
    # Індекси полів з SELECT * (0-based):
    # 0: id, 1: order_id, 2: order_number, 3: issue_card_id, 4: status
    # 5: received_by, 6: received_by_id, 7: checked_by, 8: checked_by_id
    # 9: items_expected, 10: items_returned, 11: total_items_expected
    # 12: total_items_returned, 13: items_ok, 14: items_dirty, 15: items_damaged
    # 16: items_missing, 17: cleaning_fee, 18: late_fee, 19: return_notes
    # 20: returned_at, 21: checked_at, 22: created_at, 23: updated_at
    # 24: created_by_id, 25: items, 26: receivers, 27: notes, 28: fees
    
    items_expected = []
    items_returned = []
    
    # Спочатку пробуємо items_expected (індекс 9), якщо порожньо - items (індекс 25)
    raw_items = row[9] or row[25]  # items_expected або items
    if raw_items:
        try:
            items_expected = json.loads(raw_items) if isinstance(raw_items, str) else raw_items
        except:
            pass
    
    if row[10]:  # items_returned
        try:
            items_returned = json.loads(row[10]) if isinstance(row[10], str) else row[10]
        except:
            pass
    
    # ✅ Збагатити items даними про location з products
    if items_expected and db:
        for item in items_expected:
            pid = item.get('id') or item.get('product_id')
            if pid:
                try:
                    result = db.execute(text("""
                        SELECT zone FROM products WHERE product_id = :pid
                    """), {"pid": pid})
                    row_loc = result.fetchone()
                    if row_loc and row_loc[0]:
                        item['location'] = {'zone': row_loc[0]}
                except Exception as e:
                    print(f"Error getting location for {pid}: {e}")
    
    return {
        "id": row[0],
        "order_id": row[1],
        "order_number": row[2],
        "issue_card_id": row[3],
        "status": row[4],
        "received_by": row[5],
        "checked_by": row[7],
        "items_expected": items_expected,
        "items_returned": items_returned,
        "total_items_expected": row[11],
        "total_items_returned": row[12],
        "items_ok": row[13],
        "items_dirty": row[14],
        "items_damaged": row[15],
        "items_missing": row[16],
        "cleaning_fee": float(row[17]) if row[17] else 0.0,
        "late_fee": float(row[18]) if row[18] else 0.0,
        "return_notes": row[19],
        "returned_at": row[20].isoformat() if row[20] else None,
        "checked_at": row[21].isoformat() if row[21] else None,
        "created_at": row[22].isoformat() if row[22] else None,
        "updated_at": row[23].isoformat() if row[23] else None
    }

@router.get("")
async def get_return_cards(
    status: Optional[str] = None,
    order_id: Optional[int] = None,
    db: Session = Depends(get_rh_db)
):
    """Get all return cards"""
    sql = "SELECT * FROM return_cards WHERE 1=1"
    params = {}
    
    if status:
        sql += " AND status = :status"
        params['status'] = status
    if order_id:
        sql += " AND order_id = :order_id"
        params['order_id'] = order_id
    
    sql += " ORDER BY created_at DESC"
    
    result = db.execute(text(sql), params)
    return [parse_return_card(row, db) for row in result]

@router.get("/{card_id}")
async def get_return_card(card_id: str, db: Session = Depends(get_rh_db)):
    """Get single return card"""
    result = db.execute(text("SELECT * FROM return_cards WHERE id = :id"), {"id": card_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Return card not found")
    
    return parse_return_card(row, db)

@router.post("")
async def create_return_card(
    card: ReturnCardCreate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """Create new return card"""
    card_id = f"RETURN-{uuid.uuid4().hex[:8].upper()}"
    items_json = json.dumps(card.items_expected)
    
    db.execute(text("""
        INSERT INTO return_cards (
            id, order_id, order_number, issue_card_id, status, 
            items_expected, total_items_expected, 
            created_by_id, created_at, updated_at
        ) VALUES (
            :id, :order_id, :order_number, :issue_card_id, 'pending',
            :items, :total, :created_by_id, NOW(), NOW()
        )
    """), {
        "id": card_id,
        "order_id": card.order_id,
        "order_number": card.order_number,
        "issue_card_id": card.issue_card_id,
        "items": items_json,
        "total": len(card.items_expected),
        "created_by_id": current_user["id"]
    })
    
    db.commit()
    return {"id": card_id, "message": "Return card created"}

@router.put("/{card_id}")
async def update_return_card(
    card_id: str,
    updates: ReturnCardUpdate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """Update return card"""
    result = db.execute(text("SELECT id, order_id, status FROM return_cards WHERE id = :id"), {"id": card_id})
    card_row = result.fetchone()
    if not card_row:
        raise HTTPException(status_code=404, detail="Return card not found")
    
    order_id = card_row[1]
    old_status = card_row[2]
    user_id = current_user.get("id")
    user_name = f"{current_user.get('firstname', '')} {current_user.get('lastname', '')}".strip() or current_user.get('email', 'System')
    
    set_clauses = []
    params = {"id": card_id}
    
    if updates.status is not None:
        set_clauses.append("status = :status")
        params['status'] = updates.status
        
        # Track user based on status
        if updates.status == 'received':
            # Товар прийнято від клієнта
            set_clauses.append("received_by_id = :received_by_id")
            set_clauses.append("returned_at = NOW()")
            params['received_by_id'] = current_user["id"]
        elif updates.status == 'checked':
            # Товар перевірено на пошкодження
            set_clauses.append("checked_by_id = :checked_by_id")
            set_clauses.append("checked_at = NOW()")
            params['checked_by_id'] = current_user["id"]
    
    if updates.items_returned is not None:
        set_clauses.append("items_returned = :items")
        params['items'] = json.dumps(updates.items_returned)
    if updates.return_notes is not None:
        set_clauses.append("return_notes = :notes")
        params['notes'] = updates.return_notes
    if updates.received_by is not None:
        set_clauses.append("received_by = :received_by")
        params['received_by'] = updates.received_by
    if updates.checked_by is not None:
        set_clauses.append("checked_by = :checked_by")
        params['checked_by'] = updates.checked_by
    if updates.items_ok is not None:
        set_clauses.append("items_ok = :items_ok")
        params['items_ok'] = updates.items_ok
    if updates.items_dirty is not None:
        set_clauses.append("items_dirty = :items_dirty")
        params['items_dirty'] = updates.items_dirty
    if updates.items_damaged is not None:
        set_clauses.append("items_damaged = :items_damaged")
        params['items_damaged'] = updates.items_damaged
    if updates.items_missing is not None:
        set_clauses.append("items_missing = :items_missing")
        params['items_missing'] = updates.items_missing
    
    if set_clauses:
        set_clauses.append("updated_at = NOW()")
        sql = f"UPDATE return_cards SET {', '.join(set_clauses)} WHERE id = :id"
        db.execute(text(sql), params)
        db.commit()
    
    # ✅ ЛОГУВАННЯ В ORDER_LIFECYCLE при зміні статусу
    if updates.status is not None and updates.status != old_status and order_id:
        lifecycle_stages = {
            'received': ('return_received', f'↩️ Товар прийнято від клієнта'),
            'checked': ('return_checked', f'🔍 Товар перевірено'),
            'completed': ('return_completed', f'✅ Повернення завершено'),
        }
        
        if updates.status in lifecycle_stages:
            stage, notes = lifecycle_stages[updates.status]
            db.execute(text("""
                INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_at, created_by_id, created_by_name)
                VALUES (:order_id, :stage, :notes, :created_by, NOW(), :user_id, :user_name)
            """), {
                "order_id": order_id,
                "stage": stage,
                "notes": notes,
                "created_by": current_user.get('email', 'System'),
                "user_id": user_id,
                "user_name": user_name
            })
            db.commit()
            print(f"[Lifecycle] Order {order_id}: {stage} by {user_name}")
    
    # Автоматично створити damage case якщо є брудні або пошкоджені товари
    print(f"[DEBUG] Checking damage case creation: status={updates.status}, items_returned={len(updates.items_returned) if updates.items_returned else 0}")
    if updates.status == 'checked' and updates.items_returned:
        print(f"[DEBUG] Creating damage cases for return card {card_id}")
        await _create_damage_cases_from_return(card_id, updates.items_returned, current_user, db)
    else:
        print(f"[DEBUG] Skipping damage case creation: status={updates.status}, has_items={bool(updates.items_returned)}")
    
    return {"message": "Return card updated"}

@router.post("/{card_id}/complete")
async def complete_return_card(
    card_id: str,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """Mark return card as completed"""
    db.execute(text("""
        UPDATE return_cards 
        SET status = 'resolved',
            checked_by_id = :checked_by_id,
            checked_at = NOW(), 
            updated_at = NOW()
        WHERE id = :id
    """), {"id": card_id, "checked_by_id": current_user["id"]})
    
    db.commit()
    return {"message": "Return card completed"}

@router.delete("/{card_id}")
async def delete_return_card(card_id: str, db: Session = Depends(get_rh_db)):
    """Delete return card"""
    result = db.execute(text("DELETE FROM return_cards WHERE id = :id"), {"id": card_id})
    db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Return card not found")
    
    return {"message": "Return card deleted"}

@router.get("/by-order/{order_id}")
async def get_return_card_by_order(order_id: int, db: Session = Depends(get_rh_db)):
    """Get return card by order ID"""
    result = db.execute(text("""
        SELECT * FROM return_cards WHERE order_id = :order_id ORDER BY created_at DESC LIMIT 1
    """), {"order_id": order_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Return card not found for this order")
    
    return parse_return_card(row)



async def _create_damage_cases_from_return(card_id: str, items_returned: List[dict], current_user: dict, db: Session):
    """
    Створити damage cases для брудних та пошкоджених товарів
    """
    try:
        # Отримати інформацію про return card
        card_result = db.execute(text("""
            SELECT order_id, order_number FROM return_cards WHERE id = :id
        """), {"id": card_id})
        card = card_result.fetchone()
        
        if not card:
            print(f"⚠ Return card {card_id} not found")
            return
        
        order_id = card[0]
        order_number = card[1]
        
        # Отримати інформацію про клієнта з замовлення
        order_result = db.execute(text("""
            SELECT customer_name, customer_phone, event_name FROM orders WHERE order_id = :order_id
        """), {"order_id": order_id})
        order = order_result.fetchone()
        
        customer_name = order[0] if order else None
        customer_phone = order[1] if order else None
        event_name = order[2] if order else None
        
        created_by = current_user.get('username') or current_user.get('email') or 'Unknown'
        
        # Групувати товари за типом пошкодження
        dirty_items = []
        damaged_items = []
        
        for item in items_returned:
            condition = item.get('condition', 'ok')
            if condition == 'dirty':
                dirty_items.append(item)
            elif condition == 'damaged':
                damaged_items.append(item)
        
        # Створити damage case для брудних товарів
        if dirty_items:
            await _create_single_damage_case(
                db=db,
                order_id=order_id,
                order_number=order_number,
                customer_name=customer_name,
                customer_phone=customer_phone,
                event_name=event_name,
                items=dirty_items,
                source='return',
                severity='minor',
                created_by=created_by,
                notes=f"Брудні товари з повернення {order_number}"
            )
            print(f"✅ Створено damage case для {len(dirty_items)} брудних товарів з return card {card_id}")
        
        # Створити damage case для пошкоджених товарів
        if damaged_items:
            await _create_single_damage_case(
                db=db,
                order_id=order_id,
                order_number=order_number,
                customer_name=customer_name,
                customer_phone=customer_phone,
                event_name=event_name,
                items=damaged_items,
                source='return',
                severity='major',
                created_by=created_by,
                notes=f"Пошкоджені товари з повернення {order_number}"
            )
            print(f"✅ Створено damage case для {len(damaged_items)} пошкоджених товарів з return card {card_id}")
    
    except Exception as e:
        print(f"❌ Помилка створення damage cases з return: {e}")
        # Не викидаємо помилку, щоб не заблокувати update return card


async def _create_single_damage_case(db: Session, order_id: int, order_number: str, 
                                     customer_name: str, customer_phone: str, event_name: str,
                                     items: List[dict], source: str, severity: str, 
                                     created_by: str, notes: str):
    """
    Створити записи пошкоджень в product_damage_history (єдине джерело істини)
    Замість старої системи damages + damage_items
    """
    for item in items:
        sku = item.get('sku', '')
        name = item.get('name', 'Товар')
        qty = item.get('quantity_returned', 1)
        condition = item.get('condition', 'dirty')
        item_notes = item.get('notes', '')
        
        # Отримати product_id та ціну з products
        product_result = db.execute(text("""
            SELECT product_id, name, image_url, rental_price, category_name FROM products WHERE sku = :sku
        """), {"sku": sku})
        product = product_result.fetchone()
        
        if product:
            product_id = product[0]
            product_name = product[1] or name
            image = product[2]
            base_value = float(product[3]) if product[3] else 0.0
            category_name = product[4] or ''
            
            # Оцінити вартість пошкодження
            if condition == 'dirty':
                estimate_value = base_value * 0.1
                processing_type = 'wash'
            else:
                estimate_value = base_value * 0.5
                processing_type = 'restoration'
            
            pdh_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO product_damage_history (
                    id, product_id, sku, product_name, category,
                    order_id, order_number, stage, damage_type, damage_code,
                    severity, fee, fee_per_item, qty, processed_qty,
                    base_value, estimate_value, photo_url, note,
                    processing_type, processing_status,
                    source, created_by, created_at, updated_at
                ) VALUES (
                    :id, :product_id, :sku, :name, :category,
                    :order_id, :order_number, 'return', :damage_type, :damage_code,
                    :severity, :estimate_value, :estimate_value, :qty, 0,
                    :base_value, :estimate_value, :image, :note,
                    :processing_type, 'pending',
                    'return', :created_by, NOW(), NOW()
                )
            """), {
                "id": pdh_id,
                "product_id": product_id,
                "sku": sku,
                "name": product_name,
                "category": category_name,
                "order_id": order_id,
                "order_number": order_number,
                "damage_type": 'Забруднення' if condition == 'dirty' else 'Пошкодження',
                "damage_code": condition,
                "severity": severity,
                "estimate_value": estimate_value,
                "base_value": base_value,
                "image": image,
                "note": item_notes or notes,
                "qty": qty,
                "processing_type": processing_type,
                "created_by": created_by
            })
            
            # Заморозити товар
            db.execute(text("""
                UPDATE products SET frozen_quantity = COALESCE(frozen_quantity, 0) + :qty
                WHERE product_id = :pid
            """), {"qty": qty, "pid": product_id})
    
    db.commit()
