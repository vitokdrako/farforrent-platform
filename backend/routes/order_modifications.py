"""
Order Modifications API - Дозамовлення
Редагування позицій замовлення на етапі комплектації
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import json

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/orders", tags=["order-modifications"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class AddItemRequest(BaseModel):
    product_id: int
    quantity: int
    note: Optional[str] = None


class UpdateItemQuantityRequest(BaseModel):
    quantity: int
    note: Optional[str] = None


class RemoveItemRequest(BaseModel):
    reason: Optional[str] = "Відмова клієнта"


class OrderModification(BaseModel):
    id: int
    order_id: int
    modification_type: str  # add, update, remove
    item_id: Optional[int]
    product_id: Optional[int]
    product_name: Optional[str]
    old_quantity: Optional[int]
    new_quantity: Optional[int]
    price_change: float
    deposit_change: float
    reason: Optional[str]
    created_by: Optional[str]
    created_at: str


# ============================================================
# MIGRATION - Create required tables/columns
# ============================================================

def ensure_modifications_table(db: Session):
    """Create order_modifications table if not exists"""
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS order_modifications (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            modification_type ENUM('add', 'update', 'remove') NOT NULL,
            item_id INT NULL,
            product_id INT NULL,
            product_name VARCHAR(500),
            old_quantity INT DEFAULT 0,
            new_quantity INT DEFAULT 0,
            old_price DECIMAL(10,2) DEFAULT 0,
            new_price DECIMAL(10,2) DEFAULT 0,
            price_change DECIMAL(10,2) DEFAULT 0,
            deposit_change DECIMAL(10,2) DEFAULT 0,
            reason VARCHAR(500),
            created_by VARCHAR(255),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_order_id (order_id),
            INDEX idx_created_at (created_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))
    db.commit()


def ensure_order_items_columns(db: Session):
    """Add status and original_quantity columns to order_items if not exist"""
    try:
        # Check if status column exists
        result = db.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'order_items' 
            AND COLUMN_NAME = 'status'
        """))
        if result.fetchone()[0] == 0:
            db.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN status ENUM('active', 'refused') DEFAULT 'active'
            """))
            db.commit()
        
        # Check if original_quantity column exists
        result = db.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'order_items' 
            AND COLUMN_NAME = 'original_quantity'
        """))
        if result.fetchone()[0] == 0:
            db.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN original_quantity INT NULL
            """))
            db.commit()
            
        # Check if refusal_reason column exists
        result = db.execute(text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = 'order_items' 
            AND COLUMN_NAME = 'refusal_reason'
        """))
        if result.fetchone()[0] == 0:
            db.execute(text("""
                ALTER TABLE order_items 
                ADD COLUMN refusal_reason VARCHAR(500) NULL
            """))
            db.commit()
    except Exception as e:
        print(f"Warning: Could not alter order_items table: {e}")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_order_for_modification(db: Session, order_id: int) -> dict:
    """Get order and validate it can be modified"""
    result = db.execute(text("""
        SELECT order_id, order_number, status, rental_days, 
               total_price, deposit_amount, rental_start_date, rental_end_date
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order = result.fetchone()
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    # Дозволені статуси для редагування
    allowed_statuses = ['processing', 'ready_for_issue']
    if order[2] not in allowed_statuses:
        raise HTTPException(
            status_code=400, 
            detail=f"Редагування дозволено тільки для статусів: {', '.join(allowed_statuses)}. Поточний: {order[2]}"
        )
    
    return {
        "order_id": order[0],
        "order_number": order[1],
        "status": order[2],
        "rental_days": order[3] or 1,
        "total_price": float(order[4] or 0),
        "deposit_amount": float(order[5] or 0),
        "rental_start_date": order[6],
        "rental_end_date": order[7]
    }


def get_product_info(db: Session, product_id: int) -> dict:
    """Get product information for pricing"""
    result = db.execute(text("""
        SELECT product_id, sku, name, price, rental_price, quantity, image_url
        FROM products WHERE product_id = :product_id
    """), {"product_id": product_id})
    
    product = result.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Товар не знайдено")
    
    price = float(product[4] or product[3] or 0)  # rental_price or price
    loss_value = float(product[3] or 0)
    
    return {
        "product_id": product[0],
        "sku": product[1],
        "name": product[2],
        "price_per_day": price,
        "loss_value": loss_value,
        "deposit_per_unit": loss_value / 2,
        "available_quantity": int(product[5] or 0),
        "image_url": product[6]
    }


def recalculate_order_totals(db: Session, order_id: int):
    """Recalculate order totals based on active items"""
    # Get rental_days
    order_result = db.execute(text("""
        SELECT rental_days FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id})
    rental_days = order_result.fetchone()[0] or 1
    
    # Calculate totals from active items
    items_result = db.execute(text("""
        SELECT oi.quantity, oi.price, p.price as loss_value
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
    """), {"order_id": order_id})
    
    total_price = 0
    total_deposit = 0
    total_loss = 0
    
    for item in items_result:
        qty = item[0] or 1
        price_per_day = float(item[1] or 0)
        loss_value = float(item[2] or 0)
        
        total_price += price_per_day * qty * rental_days
        total_deposit += (loss_value / 2) * qty
        total_loss += loss_value * qty
    
    # Update order totals
    db.execute(text("""
        UPDATE orders SET 
            total_price = :total_price,
            deposit_amount = :deposit_amount,
            total_loss_value = :total_loss
        WHERE order_id = :order_id
    """), {
        "order_id": order_id,
        "total_price": total_price,
        "deposit_amount": total_deposit,
        "total_loss": total_loss
    })
    
    return {
        "total_price": total_price,
        "deposit_amount": total_deposit,
        "total_loss_value": total_loss
    }


