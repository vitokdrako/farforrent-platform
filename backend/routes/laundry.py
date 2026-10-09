"""
Laundry Management Routes - Управління Хімчисткою Текстилю
Відстеження текстилю відправленого в хімчистку
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date
import uuid
import json

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/laundry", tags=["laundry"])

# ==================== Pydantic Models ====================

class LaundryItemCreate(BaseModel):
    product_id: int
    product_name: str
    sku: str
    category: str
    quantity: int
    condition_before: Optional[str] = "dirty"
    photo_before: Optional[str] = None
    notes: Optional[str] = None

class LaundryBatchCreate(BaseModel):
    laundry_company: str
    expected_return_date: str
    items: List[LaundryItemCreate]
    cost: Optional[float] = None
    notes: Optional[str] = None

class LaundryBatchUpdate(BaseModel):
    status: Optional[str] = None
    actual_return_date: Optional[str] = None
    received_by_id: Optional[int] = None
    received_by_name: Optional[str] = None
    notes: Optional[str] = None

class LaundryItemReturn(BaseModel):
    item_id: str
    returned_quantity: int
    condition_after: str = "clean"
    photo_after: Optional[str] = None
    notes: Optional[str] = None

# ==================== Helper Functions ====================

def parse_batch(row):
    """Parse laundry batch row"""
    return {
        "id": row[0],
        "batch_number": row[1],
        "status": row[2],
        "laundry_company": row[3],
        "sent_date": row[4].isoformat() if row[4] else None,
        "expected_return_date": row[5].isoformat() if row[5] else None,
        "actual_return_date": row[6].isoformat() if row[6] else None,
        "total_items": row[7],
        "returned_items": row[8],
        "cost": float(row[9]) if row[9] else 0.0,
        "notes": row[10],
        "sent_by_id": row[11],
        "sent_by_name": row[12],
        "received_by_id": row[13],
        "received_by_name": row[14],
        "created_at": row[15].isoformat() if row[15] else None,
        "updated_at": row[16].isoformat() if row[16] else None
    }

def parse_item(row):
    """Parse laundry item row"""
    return {
        "id": row[0],
        "batch_id": row[1],
        "product_id": row[2],
        "product_name": row[3],
        "sku": row[4],
        "category": row[5],
        "quantity": row[6],
        "returned_quantity": row[7] if row[7] else 0,
        "condition_before": row[8],
        "condition_after": row[9],
        "photo_before": row[10],
        "photo_after": row[11],
        "notes": row[12],
        "created_at": row[13].isoformat() if row[13] else None
    }

# ==================== Queue Endpoints ====================

@router.get("/queue")
async def get_laundry_queue(type: str = "laundry", db: Session = Depends(get_rh_db)):
    """
    Отримати чергу товарів для формування партії прання або хімчистки.
    Це товари з processing_type='wash' або 'laundry' які ще не додані в партію.
    
    Query params:
        type: 'wash' або 'laundry' (default: 'laundry')
    """
    processing_type = type if type in ('wash', 'laundry') else 'laundry'
    
    result = db.execute(text("""
        SELECT 
            pdh.id,
            pdh.product_id,
            pdh.product_name,
            pdh.sku,
            pdh.category,
            pdh.order_id,
            pdh.order_number,
            COALESCE(pdh.qty, 1) as qty,
            COALESCE(pdh.processed_qty, 0) as processed_qty,
            pdh.damage_type,
            pdh.note,
            pdh.created_at,
            pdh.laundry_batch_id,
            p.image_url as product_image
        FROM product_damage_history pdh
        LEFT JOIN products p ON pdh.product_id = p.product_id
        WHERE pdh.processing_type = :processing_type
        AND (pdh.laundry_batch_id IS NULL OR pdh.laundry_batch_id = '')
        AND (COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) > 0
        ORDER BY pdh.created_at ASC
    """), {"processing_type": processing_type})
    
    items = []
    for row in result:
        qty = row[7] or 1
        processed = row[8] or 0
        items.append({
            "id": row[0],
            "product_id": row[1],
            "product_name": row[2],
            "sku": row[3],
            "category": row[4],
            "order_id": row[5],
            "order_number": row[6],
            "qty": qty,
            "processed_qty": processed,
            "remaining_qty": qty - processed,
            "damage_type": row[9],
            "note": row[10],
            "created_at": row[11].isoformat() if row[11] else None,
            "laundry_batch_id": row[12],
            "product_image": row[13],
            "condition_before": "dirty"
        })
    
    return {"items": items, "total": len(items)}


@router.post("/queue/add-to-batch")
async def add_queue_items_to_batch(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Додати товари з черги в партію.
    
    Body:
        - item_ids: list[str] - ID записів з product_damage_history
        - batch_id: str (optional) - ID існуючої партії, або створити нову
        - laundry_company: str - назва хімчистки/пральні (для нової партії)
        - complexity: str - складність обробки ('light', 'normal', 'heavy')
        - expected_return_date: str (optional) - очікувана дата повернення
        - batch_type: str - тип партії ('wash' або 'laundry')
    """
    item_ids = data.get("item_ids", [])
    batch_id = data.get("batch_id")
    laundry_company = data.get("laundry_company", "Хімчистка")
    complexity = data.get("complexity", "normal")  # light, normal, heavy
    expected_return_date = data.get("expected_return_date")
    batch_type = data.get("batch_type", "laundry")  # wash or laundry
    
    # Отримати поточного користувача (якщо є)
    created_by = data.get("created_by", "system")
    
    if not item_ids:
        raise HTTPException(status_code=400, detail="Не вказано товари")
    
    try:
        # Якщо партія не вказана - створити нову
        if not batch_id:
            prefix = "WB" if batch_type == "wash" else "LB"
            batch_id = f"BATCH-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            batch_number = f"{prefix}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            
            db.execute(text("""
                INSERT INTO laundry_batches (
                    id, batch_number, laundry_company, status, sent_date, 
                    expected_return_date, total_items, returned_items, 
                    complexity, batch_type, created_by, created_at, updated_at
                ) VALUES (
                    :id, :batch_number, :company, 'sent', NOW(), :return_date,
                    0, 0, :complexity, :batch_type, :created_by, NOW(), NOW()
                )
            """), {
                "id": batch_id,
                "batch_number": batch_number,
                "company": laundry_company,
                "return_date": expected_return_date,
                "complexity": complexity,
                "batch_type": batch_type,
                "created_by": created_by
            })
        
        added_count = 0
        total_qty = 0
        
        for item_id in item_ids:
            # Отримати дані товару з черги
            item_row = db.execute(text("""
                SELECT pdh.product_id, pdh.product_name, pdh.sku, pdh.category,
                       COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0) as remaining,
                       pdh.note, p.image_url
                FROM product_damage_history pdh
                LEFT JOIN products p ON pdh.product_id = p.product_id
                WHERE pdh.id = :id
            """), {"id": item_id}).fetchone()
            
            if not item_row:
                continue
            
            remaining_qty = item_row[4] or 1
            
            # Додати в laundry_items
            laundry_item_id = f"ITEM-{datetime.now().strftime('%Y%m%d%H%M%S')}-{added_count}"
            db.execute(text("""
                INSERT INTO laundry_items (
                    id, batch_id, product_id, product_name, sku, category,
                    quantity, returned_quantity, condition_before, notes, created_at
                ) VALUES (
                    :id, :batch_id, :product_id, :name, :sku, :category,
                    :qty, 0, 'dirty', :notes, NOW()
                )
            """), {
                "id": laundry_item_id,
                "batch_id": batch_id,
                "product_id": item_row[0],
                "name": item_row[1],
                "sku": item_row[2],
                "category": item_row[3],
                "qty": remaining_qty,
                "notes": item_row[5]
            })
            
            # Оновити damage_history - вказати партію
            db.execute(text("""
                UPDATE product_damage_history 
                SET laundry_batch_id = :batch_id
                WHERE id = :id
            """), {"batch_id": batch_id, "id": item_id})
            
            added_count += 1
            total_qty += remaining_qty
        
        # Оновити кількість в партії
        db.execute(text("""
            UPDATE laundry_batches 
            SET total_items = total_items + :qty,
                updated_at = NOW()
            WHERE id = :batch_id
        """), {"batch_id": batch_id, "qty": total_qty})
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Додано {added_count} позицій ({total_qty} шт.) в партію",
            "batch_id": batch_id,
            "added_count": added_count,
            "total_qty": total_qty
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


