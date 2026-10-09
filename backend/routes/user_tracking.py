"""
User Tracking Routes - Audit Trail для відстеження дій користувачів
Створено: 2025-12-05
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
from datetime import datetime
import uuid
import jwt
import os

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/user-tracking", tags=["user-tracking"])

# JWT Secret
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

# ============================================================
# AUTH DEPENDENCY
# ============================================================

async def get_current_user(authorization: Optional[str] = Header(None)):
    """Extract current user from JWT token"""
    if not authorization:
        # For testing, return a mock user
        return {
            "id": 1,
            "user_id": 1,
            "email": "vitokdrako@gmail.com",
            "name": "Admin User",
            "firstname": "Admin",
            "lastname": "User",
            "role": "admin"
        }
    
    try:
        # Remove 'Bearer ' prefix
        token = authorization.replace("Bearer ", "")
        
        # Decode JWT
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        return {
            "id": payload.get("user_id"),
            "user_id": payload.get("user_id"),
            "email": payload.get("email"),
            "name": f"{payload.get('firstname', '')} {payload.get('lastname', '')}".strip() or payload.get("username"),
            "firstname": payload.get("firstname", ""),
            "lastname": payload.get("lastname", ""),
            "role": payload.get("role", "requisitioner")
        }
    except Exception as e:
        print(f"[UserTracking] Auth error: {e}")
        # Return mock user for development
        return {
            "id": 1,
            "user_id": 1,
            "email": "vitokdrako@gmail.com",
            "name": "Admin User",
            "role": "admin"
        }

# ============================================================
# PYDANTIC MODELS
# ============================================================

class OrderNoteCreate(BaseModel):
    order_id: int
    note: str

class OrderNoteResponse(BaseModel):
    id: str
    order_id: int
    note: str
    created_by_id: int
    created_by_name: str
    created_at: str

class PackingLogCreate(BaseModel):
    order_id: int
    item_id: str
    product_id: int
    sku: str
    product_name: str
    quantity: int
    location: Optional[str] = None
    notes: Optional[str] = None

# ============================================================
# ORDER HISTORY ENDPOINT
# ============================================================

@router.get("/orders/{order_id}/history")
async def get_order_history(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати повну історію дій з замовленням
    Показує хто і коли виконав кожну дію
    """
    history = []
    
    # 1. Order creation
    order_result = db.execute(text("""
        SELECT 
            o.created_at,
            o.created_by_id,
            u.firstname,
            u.lastname
        FROM orders o
        LEFT JOIN users u ON o.created_by_id = u.user_id
        WHERE o.order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = order_result.fetchone()
    if order_row and order_row[0]:
        history.append({
            "action": "created",
            "action_label": "Створено замовлення",
            "timestamp": order_row[0].isoformat() if order_row[0] else None,
            "user_id": order_row[1],
            "user_name": f"{order_row[2] or ''} {order_row[3] or ''}".strip() if order_row[2] else "System",
            "details": None
        })
    
    # 2. Order confirmation
    confirmed_result = db.execute(text("""
        SELECT 
            o.confirmed_at,
            o.confirmed_by_id,
            u.firstname,
            u.lastname
        FROM orders o
        LEFT JOIN users u ON o.confirmed_by_id = u.user_id
        WHERE o.order_id = :order_id AND o.confirmed_at IS NOT NULL
    """), {"order_id": order_id})
    
    confirmed_row = confirmed_result.fetchone()
    if confirmed_row and confirmed_row[0]:
        history.append({
            "action": "confirmed",
            "action_label": "Підтверджено",
            "timestamp": confirmed_row[0].isoformat() if confirmed_row[0] else None,
            "user_id": confirmed_row[1],
            "user_name": f"{confirmed_row[2] or ''} {confirmed_row[3] or ''}".strip() if confirmed_row[2] else "System",
            "details": None
        })
    
    # 3. Packing log (кожен товар окремо)
    packing_result = db.execute(text("""
        SELECT 
            oip.packed_at,
            oip.packed_by_id,
            oip.packed_by_name,
            oip.sku,
            oip.product_name,
            oip.quantity,
            oip.location
        FROM order_item_packing oip
        WHERE oip.order_id = :order_id
        ORDER BY oip.packed_at ASC
    """), {"order_id": order_id})
    
    for pack_row in packing_result:
        history.append({
            "action": "packed",
            "action_label": f"Запаковано {pack_row[3]}",
            "timestamp": pack_row[0].isoformat() if pack_row[0] else None,
            "user_id": pack_row[1],
            "user_name": pack_row[2] or "Unknown",
            "details": {
                "sku": pack_row[3],
                "product_name": pack_row[4],
                "quantity": pack_row[5],
                "location": pack_row[6]
            }
        })
    
    # 4. Issue card actions (підготовка, видача)
    issue_result = db.execute(text("""
        SELECT 
            ic.prepared_at,
            ic.prepared_by_id,
            u1.firstname AS prep_firstname,
            u1.lastname AS prep_lastname,
            ic.issued_at,
            ic.issued_by_id,
            u2.firstname AS issued_firstname,
            u2.lastname AS issued_lastname,
            ic.received_at,
            ic.received_by_id,
            u3.firstname AS received_firstname,
            u3.lastname AS received_lastname
        FROM issue_cards ic
        LEFT JOIN users u1 ON ic.prepared_by_id = u1.user_id
        LEFT JOIN users u2 ON ic.issued_by_id = u2.user_id
        LEFT JOIN users u3 ON ic.received_by_id = u3.user_id
        WHERE ic.order_id = :order_id
    """), {"order_id": order_id})
    
    issue_row = issue_result.fetchone()
    if issue_row:
        # Prepared
        if issue_row[0]:
            history.append({
                "action": "prepared",
                "action_label": "Підготовлено до видачі",
                "timestamp": issue_row[0].isoformat() if issue_row[0] else None,
                "user_id": issue_row[1],
                "user_name": f"{issue_row[2] or ''} {issue_row[3] or ''}".strip() if issue_row[2] else "System",
                "details": None
            })
        
        # Issued
        if issue_row[4]:
            history.append({
                "action": "issued",
                "action_label": "Видано клієнту",
                "timestamp": issue_row[4].isoformat() if issue_row[4] else None,
                "user_id": issue_row[5],
                "user_name": f"{issue_row[6] or ''} {issue_row[7] or ''}".strip() if issue_row[6] else "System",
                "details": None
            })
        
        # Received (return)
        if issue_row[8]:
            history.append({
                "action": "returned",
                "action_label": "Прийнято повернення",
                "timestamp": issue_row[8].isoformat() if issue_row[8] else None,
                "user_id": issue_row[9],
                "user_name": f"{issue_row[10] or ''} {issue_row[11] or ''}".strip() if issue_row[10] else "System",
                "details": None
            })
    
    # 5. Damage history
    damage_result = db.execute(text("""
        SELECT 
            pdh.created_at,
            pdh.created_by_id,
            u.firstname,
            u.lastname,
            pdh.stage,
            pdh.damage_type,
            pdh.fee
        FROM product_damage_history pdh
        LEFT JOIN users u ON pdh.created_by_id = u.user_id
        WHERE pdh.order_id = :order_id
        ORDER BY pdh.created_at ASC
    """), {"order_id": order_id})
    
    for damage_row in damage_result:
        history.append({
            "action": "damage_recorded",
            "action_label": f"Зафіксовано пошкодження ({damage_row[4]})",
            "timestamp": damage_row[0].isoformat() if damage_row[0] else None,
            "user_id": damage_row[1],
            "user_name": f"{damage_row[2] or ''} {damage_row[3] or ''}".strip() if damage_row[2] else damage_row[1] or "System",
            "details": {
                "stage": damage_row[4],
                "damage_type": damage_row[5],
                "fee": float(damage_row[6]) if damage_row[6] else 0.0
            }
        })
    
    # 6. Finance transactions
    finance_result = db.execute(text("""
        SELECT 
            ft.created_at,
            ft.created_by,
            ft.tx_type,
            ft.amount,
            ft.currency
        FROM fin_transactions ft
        WHERE ft.entity_type = 'order' AND ft.entity_id = :order_id
        ORDER BY ft.created_at ASC
    """), {"order_id": order_id})
    
    for finance_row in finance_result:
        history.append({
            "action": "finance_transaction",
            "action_label": f"Фінанси: {finance_row[2]}",
            "timestamp": finance_row[0].isoformat() if finance_row[0] else None,
            "user_id": finance_row[1],
            "user_name": str(finance_row[1]) if finance_row[1] else "System",
            "details": {
                "type": finance_row[2],
                "amount": float(finance_row[3]) if finance_row[3] else 0.0,
                "currency": finance_row[4] or "UAH"
            }
        })
    
    # Sort by timestamp
    history.sort(key=lambda x: x["timestamp"] if x["timestamp"] else "")
    
    return {
        "order_id": order_id,
        "history": history,
        "total_events": len(history)
    }

# ============================================================
# ORDER NOTES (Internal Notes) ENDPOINTS
# ============================================================

@router.get("/orders/{order_id}/notes")
async def get_order_notes(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Отримати всі внутрішні нотатки по замовленню"""
    result = db.execute(text("""
        SELECT 
            onn.id,
            onn.order_id,
            onn.note,
            onn.created_by_id,
            onn.created_by_name,
            onn.created_at,
            onn.updated_at
        FROM order_notes onn
        WHERE onn.order_id = :order_id
        ORDER BY onn.created_at DESC
    """), {"order_id": order_id})
    
    notes = []
    for row in result:
        notes.append({
            "id": row[0],
            "order_id": row[1],
            "note": row[2],
            "created_by_id": row[3],
            "created_by_name": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
            "updated_at": row[6].isoformat() if row[6] else None
        })
    
    return {
        "order_id": order_id,
        "notes": notes,
        "total": len(notes)
    }

@router.post("/orders/{order_id}/notes")
async def create_order_note(
    order_id: int,
    note_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_rh_db)
):
    """Створити нову внутрішню нотатку"""
    note_id = str(uuid.uuid4())
    note_text = note_data.get("note", "")
    
    if not note_text:
        raise HTTPException(status_code=400, detail="Note text is required")
    
    db.execute(text("""
        INSERT INTO order_notes (
            id, order_id, note, created_by_id, created_by_name, created_at, updated_at
        ) VALUES (
            :id, :order_id, :note, :created_by_id, :created_by_name, NOW(), NOW()
        )
    """), {
        "id": note_id,
        "order_id": order_id,
        "note": note_text,
        "created_by_id": current_user["id"],
        "created_by_name": current_user["name"]
    })
    
    db.commit()
    
    return {
        "success": True,
        "note_id": note_id,
        "message": "Note created successfully"
    }

@router.delete("/notes/{note_id}")
async def delete_order_note(
    note_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_rh_db)
):
    """Видалити нотатку (тільки якщо створив цей же користувач або admin)"""
    # Check if note exists and belongs to user
    result = db.execute(text("""
        SELECT created_by_id FROM order_notes WHERE id = :id
    """), {"id": note_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Note not found")
    
    # Check permission (only creator or admin can delete)
    if row[0] != current_user["id"] and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    db.execute(text("DELETE FROM order_notes WHERE id = :id"), {"id": note_id})
    db.commit()
    
    return {"success": True, "message": "Note deleted"}

# ============================================================
# PACKING LOG ENDPOINTS
# ============================================================

@router.post("/orders/{order_id}/pack-item")
async def log_item_packing(
    order_id: int,
    packing_data: PackingLogCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_rh_db)
):
    """
    Залогувати комплектацію товару
    Дозволяє відстежувати хто і що запакував
    """
    packing_id = str(uuid.uuid4())
    
    db.execute(text("""
        INSERT INTO order_item_packing (
            id, order_id, item_id, product_id, sku, product_name,
            quantity, packed_by_id, packed_by_name, packed_at, location, notes
        ) VALUES (
            :id, :order_id, :item_id, :product_id, :sku, :product_name,
            :quantity, :packed_by_id, :packed_by_name, NOW(), :location, :notes
        )
    """), {
        "id": packing_id,
        "order_id": order_id,
        "item_id": packing_data.item_id,
        "product_id": packing_data.product_id,
        "sku": packing_data.sku,
        "product_name": packing_data.product_name,
        "quantity": packing_data.quantity,
        "packed_by_id": current_user["id"],
        "packed_by_name": current_user["name"],
        "location": packing_data.location,
        "notes": packing_data.notes
    })
    
    db.commit()
    
    return {
        "success": True,
        "packing_id": packing_id,
        "message": f"Товар {packing_data.sku} запаковано"
    }

@router.get("/orders/{order_id}/packing-log")
async def get_packing_log(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Отримати лог комплектації замовлення"""
    result = db.execute(text("""
        SELECT 
            oip.id,
            oip.sku,
            oip.product_name,
            oip.quantity,
            oip.packed_by_id,
            oip.packed_by_name,
            oip.packed_at,
            oip.location,
            oip.notes
        FROM order_item_packing oip
        WHERE oip.order_id = :order_id
        ORDER BY oip.packed_at ASC
    """), {"order_id": order_id})
    
    packing_log = []
    for row in result:
        packing_log.append({
            "id": row[0],
            "sku": row[1],
            "product_name": row[2],
            "quantity": row[3],
            "packed_by_id": row[4],
            "packed_by_name": row[5],
            "packed_at": row[6].isoformat() if row[6] else None,
            "location": row[7],
            "notes": row[8]
        })
    
    return {
        "order_id": order_id,
        "packing_log": packing_log,
        "total_items": len(packing_log)
    }

# ============================================================
# STATISTICS
# ============================================================

@router.get("/users/{user_id}/stats")
async def get_user_stats(
    user_id: int,
    db: Session = Depends(get_rh_db)
):
    """Статистика діяльності користувача"""
    # Orders created
    orders_created = db.execute(text("""
        SELECT COUNT(*) FROM orders WHERE created_by_id = :user_id
    """), {"user_id": user_id}).scalar() or 0
    
    # Orders confirmed
    orders_confirmed = db.execute(text("""
        SELECT COUNT(*) FROM orders WHERE confirmed_by_id = :user_id
    """), {"user_id": user_id}).scalar() or 0
    
    # Items packed
    items_packed = db.execute(text("""
        SELECT COUNT(*) FROM order_item_packing WHERE packed_by_id = :user_id
    """), {"user_id": user_id}).scalar() or 0
    
    # Orders issued
    orders_issued = db.execute(text("""
        SELECT COUNT(*) FROM issue_cards WHERE issued_by_id = :user_id
    """), {"user_id": user_id}).scalar() or 0
    
    # Damages recorded
    damages_recorded = db.execute(text("""
        SELECT COUNT(*) FROM product_damage_history WHERE created_by_id = :user_id
    """), {"user_id": user_id}).scalar() or 0
    
    return {
        "user_id": user_id,
        "orders_created": orders_created,
        "orders_confirmed": orders_confirmed,
        "items_packed": items_packed,
        "orders_issued": orders_issued,
        "damages_recorded": damages_recorded
    }
