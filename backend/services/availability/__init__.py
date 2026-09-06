"""
Availability — єдине джерело правди про доступність товару.

Публічний контракт пакета:
    AvailabilityService  — розрахунок доступності (read-only)
    rules                — канонічні правила, зафіксовані власником продукту

Правила описані в `audit/AVAILABILITY_INVENTORY.md` §7. Будь-яка зміна
переліку резервуючих статусів або джерела «на обробці» змінює реальні
цифри доступності в продажі, тому робиться разом з оновленням аудиту.
"""
from .rules import (
    ACTIVE_ITEM_STATUS,
    COUNT_SOFT_RESERVATIONS,
    EXCLUDE_ARCHIVED_ORDERS,
    IN_RENT_ORDER_STATUSES,
    RELEASING_ORDER_STATUSES,
    RESERVING_ORDER_STATUSES,
    STATE_AFFECTS_AVAILABILITY,
)
from .service import AvailabilityService

__all__ = [
    "AvailabilityService",
    "RESERVING_ORDER_STATUSES",
    "IN_RENT_ORDER_STATUSES",
    "RELEASING_ORDER_STATUSES",
    "ACTIVE_ITEM_STATUS",
    "EXCLUDE_ARCHIVED_ORDERS",
    "COUNT_SOFT_RESERVATIONS",
    "STATE_AFFECTS_AVAILABILITY",
]