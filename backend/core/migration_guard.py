"""Guard для runtime-DDL endpoints (`/api/migrations/*`).

Проблема
--------
`routes/migrations.py` виконує `CREATE TABLE` / `ALTER TABLE` у відповідь на
звичайні HTTP-запити без будь-якої автентифікації. Це означає, що схему
production-БД можна змінити анонімним POST-запитом.

Рішення
-------
Функціональність НЕ видаляється (вона потрібна для legacy-деплойменту), але
доступ до неї стає явним deployment-механізмом:

1. `ALLOW_RUNTIME_MIGRATIONS=true` — вимикач. За замовчуванням вимкнено,
   тобто під час звичайної роботи API жоден DDL по HTTP не виконується.
2. `MIGRATION_TOKEN` — окремий секрет, який треба передати у заголовку
   `X-Migration-Token`.

Шляхи ендпоїнтів, їх методи, тіла запитів і відповіді не змінені —
guard додається як router-level dependency.
"""
from __future__ import annotations

import hmac
import logging
import os
from typing import Optional

from fastapi import Header, HTTPException, status

from core.security import get_bool_env

logger = logging.getLogger(__name__)

MIGRATIONS_ENABLED_FLAG = "ALLOW_RUNTIME_MIGRATIONS"
MIGRATION_TOKEN_ENV = "MIGRATION_TOKEN"

_MIN_TOKEN_LENGTH = 16


def runtime_migrations_enabled() -> bool:
    """Чи дозволено виконувати DDL через HTTP у цьому оточенні."""
    return get_bool_env(MIGRATIONS_ENABLED_FLAG, default=False)


def _configured_token() -> str:
    return (os.getenv(MIGRATION_TOKEN_ENV) or "").strip()


async def require_migration_access(
    x_migration_token: Optional[str] = Header(default=None, alias="X-Migration-Token"),
) -> None:
    """FastAPI dependency: пропускає лише явний deployment-виклик.

    Raises:
        HTTPException: 503 — механізм вимкнено або не налаштований;
            403 — токен відсутній чи невірний.
    """
    if not runtime_migrations_enabled():
        logger.warning("Спроба звернення до /api/migrations при вимкненому runtime-DDL.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Runtime-міграції вимкнені. Застосовуйте зміни схеми через "
                "deployment-механізм (apply_all_migrations.py). Щоб тимчасово "
                f"увімкнути endpoint, задайте {MIGRATIONS_ENABLED_FLAG}=true та "
                f"{MIGRATION_TOKEN_ENV}."
            ),
        )

    token = _configured_token()
    if len(token) < _MIN_TOKEN_LENGTH:
        logger.error("%s не налаштований або занадто короткий.", MIGRATION_TOKEN_ENV)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"{MIGRATION_TOKEN_ENV} не налаштований (мінімум "
                f"{_MIN_TOKEN_LENGTH} символів). Runtime-міграції недоступні."
            ),
        )

    provided = (x_migration_token or "").strip()
    if not provided or not hmac.compare_digest(provided, token):
        logger.warning("Невірний X-Migration-Token при зверненні до /api/migrations.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Невірний або відсутній заголовок X-Migration-Token.",
        )


__all__ = [
    "MIGRATIONS_ENABLED_FLAG",
    "MIGRATION_TOKEN_ENV",
    "require_migration_access",
    "runtime_migrations_enabled",
]