"""
Extended Catalog API - розширений каталог з пошуком
✅ MIGRATED: Using RentalHub DB
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/extended-catalog", tags=["extended-catalog"])

@router.get("/search")
async def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    in_stock: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_rh_db)
):
    """
    Розширений пошук товарів
    ✅ MIGRATED: Using RentalHub DB
    """
    sql = """
        SELECT 
            p.product_id, p.sku, p.name, p.description, p.price, 
            p.image_url, p.status,
            p.category_id, p.category_name, p.subcategory_id, p.subcategory_name,
            p.quantity
        FROM products p
        WHERE p.status = 1
    """
    
    params = {}
    
    if query:
        sql += " AND (p.name LIKE :query OR p.sku LIKE :query OR p.description LIKE :query)"
        params['query'] = f"%{query}%"
    
    if category:
        sql += " AND (p.category_name LIKE :category OR p.subcategory_name LIKE :category)"
        params['category'] = f"%{category}%"
    
    if min_price is not None:
        sql += " AND p.price >= :min_price"
        params['min_price'] = min_price
    
    if max_price is not None:
        sql += " AND p.price <= :max_price"
        params['max_price'] = max_price
    
    if in_stock:
        sql += " AND p.quantity > 0"
    
    sql += f" ORDER BY p.name LIMIT {limit} OFFSET {offset}"
    
    result = db.execute(text(sql), params)
    
    products = []
    for row in result:
        quantity = row[11] or 0
        products.append({
            "product_id": row[0],
            "sku": row[1],
            "name": row[2],
            "description": row[3],
            "price": float(row[4]) if row[4] else 0.0,
            "image": row[5],
            "status": row[6],
            "category_id": row[7],
            "category": row[8],
            "category_name": row[8],
            "subcategory_id": row[9],
            "subcategory": row[10],
            "subcategory_name": row[10],
            "quantity": quantity,
            "inventory_quantity": quantity,
            "in_stock": quantity > 0
        })
    
    # Count total
    count_sql = """
        SELECT COUNT(*) FROM products p
        WHERE p.status = 1
    """
    
    if query:
        count_sql += " AND (p.name LIKE :query OR p.sku LIKE :query OR p.description LIKE :query)"
    if category:
        count_sql += " AND (p.category_name LIKE :category OR p.subcategory_name LIKE :category)"
    if min_price is not None:
        count_sql += " AND p.price >= :min_price"
    if max_price is not None:
        count_sql += " AND p.price <= :max_price"
    if in_stock:
        count_sql += " AND (i.quantity > 0 OR p.quantity > 0)"
    
    total_result = db.execute(text(count_sql), params)
    total = total_result.scalar()
    
    return {
        "products": products,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/product/{product_id}")
async def get_extended_product_info(
    product_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Повна інформація про товар включаючи резервації
    ✅ MIGRATED: Using RentalHub DB
    """
    # Product details
    result = db.execute(text("""
        SELECT 
            p.product_id, p.sku, p.name, p.description, p.price, 
            p.image_url, p.status,
            p.category_id, p.category_name, p.subcategory_id, p.subcategory_name,
            p.quantity, p.zone, p.aisle, p.shelf,
            p.cleaning_status, p.product_state
        FROM products p
        WHERE p.product_id = :product_id
    """), {"product_id": product_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Get active orders with this product
    orders_result = db.execute(text("""
        SELECT DISTINCT o.order_id, o.order_number, o.rental_start_date, o.rental_end_date
        FROM orders o
        WHERE o.order_id IN (
            SELECT DISTINCT order_id FROM issue_cards
        )
        AND o.status NOT IN ('cancelled', 'returned')
        LIMIT 10
    """))
    
    active_orders = []
    for o_row in orders_result:
        active_orders.append({
            "order_id": o_row[0],
            "order_number": o_row[1],
            "start_date": o_row[2].isoformat() if o_row[2] else None,
            "end_date": o_row[3].isoformat() if o_row[3] else None
        })
    
    return {
        "product_id": row[0],
        "sku": row[1],
        "name": row[2],
        "description": row[3],
        "price": float(row[4]) if row[4] else 0.0,
        "image": row[5],
        "status": row[6],
        "category_id": row[7],
        "category": row[8],
        "category_name": row[8],
        "subcategory_id": row[9],
        "subcategory": row[10],
        "subcategory_name": row[10],
        "quantity": row[11] or 0,
        "inventory": {
            "quantity": row[11] or 0,
            "zone": row[12],
            "aisle": row[13],
            "shelf": row[14],
            "cleaning_status": row[15],
            "product_state": row[16]
        },
        "active_orders": active_orders
    }

@router.put("/product/{product_id}")
async def update_extended_product(
    product_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити розширену інформацію про товар
    ✅ MIGRATED: Using RentalHub DB
    """
    # Check exists
    result = db.execute(text("SELECT product_id FROM products WHERE product_id = :id"), {"id": product_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Update product
    set_clauses = []
    params = {"product_id": product_id}
    
    for field in ['name', 'description', 'price', 'quantity', 'status', 'sku']:
        if field in data:
            set_clauses.append(f"{field} = :{field}")
            params[field] = data[field]
    
    if set_clauses:
        sql = f"UPDATE products SET {', '.join(set_clauses)} WHERE product_id = :product_id"
        db.execute(text(sql), params)
        db.commit()
    
    return {"message": "Product updated", "product_id": product_id}

@router.post("/product/{product_id}/inventory")
async def update_product_inventory(
    product_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити інвентар товару
    ✅ MIGRATED: Using RentalHub DB
    """
    # Update product fields directly (inventory merged into products)
    set_clauses = []
    params = {"product_id": product_id}
    
    for field in ['quantity', 'zone', 'aisle', 'shelf', 'cleaning_status', 'product_state']:
        if field in data:
            set_clauses.append(f"{field} = :{field}")
            params[field] = data[field]
    
    if set_clauses:
        sql = f"UPDATE products SET {', '.join(set_clauses)} WHERE product_id = :product_id"
        db.execute(text(sql), params)
    
    db.commit()
    return {"message": "Inventory updated", "product_id": product_id}