def sync_issue_card_items(db: Session, order_id: int):
    """
    Синхронізує items в issue_card з order_items
    Викликати після додавання/видалення товарів через дозамовлення
    """
    import json
    
    # Отримуємо актуальні items з order_items
    items_result = db.execute(text("""
        SELECT 
            oi.id, oi.product_id, oi.product_name, oi.quantity, oi.price,
            p.sku, p.image_url, p.zone, p.aisle, p.shelf
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :order_id AND (oi.status = 'active' OR oi.status IS NULL)
    """), {"order_id": order_id})
    
    new_items = []
    for row in items_result:
        # Формуємо локацію
        location_parts = [row[7], row[8], row[9]]
        location = "-".join(filter(None, [str(x) for x in location_parts if x])) if any(location_parts) else None
        
        new_items.append({
            "id": row[0],
            "product_id": row[1],
            "name": row[2],
            "quantity": row[3],
            "price": float(row[4]) if row[4] else 0,
            "sku": row[5] or "",
            "image": row[6] or "",
            "location": {"zone": location or "", "state": "shelf"},
            "picked_qty": 0,
            "scanned": [],
            "packaging": {"cover": False, "box": False, "stretch": False, "black_case": False}
        })
    
    # Оновлюємо issue_card.items
    items_json = json.dumps(new_items, ensure_ascii=False)
    
    db.execute(text("""
        UPDATE issue_cards 
        SET items = :items
        WHERE order_id = :order_id
    """), {"order_id": order_id, "items": items_json})


def log_modification(
    db: Session, 
    order_id: int, 
    modification_type: str,
    item_id: int = None,
    product_id: int = None,
    product_name: str = None,
    old_quantity: int = 0,
    new_quantity: int = 0,
    old_price: float = 0,
    new_price: float = 0,
    price_change: float = 0,
    deposit_change: float = 0,
    reason: str = None,
    user_name: str = None
):
    """Log modification to history"""
    db.execute(text("""
        INSERT INTO order_modifications 
        (order_id, modification_type, item_id, product_id, product_name,
         old_quantity, new_quantity, old_price, new_price, 
         price_change, deposit_change, reason, created_by)
        VALUES 
        (:order_id, :modification_type, :item_id, :product_id, :product_name,
         :old_quantity, :new_quantity, :old_price, :new_price,
         :price_change, :deposit_change, :reason, :created_by)
    """), {
        "order_id": order_id,
        "modification_type": modification_type,
        "item_id": item_id,
        "product_id": product_id,
        "product_name": product_name,
        "old_quantity": old_quantity,
        "new_quantity": new_quantity,
        "old_price": old_price,
        "new_price": new_price,
        "price_change": price_change,
        "deposit_change": deposit_change,
        "reason": reason,
        "created_by": user_name
    })


