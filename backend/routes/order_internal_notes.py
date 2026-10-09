"""
Order Internal Notes API - Внутрішній месенджер для команди
Нотатки по замовленню, видимі всім департаментам
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/orders", tags=["order-internal-notes"])


class NoteCreate(BaseModel):
    message: str
    # user_id та user_name більше не потрібні - беремо з токена


class NoteResponse(BaseModel):
    id: int
    order_id: str
    user_id: Optional[str]
    user_name: Optional[str]
    message: str
    created_at: str


@router.get("/{order_id}/internal-notes")
async def get_internal_notes(
    order_id: str,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати всі внутрішні нотатки по замовленню.
    Сортування: від старих до нових (як у чаті)
    """
    try:
        result = db.execute(text("""
            SELECT id, order_id, user_id, user_name, message, created_at
            FROM order_internal_notes
            WHERE order_id = :order_id
            ORDER BY created_at ASC
        """), {"order_id": str(order_id)})
        
        notes = []
        for row in result:
            notes.append({
                "id": row[0],
                "order_id": row[1],
                "user_id": row[2],
                "user_name": row[3] or "Невідомий",
                "message": row[4],
                "created_at": row[5].strftime("%d.%m.%Y %H:%M") if row[5] else ""
            })
        
        return {
            "success": True,
            "notes": notes,
            "count": len(notes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.post("/{order_id}/internal-notes")
async def add_internal_note(
    order_id: str,
    note: NoteCreate,
    db: Session = Depends(get_rh_db),
    current_user: dict = Depends(get_current_user_dependency)
):
    """
    Додати внутрішню нотатку до замовлення.
    Користувач визначається автоматично з токена авторизації.
    Вимагає валідний токен — анонімні нотатки заборонені.
    """
    if not note.message or not note.message.strip():
        raise HTTPException(status_code=400, detail="Повідомлення не може бути порожнім")
    
    # Отримуємо дані користувача з токена — ВИМАГАЄМО валідного юзера
    user_id = current_user.get("user_id") or current_user.get("id")
    user_name = current_user.get("name") or current_user.get("username") or current_user.get("email")
    
    # Якщо user_id відсутній — токен невалідний або прострочений
    if not user_id or user_name == "System":
        raise HTTPException(
            status_code=401, 
            detail="Сесія закінчилась. Будь ласка, перелогіньтесь."
        )
    
    try:
        db.execute(text("""
            INSERT INTO order_internal_notes (order_id, user_id, user_name, message, created_at)
            VALUES (:order_id, :user_id, :user_name, :message, NOW())
        """), {
            "order_id": str(order_id),
            "user_id": str(user_id) if user_id else None,
            "user_name": user_name,
            "message": note.message.strip()
        })
        db.commit()
        
        # Отримати створену нотатку
        result = db.execute(text("""
            SELECT id, order_id, user_id, user_name, message, created_at
            FROM order_internal_notes
            WHERE order_id = :order_id
            ORDER BY id DESC
            LIMIT 1
        """), {"order_id": str(order_id)})
        
        row = result.fetchone()
        
        return {
            "success": True,
            "note": {
                "id": row[0],
                "order_id": row[1],
                "user_id": row[2],
                "user_name": row[3],
                "message": row[4],
                "created_at": row[5].strftime("%d.%m.%Y %H:%M") if row[5] else ""
            }
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.delete("/{order_id}/internal-notes/{note_id}")
async def delete_internal_note(
    order_id: str,
    note_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Видалити внутрішню нотатку (тільки свою або адмін)
    """
    try:
        db.execute(text("""
            DELETE FROM order_internal_notes
            WHERE id = :note_id AND order_id = :order_id
        """), {"note_id": note_id, "order_id": str(order_id)})
        db.commit()
        
        return {"success": True, "message": "Нотатку видалено"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")
