"""
Products API - Створення та управління товарами
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
import uuid
import os
import base64

from database_rentalhub import get_rh_db  # RentalHub DB
from utils.image_helper import normalize_image_url

router = APIRouter(prefix="/api/products", tags=["products"])

# Директорія для збереження фото
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "products")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload-image")
async def upload_product_image(
    file: UploadFile = File(...)
):
    """
    Завантажити фото товару
    """
    try:
        # Перевірити тип файлу
        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Дозволені тільки зображення: JPG, PNG, WEBP"
            )
        
        # Перевірити розмір (макс 5MB)
        contents = await file.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(
                status_code=400,
                detail="Розмір файлу не повинен перевищувати 5MB"
            )
        
        # Генерувати унікальне ім'я файлу
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'jpg'
        unique_filename = f"{uuid.uuid4().hex[:12]}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        # Зберегти файл
        with open(file_path, 'wb') as f:
            f.write(contents)
        
        # Повернути шлях для збереження в базі
        relative_path = f"uploads/products/{unique_filename}"
        
        return {
            'success': True,
            'filename': unique_filename,
            'path': relative_path,
            'url': f"/uploads/products/{unique_filename}",
            'size': len(contents)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка завантаження фото: {str(e)}"
        )


@router.post("/create")
async def create_product(
    data: dict,
    rh_db: Session = Depends(get_rh_db)  # ✅ Тільки RentalHub DB!
):
    """
    Створити новий товар через кабінет переобліку
    ✅ Записує ТІЛЬКИ в RentalHub products таблицю
    ⚠️ НЕ пише в OpenCart - читаємо звідти тільки через sync.py
    """
    try:
        # Генеруємо унікальний product_id (не конфліктує з OpenCart)
        # Використовуємо великі числа щоб не перетиналось з OpenCart
        result = rh_db.execute(text("SELECT COALESCE(MAX(product_id), 10000) + 1 as next_id FROM products"))
        product_id = result.fetchone()[0]
        
        sku = data.get('sku', f"RH-{product_id}")
        
        # ✅ СТВОРИТИ ЗАПИС В RENTALHUB PRODUCTS (єдина таблиця!)
        product_insert_rh = text("""
            INSERT INTO products (
                product_id, sku, name, 
                category_name, subcategory_name,
                price, quantity, status,
                image_url, description,
                color, material, size,
                zone, aisle, shelf,
                cleaning_status, product_state,
                last_audit_date
            )
            VALUES (
                :product_id, :sku, :name,
                :category, :subcategory,
                :price, :quantity, 1,
                :image, :description,
                :color, :material, :size,
                :zone, :aisle, :shelf,
                'clean', 'good',
                CURDATE()
            )
        """)
        
        # Розбити локацію
        location = data.get('location', '')
        location_parts = location.split('/')
        aisle = location_parts[0].strip() if len(location_parts) > 0 else ''
        shelf = location_parts[1].strip() if len(location_parts) > 1 else ''
        
        rh_db.execute(product_insert_rh, {
            'product_id': product_id,
            'sku': sku,
            'name': data.get('name', 'Новий товар'),
            'category': data.get('category', ''),
            'subcategory': data.get('subcategory', ''),
            'price': data.get('price', 0),
            'quantity': data.get('quantity', 1),
            'image': data.get('image', ''),
            'description': data.get('description', ''),
            'color': data.get('color', ''),
            'material': data.get('material', ''),
            'size': data.get('size', ''),
            'zone': data.get('location_zone', ''),
            'aisle': aisle,
            'shelf': shelf
        })
        
        # Commit змін ТІЛЬКИ в RentalHub DB
        rh_db.commit()
        
        return {
            'success': True,
            'product_id': product_id,
            'item_id': f'A-{product_id}',
            'message': f'Товар "{data.get("name")}" створено та переоблікований'
        }
        
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка створення товару: {str(e)}"
        )


@router.get("/categories")
async def get_categories(
    db: Session = Depends(get_rh_db)
):
    """
    ✅ MIGRATED: Отримати список категорій з RentalHub DB
    """
    try:
        # ✅ NEW: Get categories from snapshot table
        result = db.execute(text("""
            SELECT DISTINCT name
            FROM categories
            WHERE parent_id = 0 AND status = 1
            ORDER BY name
        """))
        
        categories = [row[0] for row in result if row[0]]
        
        return {'categories': categories}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.get("/{sku}")
async def get_product_by_sku(
    sku: str,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати товар за SKU для переобліку
    """
    try:
        result = db.execute(text("""
            SELECT product_id, sku, name, price, rental_price, quantity,
                   status, zone, aisle, shelf, cleaning_status, product_state, image_url
            FROM products
            WHERE sku = :sku OR product_id = :sku
            LIMIT 1
        """), {"sku": sku})
        
        row = result.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="Товар не знайдено")
        
        image_url = normalize_image_url(row[12])
            
        return {
            "product_id": row[0],
            "sku": row[1],
            "name": row[2],
            "price": float(row[3]) if row[3] else 0.0,
            "rental_price": float(row[4]) if row[4] else 0.0,
            "quantity": row[5] or 0,
            "status": row[6],
            "zone": row[7],
            "aisle": row[8],
            "shelf": row[9],
            "cleaning_status": row[10],
            "product_state": row[11],
            "image_url": image_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )


