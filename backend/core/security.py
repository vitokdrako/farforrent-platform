"""Canonical security configuration для RentalOS backend.

Єдине джерело правди для:
  * JWT-секрету (раніше був продубльований у 6 файлах зі слабким default);
  * обов'язкових credentials з environment (раніше hardcoded у коді).

Модуль additive-only: не змінює API-контракти, не торкається схеми БД
і не переносить routes.

Політика JWT-секрету
--------------------
* Секрет читається ЛИШЕ з environment (`JWT_SECRET_KEY`, legacy-alias
  `EVENT_JWT_SECRET`).
* Формат токена не змінено: алгоритм і далі HS256, payload не зачеплено.
  Якщо в `.env` виставити той самий секрет, що використовувався раніше,
  усі видані токени залишаються валідними.
* Якщо секрет відсутній або дорівнює відомому placeholder-значенню:
    - у production  -> `SecurityConfigError` (явна помилка, не тихий default);
    - у dev/test    -> генерується випадковий ephemeral-секрет на час процесу
                       з попередженням у лог (передбачуваного default немає).
"""
from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path
from typing import Iterable, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Backend root — той самий `.env`, який уже читають database.py / database_rentalhub.py
BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

#: Алгоритм підпису JWT. Не змінювати без міграції всіх виданих токенів.
JWT_ALGORITHM = "HS256"

#: Оточення, у яких допускається ephemeral-секрет замість жорсткої помилки.
_DEV_ENVIRONMENTS = frozenset({"development", "dev", "local", "test", "testing"})

#: Placeholder-значення, які раніше стояли як default у коді.
#: Такий секрет вважається відсутнім, бо він публічний.
_KNOWN_INSECURE_SECRETS = frozenset(
    {
        "your-secret-key-change-in-production",
        "event-tool-secret-key-change-in-production",
        "your-secret-key",
        "change-me",
        "changeme",
        "secret",
        "test",
    }
)

#: Довжина, коротше за яку секрет приймається, але з попередженням.
_RECOMMENDED_SECRET_LENGTH = 32

_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "on"})


class SecurityConfigError(RuntimeError):
    """Конфігурація безпеки неповна або небезпечна для запуску."""


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def get_environment() -> str:
    """Поточне оточення у нижньому регістрі.

    Порядок: `ENVIRONMENT`, потім legacy `ENV`. За замовчуванням `production`,
    тобто strict-режим — безпечніше помилитися в бік суворості.
    """
    raw = os.getenv("ENVIRONMENT") or os.getenv("ENV") or "production"
    return raw.strip().lower()


def is_production() -> bool:
    """True для всього, що не позначено явно як dev/local/test."""
    return get_environment() not in _DEV_ENVIRONMENTS


def get_bool_env(name: str, default: bool = False) -> bool:
    """Прочитати boolean-флаг з environment."""
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in _TRUE_VALUES


def get_required_env(
    name: str,
    aliases: Iterable[str] = (),
    *,
    allow_empty: bool = False,
    hint: str = "",
) -> str:
    """Обов'язкова змінна оточення.

    Args:
        name: Основне ім'я змінної.
        aliases: Legacy-імена, які перевіряються після основного.
        allow_empty: Дозволити порожнє значення (наприклад, пароль root без пароля).
        hint: Додаткова підказка в тексті помилки.

    Raises:
        SecurityConfigError: Значення відсутнє (і `allow_empty` = False).
    """
    candidates = (name, *aliases)
    for candidate in candidates:
        raw = os.getenv(candidate)
        if raw is None:
            continue
        value = raw.strip()
        if value or allow_empty:
            return value

    if allow_empty:
        return ""

    names = " / ".join(candidates)
    suffix = f" {hint}" if hint else ""
    raise SecurityConfigError(
        f"Обов'язкова змінна оточення не задана: {names}. "
        f"Додайте її у backend/.env (шаблон — backend/.env.example)."
        f"{suffix}"
    )


# ---------------------------------------------------------------------------
# JWT secret
# ---------------------------------------------------------------------------

_jwt_secret_cache: Optional[str] = None


