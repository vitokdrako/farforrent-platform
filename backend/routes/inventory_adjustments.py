"""
Inventory Adjustments API - Коригування інвентарю
Для вичитання втрачених/пошкоджених товарів з обігу
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import uuid

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/inventory-adjustments", tags=["inventory-adjustments"])

@router.post("/write-off")
async def write_off_product(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Вичитати товар з обігу (втрата/критичне пошкодження)
    
    Параметри:
    - product_id: ID товару
    - sku: Артикул
    - quantity: Кількість для списання
    - reason: Причина ('lost', 'damaged_critical', 'broken')
    - order_id: ID замовлення (опціонально)
    - note: Примітка
    """
    try:
        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)
        reason = data.get("reason", "lost")
        
        # Перевірити поточну кількість
        result = db.execute(text("""
            SELECT quantity FROM products WHERE product_id = :product_id
        """), {"product_id": product_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Товар не знайдено")
        
        current_qty = int(row[0])
        new_qty = max(0, current_qty - quantity)
        
        # Оновити кількість
        db.execute(text("""
            UPDATE products 
            SET quantity = :new_qty
            WHERE product_id = :product_id
        """), {
            "product_id": product_id,
            "new_qty": new_qty
        })
        
        # Записати в історію коригувань (можна створити окрему таблицю)
        adjustment_id = str(uuid.uuid4())
        
        # Поки що логування, потім можна створити таблицю inventory_adjustments
        print(f"[Inventory] Списано {quantity} од. товару {product_id} ({data.get('sku')})")
        print(f"[Inventory] Причина: {reason}, було: {current_qty}, стало: {new_qty}")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Списано {quantity} од. з обігу",
            "product_id": product_id,
            "previous_quantity": current_qty,
            "new_quantity": new_qty,
            "reason": reason
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка списання: {str(e)}")


@router.post("/adjust")
async def adjust_inventory(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Коригування інвентарю (додати або відняти)
    
    Параметри:
    - product_id: ID товару
    - adjustment: Кількість (+10 або -5)
    - reason: Причина коригування
    - note: Примітка
    """
    try:
        product_id = data.get("product_id")
        adjustment = int(data.get("adjustment", 0))
        reason = data.get("reason", "manual_adjustment")
        
        # Перевірити поточну кількість
        result = db.execute(text("""
            SELECT quantity FROM products WHERE product_id = :product_id
        """), {"product_id": product_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Товар не знайдено")
        
        current_qty = int(row[0])
        new_qty = max(0, current_qty + adjustment)
        
        # Оновити кількість
        db.execute(text("""
            UPDATE products 
            SET quantity = :new_qty
            WHERE product_id = :product_id
        """), {
            "product_id": product_id,
            "new_qty": new_qty
        })
        
        print(f"[Inventory] Коригування {adjustment:+d} од. товару {product_id}")
        print(f"[Inventory] Причина: {reason}, було: {current_qty}, стало: {new_qty}")
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Інвентар скориговано: {adjustment:+d}",
            "product_id": product_id,
            "previous_quantity": current_qty,
            "new_quantity": new_qty,
            "adjustment": adjustment,
            "reason": reason
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка коригування: {str(e)}")


@router.get("/product/{product_id}/status")
async def get_product_status(
    product_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати повний статус товару:
    - Загальна кількість
    - Заморожено (в замовленнях)
    - В оренді
    - Доступно
    """
    try:
        # Загальна кількість
        result = db.execute(text("""
            SELECT quantity FROM products WHERE product_id = :product_id
        """), {"product_id": product_id})
        row = result.fetchone()
        total_qty = int(row[0]) if row else 0
        
        # Заморожено (в активних замовленнях)
        frozen_result = db.execute(text("""
            SELECT COALESCE(SUM(oi.quantity), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.product_id = :product_id
            AND o.status IN ('processing', 'ready_for_issue', 'issued', 'on_rent')
        """), {"product_id": product_id})
        frozen_row = frozen_result.fetchone()
        frozen_qty = int(frozen_row[0]) if frozen_row else 0
        
        # В оренді (видано)
        in_rent_result = db.execute(text("""
            SELECT COALESCE(SUM(oi.quantity), 0)
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            WHERE oi.product_id = :product_id
            AND o.status IN ('issued', 'on_rent')
        """), {"product_id": product_id})
        in_rent_row = in_rent_result.fetchone()
        in_rent_qty = int(in_rent_row[0]) if in_rent_row else 0
        
        available_qty = max(0, total_qty - frozen_qty)
        
        return {
            "product_id": product_id,
            "total_quantity": total_qty,
            "frozen_quantity": frozen_qty,
            "in_rent_quantity": in_rent_qty,
            "available_quantity": available_qty,
            "status": {
                "in_stock": total_qty > 0,
                "available_for_rent": available_qty > 0,
                "all_in_use": frozen_qty >= total_qty
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка отримання статусу: {str(e)}")
