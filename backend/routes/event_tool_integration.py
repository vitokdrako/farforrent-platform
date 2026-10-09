"""
Event Tool Integration API
Endpoints для конвертації Event Boards в Orders
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid
import logging

from database_rentalhub import get_rh_db_sync

router = APIRouter(prefix="/api/event-tool", tags=["event-tool"])
logger = logging.getLogger(__name__)


# ============================================================
# PYDANTIC MODELS
# ============================================================

class EventToolOrderItem(BaseModel):
    """Товар з Event Board"""
    sku: str
    name: str
    quantity: int
    rental_price: float  # Ціна за день
    deposit: float  # Депозит за одиницю
    image_url: Optional[str] = None


class EventToolOrderCreate(BaseModel):
    """Дані для створення замовлення з Event Tool"""
    # Event Board info
    event_board_id: str = Field(..., description="ID Event Board")
    
    # Customer info (з Event Tool auth)
    customer_id: Optional[int] = None
    customer_name: str
    customer_phone: str
    customer_email: str
    
    # Dates
    issue_date: str = Field(..., description="Дата видачі (YYYY-MM-DD)")
    return_date: str = Field(..., description="Дата повернення (YYYY-MM-DD)")
    
    # Delivery
    delivery_address: Optional[str] = None
    city: Optional[str] = None
    delivery_type: Optional[str] = "самовивіз"  # самовивіз/доставка
    
    # Items
    items: List[EventToolOrderItem]
    
    # Financial
    total_price: float
    deposit_amount: float
    discount: Optional[float] = 0.0
    
    # Comments
    customer_comment: Optional[str] = None
    event_type: Optional[str] = None  # весілля, день народження, корпоратив
    guest_count: Optional[int] = None


class EventToolOrderResponse(BaseModel):
    """Відповідь після створення замовлення"""
    success: bool
    order_id: str
    order_number: str
    status: str
    message: str


# ============================================================
# MIGRATION: Add Event Tool fields to orders table
# ============================================================

@router.post("/migrate-orders-table")
async def migrate_orders_table_for_event_tool(db = Depends(get_rh_db_sync)):
    """
    Додає поля для Event Tool integration до таблиці orders
    Безпечно запускати кілька разів - перевіряє чи існують колонки
    """
    try:
        fields_to_add = [
            ("event_board_id", "VARCHAR(255)"),
            ("source", "VARCHAR(50) DEFAULT 'manual'"),  # opencart/event_tool/manual
            ("delivery_address", "TEXT"),
            ("delivery_type", "VARCHAR(50)"),  # самовивіз/доставка
            ("event_type", "VARCHAR(100)"),  # тип заходу
            ("guest_count", "INT"),  # кількість гостей
        ]
        
        added = []
        
        for field_name, field_type in fields_to_add:
            # Check if column exists
            check_query = text("""
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'orders'
                AND COLUMN_NAME = :field_name
            """)
            
            result = db.execute(check_query, {"field_name": field_name}).fetchone()
            
            if result[0] == 0:
                # Add column
                alter_query = text(f"ALTER TABLE orders ADD COLUMN {field_name} {field_type}")
                db.execute(alter_query)
                db.commit()
                added.append(field_name)
                logger.info(f"✅ Added column: {field_name}")
        
        db.close()
        
        return {
            "success": True,
            "message": f"Migration complete. Added {len(added)} columns",
            "added_columns": added
        }
        
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# CONVERT EVENT BOARD TO ORDER
# ============================================================

@router.post("/convert-to-order", response_model=EventToolOrderResponse)
async def convert_event_board_to_order(
    order_data: EventToolOrderCreate,
    db = Depends(get_rh_db_sync)
):
    """
    Конвертує Event Board в Order
    
    Workflow:
    1. Перевірити availability товарів
    2. Створити order в БД
    3. Створити order_items
    4. Конвертувати soft → hard reservations
    5. Оновити event_board.converted_to_order_id
    6. Повернути order info
    """
    try:
        # 1. Generate order number
        order_number = f"EV-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
        order_id = str(uuid.uuid4())
        
        # 2. Calculate rental days
        from datetime import datetime as dt
        issue_dt = dt.strptime(order_data.issue_date, "%Y-%m-%d")
        return_dt = dt.strptime(order_data.return_date, "%Y-%m-%d")
        rental_days = (return_dt - issue_dt).days
        
        if rental_days <= 0:
            raise HTTPException(
                status_code=400,
                detail="Дата повернення має бути пізніше дати видачі"
            )
        
        # 3. Check availability (перевірка конфліктів)
        for item in order_data.items:
            check_query = text("""
                SELECT 
                    p.quantity as total_quantity,
                    COALESCE(SUM(pr.quantity), 0) as reserved_quantity
                FROM products p
                LEFT JOIN product_reservations pr ON 
                    pr.sku = p.sku AND
                    pr.status = 'active' AND
                    (
                        (pr.start_date <= :issue_date AND pr.end_date >= :issue_date) OR
                        (pr.start_date <= :return_date AND pr.end_date >= :return_date) OR
                        (pr.start_date >= :issue_date AND pr.end_date <= :return_date)
                    )
                WHERE p.sku = :sku
                GROUP BY p.quantity
            """)
            
            result = db.execute(check_query, {
                "sku": item.sku,
                "issue_date": order_data.issue_date,
                "return_date": order_data.return_date
            }).fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=404,
                    detail=f"Товар {item.sku} не знайдено"
                )
            
            total_qty, reserved_qty = result
            available = total_qty - reserved_qty
            
            if available < item.quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Товар {item.name} недоступний в потрібній кількості. Доступно: {available}, потрібно: {item.quantity}"
                )
        
        # 4. Create order
        insert_order = text("""
            INSERT INTO orders (
                order_id, order_number, customer_id, customer_name, phone, email,
                issue_date, return_date, rental_days,
                total_price, deposit_amount, discount,
                status, source, event_board_id,
                delivery_address, city, delivery_type,
                customer_comment, event_type, guest_count,
                created_at
            ) VALUES (
                :order_id, :order_number, :customer_id, :customer_name, :phone, :email,
                :issue_date, :return_date, :rental_days,
                :total_price, :deposit_amount, :discount,
                'pending', 'event_tool', :event_board_id,
                :delivery_address, :city, :delivery_type,
                :customer_comment, :event_type, :guest_count,
                NOW()
            )
        """)
        
        db.execute(insert_order, {
            "order_id": order_id,
            "order_number": order_number,
            "customer_id": order_data.customer_id,
            "customer_name": order_data.customer_name,
            "phone": order_data.customer_phone,
            "email": order_data.customer_email,
            "issue_date": order_data.issue_date,
            "return_date": order_data.return_date,
            "rental_days": rental_days,
            "total_price": order_data.total_price,
            "deposit_amount": order_data.deposit_amount,
            "discount": order_data.discount,
            "event_board_id": order_data.event_board_id,
            "delivery_address": order_data.delivery_address,
            "city": order_data.city,
            "delivery_type": order_data.delivery_type,
            "customer_comment": order_data.customer_comment,
            "event_type": order_data.event_type,
            "guest_count": order_data.guest_count
        })
        
        # 5. Create order items
        for item in order_data.items:
            item_id = str(uuid.uuid4())
            insert_item = text("""
                INSERT INTO order_items (
                    item_id, order_id, sku, product_name, quantity,
                    rental_price, deposit_per_unit,
                    total_rental, total_deposit
                ) VALUES (
                    :item_id, :order_id, :sku, :name, :quantity,
                    :rental_price, :deposit,
                    :total_rental, :total_deposit
                )
            """)
            
            db.execute(insert_item, {
                "item_id": item_id,
                "order_id": order_id,
                "sku": item.sku,
                "name": item.name,
                "quantity": item.quantity,
                "rental_price": item.rental_price,
                "deposit": item.deposit,
                "total_rental": item.rental_price * item.quantity * rental_days,
                "total_deposit": item.deposit * item.quantity
            })
            
            # 6. Create product reservation (hard)
            reservation_id = str(uuid.uuid4())
            insert_reservation = text("""
                INSERT INTO product_reservations (
                    reservation_id, order_id, sku, quantity,
                    start_date, end_date, status
                ) VALUES (
                    :reservation_id, :order_id, :sku, :quantity,
                    :start_date, :end_date, 'active'
                )
            """)
            
            db.execute(insert_reservation, {
                "reservation_id": reservation_id,
                "order_id": order_id,
                "sku": item.sku,
                "quantity": item.quantity,
                "start_date": order_data.issue_date,
                "end_date": order_data.return_date
            })
        
        # 7. Update event_board (mark as converted)
        update_board = text("""
            UPDATE event_boards 
            SET converted_to_order_id = :order_id, updated_at = NOW()
            WHERE board_id = :board_id
        """)
        
        db.execute(update_board, {
            "order_id": order_id,
            "board_id": order_data.event_board_id
        })
        
        db.commit()
        db.close()
        
        logger.info(f"✅ Event Board {order_data.event_board_id} converted to Order {order_number}")
        
        return EventToolOrderResponse(
            success=True,
            order_id=order_id,
            order_number=order_number,
            status="pending",
            message=f"Замовлення {order_number} успішно створено! Очікує підтвердження адміністратора."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        db.close()
        logger.error(f"Error converting Event Board to Order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Помилка створення замовлення: {str(e)}")


@router.get("/order-status/{order_id}")
async def get_event_tool_order_status(order_id: str, db = Depends(get_rh_db_sync)):
    """
    Отримати статус замовлення для відображення в Event Tool
    """
    try:
        query = text("""
            SELECT 
                order_id, order_number, status, 
                issue_date, return_date,
                total_price, deposit_amount,
                customer_comment, manager_comment,
                created_at
            FROM orders
            WHERE order_id = :order_id AND source = 'event_tool'
        """)
        
        result = db.execute(query, {"order_id": order_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")
        
        db.close()
        
        return {
            "order_id": result[0],
            "order_number": result[1],
            "status": result[2],
            "status_display": get_status_display(result[2]),
            "issue_date": str(result[3]),
            "return_date": str(result[4]),
            "total_amount": float(result[5]),
            "deposit_amount": float(result[6]),
            "customer_comment": result[7],
            "manager_comment": result[8],
            "created_at": str(result[9])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def get_status_display(status: str) -> str:
    """Перетворити статус в зрозумілий текст для клієнта"""
    status_map = {
        "pending": "Очікує підтвердження",
        "confirmed": "Підтверджено ✓",
        "preparation": "Готується до видачі",
        "issued": "Видано (у вас)",
        "returned": "Повернуто. Дякуємо!",
        "cancelled": "Скасовано"
    }
    return status_map.get(status, status)
