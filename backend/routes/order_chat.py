"""
Order chat router — двосторонній чат менеджер↔клієнт по замовленню.

Клієнт пише через /api/event/orders/{id}/chat/*
Менеджер пише через /api/admin/orders/{id}/chat/*
Обидві сторони бачать одну й ту саму стрічку.
"""
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional
import logging

from database_rentalhub import get_rh_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# Pydantic schemas
# ============================================================================
class SendMessageRequest(BaseModel):
    message: str
    attachment_url: Optional[str] = None


# ============================================================================
# Common helpers
# ============================================================================
def _serialize_message(row) -> dict:
    return {
        "id": row[0],
        "order_id": row[1],
        "sender_type": row[2],
        "sender_id": row[3],
        "sender_name": row[4],
        "message": row[5],
        "attachment_url": row[6],
        "created_at": row[7].isoformat() if row[7] else None,
        "read_by_client": row[8] is not None,
        "read_by_manager": row[9] is not None,
    }


def _list_messages(db: Session, order_id: int):
    rows = db.execute(text("""
        SELECT id, order_id, sender_type, sender_id, sender_name, message,
               attachment_url, created_at, read_by_client_at, read_by_manager_at
        FROM order_chat_messages WHERE order_id = :oid ORDER BY created_at ASC, id ASC
    """), {"oid": order_id}).fetchall()
    return [_serialize_message(r) for r in rows]


def _verify_order_belongs_to_client(db: Session, order_id: int, customer_email: str,
                                     client_user_id: Optional[int] = None) -> bool:
    cols_rows = db.execute(text("SHOW COLUMNS FROM orders")).fetchall()
    existing_cols = {r[0] for r in cols_rows}
    conditions = []
    params = {"oid": order_id}
    if "customer_email" in existing_cols:
        conditions.append("LOWER(customer_email) = :email")
        params["email"] = (customer_email or "").lower().strip()
    if "client_user_id" in existing_cols and client_user_id:
        conditions.append("client_user_id = :cuid")
        params["cuid"] = client_user_id
    if "event_tool_customer_id" in existing_cols:
        conditions.append("event_tool_customer_id IN (SELECT customer_id FROM event_customers WHERE LOWER(email) = :email2)")
        params["email2"] = (customer_email or "").lower().strip()
    if not conditions:
        return False
    sql = f"""SELECT 1 FROM orders WHERE order_id = :oid AND ({' OR '.join(conditions)}) LIMIT 1"""
    return db.execute(text(sql), params).scalar() is not None


# ============================================================================
# CLIENT-side endpoints  (/api/event/orders/{order_id}/chat)
# ============================================================================
client_router = APIRouter(prefix="/event/orders", tags=["chat-client"])


def _get_client_from_token(token: str, db: Session) -> dict:
    # Imported lazily to avoid circular import
    from routes.event_tool import get_current_customer
    return get_current_customer(token, db)