@router.post("/inventory/recount")
async def save_inventory_recount(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Зберегти результат переобліку товару
    """
    try:
        recount_id = str(uuid.uuid4())
        
        # Зберегти в таблицю inventory_recounts
        db.execute(text("""
            INSERT INTO inventory_recounts (
                id, sku, product_id, status, notes, 
                damage_type, severity, timestamp, created_at
            ) VALUES (
                :id, :sku, :product_id, :status, :notes,
                :damage_type, :severity, :timestamp, NOW()
            )
        """), {
            "id": recount_id,
            "sku": data.get("sku"),
            "product_id": data.get("product_id"),
            "status": data.get("status"),
            "notes": data.get("notes"),
            "damage_type": data.get("damage_type"),
            "severity": data.get("severity"),
            "timestamp": data.get("timestamp")
        })
        
        db.commit()
        
        return {
            "success": True,
            "recount_id": recount_id,
            "message": "Переобік успішно збережено"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка збереження: {str(e)}"
        )


@router.post("/inventory/recounts/batch")
async def get_recounts_batch(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати останні переобліки для списку SKU
    """
    try:
        skus = data.get("skus", [])
        if not skus:
            return []
        
        # Отримати останній переобік для кожного SKU
        placeholders = ",".join([f":sku{i}" for i in range(len(skus))])
        params = {f"sku{i}": sku for i, sku in enumerate(skus)}
        
        result = db.execute(text(f"""
            SELECT ir1.sku, ir1.status, ir1.notes, ir1.damage_type, ir1.severity, ir1.timestamp
            FROM inventory_recounts ir1
            INNER JOIN (
                SELECT sku, MAX(timestamp) as max_timestamp
                FROM inventory_recounts
                WHERE sku IN ({placeholders})
                GROUP BY sku
            ) ir2 ON ir1.sku = ir2.sku AND ir1.timestamp = ir2.max_timestamp
        """), params)
        
        recounts = []
        for row in result:
            recounts.append({
                "sku": row[0],
                "status": row[1],
                "notes": row[2],
                "damage_type": row[3],
                "severity": row[4],
                "timestamp": row[5].isoformat() if row[5] else None
            })
        
        return recounts
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка: {str(e)}"
        )



@router.get("/search")
async def search_products(
    q: str,
    category: str = None,
    limit: int = 20,
    db: Session = Depends(get_rh_db)
):
    """
    Пошук товарів за назвою, SKU або категорією
    """
    try:
        sql = """
            SELECT 
                product_id, sku, name, category_name, quantity, price
            FROM products
            WHERE (name LIKE :query OR sku LIKE :query)
        """
        
        params = {"query": f"%{q}%"}
        
        if category:
            sql += " AND category_name = :category"
            params["category"] = category
        
        sql += " ORDER BY name LIMIT :limit"
        params["limit"] = limit
        
        result = db.execute(text(sql), params)
        
        products = []
        for row in result:
            products.append({
                "product_id": row[0],
                "sku": row[1],
                "name": row[2],
                "category_name": row[3],
                "quantity": row[4] or 0,
                "price": float(row[5]) if row[5] else 0.0
            })
        
        return products
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Помилка пошуку: {str(e)}"
        )

