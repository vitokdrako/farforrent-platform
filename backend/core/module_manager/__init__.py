"""Module Manager — plugin-архітектура Rental OS.

Additive-only: існуючий `server.py` продовжує працювати без змін.
Менеджер не переносить routes, не змінює API і не торкається схеми БД.

Швидкий старт:
    >>> from core.module_manager import get_module_manager
    >>> manager = get_module_manager()
    >>> manager.module_status("finance")["enabled"]
    True
    >>> manager.disable_module("analytics")["enabled"]
    False
"""
from typing import Optional

from .manager import (
    DependencyError,
    DuplicateModule,
    ModuleDisabledError,
    ModuleError,
    ModuleManager,
    ModuleNotFound,
)
from .manifest import ModuleManifest, RouteDescriptor
from .manifests import default_manifests
from .registry import ModuleRegistry
from .state import ModuleState

_manager: Optional[ModuleManager] = None


def build_module_manager(state: Optional[ModuleState] = None) -> ModuleManager:
    """Створити менеджер із зареєстрованими стандартними модулями.

    Args:
        state: Кастомне сховище стану (напр. для тестів).

    Returns:
        Готовий до роботи ModuleManager після bootstrap.
    """
    manager = ModuleManager(state=state)
    manager.register_all(default_manifests())
    manager.bootstrap()
    return manager


def get_module_manager() -> ModuleManager:
    """Отримати процес-глобальний екземпляр менеджера (singleton)."""
    global _manager
    if _manager is None:
        _manager = build_module_manager()
    return _manager


def reset_module_manager() -> None:
    """Скинути singleton. Використовується у тестах."""
    global _manager
    _manager = None


def is_module_enabled(name: str) -> bool:
    """Зручний хелпер для перевірки стану модуля з будь-якого місця коду."""
    return get_module_manager().is_enabled(name)


__all__ = [
    "ModuleManager",
    "ModuleRegistry",
    "ModuleManifest",
    "ModuleState",
    "RouteDescriptor",
    "ModuleError",
    "ModuleNotFound",
    "DuplicateModule",
    "DependencyError",
    "ModuleDisabledError",
    "default_manifests",
    "build_module_manager",
    "get_module_manager",
    "reset_module_manager",
    "is_module_enabled",
]