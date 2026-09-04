"""Реєстр модулів: зберігання манифестів і розв'язання залежностей."""
from typing import Dict, Iterable, List, Set, Tuple

from .manifest import ModuleManifest


class ModuleError(Exception):
    """Базова помилка модульної системи."""


class ModuleNotFound(ModuleError):
    """Модуль не зареєстрований."""


class DuplicateModule(ModuleError):
    """Модуль із таким іменем уже зареєстрований."""


class DependencyError(ModuleError):
    """Проблема із залежностями: невідома залежність або цикл."""


class ModuleRegistry:
    """Тримає манифести та відповідає на питання про залежності.

    Реєстр не знає нічого про enabled/disabled — це відповідальність
    ModuleManager. Тут лише статична структура модулів.
    """

    def __init__(self) -> None:
        self._manifests: Dict[str, ModuleManifest] = {}

    # ------------------------------------------------------------------
    # Реєстрація
    # ------------------------------------------------------------------
    def register(self, manifest: ModuleManifest, replace: bool = False) -> ModuleManifest:
        """Зареєструвати модуль.

        Args:
            manifest: Манифест модуля.
            replace: Дозволити перезапис уже зареєстрованого імені.

        Returns:
            Зареєстрований манифест.

        Raises:
            DuplicateModule: Якщо ім'я вже зайняте і replace=False.
        """
        if manifest.name in self._manifests and not replace:
            raise DuplicateModule(f"Модуль {manifest.name!r} уже зареєстрований")
        self._manifests[manifest.name] = manifest
        return manifest

    def register_all(
        self, manifests: Iterable[ModuleManifest], replace: bool = False
    ) -> List[ModuleManifest]:
        """Зареєструвати кілька модулів послідовно."""
        return [self.register(m, replace=replace) for m in manifests]

    # ------------------------------------------------------------------
    # Читання
    # ------------------------------------------------------------------
    def has(self, name: str) -> bool:
        """Чи зареєстрований модуль."""
        return name in self._manifests

    def get(self, name: str) -> ModuleManifest:
        """Отримати манифест або кинути ModuleNotFound."""
        try:
            return self._manifests[name]
        except KeyError:
            raise ModuleNotFound(f"Модуль {name!r} не зареєстрований") from None

    def names(self) -> List[str]:
        """Імена модулів у порядку реєстрації."""
        return list(self._manifests.keys())

    def all(self) -> List[ModuleManifest]:
        """Усі манифести в порядку реєстрації."""
        return list(self._manifests.values())

    def core_names(self) -> Set[str]:
        """Імена CORE-модулів, які не можна вимкнути."""
        return {m.name for m in self._manifests.values() if m.core}

    def default_enabled_names(self) -> Set[str]:
        """Модулі, увімкнені за замовчуванням при першій інсталяції."""
        return {m.name for m in self._manifests.values() if m.default_enabled}

    # ------------------------------------------------------------------
    # Залежності
    # ------------------------------------------------------------------
    def validate(self) -> None:
        """Перевірити цілісність графа залежностей.

        Raises:
            DependencyError: Невідома залежність або цикл.
        """
        for manifest in self._manifests.values():
            for dep in manifest.requires:
                if dep not in self._manifests:
                    raise DependencyError(
                        f"Модуль {manifest.name!r} вимагає невідомий модуль {dep!r}"
                    )
        self.resolve_order(self.names())

    def dependencies(self, name: str, recursive: bool = True) -> List[str]:
        """Модулі, від яких залежить вказаний.

        Args:
            name: Ім'я модуля.
            recursive: Включати транзитивні залежності.

        Returns:
            Імена залежностей у детермінованому порядку.
        """
        manifest = self.get(name)
        if not recursive:
            return list(manifest.requires)

        seen: Set[str] = set()
        ordered: List[str] = []

        def walk(current: str) -> None:
            for dep in self.get(current).requires:
                if dep in seen:
                    continue
                seen.add(dep)
                walk(dep)
                ordered.append(dep)

        walk(name)
        return ordered

    def dependents(self, name: str, recursive: bool = True) -> List[str]:
        """Модулі, які залежать від вказаного (обернений напрямок)."""
        self.get(name)  # переконатися, що модуль існує
        direct = [
            m.name for m in self._manifests.values() if name in m.requires
        ]
        if not recursive:
            return direct

        seen: Set[str] = set(direct)
        queue: List[str] = list(direct)
        while queue:
            current = queue.pop(0)
            for m in self._manifests.values():
                if current in m.requires and m.name not in seen:
                    seen.add(m.name)
                    queue.append(m.name)
        return [n for n in self._manifests if n in seen]

    def resolve_order(self, names: Iterable[str]) -> List[str]:
        """Топологічно відсортувати модулі: залежності йдуть першими.

        Args:
            names: Імена модулів для сортування.

        Returns:
            Імена у порядку завантаження.

        Raises:
            DependencyError: Якщо у графі є цикл.
        """
        requested = [n for n in names]
        for name in requested:
            self.get(name)

        target = set(requested)
        state: Dict[str, int] = {}  # 0 = в обробці, 1 = завершено
        ordered: List[str] = []

        def visit(current: str, path: Tuple[str, ...]) -> None:
            mark = state.get(current)
            if mark == 1:
                return
            if mark == 0:
                cycle = " -> ".join(path + (current,))
                raise DependencyError(f"Циклічна залежність модулів: {cycle}")
            state[current] = 0
            for dep in self.get(current).requires:
                if dep in target:
                    visit(dep, path + (current,))
            state[current] = 1
            ordered.append(current)

        for name in sorted(target):
            visit(name, ())
        return ordered

    def missing_dependencies(self, name: str, enabled: Set[str]) -> List[str]:
        """Які залежності модуля відсутні у наборі enabled."""
        return [dep for dep in self.dependencies(name) if dep not in enabled]

    def blocking_dependents(self, name: str, enabled: Set[str]) -> List[str]:
        """Які увімкнені модулі заблокують вимикання вказаного."""
        return [dep for dep in self.dependents(name) if dep in enabled]