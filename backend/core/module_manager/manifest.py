"""Декларативний опис модуля Rental OS.

Манифест НЕ містить бізнес-логіки і НЕ імпортує route-модулі.
Він лише описує, де вони лежать, щоб ModuleManager міг підключити
їх lazy — тільки якщо модуль увімкнений.
"""
from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True)
class RouteDescriptor:
    """Посилання на існуючий APIRouter без його імпорту.

    Attributes:
        module_path: Python-шлях модуля, напр. "routes.inventory".
        attr: Ім'я атрибута-роутера в модулі, напр. "router" або "decor_router".
        prefix: Префікс, з яким роутер реєструється в server.py.
            None означає, що prefix не передається у include_router
            (роутер уже має власний prefix).
    """

    module_path: str
    attr: str = "router"
    prefix: Optional[str] = None

    @property
    def key(self) -> str:
        """Унікальний ключ дескриптора для canonical order та діагностики."""
        return f"{self.module_path}:{self.attr}"


@dataclass(frozen=True)
class ModuleManifest:
    """Манифест модуля.

    Attributes:
        name: Технічна назва (lowercase, без пробілів).
        version: Версія манифеста.
        title: Людська назва для UI.
        description: Коротке призначення модуля.
        requires: Імена модулів, без яких цей не працює.
        core: True для CORE — такий модуль неможливо вимкнути.
        default_enabled: Чи увімкнений модуль при першій інсталяції.
        routes: Дескриптори роутерів, що належать модулю.
        permissions: Реєстр permissions модуля (finance.view тощо).
        tables: Таблиці БД, які модуль читає або пише. Довідково —
            ModuleManager не створює й не змінює схему.
        hard_imports: Відомі прямі cross-route імпорти з інших модулів.
            Використовується для попередження: доки вони існують,
            вимикання модуля-джерела зламає імпортера.
        notes: Застереження з аудиту (мертвий код, зламані імпорти).
    """

    name: str
    version: str
    title: str
    description: str
    requires: Tuple[str, ...] = ()
    core: bool = False
    default_enabled: bool = True
    routes: Tuple[RouteDescriptor, ...] = ()
    permissions: Tuple[str, ...] = ()
    tables: Tuple[str, ...] = ()
    hard_imports: Tuple[str, ...] = ()
    notes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ModuleManifest.name не може бути порожнім")
        if self.name != self.name.strip().lower():
            raise ValueError(
                f"ModuleManifest.name має бути lowercase без пробілів: {self.name!r}"
            )
        if self.name in self.requires:
            raise ValueError(f"Модуль {self.name!r} не може залежати від себе")
        if self.core and not self.default_enabled:
            raise ValueError(f"CORE-модуль {self.name!r} мусить бути default_enabled")

    def to_dict(self) -> dict:
        """Серіалізація манифеста для API/CLI-виводу."""
        return {
            "name": self.name,
            "version": self.version,
            "title": self.title,
            "description": self.description,
            "requires": list(self.requires),
            "core": self.core,
            "default_enabled": self.default_enabled,
            "routes": [
                {
                    "module_path": r.module_path,
                    "attr": r.attr,
                    "prefix": r.prefix,
                }
                for r in self.routes
            ],
            "permissions": list(self.permissions),
            "tables": list(self.tables),
            "hard_imports": list(self.hard_imports),
            "notes": list(self.notes),
        }