def _get_token(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization required")
    return authorization.split(" ", 1)[1]


@client_router.get("/{order_id}/chat/messages")
async def client_list_messages(
    order_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(_get_token),
):
    customer = _get_client_from_token(token, db)
    email = customer.get("email") or ""
    cu = db.execute(text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
                    {"e": email.lower()}).fetchone()
    client_user_id = cu[0] if cu else None
    if not _verify_order_belongs_to_client(db, order_id, email, client_user_id):
        raise HTTPException(status_code=404, detail="Order not found or access denied")
    # Mark messages from manager as read by client
    db.execute(text("""
        UPDATE order_chat_messages SET read_by_client_at = NOW()
        WHERE order_id = :oid AND sender_type IN ('manager','system') AND read_by_client_at IS NULL
    """), {"oid": order_id})
    db.commit()
    return {"messages": _list_messages(db, order_id)}


@client_router.post("/{order_id}/chat/messages")
async def client_send_message(
    order_id: int,
    body: SendMessageRequest,
    db: Session = Depends(get_rh_db),
    token: str = Depends(_get_token),
):
    customer = _get_client_from_token(token, db)
    email = customer.get("email") or ""
    cu = db.execute(text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
                    {"e": email.lower()}).fetchone()
    client_user_id = cu[0] if cu else None
    if not _verify_order_belongs_to_client(db, order_id, email, client_user_id):
        raise HTTPException(status_code=404, detail="Order not found or access denied")
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    sender_name = (f"{customer.get('firstname','')} {customer.get('lastname','')}".strip()
                   or email)
    db.execute(text("""
        INSERT INTO order_chat_messages
            (order_id, sender_type, sender_id, sender_name, message, attachment_url, read_by_client_at)
        VALUES (:oid, 'client', :sid, :name, :msg, :att, NOW())
    """), {"oid": order_id, "sid": customer.get("customer_id"),
           "name": sender_name, "msg": body.message.strip(),
           "att": body.attachment_url})
    db.commit()
    return {"ok": True, "messages": _list_messages(db, order_id)}


@client_router.get("/{order_id}/chat/unread_count")
async def client_unread_count(
    order_id: int,
    db: Session = Depends(get_rh_db),
    token: str = Depends(_get_token),
):
    customer = _get_client_from_token(token, db)
    email = customer.get("email") or ""
    cu = db.execute(text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
                    {"e": email.lower()}).fetchone()
    client_user_id = cu[0] if cu else None
    if not _verify_order_belongs_to_client(db, order_id, email, client_user_id):
        raise HTTPException(status_code=404, detail="Order not found or access denied")
    cnt = db.execute(text("""
        SELECT COUNT(*) FROM order_chat_messages
        WHERE order_id = :oid AND sender_type IN ('manager','system') AND read_by_client_at IS NULL
    """), {"oid": order_id}).scalar() or 0
    return {"unread": int(cnt)}


# ============================================================================
# MANAGER-side endpoints  (/api/admin/orders/{order_id}/chat)
# ============================================================================
admin_router = APIRouter(prefix="/admin/orders", tags=["chat-admin"])


@admin_router.get("/{order_id}/chat/messages")
async def admin_list_messages(order_id: int, db: Session = Depends(get_rh_db)):
    db.execute(text("""
        UPDATE order_chat_messages SET read_by_manager_at = NOW()
        WHERE order_id = :oid AND sender_type = 'client' AND read_by_manager_at IS NULL
    """), {"oid": order_id})
    db.commit()
    return {"messages": _list_messages(db, order_id)}


@admin_router.post("/{order_id}/chat/messages")
async def admin_send_message(
    order_id: int,
    body: SendMessageRequest,
    sender_name: Optional[str] = "Менеджер",
    db: Session = Depends(get_rh_db),
):
    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    db.execute(text("""
        INSERT INTO order_chat_messages
            (order_id, sender_type, sender_name, message, attachment_url, read_by_manager_at)
        VALUES (:oid, 'manager', :name, :msg, :att, NOW())
    """), {"oid": order_id, "name": sender_name or "Менеджер",
           "msg": body.message.strip(), "att": body.attachment_url})
    db.commit()

    # Push клієнту про нове повідомлення
    try:
        from services.push_notifications import notify_chat_message
        notify_chat_message(db, order_id, body.message, sender_name)
    except Exception as e:
        logger.warning(f"chat push notify failed: {e}")

    return {"ok": True, "messages": _list_messages(db, order_id)}


@admin_router.get("/{order_id}/chat/unread_count")
async def admin_unread_count(order_id: int, db: Session = Depends(get_rh_db)):
    cnt = db.execute(text("""
        SELECT COUNT(*) FROM order_chat_messages
        WHERE order_id = :oid AND sender_type = 'client' AND read_by_manager_at IS NULL
    """), {"oid": order_id}).scalar() or 0
    return {"unread": int(cnt)}
