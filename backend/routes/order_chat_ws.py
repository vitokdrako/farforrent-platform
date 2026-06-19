"""
WebSocket для real-time чату менеджер ↔ клієнт.

Endpoints:
  /api/ws/chat/client/{order_id}?token=...   — клієнт підключається з JWT
  /api/ws/chat/admin/{order_id}              — менеджер (cookie/session auth)

Повідомлення WS:
  Server → Client:
    {"type": "init", "messages": [...]}
    {"type": "new_message", "message": {...}}
    {"type": "read_receipt", "by": "client|manager", "at": "..."}
  Client → Server:
    {"type": "send", "message": "..."}
    {"type": "typing", "is_typing": true}
    {"type": "ping"}

Архітектура:
  - На кожен order_id зберігаємо in-memory кімнату {order_id: [WebSocket, ...]}
  - При повідомленні з одного клієнта broadcast'имо всім у кімнаті
  - При закритті WS видаляємо з кімнати
"""
import logging
import json
from typing import Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from database_rentalhub import get_rh_db, RHSessionLocal
from routes.order_chat import _serialize_message, _list_messages, _verify_order_belongs_to_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket-chat"])


class ChatRoom:
    """In-memory pub/sub для чат-кімнати замовлення."""
    def __init__(self):
        # order_id -> list of (websocket, role)
        self._rooms: Dict[int, List[tuple]] = {}

    def join(self, order_id: int, ws: WebSocket, role: str):
        self._rooms.setdefault(order_id, []).append((ws, role))

    def leave(self, order_id: int, ws: WebSocket):
        room = self._rooms.get(order_id, [])
        self._rooms[order_id] = [(w, r) for w, r in room if w is not ws]
        if not self._rooms[order_id]:
            del self._rooms[order_id]

    async def broadcast(self, order_id: int, payload: dict, exclude: Optional[WebSocket] = None):
        room = self._rooms.get(order_id, [])
        dead = []
        for ws, role in room:
            if ws is exclude:
                continue
            try:
                await ws.send_json(payload)
            except Exception as e:
                logger.warning(f"WS send failed (will drop): {e}")
                dead.append(ws)
        for w in dead:
            self.leave(order_id, w)

    def members(self, order_id: int) -> int:
        return len(self._rooms.get(order_id, []))


chat_room = ChatRoom()


# ============================================================================
# Helpers
# ============================================================================
def _save_message(db: Session, order_id: int, sender_type: str,
                  sender_id: Optional[int], sender_name: str,
                  message: str, attachment_url: Optional[str] = None):
    """Зберегти повідомлення і повернути серіалізовану версію."""
    if sender_type == "client":
        db.execute(text("""
            INSERT INTO order_chat_messages
              (order_id, sender_type, sender_id, sender_name, message, attachment_url, read_by_client_at)
            VALUES (:oid, 'client', :sid, :name, :msg, :att, NOW())
        """), {"oid": order_id, "sid": sender_id, "name": sender_name,
               "msg": message, "att": attachment_url})
    else:
        db.execute(text("""
            INSERT INTO order_chat_messages
              (order_id, sender_type, sender_id, sender_name, message, attachment_url, read_by_manager_at)
            VALUES (:oid, 'manager', :sid, :name, :msg, :att, NOW())
        """), {"oid": order_id, "sid": sender_id, "name": sender_name,
               "msg": message, "att": attachment_url})
    db.commit()
    msg_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
    row = db.execute(text("""
        SELECT id, order_id, sender_type, sender_id, sender_name, message,
               attachment_url, created_at, read_by_client_at, read_by_manager_at
        FROM order_chat_messages WHERE id = :id
    """), {"id": msg_id}).fetchone()
    return _serialize_message(row)


def _mark_read(db: Session, order_id: int, by_role: str):
    """Позначити повідомлення як прочитані."""
    if by_role == "client":
        db.execute(text("""
            UPDATE order_chat_messages SET read_by_client_at = NOW()
            WHERE order_id = :oid AND sender_type IN ('manager','system') AND read_by_client_at IS NULL
        """), {"oid": order_id})
    else:
        db.execute(text("""
            UPDATE order_chat_messages SET read_by_manager_at = NOW()
            WHERE order_id = :oid AND sender_type = 'client' AND read_by_manager_at IS NULL
        """), {"oid": order_id})
    db.commit()