# ==================== Batch Endpoints ====================

@router.get("/batches")
async def get_laundry_batches(
    status: Optional[str] = None,
    laundry_company: Optional[str] = None,
    type: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати список партій
    Status: sent, partial_return, returned, completed
    Type: wash, laundry (optional filter by batch_type)
    """
    sql = "SELECT * FROM laundry_batches WHERE 1=1"
    params = {}
    
    if status:
        sql += " AND status = :status"
        params['status'] = status
    if laundry_company:
        sql += " AND laundry_company = :company"
        params['company'] = laundry_company
    if type and type in ('wash', 'laundry'):
        sql += " AND COALESCE(batch_type, 'laundry') = :batch_type"
        params['batch_type'] = type
    
    sql += " ORDER BY sent_date DESC"
    
    result = db.execute(text(sql), params)
    batches = [parse_batch(row) for row in result]
    
    # Додати інформацію про товари для кожної партії з фото
    for batch in batches:
        items_result = db.execute(
            text("""
                SELECT li.*, p.image_url as product_image
                FROM laundry_items li
                LEFT JOIN products p ON li.product_id = p.product_id
                WHERE li.batch_id = :batch_id
            """),
            {"batch_id": batch["id"]}
        )
        items = []
        for r in items_result:
            item = parse_item(r)
            if len(r) > 14:
                item["product_image"] = r[14]
            items.append(item)
        batch["items"] = items
    
    return batches

@router.get("/batches/{batch_id}")
async def get_laundry_batch(
    batch_id: str,
    db: Session = Depends(get_rh_db)
):
    """Отримати деталі партії"""
    result = db.execute(
        text("SELECT * FROM laundry_batches WHERE id = :id"),
        {"id": batch_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Партію не знайдено")
    
    batch = parse_batch(row)
    
    # Отримати товари в партії з фото
    items_result = db.execute(
        text("""
            SELECT li.*, p.image_url as product_image
            FROM laundry_items li
            LEFT JOIN products p ON li.product_id = p.product_id
            WHERE li.batch_id = :batch_id
        """),
        {"batch_id": batch_id}
    )
    
    items = []
    for r in items_result:
        item = parse_item(r)
        # Додаємо product_image якщо є
        if len(r) > 14:
            item["product_image"] = r[14]
        items.append(item)
    
    batch["items"] = items
    
    return batch

@router.post("/batches")
async def create_laundry_batch(
    batch_data: LaundryBatchCreate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Створити нову партію відправлення в хімчистку
    Автоматично "заморожує" кількість товарів на складі
    """
    try:
        batch_id = str(uuid.uuid4())
        
        # Генерувати номер партії
        result = db.execute(text("SELECT COUNT(*) as count FROM laundry_batches"))
        count = result.fetchone()[0]
        batch_number = f"LAUNDRY-{count + 1:05d}"
        
        total_items = sum(item.quantity for item in batch_data.items)
        
        # Створити партію
        db.execute(text("""
            INSERT INTO laundry_batches (
                id, batch_number, status, laundry_company,
                sent_date, expected_return_date, total_items, returned_items,
                cost, notes, sent_by_id, sent_by_name, created_at, updated_at
            ) VALUES (
                :id, :batch_number, 'sent', :company,
                :sent_date, :expected_date, :total_items, 0,
                :cost, :notes, :user_id, :user_name, NOW(), NOW()
            )
        """), {
            "id": batch_id,
            "batch_number": batch_number,
            "company": batch_data.laundry_company,
            "sent_date": date.today(),
            "expected_date": batch_data.expected_return_date,
            "total_items": total_items,
            "cost": batch_data.cost or 0.0,
            "notes": batch_data.notes,
            "user_id": current_user["id"],
            "user_name": current_user["name"]
        })
        
        # Додати товари до партії
        for item in batch_data.items:
            item_id = str(uuid.uuid4())
            
            db.execute(text("""
                INSERT INTO laundry_items (
                    id, batch_id, product_id, product_name, sku, category,
                    quantity, returned_quantity, condition_before, photo_before,
                    notes, created_at
                ) VALUES (
                    :id, :batch_id, :product_id, :product_name, :sku, :category,
                    :quantity, 0, :condition, :photo, :notes, NOW()
                )
            """), {
                "id": item_id,
                "batch_id": batch_id,
                "product_id": item.product_id,
                "product_name": item.product_name,
                "sku": item.sku,
                "category": item.category,
                "quantity": item.quantity,
                "condition": item.condition_before,
                "photo": item.photo_before,
                "notes": item.notes
            })
            
            # "Заморожування" кількості на складі
            # Зменшуємо available_quantity, але не зменшуємо total_quantity
            db.execute(text("""
                UPDATE products 
                SET quantity = GREATEST(0, quantity - :qty)
                WHERE product_id = :product_id
            """), {
                "qty": item.quantity,
                "product_id": item.product_id
            })
            
            # Оновити стан товару в inventory - позначити як "в хімчистці"
            db.execute(text("""
                UPDATE products 
                SET product_state = 'in_laundry', 
                    cleaning_status = 'sent_to_laundry'
                WHERE product_id = :product_id
            """), {"product_id": item.product_id})
        
        db.commit()
        
        return {
            "id": batch_id,
            "batch_number": batch_number,
            "message": f"Партію {batch_number} створено. Відправлено {total_items} од. текстилю."
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка створення партії: {str(e)}")

@router.put("/batches/{batch_id}")
async def update_laundry_batch(
    batch_id: str,
    updates: LaundryBatchUpdate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """Оновити інформацію про партію"""
    result = db.execute(
        text("SELECT id FROM laundry_batches WHERE id = :id"),
        {"id": batch_id}
    )
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Партію не знайдено")
    
    set_clauses = []
    params = {"id": batch_id}
    
    if updates.status is not None:
        set_clauses.append("status = :status")
        params['status'] = updates.status
        
        # Якщо статус змінюється на 'returned', зберігаємо хто прийняв
        if updates.status == 'returned':
            set_clauses.append("received_by_id = :received_by_id")
            set_clauses.append("received_by_name = :received_by_name")
            params['received_by_id'] = current_user["id"]
            params['received_by_name'] = current_user["name"]
    
    if updates.actual_return_date is not None:
        set_clauses.append("actual_return_date = :return_date")
        params['return_date'] = updates.actual_return_date
    if updates.received_by_id is not None:
        set_clauses.append("received_by_id = :received_by_id")
        params['received_by_id'] = updates.received_by_id
    if updates.received_by_name is not None:
        set_clauses.append("received_by_name = :received_by_name")
        params['received_by_name'] = updates.received_by_name
    if updates.notes is not None:
        set_clauses.append("notes = :notes")
        params['notes'] = updates.notes
    
    if set_clauses:
        set_clauses.append("updated_at = NOW()")
        sql = f"UPDATE laundry_batches SET {', '.join(set_clauses)} WHERE id = :id"
        db.execute(text(sql), params)
        db.commit()
    
    return {"message": "Партію оновлено"}

@router.post("/batches/{batch_id}/return-items")
async def return_laundry_items(
    batch_id: str,
    items: List[LaundryItemReturn],
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Прийняти повернення товарів з хімчистки (часткове або повне)
    Автоматично повертає товари на склад
    """
    try:
        # Перевірити чи існує партія
        batch_result = db.execute(
            text("SELECT * FROM laundry_batches WHERE id = :id"),
            {"id": batch_id}
        )
        batch_row = batch_result.fetchone()
        
        if not batch_row:
            raise HTTPException(status_code=404, detail="Партію не знайдено")
        
        batch = parse_batch(batch_row)
        
        total_returned = 0
        
        for item_return in items:
            # Оновити інформацію про повернення товару
            db.execute(text("""
                UPDATE laundry_items
                SET 
                    returned_quantity = returned_quantity + :qty,
                    condition_after = :condition,
                    photo_after = :photo,
                    notes = CONCAT(COALESCE(notes, ''), '\n', COALESCE(:notes, ''))
                WHERE id = :item_id
            """), {
                "item_id": item_return.item_id,
                "qty": item_return.returned_quantity,
                "condition": item_return.condition_after,
                "photo": item_return.photo_after,
                "notes": item_return.notes or ""
            })
            
            # Отримати інформацію про товар
            item_result = db.execute(
                text("SELECT * FROM laundry_items WHERE id = :id"),
                {"id": item_return.item_id}
            )
            item_row = item_result.fetchone()
            item = parse_item(item_row)
            
            # Повернути товар на склад (розморозити)
            db.execute(text("""
                UPDATE products 
                SET frozen_quantity = GREATEST(COALESCE(frozen_quantity, 0) - :qty, 0)
                WHERE product_id = :product_id
            """), {
                "qty": item_return.returned_quantity,
                "product_id": item["product_id"]
            })
            
            # Перевірити чи всі одиниці цього товару повернуті
            new_returned = item["returned_quantity"] + item_return.returned_quantity
            if new_returned >= item["quantity"]:
                # Товар повністю повернуто - оновити стан на "доступний"
                db.execute(text("""
                    UPDATE products 
                    SET product_state = 'available', 
                        cleaning_status = 'clean'
                    WHERE product_id = :product_id
                """), {"product_id": item["product_id"]})
            
            # Оновити product_damage_history якщо прив'язаний
            try:
                # Знайти damage_history запис через laundry_item_id
                pdh_row = db.execute(text("""
                    SELECT id FROM product_damage_history 
                    WHERE laundry_item_id = :lid
                    AND processing_type = 'laundry'
                    LIMIT 1
                """), {"lid": item_return.item_id}).fetchone()
                
                if pdh_row:
                    pdh_id = pdh_row[0]
                    if new_returned >= item["quantity"]:
                        db.execute(text("""
                            UPDATE product_damage_history
                            SET processing_status = 'completed',
                                processing_type = 'returned_to_stock',
                                processed_qty = qty,
                                returned_from_processing_at = NOW()
                            WHERE id = :pid
                        """), {"pid": pdh_id})
                    else:
                        db.execute(text("""
                            UPDATE product_damage_history
                            SET processed_qty = COALESCE(processed_qty, 0) + :rqty
                            WHERE id = :pid
                        """), {"pid": pdh_id, "rqty": item_return.returned_quantity})
            except Exception:
                pass
            
            total_returned += item_return.returned_quantity
        
        # Оновити загальну кількість повернених товарів у партії
        db.execute(text("""
            UPDATE laundry_batches
            SET 
                returned_items = returned_items + :qty,
                status = CASE 
                    WHEN returned_items + :qty >= total_items THEN 'returned'
                    ELSE 'partial_return'
                END,
                received_by_id = :user_id,
                received_by_name = :user_name,
                actual_return_date = CASE 
                    WHEN actual_return_date IS NULL THEN :today
                    ELSE actual_return_date
                END,
                updated_at = NOW()
            WHERE id = :batch_id
        """), {
            "batch_id": batch_id,
            "qty": total_returned,
            "user_id": current_user["id"],
            "user_name": current_user["name"],
            "today": date.today()
        })
        
        db.commit()
        
        return {
            "message": f"Прийнято {total_returned} од. текстилю",
            "returned_items": total_returned,
            "batch_status": "returned" if (batch["returned_items"] + total_returned) >= batch["total_items"] else "partial_return"
        }
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка прийому товарів: {str(e)}")

@router.post("/batches/{batch_id}/complete")
async def complete_laundry_batch(
    batch_id: str,
    db: Session = Depends(get_rh_db)
):
    """Закрити партію (всі товари повернуті та перевірені)"""
    db.execute(text("""
        UPDATE laundry_batches
        SET status = 'completed', updated_at = NOW()
        WHERE id = :id
    """), {"id": batch_id})
    
    db.commit()
    return {"message": "Партію закрито"}

@router.delete("/batches/{batch_id}")
async def delete_laundry_batch(
    batch_id: str,
    db: Session = Depends(get_rh_db)
):
    """
    Видалити партію.
    - Партії зі статусом 'completed' можна видалити без обмежень
    - Партії зі статусом 'sent' можна видалити тільки якщо не було повернень
    """
    try:
        # Перевірити статус партії
        result = db.execute(
            text("SELECT status, returned_items, total_items FROM laundry_batches WHERE id = :id"),
            {"id": batch_id}
        )
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Партію не знайдено")
        
        status = row[0]
        returned_items = row[1] or 0
        # total_items = row[2] or 0  # Not used currently
        
        # Для completed партій - дозволяємо видалення
        # Для sent партій - тільки якщо не було повернень
        if status == 'sent' and returned_items > 0:
            raise HTTPException(
                status_code=400,
                detail="Не можна видалити партію зі статусом 'sent' якщо вже є повернення"
            )
        
        # Видалити товари партії
        db.execute(text("DELETE FROM laundry_items WHERE batch_id = :batch_id"), {"batch_id": batch_id})
        
        # Очистити посилання на партію в damage history
        db.execute(text("""
            UPDATE product_damage_history 
            SET laundry_batch_id = NULL, laundry_item_id = NULL
            WHERE laundry_batch_id = :batch_id
        """), {"batch_id": batch_id})
        
        # Видалити партію
        db.execute(text("DELETE FROM laundry_batches WHERE id = :id"), {"id": batch_id})
        
        db.commit()
        return {"success": True, "message": "Партію видалено"}
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Print / Export Endpoints ====================

@router.get("/batches/{batch_id}/print")
async def get_batch_print_view(
    batch_id: str,
    db: Session = Depends(get_rh_db)
):
    """Redirect to preview endpoint"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=f"/api/laundry/batches/{batch_id}/preview")


@router.get("/batches/{batch_id}/preview")
async def get_batch_preview(
    batch_id: str,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати HTML preview партії для друку.
    Стилізовано як estimate документ.
    """
    from jinja2 import Environment, FileSystemLoader
    from fastapi.responses import HTMLResponse
    import os
    
    # Get batch info
    batch_result = db.execute(text("""
        SELECT id, batch_number, laundry_company, status, sent_date, 
               expected_return_date, total_items, returned_items, 
               complexity, batch_type, created_at
        FROM laundry_batches
        WHERE id = :batch_id
    """), {"batch_id": batch_id})
    
    batch_row = batch_result.fetchone()
    if not batch_row:
        raise HTTPException(status_code=404, detail="Партію не знайдено")
    
    batch = {
        "id": batch_row[0],
        "batch_number": batch_row[1],
        "laundry_company": batch_row[2],
        "status": batch_row[3],
        "sent_date": batch_row[4].strftime("%d.%m.%Y") if batch_row[4] else "",
        "expected_return_date": batch_row[5].strftime("%d.%m.%Y") if batch_row[5] else None,
        "total_items": batch_row[6] or 0,
        "returned_items": batch_row[7] or 0,
        "complexity": batch_row[8] or "normal",
        "batch_type": batch_row[9] or "laundry"
    }
    
    # Get batch items
    items_result = db.execute(text("""
        SELECT 
            li.id, li.product_id, li.product_name, li.sku, li.category,
            li.quantity, li.returned_quantity, li.condition_before, li.notes,
            NULL as order_number,
            p.image_url
        FROM laundry_items li
        LEFT JOIN products p ON li.product_id = p.product_id
        WHERE li.batch_id = :batch_id
        ORDER BY li.created_at
    """), {"batch_id": batch_id})
    
    # Base URL for images
    base_url = "https://backrentalhub.farforrent.com.ua"
    
    items = []
    for row in items_result:
        image_url = row[10]
        # Build full image URL
        if image_url:
            if not image_url.startswith('http'):
                image_url = f"{base_url}/{image_url.lstrip('/')}"
        
        items.append({
            "id": row[0],
            "product_id": row[1],
            "product_name": row[2],
            "sku": row[3],
            "category": row[4],
            "quantity": row[5] or 1,
            "returned_quantity": row[6] or 0,
            "condition_before": row[7],
            "notes": row[8],
            "order_number": row[9],
            "image_url": image_url
        })
    
    # Determine colors based on batch type
    if batch["batch_type"] == "wash":
        batch_type_name = "Прання"
        primary_color = "#0891b2"  # cyan-600
        dark_color = "#0e7490"     # cyan-700
        light_bg = "#ecfeff"       # cyan-50
    else:
        batch_type_name = "Хімчистка"
        primary_color = "#9333ea"  # purple-600
        dark_color = "#7e22ce"     # purple-700
        light_bg = "#faf5ff"       # purple-50
    
    # Load and render template
    templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "documents")
    env = Environment(loader=FileSystemLoader(templates_dir))
    template = env.get_template("laundry_batch.html")
    
    html = template.render(
        batch=batch,
        items=items,
        batch_type_name=batch_type_name,
        primary_color=primary_color,
        dark_color=dark_color,
        light_bg=light_bg,
        company_name="FarforRent",
        notes="",
        generated_at=datetime.now().strftime("%d.%m.%Y %H:%M")
    )
    
    return HTMLResponse(content=html)


# ==================== Statistics Endpoints ====================

@router.get("/statistics")
async def get_laundry_statistics(db: Session = Depends(get_rh_db)):
    """Отримати загальну статистику по хімчистці"""
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_batches,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as active_batches,
            SUM(total_items) as total_items_sent,
            SUM(returned_items) as total_items_returned,
            SUM(cost) as total_cost
        FROM laundry_batches
    """))
    
    row = result.fetchone()
    
    return {
        "total_batches": row[0] or 0,
        "active_batches": row[1] or 0,
        "total_items_sent": row[2] or 0,
        "total_items_returned": row[3] or 0,
        "total_cost": float(row[4]) if row[4] else 0.0
    }

@router.get("/companies")
async def get_laundry_companies(db: Session = Depends(get_rh_db)):
    """Отримати список компаній-пралень"""
    result = db.execute(text("""
        SELECT DISTINCT laundry_company
        FROM laundry_batches
        WHERE laundry_company IS NOT NULL
        ORDER BY laundry_company
    """))
    
    companies = [row[0] for row in result]
    return {"companies": companies}

# ==================== Laundry Queue Endpoints ====================
# Використовуємо tasks таблицю з task_type='laundry_queue' для черги хімчистки

class QueueItemCreate(BaseModel):
    damage_id: Optional[str] = None
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    product_id: Optional[int] = None
    product_name: str
    sku: str
    category: Optional[str] = "textile"
    quantity: int = 1
    condition: Optional[str] = "dirty"
    notes: Optional[str] = None
    source: Optional[str] = "damage_cabinet"  # damage_cabinet, return, manual

# Note: Primary queue endpoint is defined at line ~98 using product_damage_history table

@router.post("/queue")
async def add_to_laundry_queue(
    item: QueueItemCreate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Додати товар до черги хімчистки
    Створюємо task з task_type='laundry_queue'
    """
    try:
        task_id = str(uuid.uuid4())[:8]
        
        # Створити завдання в черзі хімчистки
        db.execute(text("""
            INSERT INTO tasks (
                id, order_id, order_number, damage_id, title, description,
                task_type, status, priority, assigned_to, created_by, created_at, updated_at
            ) VALUES (
                :id, :order_id, :order_number, :damage_id, :title, :description,
                'laundry_queue', 'todo', 'medium', NULL, :created_by, NOW(), NOW()
            )
        """), {
            "id": task_id,
            "order_id": item.order_id,
            "order_number": item.order_number,
            "damage_id": item.damage_id,
            "title": f"🧺 В чергу хімчистки: {item.product_name} ({item.sku})",
            "description": f"Товар очікує відправки в хімчистку.\nСтан: {item.condition}.\nКількість: {item.quantity}\n{item.notes or ''}",
            "created_by": current_user.get('name', 'System')
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Товар '{item.product_name}' додано до черги хімчистки",
            "queue_id": task_id,
            "task_id": task_id
        }
        
    except Exception as e:
        db.rollback()
        print(f"[Laundry] Error adding to queue: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/queue/{item_id}")
async def remove_from_laundry_queue(
    item_id: str,
    db: Session = Depends(get_rh_db)
):
    """Видалити товар з черги хімчистки"""
    try:
        db.execute(text("""
            DELETE FROM tasks WHERE id = :id AND task_type = 'laundry_queue'
        """), {"id": item_id})
        db.commit()
        return {"message": "Товар видалено з черги"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

class BatchFromQueueCreate(BaseModel):
    item_ids: List[str]
    laundry_company: str
    expected_return_date: str
    cost: Optional[float] = None
    notes: Optional[str] = None

@router.post("/batches/from-queue")
async def create_batch_from_queue(
    data: BatchFromQueueCreate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Створити партію хімчистки з товарів черги
    """
    try:
        if not data.item_ids:
            raise HTTPException(status_code=400, detail="Виберіть товари для партії")
        
        batch_id = str(uuid.uuid4())[:8]
        batch_number = f"LB-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Отримати товари з черги (tasks)
        placeholders = ','.join([f':id_{i}' for i in range(len(data.item_ids))])
        params = {f'id_{i}': item_id for i, item_id in enumerate(data.item_ids)}
        
        result = db.execute(text(f"""
            SELECT id, title, description, order_id, order_number
            FROM tasks
            WHERE id IN ({placeholders}) AND task_type = 'laundry_queue' AND status = 'todo'
        """), params)
        
        queue_items = list(result)
        
        if not queue_items:
            raise HTTPException(status_code=400, detail="Обрані товари вже додано до іншої партії")
        
        total_items = len(queue_items)
        
        # Створити партію
        db.execute(text("""
            INSERT INTO laundry_batches (
                id, batch_number, status, laundry_company, sent_date,
                expected_return_date, total_items, returned_items, cost, notes,
                sent_by_id, sent_by_name, created_at, updated_at
            ) VALUES (
                :id, :batch_number, 'sent', :laundry_company, NOW(),
                :expected_return_date, :total_items, 0, :cost, :notes,
                :sent_by_id, :sent_by_name, NOW(), NOW()
            )
        """), {
            "id": batch_id,
            "batch_number": batch_number,
            "laundry_company": data.laundry_company,
            "expected_return_date": data.expected_return_date,
            "total_items": total_items,
            "cost": data.cost or 0,
            "notes": data.notes,
            "sent_by_id": current_user.get('id'),
            "sent_by_name": current_user.get('name', 'System')
        })
        
        # Додати товари до партії (laundry_items)
        for row in queue_items:
            item_id = str(uuid.uuid4())[:8]
            title = row[1] or ''
            product_name = title.replace('🧺 В чергу хімчистки: ', '').split(' (')[0]
            sku = title.split('(')[-1].replace(')', '') if '(' in title else 'N/A'
            
            db.execute(text("""
                INSERT INTO laundry_items (
                    id, batch_id, product_id, product_name, sku, category,
                    quantity, returned_quantity, condition_before, created_at
                ) VALUES (
                    :id, :batch_id, 0, :product_name, :sku, 'textile',
                    1, 0, 'dirty', NOW()
                )
            """), {
                "id": item_id,
                "batch_id": batch_id,
                "product_name": product_name,
                "sku": sku
            })
        
        # Оновити статус завдань - позначити як виконані
        db.execute(text(f"""
            UPDATE tasks SET status = 'done', completed_at = NOW(), updated_at = NOW()
            WHERE id IN ({placeholders}) AND task_type = 'laundry_queue'
        """), params)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Партію {batch_number} створено з {len(queue_items)} товарів",
            "batch_id": batch_id,
            "batch_number": batch_number
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[Laundry] Error creating batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))