# ============================================================
# API ENDPOINTS
# ============================================================

@router.post("/{order_id}/items")
async def add_item_to_order(
    order_id: int,
    request: AddItemRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Додати товар до замовлення (дозамовлення)
    Якщо товар вже є - збільшує кількість
    Дозволено тільки на етапах: processing, ready_for_issue
    """
    ensure_modifications_table(db)
    ensure_order_items_columns(db)
    
    # Validate order
    order = get_order_for_modification(db, order_id)
    
    # Get product info
    product = get_product_info(db, request.product_id)
    
    # Check availability
    if product["available_quantity"] < request.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Недостатня кількість на складі. Доступно: {product['available_quantity']}"
        )
    
    # Calculate prices
    rental_days = order["rental_days"]
    
    # Перевіряємо чи товар вже є в замовленні
    existing_result = db.execute(text("""
        SELECT id, quantity, price, total_rental
        FROM order_items
        WHERE order_id = :order_id AND product_id = :product_id AND (status = 'active' OR status IS NULL)
        LIMIT 1
    """), {"order_id": order_id, "product_id": request.product_id})
    
    existing_item = existing_result.fetchone()
    
    if existing_item:
        # Товар вже є - оновлюємо кількість
        item_id = existing_item[0]
        old_quantity = existing_item[1]
        new_quantity = old_quantity + request.quantity
        price_per_day = float(existing_item[2])
        new_total_rental = price_per_day * new_quantity * rental_days
        
        db.execute(text("""
            UPDATE order_items SET 
                quantity = :quantity,
                total_rental = :total_rental
            WHERE id = :item_id
        """), {
            "item_id": item_id,
            "quantity": new_quantity,
            "total_rental": new_total_rental
        })
        
        # Calculate changes
        old_total = price_per_day * old_quantity * rental_days
        price_change = new_total_rental - old_total
        deposit_change = product["deposit_per_unit"] * request.quantity
        
        # Log modification
        user_name = current_user.get("name", "Система") if current_user else "Система"
        log_modification(
            db=db,
            order_id=order_id,
            modification_type="update",
            item_id=item_id,
            product_id=product["product_id"],
            product_name=product["name"],
            old_quantity=old_quantity,
            new_quantity=new_quantity,
            old_price=old_total,
            new_price=new_total_rental,
            price_change=price_change,
            deposit_change=deposit_change,
            reason=request.note or f"Дозамовлення: +{request.quantity} шт",
            user_name=user_name
        )
        
        message = f"Кількість '{product['name']}' збільшено: {old_quantity} → {new_quantity}"
        
    else:
        # Новий товар - додаємо
        total_rental = product["price_per_day"] * request.quantity * rental_days
        
        db.execute(text("""
            INSERT INTO order_items 
            (order_id, product_id, product_name, quantity, price, total_rental, image_url, status)
            VALUES 
            (:order_id, :product_id, :product_name, :quantity, :price, :total_rental, :image_url, 'active')
        """), {
            "order_id": order_id,
            "product_id": product["product_id"],
            "product_name": product["name"],
            "quantity": request.quantity,
            "price": product["price_per_day"],
            "total_rental": total_rental,
            "image_url": product["image_url"]
        })
        
        # Get inserted item id
        result = db.execute(text("SELECT LAST_INSERT_ID()"))
        item_id = result.fetchone()[0]
        
        # Calculate changes
        price_change = total_rental
        deposit_change = product["deposit_per_unit"] * request.quantity
        new_quantity = request.quantity
        
        # Log modification
        user_name = current_user.get("name", "Система") if current_user else "Система"
        log_modification(
            db=db,
            order_id=order_id,
            modification_type="add",
            item_id=item_id,
            product_id=product["product_id"],
            product_name=product["name"],
            old_quantity=0,
            new_quantity=request.quantity,
            new_price=total_rental,
            price_change=price_change,
            deposit_change=deposit_change,
            reason=request.note or "Дозамовлення",
            user_name=user_name
        )
        
        message = f"Товар '{product['name']}' додано до замовлення"
    
    # Recalculate totals
    new_totals = recalculate_order_totals(db, order_id)
    
    # Sync issue_card items
    sync_issue_card_items(db, order_id)
    
    db.commit()
    
    return {
        "success": True,
        "message": message,
        "item": {
            "id": item_id,
            "product_id": product["product_id"],
            "product_name": product["name"],
            "quantity": new_quantity,
            "price": product["price_per_day"]
        },
        "totals": new_totals,
        "modification": {
            "type": "add" if not existing_item else "update",
            "price_change": price_change,
            "deposit_change": deposit_change
        }
    }


@router.patch("/{order_id}/items/{item_id}")
async def update_item_quantity(
    order_id: int,
    item_id: int,
    request: UpdateItemQuantityRequest,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Оновити кількість товару в замовленні
    Дозволено тільки на етапах: processing, ready_for_issue
    """
    ensure_modifications_table(db)
    ensure_order_items_columns(db)
    
    # Validate order
    order = get_order_for_modification(db, order_id)
    
    # Get current item
    result = db.execute(text("""
        SELECT oi.id, oi.product_id, oi.product_name, oi.quantity, oi.price, 
               oi.original_quantity, p.price as loss_value, p.quantity as available
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.id = :item_id AND oi.order_id = :order_id
    """), {"item_id": item_id, "order_id": order_id})
    
    item = result.fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Позицію не знайдено")
    
    old_quantity = item[3]
    price_per_day = float(item[4] or 0)
    loss_value = float(item[6] or 0)
    available = int(item[7] or 0)
    original_quantity = item[5] or old_quantity
    
    if request.quantity < 0:
        raise HTTPException(status_code=400, detail="Кількість не може бути від'ємною")
    
    # Check availability for increase
    quantity_diff = request.quantity - old_quantity
    if quantity_diff > 0 and quantity_diff > available:
        raise HTTPException(
            status_code=400,
            detail=f"Недостатня кількість на складі. Доступно: {available}"
        )
    
    rental_days = order["rental_days"]
    old_total = price_per_day * old_quantity * rental_days
    new_total = price_per_day * request.quantity * rental_days
    
    # Update item
    db.execute(text("""
        UPDATE order_items SET 
            quantity = :quantity,
            total_rental = :total_rental,
            original_quantity = COALESCE(original_quantity, :original_quantity)
        WHERE id = :item_id
    """), {
        "item_id": item_id,
        "quantity": request.quantity,
        "total_rental": new_total,
        "original_quantity": original_quantity
    })
    
    # Calculate changes
    price_change = new_total - old_total
    deposit_per_unit = loss_value / 2
    deposit_change = deposit_per_unit * quantity_diff
    
    # Log modification
    user_name = current_user.get("name", "Система") if current_user else "Система"
    log_modification(
        db=db,
        order_id=order_id,
        modification_type="update",
        item_id=item_id,
        product_id=item[1],
        product_name=item[2],
        old_quantity=old_quantity,
        new_quantity=request.quantity,
        old_price=old_total,
        new_price=new_total,
        price_change=price_change,
        deposit_change=deposit_change,
        reason=request.note or f"Зміна кількості: {old_quantity} → {request.quantity}",
        user_name=user_name
    )
    
    # Recalculate totals
    new_totals = recalculate_order_totals(db, order_id)
    
    # Sync issue_card items
    sync_issue_card_items(db, order_id)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Кількість оновлено: {old_quantity} → {request.quantity}",
        "item": {
            "id": item_id,
            "product_name": item[2],
            "old_quantity": old_quantity,
            "new_quantity": request.quantity,
            "price_change": price_change
        },
        "totals": new_totals,
        "modification": {
            "type": "update",
            "quantity_diff": quantity_diff,
            "price_change": price_change,
            "deposit_change": deposit_change
        }
    }


