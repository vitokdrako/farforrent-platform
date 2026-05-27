"""
Bulk Product Editor API - масове редагування продуктів
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database_rentalhub import get_rh_db
from typing import Optional
from pydantic import BaseModel
import json

router = APIRouter(prefix="/api/admin/bulk-products", tags=["bulk-products"])


@router.get("")
async def list_products_bulk(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=10, le=200),
    search: Optional[str] = None,
    category: Optional[str] = None,
    color: Optional[str] = None,
    shape: Optional[str] = None,
    product_state: Optional[str] = None,
    missing: Optional[str] = None,  # "color", "size", "photo", "price", "dimensions"
    db: Session = Depends(get_rh_db)
):
    """Список продуктів для масового редагування з фільтрами та пагінацією"""
    
    conditions = []
    params = {}
    
    if search:
        conditions.append("(p.name LIKE :search OR p.sku LIKE :search OR CAST(p.product_id AS CHAR) LIKE :search)")
        params["search"] = f"%{search}%"
    
    if category:
        conditions.append("p.category_name = :category")
        params["category"] = category
    
    if color:
        conditions.append("p.color LIKE :color")
        params["color"] = f"%{color}%"
    
    if shape:
        conditions.append("p.shape = :shape")
        params["shape"] = shape
    
    if product_state:
        conditions.append("p.product_state = :product_state")
        params["product_state"] = product_state
    
    # Missing attributes filter
    if missing:
        missing_map = {
            "color": "(p.color IS NULL OR p.color = '')",
            "photo": "(p.image_url IS NULL OR p.image_url = '')",
            "price": "(p.rental_price IS NULL OR p.rental_price = 0)",
            "loss_price": "(p.price IS NULL OR p.price = 0)",
            "dimensions": "(p.height_cm IS NULL AND p.width_cm IS NULL AND p.depth_cm IS NULL AND p.diameter_cm IS NULL)",
            "shape": "(p.shape IS NULL OR p.shape = '')",
            "material": "(p.material IS NULL OR p.material = '')",
            "category": "(p.category_name IS NULL OR p.category_name = '')",
            "sku": "(p.sku IS NULL OR p.sku = '')",
        }
        if missing in missing_map:
            conditions.append(missing_map[missing])
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    # Count total
    count_sql = f"SELECT COUNT(*) FROM products p WHERE {where_clause}"
    total = db.execute(text(count_sql), params).scalar()
    
    # Fetch page
    offset = (page - 1) * per_page
    params["limit"] = per_page
    params["offset"] = offset
    
    data_sql = f"""
        SELECT p.product_id, p.sku, p.name, p.category_name, p.subcategory_name,
               p.color, p.material, p.size, p.shape,
               p.price, p.rental_price, p.quantity, p.status,
               p.image_url, p.zone, p.aisle, p.shelf,
               p.cleaning_status, p.product_state,
               p.height_cm, p.width_cm, p.depth_cm, p.diameter_cm,
               p.description, p.care_instructions, p.hashtags,
               p.family_id, p.frozen_quantity, p.in_laundry
        FROM products p
        WHERE {where_clause}
        ORDER BY p.product_id DESC
        LIMIT :limit OFFSET :offset
    """
    
    rows = db.execute(text(data_sql), params).fetchall()
    
    products = []
    for r in rows:
        hashtags_val = r[25]
        if isinstance(hashtags_val, str):
            try:
                hashtags_val = json.loads(hashtags_val)
            except Exception:
                hashtags_val = []
        
        products.append({
            "product_id": r[0],
            "sku": r[1] or "",
            "name": r[2] or "",
            "category_name": r[3] or "",
            "subcategory_name": r[4] or "",
            "color": r[5] or "",
            "material": r[6] or "",
            "size": r[7] or "",
            "shape": r[8] or "",
            "price": float(r[9]) if r[9] else 0,
            "rental_price": float(r[10]) if r[10] else 0,
            "quantity": r[11] or 0,
            "status": r[12],
            "image_url": r[13] or "",
            "zone": r[14] or "",
            "aisle": r[15] or "",
            "shelf": r[16] or "",
            "cleaning_status": r[17] or "",
            "product_state": r[18] or "",
            "height_cm": float(r[19]) if r[19] else None,
            "width_cm": float(r[20]) if r[20] else None,
            "depth_cm": float(r[21]) if r[21] else None,
            "diameter_cm": float(r[22]) if r[22] else None,
            "description": r[23] or "",
            "care_instructions": r[24] or "",
            "hashtags": hashtags_val or [],
            "family_id": r[26],
            "frozen_quantity": r[27] or 0,
            "in_laundry": r[28] or 0,
        })
    
    return {
        "products": products,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": (total + per_page - 1) // per_page,
    }


@router.get("/filters")
async def get_filter_options(db: Session = Depends(get_rh_db)):
    """Отримати доступні опції для фільтрів"""
    
    categories = db.execute(text(
        "SELECT DISTINCT category_name FROM products WHERE category_name IS NOT NULL AND category_name != '' ORDER BY category_name"
    )).fetchall()
    
    # Get base colors (first color before comma)
    colors_raw = db.execute(text(
        "SELECT DISTINCT color FROM products WHERE color IS NOT NULL AND color != '' ORDER BY color"
    )).fetchall()
    
    # Extract unique base colors
    base_colors = set()
    for r in colors_raw:
        parts = [c.strip() for c in r[0].split(",")]
        for p in parts:
            if p:
                base_colors.add(p)
    
    shapes = db.execute(text(
        "SELECT DISTINCT shape FROM products WHERE shape IS NOT NULL AND shape != '' ORDER BY shape"
    )).fetchall()
    
    states = db.execute(text(
        "SELECT DISTINCT product_state FROM products WHERE product_state IS NOT NULL AND product_state != '' ORDER BY product_state"
    )).fetchall()
    
    # Count missing attributes
    missing_counts = {}
    for attr, cond in [
        ("color", "(color IS NULL OR color = '')"),
        ("photo", "(image_url IS NULL OR image_url = '')"),
        ("price", "(rental_price IS NULL OR rental_price = 0)"),
        ("loss_price", "(price IS NULL OR price = 0)"),
        ("dimensions", "(height_cm IS NULL AND width_cm IS NULL AND depth_cm IS NULL AND diameter_cm IS NULL)"),
        ("shape", "(shape IS NULL OR shape = '')"),
        ("material", "(material IS NULL OR material = '')"),
        ("sku", "(sku IS NULL OR sku = '')"),
    ]:
        count = db.execute(text(f"SELECT COUNT(*) FROM products WHERE {cond}")).scalar()
        if count > 0:
            missing_counts[attr] = count
    
    return {
        "categories": [r[0] for r in categories],
        "colors": sorted(base_colors),
        "shapes": [r[0] for r in shapes],
        "states": [r[0] for r in states],
        "missing_counts": missing_counts,
    }


class BulkProductUpdate(BaseModel):
    name: Optional[str] = None
    sku: Optional[str] = None
    category_name: Optional[str] = None
    color: Optional[str] = None
    material: Optional[str] = None
    size: Optional[str] = None
    shape: Optional[str] = None
    price: Optional[float] = None
    rental_price: Optional[float] = None
    quantity: Optional[int] = None
    zone: Optional[str] = None
    aisle: Optional[str] = None
    shelf: Optional[str] = None
    product_state: Optional[str] = None
    cleaning_status: Optional[str] = None
    height_cm: Optional[float] = None
    width_cm: Optional[float] = None
    depth_cm: Optional[float] = None
    diameter_cm: Optional[float] = None
    description: Optional[str] = None
    care_instructions: Optional[str] = None
    hashtags: Optional[list] = None


@router.patch("/{product_id}")
async def update_product_bulk(
    product_id: int,
    data: BulkProductUpdate,
    db: Session = Depends(get_rh_db)
):
    """Оновити один продукт (інлайн редагування)"""
    
    # Check product exists
    exists = db.execute(text("SELECT product_id FROM products WHERE product_id = :pid"), {"pid": product_id}).fetchone()
    if not exists:
        raise HTTPException(status_code=404, detail="Продукт не знайдено")
    
    update_fields = []
    params = {"pid": product_id}
    
    update_data = data.dict(exclude_unset=True)
    
    allowed_fields = [
        "name", "sku", "category_name", "color", "material", "size", "shape",
        "price", "rental_price", "quantity", "zone", "aisle", "shelf",
        "product_state", "cleaning_status", "height_cm", "width_cm",
        "depth_cm", "diameter_cm", "description", "care_instructions"
    ]
    
    for field in allowed_fields:
        if field in update_data:
            update_fields.append(f"{field} = :{field}")
            params[field] = update_data[field]
    
    # Handle hashtags specially (JSON column)
    if "hashtags" in update_data:
        update_fields.append("hashtags = :hashtags")
        params["hashtags"] = json.dumps(update_data["hashtags"], ensure_ascii=False) if update_data["hashtags"] else None
    
    if not update_fields:
        raise HTTPException(status_code=400, detail="Немає полів для оновлення")
    
    sql = f"UPDATE products SET {', '.join(update_fields)} WHERE product_id = :pid"
    db.execute(text(sql), params)
    db.commit()
    
    return {"ok": True, "product_id": product_id, "updated_fields": list(update_data.keys())}
