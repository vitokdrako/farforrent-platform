"""
Product Sets API - Керування наборами товарів
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database_rentalhub import get_rh_db
from uuid import uuid4

router = APIRouter(prefix="/api/product-sets", tags=["product-sets"])


@router.get("")
async def get_sets(
    is_active: bool = None,
    db: Session = Depends(get_rh_db)
):
    """Отримати всі набори з товарами"""
    try:
        # Базовий запит
        sql = """
            SELECT 
                ps.id, ps.name, ps.description, ps.image_url, 
                ps.set_price, ps.is_active, ps.created_at
            FROM product_sets ps
            WHERE 1=1
        """
        params = {}
        
        if is_active is not None:
            sql += " AND ps.is_active = :is_active"
            params['is_active'] = is_active
        
        sql += " ORDER BY ps.created_at DESC"
        
        result = db.execute(text(sql), params)
        sets = []
        
        for row in result:
            set_id = row[0]
            
            # Отримати товари набору
            items_result = db.execute(text("""
                SELECT 
                    psi.id, psi.product_id, psi.quantity,
                    p.sku, p.name, p.rental_price, p.image_url,
                    p.category_name, p.color, p.material
                FROM product_set_items psi
                JOIN products p ON psi.product_id = p.product_id
                WHERE psi.set_id = :set_id
                ORDER BY p.name
            """), {"set_id": set_id})
            
            items = []
            total_price = 0
            for item_row in items_result:
                item_price = float(item_row[5] or 0) * item_row[2]
                total_price += item_price
                items.append({
                    "id": item_row[0],
                    "product_id": item_row[1],
                    "quantity": item_row[2],
                    "sku": item_row[3],
                    "name": item_row[4],
                    "rental_price": float(item_row[5] or 0),
                    "image": item_row[6],
                    "category": item_row[7],
                    "color": item_row[8],
                    "material": item_row[9],
                    "subtotal": item_price
                })
            
            sets.append({
                "id": set_id,
                "name": row[1],
                "description": row[2],
                "image_url": row[3],
                "set_price": float(row[4]) if row[4] else None,
                "calculated_price": total_price,
                "final_price": float(row[4]) if row[4] else total_price,
                "is_active": bool(row[5]),
                "created_at": str(row[6]) if row[6] else None,
                "items": items,
                "items_count": len(items)
            })
        
        return {"sets": sets, "total": len(sets)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.get("/{set_id}")
async def get_set(
    set_id: str,
    db: Session = Depends(get_rh_db)
):
    """Отримати один набір з деталями"""
    try:
        result = db.execute(text("""
            SELECT id, name, description, image_url, set_price, is_active, created_at
            FROM product_sets WHERE id = :set_id
        """), {"set_id": set_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Набір не знайдено")
        
        # Отримати товари
        items_result = db.execute(text("""
            SELECT 
                psi.id, psi.product_id, psi.quantity,
                p.sku, p.name, p.rental_price, p.image_url,
                p.category_name, p.color, p.material, p.quantity as stock
            FROM product_set_items psi
            JOIN products p ON psi.product_id = p.product_id
            WHERE psi.set_id = :set_id
        """), {"set_id": set_id})
        
        items = []
        total_price = 0
        for item_row in items_result:
            item_price = float(item_row[5] or 0) * item_row[2]
            total_price += item_price
            items.append({
                "id": item_row[0],
                "product_id": item_row[1],
                "quantity": item_row[2],
                "sku": item_row[3],
                "name": item_row[4],
                "rental_price": float(item_row[5] or 0),
                "image": item_row[6],
                "category": item_row[7],
                "color": item_row[8],
                "material": item_row[9],
                "stock": item_row[10],
                "subtotal": item_price
            })
        
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "image_url": row[3],
            "set_price": float(row[4]) if row[4] else None,
            "calculated_price": total_price,
            "final_price": float(row[4]) if row[4] else total_price,
            "is_active": bool(row[5]),
            "created_at": str(row[6]) if row[6] else None,
            "items": items
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("")
async def create_set(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Створити новий набір
    Body: { name, description?, image_url?, set_price?, items: [{product_id, quantity}] }
    """
    try:
        set_id = str(uuid4())
        name = data.get("name")
        
        if not name:
            raise HTTPException(status_code=400, detail="Назва набору обов'язкова")
        
        # Створити набір
        db.execute(text("""
            INSERT INTO product_sets (id, name, description, image_url, set_price, is_active)
            VALUES (:id, :name, :description, :image_url, :set_price, TRUE)
        """), {
            "id": set_id,
            "name": name,
            "description": data.get("description"),
            "image_url": data.get("image_url"),
            "set_price": data.get("set_price")
        })
        
        # Додати товари
        items = data.get("items", [])
        for item in items:
            db.execute(text("""
                INSERT INTO product_set_items (id, set_id, product_id, quantity)
                VALUES (:id, :set_id, :product_id, :quantity)
            """), {
                "id": str(uuid4()),
                "set_id": set_id,
                "product_id": item.get("product_id"),
                "quantity": item.get("quantity", 1)
            })
        
        db.commit()
        
        return {"success": True, "id": set_id, "message": "Набір створено"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.put("/{set_id}")
async def update_set(
    set_id: str,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити набір
    Body: { name?, description?, image_url?, set_price?, is_active?, items?: [{product_id, quantity}] }
    """
    try:
        # Перевірити що набір існує
        result = db.execute(text("SELECT id FROM product_sets WHERE id = :id"), {"id": set_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Набір не знайдено")
        
        # Оновити основні поля
        updates = []
        params = {"id": set_id}
        
        if "name" in data:
            updates.append("name = :name")
            params["name"] = data["name"]
        if "description" in data:
            updates.append("description = :description")
            params["description"] = data["description"]
        if "image_url" in data:
            updates.append("image_url = :image_url")
            params["image_url"] = data["image_url"]
        if "set_price" in data:
            updates.append("set_price = :set_price")
            params["set_price"] = data["set_price"]
        if "is_active" in data:
            updates.append("is_active = :is_active")
            params["is_active"] = data["is_active"]
        
        if updates:
            sql = f"UPDATE product_sets SET {', '.join(updates)} WHERE id = :id"
            db.execute(text(sql), params)
        
        # Оновити товари якщо передані
        if "items" in data:
            # Видалити старі
            db.execute(text("DELETE FROM product_set_items WHERE set_id = :set_id"), {"set_id": set_id})
            
            # Додати нові
            for item in data["items"]:
                db.execute(text("""
                    INSERT INTO product_set_items (id, set_id, product_id, quantity)
                    VALUES (:id, :set_id, :product_id, :quantity)
                """), {
                    "id": str(uuid4()),
                    "set_id": set_id,
                    "product_id": item.get("product_id"),
                    "quantity": item.get("quantity", 1)
                })
        
        db.commit()
        
        return {"success": True, "message": "Набір оновлено"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.delete("/{set_id}")
async def delete_set(
    set_id: str,
    db: Session = Depends(get_rh_db)
):
    """Видалити набір"""
    try:
        result = db.execute(text("SELECT id FROM product_sets WHERE id = :id"), {"id": set_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Набір не знайдено")
        
        db.execute(text("DELETE FROM product_sets WHERE id = :id"), {"id": set_id})
        db.commit()
        
        return {"success": True, "message": "Набір видалено"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("/{set_id}/items")
async def add_item_to_set(
    set_id: str,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Додати товар до набору
    Body: { product_id, quantity? }
    """
    try:
        product_id = data.get("product_id")
        quantity = data.get("quantity", 1)
        
        if not product_id:
            raise HTTPException(status_code=400, detail="product_id обов'язковий")
        
        # Перевірити що набір існує
        result = db.execute(text("SELECT id FROM product_sets WHERE id = :id"), {"id": set_id})
        if not result.fetchone():
            raise HTTPException(status_code=404, detail="Набір не знайдено")
        
        # Перевірити чи товар вже є в наборі
        existing = db.execute(text("""
            SELECT id FROM product_set_items 
            WHERE set_id = :set_id AND product_id = :product_id
        """), {"set_id": set_id, "product_id": product_id}).fetchone()
        
        if existing:
            # Оновити кількість
            db.execute(text("""
                UPDATE product_set_items SET quantity = quantity + :quantity
                WHERE set_id = :set_id AND product_id = :product_id
            """), {"set_id": set_id, "product_id": product_id, "quantity": quantity})
        else:
            # Додати новий
            db.execute(text("""
                INSERT INTO product_set_items (id, set_id, product_id, quantity)
                VALUES (:id, :set_id, :product_id, :quantity)
            """), {
                "id": str(uuid4()),
                "set_id": set_id,
                "product_id": product_id,
                "quantity": quantity
            })
        
        db.commit()
        
        return {"success": True, "message": "Товар додано до набору"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.delete("/{set_id}/items/{product_id}")
async def remove_item_from_set(
    set_id: str,
    product_id: int,
    db: Session = Depends(get_rh_db)
):
    """Видалити товар з набору"""
    try:
        db.execute(text("""
            DELETE FROM product_set_items 
            WHERE set_id = :set_id AND product_id = :product_id
        """), {"set_id": set_id, "product_id": product_id})
        db.commit()
        
        return {"success": True, "message": "Товар видалено з набору"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")
