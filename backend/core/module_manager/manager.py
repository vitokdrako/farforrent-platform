"""ModuleManager — реєстрація, вмикання, вимикання та статус модулів.

Принципи (обмеження Завдання №2):
    * Існуючі routes НЕ переносяться — менеджер лише посилається на них.
    * API НЕ змінюється — `load_enabled_modules` реєструє ті самі роутери
      з тими самими префіксами у детермінованому canonical-порядку.
    * Схема БД НЕ змінюється — стан модулів лежить у JSON-файлі.

Менеджер additive: поточний `server.py` продовжує працювати без змін.
Перехід на менеджер — окремий крок, коли будуть розірвані прямі
cross-route імпорти (див. audit/ARCHITECTURAL_MAP.md §6.1).
"""
import importlib
import logging
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .manifest import ModuleManifest, RouteDescriptor
from .registry import (
    DependencyError,
    DuplicateModule,
    ModuleError,
    ModuleNotFound,
    ModuleRegistry,
)
from .state import ModuleState

logger = logging.getLogger(__name__)


class ModuleDisabledError(ModuleError):
    """Спроба вимкнути модуль, який вимкнути неможливо."""


class ModuleManager:
    """Керує життєвим циклом модулів Rental OS.

    Публічний контракт:
        register_module(manifest)     — зареєструвати модуль
        enable_module(name)           — увімкнути (з перевіркою залежностей)
        disable_module(name)          — вимкнути (з перевіркою залежних)
        module_status(name) / status() — виставити стан назовні

    Example:
        >>> manager = ModuleManager()
        >>> manager.register_all(default_manifests())
        >>> manager.bootstrap()
        >>> manager.enable_module("finance")["enabled"]
        True
    """

    def __init__(
        self,
        registry: Optional[ModuleRegistry] = None,
        state: Optional[ModuleState] = None,
    ) -> None:
        self.registry = registry or ModuleRegistry()
        self.state = state or ModuleState()
        self._loaded_routes: Dict[str, List[str]] = {}
        self._load_errors: Dict[str, str] = {}
        self._bootstrapped = False

    # ==================================================================
    # REGISTER
    # ==================================================================
    def register_module(
        self, manifest: ModuleManifest, replace: bool = False
    ) -> ModuleManifest:
        """Зареєструвати модуль у реєстрі.

        Args:
            manifest: Манифест модуля.
            replace: Дозволити перезапис уже зареєстрованого імені.

        Returns:
            Зареєстрований манифест.

        Raises:
            DuplicateModule: Ім'я вже зайняте і replace=False.
        """
        registered = self.registry.register(manifest, replace=replace)
        logger.debug("Модуль зареєстровано: %s v%s", registered.name, registered.version)
        return registered

    def register_all(
        self, manifests: Iterable[ModuleManifest], replace: bool = False
    ) -> List[ModuleManifest]:
        """Зареєструвати набір модулів і перевірити граф залежностей."""
        result = self.registry.register_all(manifests, replace=replace)
        self.registry.validate()
        return result

    # ==================================================================
    # BOOTSTRAP
    # ==================================================================
    def bootstrap(self) -> Set[str]:
        """Завантажити стан із диска; при першому запуску — застосувати defaults.

        CORE завжди додається до увімкнених, навіть якщо у файлі стану
        його немає (напр. після ручного редагування).

        Returns:
            Набір увімкнених модулів.
        """
        defaults = self.registry.default_enabled_names() | self.registry.core_names()
        enabled = self.state.ensure_loaded(defaults=defaults)

        unknown = {name for name in enabled if not self.registry.has(name)}
        if unknown:
            logger.warning(
                "У стані модулів є незареєстровані імена, ігноруються: %s",
                ", ".join(sorted(unknown)),
            )
            enabled -= unknown

        missing_core = self.registry.core_names() - enabled
        if missing_core:
            enabled |= missing_core
            logger.info(
                "CORE-модулі відновлено як увімкнені: %s",
                ", ".join(sorted(missing_core)),
            )

        if enabled != self.state.enabled:
            self.state.set_enabled(enabled, reason="bootstrap-normalize")

        self._bootstrapped = True
        return set(enabled)

    def _ensure_bootstrapped(self) -> None:
        if not self._bootstrapped:
            self.bootstrap()

    # ==================================================================
    # ENABLE
    # ==================================================================
    def enable_module(
        self, name: str, with_dependencies: bool = True
    ) -> Dict[str, object]:
        """Увімкнути модуль.

        Args:
            name: Ім'я модуля.
            with_dependencies: Автоматично увімкнути відсутні залежності.
                Якщо False і залежності відсутні — кидає DependencyError.

        Returns:
            Статус модуля після операції плюс список `also_enabled`.

        Raises:
            ModuleNotFound: Модуль не зареєстрований.
            DependencyError: Відсутні залежності і with_dependencies=False.
        """
        self._ensure_bootstrapped()
        self.registry.get(name)
        enabled = self.state.enabled

        if name in enabled:
            status = self.module_status(name)
            status["also_enabled"] = []
            status["changed"] = False
            return status

        missing = self.registry.missing_dependencies(name, enabled)
        if missing and not with_dependencies:
            raise DependencyError(
                f"Модуль {name!r} вимагає вимкнені модулі: {', '.join(missing)}"
            )

        to_enable = set(missing) | {name}
        self.state.enable(to_enable, reason=f"enable:{name}")

        status = self.module_status(name)
        status["also_enabled"] = sorted(missing)
        status["changed"] = True
        logger.info(
            "Модуль увімкнено: %s%s",
            name,
            f" (разом із залежностями: {', '.join(sorted(missing))})" if missing else "",
        )
        return status

    # ==================================================================
    # DISABLE
    # ==================================================================
    def disable_module(
        self, name: str, cascade: bool = False
    ) -> Dict[str, object]:
        """Вимкнути модуль.

        Args:
            name: Ім'я модуля.
            cascade: Вимкнути також усі модулі, що залежать від цього.
                Якщо False і є увімкнені залежні — кидає DependencyError.

        Returns:
            Статус модуля після операції плюс список `also_disabled`.

        Raises:
            ModuleNotFound: Модуль не зареєстрований.
            ModuleDisabledError: Модуль позначений як CORE.
            DependencyError: Є увімкнені залежні і cascade=False.
        """
        self._ensure_bootstrapped()
        manifest = self.registry.get(name)

        if manifest.core:
            raise ModuleDisabledError(
                f"Модуль {name!r} є CORE і не може бути вимкнений"
            )

        enabled = self.state.enabled
        if name not in enabled:
            status = self.module_status(name)
            status["also_disabled"] = []
            status["changed"] = False
            return status

        blocking = self.registry.blocking_dependents(name, enabled)
        if blocking and not cascade:
            raise DependencyError(
                f"Модуль {name!r} не можна вимкнути: від нього залежать "
                f"увімкнені модулі: {', '.join(blocking)}. "
                "Використайте cascade=True або вимкніть їх спершу."
            )

        protected = [n for n in blocking if self.registry.get(n).core]
        if protected:
            raise ModuleDisabledError(
                f"Модуль {name!r} не можна вимкнути: від нього залежать "
                f"CORE-модулі: {', '.join(protected)}"
            )

        to_disable = set(blocking) | {name}
        self.state.disable(to_disable, reason=f"disable:{name}")

        status = self.module_status(name)
        status["also_disabled"] = sorted(blocking)
        status["changed"] = True
        logger.info(
            "Модуль вимкнено: %s%s",
            name,
            f" (каскадно: {', '.join(sorted(blocking))})" if blocking else "",
        )
        return status

    def set_enabled_modules(self, names: Sequence[str]) -> Dict[str, object]:
        """Встановити повний набір увімкнених модулів (для installer).

        Args:
            names: Імена модулів, які треба увімкнути.

        Returns:
            Загальний статус системи після застосування.

        Raises:
            DependencyError: Набір неповний щодо залежностей.
        """
        self._ensure_bootstrapped()
        target = set(names) | self.registry.core_names()
        for name in target:
            self.registry.get(name)

        for name in sorted(target):
            missing = [d for d in self.registry.dependencies(name) if d not in target]
            if missing:
                raise DependencyError(
                    f"Модуль {name!r} вимагає відсутні у наборі модулі: "
                    f"{', '.join(missing)}"
                )

        self.state.set_enabled(target, reason="set-enabled")
        return self.status()

    # ==================================================================
    # STATUS
    # ==================================================================
    def is_enabled(self, name: str) -> bool:
        """Чи увімкнений модуль. Незареєстрований вважається вимкненим."""
        self._ensure_bootstrapped()
        if not self.registry.has(name):
            return False
        return self.state.is_enabled(name)

    def enabled_modules(self) -> List[str]:
        """Увімкнені модулі в порядку завантаження (залежності першими)."""
        self._ensure_bootstrapped()
        return self.registry.resolve_order(self.state.enabled)

    def module_status(self, name: str) -> Dict[str, object]:
        """Детальний статус одного модуля."""
        self._ensure_bootstrapped()
        manifest = self.registry.get(name)
        enabled = self.state.enabled
        is_on = name in enabled

        return {
            "name": manifest.name,
            "title": manifest.title,
            "version": manifest.version,
            "description": manifest.description,
            "core": manifest.core,
            "enabled": is_on,
            "can_disable": not manifest.core,
            "requires": list(manifest.requires),
            "missing_dependencies": self.registry.missing_dependencies(name, enabled),
            "dependents": self.registry.dependents(name),
            "blocking_dependents": self.registry.blocking_dependents(name, enabled),
            "route_count": len(manifest.routes),
            "routes_loaded": list(self._loaded_routes.get(name, [])),
            "permissions": list(manifest.permissions) if is_on else [],
            "declared_permissions": list(manifest.permissions),
            "tables": list(manifest.tables),
            "hard_imports": list(manifest.hard_imports),
            "notes": list(manifest.notes),
            "load_error": self._load_errors.get(name),
        }

    def status(self) -> Dict[str, object]:
        """Статус усієї модульної системи (для API `/modules` та CLI)."""
        self._ensure_bootstrapped()
        modules = [self.module_status(name) for name in self.registry.names()]
        enabled = [m for m in modules if m["enabled"]]
        return {
            "state_file": str(self.state.path),
            "total": len(modules),
            "enabled_count": len(enabled),
            "disabled_count": len(modules) - len(enabled),
            "enabled": sorted(m["name"] for m in enabled),
            "load_order": self.enabled_modules(),
            "permissions": self.active_permissions(),
            "warnings": self.integrity_warnings(),
            "modules": modules,
        }

    def active_permissions(self) -> List[str]:
        """Permissions лише увімкнених модулів.

        Вимкнений модуль не віддає жодного permission — саме цього
        вимагає умова «якщо Finance вимкнений, його permissions немає».
        """
        self._ensure_bootstrapped()
        result: Set[str] = set()
        for name in self.state.enabled:
            result |= set(self.registry.get(name).permissions)
        return sorted(result)

    def integrity_warnings(self) -> List[str]:
        """Попередження про стан, що суперечить фактичному коду.

        Головне джерело — прямі cross-route імпорти: доки вони існують,
        вимкнений модуль усе одно буде імпортований залежним модулем.
        """
        self._ensure_bootstrapped()
        warnings: List[str] = []
        enabled = self.state.enabled

        for name in self.registry.names():
            manifest = self.registry.get(name)
            if name not in enabled:
                continue
            for source in manifest.hard_imports:
                if source not in enabled:
                    warnings.append(
                        f"Модуль '{name}' має прямий import з '{source}', "
                        f"який вимкнений — імпорт зламається у рантаймі"
                    )
        for name, error in self._load_errors.items():
            warnings.append(f"Модуль '{name}': помилка завантаження — {error}")
        return warnings

    # ==================================================================
    # ROUTE LOADING (opt-in, API не змінюється)
    # ==================================================================
    def canonical_route_order(self) -> List[RouteDescriptor]:
        """Дескриптори роутерів увімкнених модулів у canonical-порядку.

        Порядок детермінований: модулі — у порядку завантаження
        (залежності першими), роутери всередині модуля — у порядку
        оголошення в манифесті. Це гарантує, що при однаковому наборі
        модулів набір і порядок endpoint'ів завжди однаковий.
        """
        descriptors: List[RouteDescriptor] = []
        for name in self.enabled_modules():
            descriptors.extend(self.registry.get(name).routes)
        return descriptors

    def load_enabled_modules(self, app, strict: bool = False) -> Dict[str, object]:
        """Підключити роутери увімкнених модулів до FastAPI-застосунку.

        Роутери імпортуються lazy: вимкнений модуль не імпортується взагалі,
        тому його endpoint'и, permissions і залежності не з'являються.

        Args:
            app: Екземпляр FastAPI.
            strict: Кидати виняток при помилці імпорту роутера.
                За замовчуванням помилка логується і йде у warnings.

        Returns:
            Звіт: скільки модулів і роутерів підключено, та помилки.
        """
        self._ensure_bootstrapped()
        self._loaded_routes = {}
        self._load_errors = {}

        loaded_modules: List[str] = []
        loaded_routers = 0

        for name in self.enabled_modules():
            manifest = self.registry.get(name)
            module_routes: List[str] = []

            for descriptor in manifest.routes:
                try:
                    imported = importlib.import_module(descriptor.module_path)
                    router = getattr(imported, descriptor.attr)
                except (ImportError, AttributeError) as exc:
                    message = f"{descriptor.key}: {exc}"
                    self._load_errors[name] = message
                    logger.error("Не вдалося підключити роутер %s", message)
                    if strict:
                        raise ModuleError(
                            f"Модуль {name!r}: не вдалося підключити {descriptor.key}"
                        ) from exc
                    continue

                if descriptor.prefix:
                    app.include_router(router, prefix=descriptor.prefix)
                else:
                    app.include_router(router)

                module_routes.append(descriptor.key)
                loaded_routers += 1

            self._loaded_routes[name] = module_routes
            loaded_modules.append(name)
            logger.info(
                "Модуль '%s' підключено: %d роутер(ів)", name, len(module_routes)
            )

        report = {
            "modules_loaded": loaded_modules,
            "modules_count": len(loaded_modules),
            "routers_loaded": loaded_routers,
            "errors": dict(self._load_errors),
            "warnings": self.integrity_warnings(),
        }
        logger.info(
            "ModuleManager: %d модулів, %d роутерів",
            len(loaded_modules),
            loaded_routers,
        )
        return report


__all__ = [
    "ModuleManager",
    "ModuleDisabledError",
    "ModuleError",
    "ModuleNotFound",
    "DuplicateModule",
    "DependencyError",
]