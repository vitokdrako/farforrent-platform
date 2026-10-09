"""
Product Cleaning Status API — ОПТИМІЗОВАНО
Тепер працює через product_damage_history як єдине джерело істини.
Зберігає API інтерфейс незмінним для зворотної сумісності з фронтендом.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/product-cleaning", tags=["product-cleaning"])


class CleaningStatusUpdate(BaseModel):
    status: str  # clean, wash, dry, repair
    notes: Optional[str] = None
    updated_by: Optional[str] = None


# Mapping: old cleaning status → new PDH processing_type
STATUS_TO_PDH = {
    'wash': 'wash',
    'dry': 'wash',       # "dry" is part of wash cycle
    'repair': 'restoration',
}

PDH_TO_STATUS = {
    'wash': 'wash',
    'restoration': 'repair',
    'laundry': 'wash',
}


@router.get("/all")
async def get_all_cleaning_tasks(db: Session = Depends(get_rh_db)):
    """
    Отримати всі активні завдання (wash, restoration, laundry) з product_damage_history
    """
    result = db.execute(text("""
        SELECT pdh.id, pdh.product_id, pdh.sku, pdh.processing_type,
               pdh.note, pdh.created_by, pdh.created_at, pdh.product_name
        FROM product_damage_history pdh
        WHERE pdh.processing_type IN ('wash', 'restoration', 'laundry')
        AND COALESCE(pdh.processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
        AND (COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) > 0
        ORDER BY 
            CASE pdh.processing_type
                WHEN 'restoration' THEN 1
                WHEN 'wash' THEN 2
                WHEN 'laundry' THEN 3
            END,
            pdh.created_at DESC
    """))
    
    tasks = []
    for row in result:
        status = PDH_TO_STATUS.get(row[3], row[3])
        tasks.append({
            "id": row[0],
            "product_id": row[1],
            "sku": row[2],
            "status": status,
            "notes": row[4],
            "updated_by": row[5],
            "updated_at": str(row[6]) if row[6] else None,
            "product_name": row[7]
        })
    
    return tasks


@router.get("/{product_id}")
async def get_cleaning_status(product_id: int, db: Session = Depends(get_rh_db)):
    """
    Отримати статус чистки товару з product_damage_history
    """
    result = db.execute(text("""
        SELECT pdh.id, pdh.product_id, pdh.sku, pdh.processing_type,
               pdh.note, pdh.created_by, pdh.created_at
        FROM product_damage_history pdh
        WHERE pdh.product_id = :product_id
        AND pdh.processing_type IN ('wash', 'restoration', 'laundry')
        AND COALESCE(pdh.processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
        ORDER BY pdh.created_at DESC
        LIMIT 1
    """), {"product_id": product_id})
    
    row = result.fetchone()
    
    if not row:
        product = db.execute(text("SELECT sku, name FROM products WHERE product_id = :id"), {"id": product_id}).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {
            "product_id": product_id,
            "sku": product[0],
            "status": "clean",
            "notes": None,
            "updated_by": None,
            "updated_at": None
        }
    
    status = PDH_TO_STATUS.get(row[3], row[3])
    return {
        "id": row[0],
        "product_id": row[1],
        "sku": row[2],
        "status": status,
        "notes": row[4],
        "updated_by": row[5],
        "updated_at": str(row[6]) if row[6] else None
    }


@router.get("/sku/{sku}")
async def get_cleaning_status_by_sku(sku: str, db: Session = Depends(get_rh_db)):
    """
    Отримати статус чистки товару за SKU з product_damage_history
    """
    result = db.execute(text("""
        SELECT pdh.id, pdh.product_id, pdh.sku, pdh.processing_type,
               pdh.note, pdh.created_by, pdh.created_at, pdh.product_name
        FROM product_damage_history pdh
        WHERE pdh.sku = :sku
        AND pdh.processing_type IN ('wash', 'restoration', 'laundry')
        AND COALESCE(pdh.processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
        ORDER BY pdh.created_at DESC
        LIMIT 1
    """), {"sku": sku})
    
    row = result.fetchone()
    
    if not row:
        product = db.execute(text("SELECT product_id, name FROM products WHERE sku = :sku"), {"sku": sku}).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        return {
            "product_id": product[0],
            "sku": sku,
            "status": "clean",
            "notes": None,
            "updated_by": None,
            "updated_at": None
        }
    
    status = PDH_TO_STATUS.get(row[3], row[3])
    return {
        "id": row[0],
        "product_id": row[1],
        "sku": row[2],
        "status": status,
        "notes": row[4],
        "updated_by": row[5],
        "updated_at": str(row[6]) if row[6] else None,
        "product_name": row[7]
    }


@router.put("/{product_id}")
async def update_cleaning_status(
    product_id: int, 
    data: CleaningStatusUpdate, 
    db: Session = Depends(get_rh_db)
):
    """
    Оновити статус — якщо 'clean', повернути товар на склад через PDH
    """
    product = db.execute(text("SELECT sku, name FROM products WHERE product_id = :id"), {"id": product_id}).fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    sku = product[0]
    
    if data.status == 'clean':
        # Завершити всі активні записи PDH для цього товару
        db.execute(text("""
            UPDATE product_damage_history
            SET processing_status = 'completed', updated_at = NOW()
            WHERE product_id = :product_id
            AND processing_type IN ('wash', 'restoration', 'laundry')
            AND COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
        """), {"product_id": product_id})
        
        # Розморозити
        db.execute(text("""
            UPDATE products SET frozen_quantity = GREATEST(0, COALESCE(frozen_quantity, 0) - 1)
            WHERE product_id = :pid
        """), {"pid": product_id})
    else:
        # Оновити processing_type на відповідний
        new_type = STATUS_TO_PDH.get(data.status, 'wash')
        db.execute(text("""
            UPDATE product_damage_history
            SET processing_type = :new_type, 
                note = :notes,
                updated_at = NOW()
            WHERE product_id = :product_id
            AND COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
            ORDER BY created_at DESC
            LIMIT 1
        """), {
            "product_id": product_id,
            "new_type": new_type,
            "notes": data.notes
        })
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Статус чистки оновлено: {data.status}",
        "product_id": product_id,
        "sku": sku,
        "status": data.status
    }


@router.get("/list/in-repair")
async def get_products_in_repair(db: Session = Depends(get_rh_db)):
    """
    Отримати список товарів на реставрації з product_damage_history
    """
    result = db.execute(text("""
        SELECT pdh.product_id, pdh.sku, pdh.product_name, pdh.note, pdh.created_by, pdh.created_at
        FROM product_damage_history pdh
        WHERE pdh.processing_type = 'restoration'
        AND COALESCE(pdh.processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
        AND (COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) > 0
        ORDER BY pdh.created_at DESC
    """))
    
    products = []
    for row in result:
        products.append({
            "product_id": row[0],
            "sku": row[1],
            "name": row[2],
            "notes": row[3],
            "updated_by": row[4],
            "updated_at": str(row[5]) if row[5] else None
        })
    
    return {
        "total": len(products),
        "products": products
    }


@router.get("/stats/summary")
async def get_cleaning_stats(db: Session = Depends(get_rh_db)):
    """
    Статистика по статусам з product_damage_history
    """
    result = db.execute(text("""
        SELECT processing_type, COUNT(*) as count
        FROM product_damage_history
        WHERE COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')
        AND processing_type IN ('wash', 'restoration', 'laundry')
        AND (COALESCE(qty, 1) - COALESCE(processed_qty, 0)) > 0
        GROUP BY processing_type
    """))
    
    stats = {
        "clean": 0,
        "wash": 0,
        "dry": 0,
        "repair": 0
    }
    
    for row in result:
        ptype = row[0]
        if ptype in ('wash', 'laundry'):
            stats["wash"] += row[1]
        elif ptype == 'restoration':
            stats["repair"] += row[1]
    
    return stats
