"""Спільний шар чату по замовленню.

Причина існування: HTTP-роут чату (`routes/order_chat.py`) і WebSocket-роут
(`routes/order_chat_ws.py`) віддають клієнту той самий формат повідомлення
і застосовують ту саму перевірку доступу до замовлення. Раніше WS-модуль
імпортував приватні хелпери з HTTP-модуля (route -> route). Тепер обидва
залежать від цього сервісу.

Код перенесено 1:1: SQL-запити, набір полів і семантика не змінені, тому
payload HTTP-відповідей і WS-повідомлень залишається байт-у-байт таким самим.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session


def serialize_message(row) -> dict:
    """Перетворити рядок `order_chat_messages` у payload для клієнта.

    Порядок полів у SELECT є частиною контракту: див. `list_messages`.
    """
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


def list_messages(db: Session, order_id: int) -> list[dict]:
    """Уся стрічка повідомлень замовлення у хронологічному порядку."""
    rows = db.execute(text("""
        SELECT id, order_id, sender_type, sender_id, sender_name, message,
               attachment_url, created_at, read_by_client_at, read_by_manager_at
        FROM order_chat_messages WHERE order_id = :oid ORDER BY created_at ASC, id ASC
    """), {"oid": order_id}).fetchall()
    return [serialize_message(r) for r in rows]


def verify_order_belongs_to_client(
    db: Session,
    order_id: int,
    customer_email: str,
    client_user_id: Optional[int] = None,
) -> bool:
    """Чи належить замовлення цьому клієнту.

    Схема `orders` історично різна між середовищами, тому набір умов
    будується за фактично наявними колонками (`SHOW COLUMNS`). Якщо жодної
    придатної колонки немає — доступ не підтверджений.
    """
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
        conditions.append(
            "event_tool_customer_id IN "
            "(SELECT customer_id FROM event_customers WHERE LOWER(email) = :email2)"
        )
        params["email2"] = (customer_email or "").lower().strip()
    if not conditions:
        return False
    sql = f"""SELECT 1 FROM orders WHERE order_id = :oid AND ({' OR '.join(conditions)}) LIMIT 1"""
    return db.execute(text(sql), params).scalar() is not None


__all__ = [
    "list_messages",
    "serialize_message",
    "verify_order_belongs_to_client",
]