def reset_jwt_secret_cache() -> None:
    """Скинути кеш секрету. Використовується тестами."""
    global _jwt_secret_cache
    _jwt_secret_cache = None


def _read_raw_jwt_secret() -> str:
    raw = os.getenv("JWT_SECRET_KEY") or os.getenv("EVENT_JWT_SECRET") or ""
    return raw.strip()


def get_jwt_secret() -> str:
    """Canonical JWT-секрет.

    Returns:
        Секрет для підпису та верифікації токенів.

    Raises:
        SecurityConfigError: У production секрет відсутній або є placeholder.
    """
    global _jwt_secret_cache
    if _jwt_secret_cache is not None:
        return _jwt_secret_cache

    secret = _read_raw_jwt_secret()
    insecure = (not secret) or secret.lower() in _KNOWN_INSECURE_SECRETS

    if insecure:
        if is_production():
            raise SecurityConfigError(
                "JWT_SECRET_KEY не заданий або дорівнює небезпечному "
                "placeholder-значенню. Backend не буде запущено в production. "
                "Згенеруйте секрет (`python -c \"import secrets; "
                "print(secrets.token_urlsafe(48))\"`) і додайте JWT_SECRET_KEY "
                "у backend/.env. Щоб зберегти вже видані токени, вкажіть той "
                "самий секрет, який використовувався раніше."
            )
        secret = secrets.token_urlsafe(48)
        logger.warning(
            "JWT_SECRET_KEY не заданий. Згенеровано тимчасовий секрет на час "
            "цього процесу (ENVIRONMENT=%s). Токени стануть недійсними після "
            "перезапуску. Для стабільної роботи задайте JWT_SECRET_KEY у .env.",
            get_environment(),
        )
    elif len(secret) < _RECOMMENDED_SECRET_LENGTH:
        logger.warning(
            "JWT_SECRET_KEY коротший за %d символів. Рекомендується довший "
            "секрет, але поточне значення прийнято, щоб не інвалідувати "
            "вже видані токени.",
            _RECOMMENDED_SECRET_LENGTH,
        )

    _jwt_secret_cache = secret
    return secret


# ---------------------------------------------------------------------------
# JWT decoding (canonical, framework-neutral)
# ---------------------------------------------------------------------------


class TokenError(RuntimeError):
    """Помилка перевірки JWT, незалежна від web-фреймворку.

    Route-шар мапить її у власний HTTP-контракт (наприклад, 401), а
    WebSocket-шар — у власний close-code. Сам core не знає про FastAPI.

    Attributes:
        reason: `"expired"` або `"invalid"`.
        message: Текст, який історично віддавався клієнту.
    """

    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason
        self.message = message


def decode_jwt_token(token: str) -> dict:
    """Декодувати та перевірити JWT.

    Формат токена не змінюється: той самий секрет (`get_jwt_secret`), той
    самий алгоритм (`JWT_ALGORITHM` = HS256), той самий payload. Claim `sub`
    приводиться до int, коли це можливо — для customer-токенів Event Tool;
    admin/manager-токени мають `sub` у вигляді email-рядка і залишаються
    без змін, щоб виклик вище повернув коректний 401, а не 500.

    Args:
        token: Закодований JWT.

    Returns:
        Розкодований payload.

    Raises:
        TokenError: Токен протермінований (`reason="expired"`) або
            недійсний (`reason="invalid"`).
    """
    import jwt

    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[JWT_ALGORITHM])
        if "sub" in payload:
            try:
                payload["sub"] = int(payload["sub"])
            except (TypeError, ValueError):
                pass
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenError("expired", "Token expired")
    except jwt.InvalidTokenError as exc:
        logger.error("JWT decode error: %s", exc)
        raise TokenError("invalid", "Invalid token")


__all__ = [
    "BACKEND_DIR",
    "JWT_ALGORITHM",
    "SecurityConfigError",
    "TokenError",
    "decode_jwt_token",
    "get_bool_env",
    "get_environment",
    "get_jwt_secret",
    "get_required_env",
    "is_production",
    "reset_jwt_secret_cache",
]