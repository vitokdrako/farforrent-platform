"""
Damages API — LEGACY обгортка
Тепер все працює через product_damage_history.
Цей файл зберігає зворотну сумісність для старих API клієнтів.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/damages", tags=["damages-legacy"])


@router.get("")
async def get_damages(
    status: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Отримати кейси шкоди з product_damage_history"""
    sql = """
        SELECT id, product_id, sku, product_name, order_id, order_number,
               processing_type, processing_status, qty, processed_qty,
               estimate_value, note, created_at, source, created_by
        FROM product_damage_history
        WHERE processing_type IN ('wash', 'restoration', 'laundry')
    """
    params = {}
    
    if status == 'open':
        sql += " AND COALESCE(processing_status, '') NOT IN ('completed', 'returned_to_stock', 'hidden', 'deleted')"
    elif status == 'closed':
        sql += " AND processing_status IN ('completed', 'returned_to_stock')"
    
    sql += " ORDER BY created_at DESC"
    
    result = db.execute(text(sql), params)
    cases = []
    for r in result:
        cases.append({
            "id": r[0],
            "product_id": r[1],
            "sku": r[2],
            "product_name": r[3],
            "order_id": r[4],
            "order_number": r[5],
            "case_status": "open" if r[7] not in ('completed', 'returned_to_stock') else "closed",
            "severity": "minor",
            "processing_type": r[6],
            "processing_status": r[7],
            "qty": r[8],
            "estimate_value": float(r[10]) if r[10] else 0,
            "notes": r[11],
            "created_at": r[12].isoformat() if r[12] else None,
            "source": r[13],
            "created_by": r[14]
        })
    
    return cases


@router.get("/{case_id}")
async def get_damage_case(case_id: str, db: Session = Depends(get_rh_db)):
    """Отримати один кейс"""
    result = db.execute(text("""
        SELECT id, product_id, sku, product_name, order_id, order_number,
               processing_type, processing_status, qty, processed_qty,
               estimate_value, note, created_at, source, created_by, photo_url
        FROM product_damage_history WHERE id = :id
    """), {"id": case_id}).fetchone()
    
    if not result:
        raise HTTPException(status_code=404, detail="Not found")
    
    return {
        "id": result[0],
        "product_id": result[1],
        "sku": result[2],
        "product_name": result[3],
        "order_id": result[4],
        "order_number": result[5],
        "processing_type": result[6],
        "processing_status": result[7],
        "qty": result[8],
        "processed_qty": result[9],
        "estimate_value": float(result[10]) if result[10] else 0,
        "note": result[11],
        "created_at": result[12].isoformat() if result[12] else None,
        "source": result[13],
        "created_by": result[14],
        "photo_url": result[15],
        "items": []
    }
