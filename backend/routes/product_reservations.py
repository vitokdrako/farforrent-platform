"""
Product Reservations API - Резервування товарів
Система заморожування товарів на період оренди
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional
import uuid

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/product-reservations", tags=["product-reservations"])

# Міграція таблиці
@router.post("/migrate")
async def migrate_table(db: Session = Depends(get_rh_db)):
    """Створити таблицю product_reservations"""
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS product_reservations (
                id VARCHAR(36) PRIMARY KEY,
                product_id INT NOT NULL,
                sku VARCHAR(255),
                order_id INT NOT NULL,
                order_number VARCHAR(50),
                
                quantity INT NOT NULL DEFAULT 1,
                reserved_from DATE NOT NULL,
                reserved_until DATE NOT NULL,
                
                status VARCHAR(20) DEFAULT 'active',
                
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                released_at DATETIME,
                
                INDEX idx_product_id (product_id),
                INDEX idx_sku (sku),
                INDEX idx_order_id (order_id),
                INDEX idx_status (status),
                INDEX idx_dates (reserved_from, reserved_until),
                
                FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """))
        db.commit()
        return {"success": True, "message": "Таблиця створена успішно"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/")
async def create_reservation(
    reservation_data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Створити резерв товару
    
    Параметри:
    - product_id: ID товару
    - sku: Артикул товару
    - order_id: ID замовлення
    - order_number: Номер замовлення
    - quantity: Кількість (за замовчуванням 1)
    - reserved_from: Дата початку резерву (YYYY-MM-DD)
    - reserved_until: Дата кінця резерву (YYYY-MM-DD)
    """
    try:
        reservation_id = str(uuid.uuid4())
        
        db.execute(text("""
            INSERT INTO product_reservations (
                id, product_id, sku, order_id, order_number,
                quantity, reserved_from, reserved_until, status, created_at
            ) VALUES (
                :id, :product_id, :sku, :order_id, :order_number,
                :quantity, :reserved_from, :reserved_until, 'active', NOW()
            )
        """), {
            "id": reservation_id,
            "product_id": reservation_data.get("product_id"),
            "sku": reservation_data.get("sku"),
            "order_id": reservation_data.get("order_id"),
            "order_number": reservation_data.get("order_number"),
            "quantity": reservation_data.get("quantity", 1),
            "reserved_from": reservation_data.get("reserved_from"),
            "reserved_until": reservation_data.get("reserved_until")
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": "Резерв створено",
            "reservation_id": reservation_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка створення резерву: {str(e)}")


@router.post("/batch")
async def create_batch_reservations(
    order_data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Створити резерви для всіх позицій замовлення
    
    Параметри:
    - order_id: ID замовлення
    - order_number: Номер замовлення
    - items: Масив товарів [{product_id, sku, quantity}]
    - reserved_from: Дата початку
    - reserved_until: Дата кінця
    """
    try:
        order_id = order_data.get("order_id")
        order_number = order_data.get("order_number")
        items = order_data.get("items", [])
        reserved_from = order_data.get("reserved_from")
        reserved_until = order_data.get("reserved_until")
        
        created_ids = []
        
        for item in items:
            reservation_id = str(uuid.uuid4())
            
            db.execute(text("""
                INSERT INTO product_reservations (
                    id, product_id, sku, order_id, order_number,
                    quantity, reserved_from, reserved_until, status, created_at
                ) VALUES (
                    :id, :product_id, :sku, :order_id, :order_number,
                    :quantity, :reserved_from, :reserved_until, 'active', NOW()
                )
            """), {
                "id": reservation_id,
                "product_id": item.get("product_id"),
                "sku": item.get("sku"),
                "order_id": order_id,
                "order_number": order_number,
                "quantity": item.get("quantity", 1),
                "reserved_from": reserved_from,
                "reserved_until": reserved_until
            })
            
            created_ids.append(reservation_id)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Створено {len(created_ids)} резервів",
            "reservation_ids": created_ids,
            "order_id": order_id
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка створення резервів: {str(e)}")


@router.delete("/order/{order_id}")
async def release_order_reservations(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Розморозити всі резерви для замовлення"""
    try:
        result = db.execute(text("""
            UPDATE product_reservations
            SET status = 'released', released_at = NOW()
            WHERE order_id = :order_id AND status = 'active'
        """), {"order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Розморожено резерви для замовлення {order_id}",
            "released_count": result.rowcount
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка розморожування: {str(e)}")


@router.get("/order/{order_id}")
async def get_order_reservations(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Отримати всі резерви замовлення"""
    try:
        result = db.execute(text("""
            SELECT 
                id, product_id, sku, order_id, order_number,
                quantity, reserved_from, reserved_until,
                status, created_at, released_at
            FROM product_reservations
            WHERE order_id = :order_id
            ORDER BY created_at DESC
        """), {"order_id": order_id})
        
        reservations = []
        for row in result:
            reservations.append({
                "id": row[0],
                "product_id": row[1],
                "sku": row[2],
                "order_id": row[3],
                "order_number": row[4],
                "quantity": row[5],
                "reserved_from": row[6].isoformat() if row[6] else None,
                "reserved_until": row[7].isoformat() if row[7] else None,
                "status": row[8],
                "created_at": row[9].isoformat() if row[9] else None,
                "released_at": row[10].isoformat() if row[10] else None
            })
        
        return {
            "order_id": order_id,
            "total_reservations": len(reservations),
            "reservations": reservations
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка читання: {str(e)}")


@router.get("/product/{product_id}/check")
async def check_product_availability(
    product_id: int,
    date_from: str,
    date_until: str,
    db: Session = Depends(get_rh_db)
):
    """
    Перевірити доступність товару на період
    Повертає кількість зарезервованих одиниць
    """
    try:
        result = db.execute(text("""
            SELECT COALESCE(SUM(quantity), 0) as reserved_qty
            FROM product_reservations
            WHERE product_id = :product_id
            AND status = 'active'
            AND (
                (reserved_from <= :date_until AND reserved_until >= :date_from)
            )
        """), {
            "product_id": product_id,
            "date_from": date_from,
            "date_until": date_until
        })
        
        row = result.fetchone()
        reserved_qty = int(row[0]) if row else 0
        
        # Отримати загальну кількість товару
        product_result = db.execute(text("""
            SELECT quantity FROM products WHERE product_id = :product_id
        """), {"product_id": product_id})
        
        product_row = product_result.fetchone()
        total_qty = int(product_row[0]) if product_row else 0
        
        available_qty = max(0, total_qty - reserved_qty)
        
        return {
            "product_id": product_id,
            "total_quantity": total_qty,
            "reserved_quantity": reserved_qty,
            "available_quantity": available_qty,
            "period": {
                "from": date_from,
                "until": date_until
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка перевірки: {str(e)}")