# ============================================================================
# CLIENT WebSocket
# ============================================================================
@router.websocket("/chat/client/{order_id}")
async def chat_client_ws(websocket: WebSocket, order_id: int, token: str = Query(...)):
    """
    Клієнтський WS для чату по замовленню. Auth — JWT у query param `?token=...`.
    """
    await websocket.accept()
    db = RHSessionLocal()
    try:
        # 1. Auth via JWT
        from routes.event_tool import decode_token
        try:
            payload = decode_token(token)
            customer_id = payload.get("sub")
        except Exception as e:
            await websocket.send_json({"type": "error", "message": "Invalid token"})
            await websocket.close(code=4401)
            return

        cust_row = db.execute(text("""
            SELECT customer_id, email, firstname, lastname
            FROM event_customers WHERE customer_id = :id
        """), {"id": customer_id}).fetchone()
        if not cust_row:
            await websocket.send_json({"type": "error", "message": "Customer not found"})
            await websocket.close(code=4401)
            return

        email = cust_row[1] or ""
        sender_name = f"{cust_row[2] or ''} {cust_row[3] or ''}".strip() or email

        cu = db.execute(text("SELECT id FROM client_users WHERE email_normalized = :e LIMIT 1"),
                        {"e": email.lower()}).fetchone()
        client_user_id = cu[0] if cu else None
        if not _verify_order_belongs_to_client(db, order_id, email, client_user_id):
            await websocket.send_json({"type": "error", "message": "Order access denied"})
            await websocket.close(code=4403)
            return

        # 2. Join room
        chat_room.join(order_id, websocket, "client")
        logger.info(f"WS client joined order={order_id} (members={chat_room.members(order_id)})")

        # 3. Send initial messages + mark read
        _mark_read(db, order_id, "client")
        await websocket.send_json({
            "type": "init",
            "messages": _list_messages(db, order_id),
        })
        # Notify others that messages were read
        await chat_room.broadcast(order_id, {
            "type": "read_receipt", "by": "client",
        }, exclude=websocket)

        # 4. Receive loop
        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")
            if mtype == "send":
                msg_text = (data.get("message") or "").strip()
                if not msg_text:
                    continue
                msg = _save_message(db, order_id, "client", customer_id, sender_name,
                                    msg_text, data.get("attachment_url"))
                # Broadcast to ALL in room (including sender for ack)
                await chat_room.broadcast(order_id, {
                    "type": "new_message", "message": msg
                })
                # Web Push to managers (no admin WS in room → fire push)
                # Currently no admin-side push system; skip.
            elif mtype == "typing":
                await chat_room.broadcast(order_id, {
                    "type": "typing", "by": "client",
                    "is_typing": bool(data.get("is_typing")),
                }, exclude=websocket)
            elif mtype == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                logger.debug(f"unknown WS msg type: {mtype}")

    except WebSocketDisconnect:
        logger.info(f"WS client disconnected order={order_id}")
    except Exception as e:
        logger.exception(f"WS client error: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        chat_room.leave(order_id, websocket)
        db.close()


# ============================================================================
# ADMIN/MANAGER WebSocket
# ============================================================================
@router.websocket("/chat/admin/{order_id}")
async def chat_admin_ws(websocket: WebSocket, order_id: int,
                        manager_name: str = Query("Менеджер")):
    """
    WS для менеджера. Auth: simplified (admin frontend is cookie-protected;
    тут просто перевіряємо що замовлення існує).
    """
    await websocket.accept()
    db = RHSessionLocal()
    try:
        exists = db.execute(text("SELECT 1 FROM orders WHERE order_id = :oid"),
                            {"oid": order_id}).scalar()
        if not exists:
            await websocket.send_json({"type": "error", "message": "Order not found"})
            await websocket.close(code=4404)
            return

        chat_room.join(order_id, websocket, "manager")
        logger.info(f"WS manager joined order={order_id} (members={chat_room.members(order_id)})")

        _mark_read(db, order_id, "manager")
        await websocket.send_json({
            "type": "init",
            "messages": _list_messages(db, order_id),
        })
        await chat_room.broadcast(order_id, {
            "type": "read_receipt", "by": "manager",
        }, exclude=websocket)

        while True:
            data = await websocket.receive_json()
            mtype = data.get("type")
            if mtype == "send":
                msg_text = (data.get("message") or "").strip()
                if not msg_text:
                    continue
                msg = _save_message(db, order_id, "manager", None, manager_name,
                                    msg_text, data.get("attachment_url"))
                await chat_room.broadcast(order_id, {
                    "type": "new_message", "message": msg
                })
                # Push клієнту (якщо він не у WS)
                if not any(r == "client" for _, r in chat_room._rooms.get(order_id, [])):
                    try:
                        from services.push_notifications import send_to_customer
                        c = db.execute(text("""
                            SELECT event_tool_customer_id, order_number FROM orders WHERE order_id = :oid
                        """), {"oid": order_id}).fetchone()
                        if c and c[0]:
                            send_to_customer(db, c[0],
                                title=f"💬 Менеджер написав ({c[1]})",
                                body=msg_text[:120], url="/profile",
                                tag=f"chat-{order_id}")
                    except Exception as e:
                        logger.warning(f"push from admin WS failed: {e}")
            elif mtype == "typing":
                await chat_room.broadcast(order_id, {
                    "type": "typing", "by": "manager",
                    "is_typing": bool(data.get("is_typing")),
                }, exclude=websocket)
            elif mtype == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WS manager disconnected order={order_id}")
    except Exception as e:
        logger.exception(f"WS manager error: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        chat_room.leave(order_id, websocket)
        db.close()
