"""Ідентифікація клієнта кабінету за JWT.

Причина існування: `routes/order_chat.py` викликав `get_current_customer`
з `routes/event_tool.py` (route -> route). Тепер обидва модулі залежать
від цього сервісу.

Контракт збережено 1:1: ті самі HTTP-статуси й тексти (`401 "Invalid token"`,
`401 "Customer not found"`), той самий набір полів у результаті. Декодування
токена делеговане в `core.security`, тому формат токена не змінюється:
той самий секрет, той самий алгоритм HS256, той самий payload.
"""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.security import TokenError, decode_jwt_token


def decode_customer_token(token: str) -> dict:
    """Декодувати JWT і повернути payload, мапуючи помилки у 401.

    Raises:
        HTTPException: 401 з текстом `"Token expired"` або `"Invalid token"` —
            рівно ті самі значення, що віддавалися раніше.
    """
    try:
        return decode_jwt_token(token)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=exc.message)


def get_current_customer(token: str, db: Session) -> dict:
    """Отримати поточного клієнта кабінету з токена.

    Args:
        token: Закодований JWT клієнта.
        db: Сесія RentalHub.

    Returns:
        Дані клієнта: `customer_id`, `email`, `firstname`, `lastname`, `telephone`.

    Raises:
        HTTPException: 401, якщо токен недійсний або клієнта не знайдено.
    """
    payload = decode_customer_token(token)
    customer_id = payload.get("sub")
    if not customer_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = db.execute(
        text("SELECT * FROM event_customers WHERE customer_id = :id"),
        {"id": customer_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=401, detail="Customer not found")

    return {
        "customer_id": row[0],
        "email": row[1],
        "firstname": row[3],
        "lastname": row[4],
        "telephone": row[5],
    }


__all__ = ["decode_customer_token", "get_current_customer"]