@router.delete("/{order_id}/items/{item_id}")
async def remove_item_from_order(
    order_id: int,
    item_id: int,
    request: RemoveItemRequest = None,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Видалити/відмовити позицію в замовленні
    Позначається як 'refused', не видаляється фізично
    """
    ensure_modifications_table(db)
    ensure_order_items_columns(db)
    
    if request is None:
        request = RemoveItemRequest()
    
    # Validate order (ensures status is valid for modification)
    get_order_for_modification(db, order_id)
    
    # Get current item
    result = db.execute(text("""
        SELECT oi.id, oi.product_id, oi.product_name, oi.quantity, oi.price, 
               oi.total_rental, p.price as loss_value
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.id = :item_id AND oi.order_id = :order_id
    """), {"item_id": item_id, "order_id": order_id})
    
    item = result.fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Позицію не знайдено")
    
    old_quantity = item[3]
    old_total = float(item[5] or 0)
    loss_value = float(item[6] or 0)
    
    # Mark as refused (not delete)
    db.execute(text("""
        UPDATE order_items SET 
            status = 'refused',
            refusal_reason = :reason,
            original_quantity = COALESCE(original_quantity, quantity)
        WHERE id = :item_id
    """), {
        "item_id": item_id,
        "reason": request.reason
    })
    
    # ✅ Повернути товар в наявність (збільшити quantity)
    product_id = item[1]
    db.execute(text("""
        UPDATE products 
        SET quantity = quantity + :qty
        WHERE product_id = :product_id
    """), {
        "qty": old_quantity,
        "product_id": product_id
    })
    
    # Calculate changes
    price_change = -old_total
    deposit_change = -(loss_value / 2) * old_quantity
    
    # Log modification
    user_name = current_user.get("name", "Система") if current_user else "Система"
    log_modification(
        db=db,
        order_id=order_id,
        modification_type="remove",
        item_id=item_id,
        product_id=item[1],
        product_name=item[2],
        old_quantity=old_quantity,
        new_quantity=0,
        old_price=old_total,
        new_price=0,
        price_change=price_change,
        deposit_change=deposit_change,
        reason=request.reason,
        user_name=user_name
    )
    
    # Recalculate totals
    new_totals = recalculate_order_totals(db, order_id)
    
    # Sync issue_card items
    sync_issue_card_items(db, order_id)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Позицію '{item[2]}' позначено як відмова",
        "item": {
            "id": item_id,
            "product_name": item[2],
            "status": "refused",
            "reason": request.reason
        },
        "totals": new_totals,
        "modification": {
            "type": "remove",
            "price_change": price_change,
            "deposit_change": deposit_change
        }
    }


@router.post("/{order_id}/items/{item_id}/restore")
async def restore_refused_item(
    order_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Відновити відмовлену позицію
    """
    ensure_modifications_table(db)
    
    # Validate order
    order = get_order_for_modification(db, order_id)
    
    # Get item
    result = db.execute(text("""
        SELECT id, product_id, product_name, quantity, price, total_rental, 
               original_quantity, status
        FROM order_items 
        WHERE id = :item_id AND order_id = :order_id
    """), {"item_id": item_id, "order_id": order_id})
    
    item = result.fetchone()
    if not item:
        raise HTTPException(status_code=404, detail="Позицію не знайдено")
    
    if item[7] != 'refused':
        raise HTTPException(status_code=400, detail="Позиція не є відмовленою")
    
    # Restore original quantity
    original_qty = item[6] or item[3]
    rental_days = order["rental_days"]
    price_per_day = float(item[4] or 0)
    new_total = price_per_day * original_qty * rental_days
    product_id = item[1]
    
    # ✅ Перевірити наявність товару перед відновленням
    avail_result = db.execute(text("""
        SELECT quantity FROM products WHERE product_id = :product_id
    """), {"product_id": product_id})
    avail_row = avail_result.fetchone()
    available_qty = avail_row[0] if avail_row else 0
    
    if available_qty < original_qty:
        raise HTTPException(
            status_code=400, 
            detail=f"Недостатня кількість товару на складі. Доступно: {available_qty}, потрібно: {original_qty}"
        )
    
    db.execute(text("""
        UPDATE order_items SET 
            status = 'active',
            quantity = :quantity,
            total_rental = :total_rental,
            refusal_reason = NULL
        WHERE id = :item_id
    """), {
        "item_id": item_id,
        "quantity": original_qty,
        "total_rental": new_total
    })
    
    # ✅ Зменшити кількість товару (зарезервувати)
    db.execute(text("""
        UPDATE products 
        SET quantity = quantity - :qty
        WHERE product_id = :product_id
    """), {
        "qty": original_qty,
        "product_id": product_id
    })
    
    # Log modification
    user_name = current_user.get("name", "Система") if current_user else "Система"
    log_modification(
        db=db,
        order_id=order_id,
        modification_type="add",
        item_id=item_id,
        product_id=item[1],
        product_name=item[2],
        old_quantity=0,
        new_quantity=original_qty,
        price_change=new_total,
        reason="Відновлено відмовлену позицію",
        user_name=user_name
    )
    
    # Recalculate totals
    new_totals = recalculate_order_totals(db, order_id)
    
    # Sync issue_card items
    sync_issue_card_items(db, order_id)
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Позицію '{item[2]}' відновлено",
        "item": {
            "id": item_id,
            "product_name": item[2],
            "status": "active",
            "quantity": original_qty
        },
        "totals": new_totals
    }


@router.get("/{order_id}/modifications")
async def get_order_modifications(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати історію змін замовлення
    """
    ensure_modifications_table(db)
    
    result = db.execute(text("""
        SELECT id, order_id, modification_type, item_id, product_id, product_name,
               old_quantity, new_quantity, old_price, new_price, 
               price_change, deposit_change, reason, created_by, created_at
        FROM order_modifications
        WHERE order_id = :order_id
        ORDER BY created_at DESC
    """), {"order_id": order_id})
    
    modifications = []
    for row in result:
        modifications.append({
            "id": row[0],
            "order_id": row[1],
            "modification_type": row[2],
            "item_id": row[3],
            "product_id": row[4],
            "product_name": row[5],
            "old_quantity": row[6],
            "new_quantity": row[7],
            "old_price": float(row[8] or 0),
            "new_price": float(row[9] or 0),
            "price_change": float(row[10] or 0),
            "deposit_change": float(row[11] or 0),
            "reason": row[12],
            "created_by": row[13],
            "created_at": row[14].isoformat() if row[14] else None
        })
    
    return {
        "order_id": order_id,
        "modifications": modifications,
        "total_count": len(modifications)
    }


@router.get("/{order_id}/items/refused")
async def get_refused_items(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати список відмовлених позицій замовлення
    """
    ensure_order_items_columns(db)
    
    result = db.execute(text("""
        SELECT oi.id, oi.product_id, oi.product_name, oi.quantity, oi.price,
               oi.original_quantity, oi.refusal_reason, p.image_url
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :order_id AND oi.status = 'refused'
    """), {"order_id": order_id})
    
    items = []
    for row in result:
        items.append({
            "id": row[0],
            "product_id": row[1],
            "product_name": row[2],
            "quantity": row[3],
            "price": float(row[4] or 0),
            "original_quantity": row[5],
            "refusal_reason": row[6],
            "image_url": row[7]
        })
    
    return {
        "order_id": order_id,
        "refused_items": items,
        "count": len(items)
    }


@router.post("/{order_id}/sync-items")
async def sync_order_items_to_issue_card(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Синхронізувати items з order_items до issue_card.items
    Корисно якщо items не співпадають
    """
    # Перевіряємо чи існує issue_card
    result = db.execute(text("""
        SELECT id FROM issue_cards WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Issue card не знайдено")
    
    # Синхронізуємо
    sync_issue_card_items(db, order_id)
    db.commit()
    
    return {
        "success": True,
        "message": "Items синхронізовано з order_items до issue_card"
    }

