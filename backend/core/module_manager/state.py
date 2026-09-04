"""Persistence стану модулів.

Схему БД змінювати заборонено, тому стан зберігається у JSON-файлі
поза базою. Шлях налаштовується через MODULE_STATE_PATH.
"""
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

STATE_VERSION = 1
DEFAULT_STATE_FILENAME = "module_state.json"


def default_state_path() -> Path:
    """Шлях до файлу стану.

    Пріоритет: env MODULE_STATE_PATH, інакше backend/module_state.json.
    """
    env_path = os.environ.get("MODULE_STATE_PATH")
    if env_path:
        return Path(env_path).expanduser()
    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / DEFAULT_STATE_FILENAME


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ModuleState:
    """Читає та записує набір увімкнених модулів.

    Файл стану має вигляд:
        {
          "version": 1,
          "updated_at": "2026-09-04T00:00:00+00:00",
          "enabled": ["core", "inventory", "rental"],
          "history": [{"at": ..., "action": "enable", "module": "finance"}]
        }
    """

    MAX_HISTORY = 200

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path else default_state_path()
        self._enabled: Set[str] = set()
        self._history: List[dict] = []
        self._loaded = False

    # ------------------------------------------------------------------
    # Ініціалізація
    # ------------------------------------------------------------------
    def exists(self) -> bool:
        """Чи вже існує файл стану."""
        return self.path.is_file()

    def load(self, defaults: Optional[Set[str]] = None) -> Set[str]:
        """Завантажити стан із диска.

        Args:
            defaults: Набір модулів для першої інсталяції, коли файлу немає.

        Returns:
            Набір увімкнених модулів.
        """
        if self.exists():
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                raise RuntimeError(
                    f"Не вдалося прочитати стан модулів {self.path}: {exc}"
                ) from exc
            enabled = raw.get("enabled") or []
            if not isinstance(enabled, list):
                raise RuntimeError(
                    f"Поле 'enabled' у {self.path} має бути списком"
                )
            self._enabled = {str(name) for name in enabled}
            history = raw.get("history") or []
            self._history = list(history) if isinstance(history, list) else []
        else:
            self._enabled = set(defaults or ())
            self._history = []
            self.save(reason="bootstrap")
        self._loaded = True
        return set(self._enabled)

    def ensure_loaded(self, defaults: Optional[Set[str]] = None) -> Set[str]:
        """Завантажити стан лише один раз."""
        if not self._loaded:
            self.load(defaults=defaults)
        return set(self._enabled)

    # ------------------------------------------------------------------
    # Мутації
    # ------------------------------------------------------------------
    @property
    def enabled(self) -> Set[str]:
        """Копія набору увімкнених модулів."""
        return set(self._enabled)

    def is_enabled(self, name: str) -> bool:
        """Чи увімкнений модуль."""
        return name in self._enabled

    def set_enabled(self, names: Set[str], reason: str = "set") -> Set[str]:
        """Замінити набір увімкнених модулів і зберегти."""
        self._enabled = set(names)
        self.save(reason=reason)
        return set(self._enabled)

    def enable(self, names: Set[str], reason: str = "enable") -> Set[str]:
        """Додати модулі до увімкнених."""
        added = set(names) - self._enabled
        if added:
            self._enabled |= added
            for name in sorted(added):
                self._append_history("enable", name, reason)
            self.save(reason=reason)
        return set(self._enabled)

    def disable(self, names: Set[str], reason: str = "disable") -> Set[str]:
        """Вилучити модулі з увімкнених."""
        removed = set(names) & self._enabled
        if removed:
            self._enabled -= removed
            for name in sorted(removed):
                self._append_history("disable", name, reason)
            self.save(reason=reason)
        return set(self._enabled)

    def history(self, limit: int = 20) -> List[dict]:
        """Останні записи журналу змін."""
        return list(self._history[-limit:])

    # ------------------------------------------------------------------
    # Запис на диск
    # ------------------------------------------------------------------
    def save(self, reason: str = "save") -> Path:
        """Атомарно записати стан на диск."""
        payload = {
            "version": STATE_VERSION,
            "updated_at": _utc_now(),
            "reason": reason,
            "enabled": sorted(self._enabled),
            "history": self._history[-self.MAX_HISTORY :],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".module_state.", dir=str(self.path.parent)
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
            os.replace(tmp_name, self.path)
        except BaseException:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
            raise
        return self.path

    def _append_history(self, action: str, module: str, reason: str) -> None:
        self._history.append(
            {
                "at": _utc_now(),
                "action": action,
                "module": module,
                "reason": reason,
            }
        )

    def to_dict(self) -> Dict[str, object]:
        """Стан у вигляді словника для API/CLI."""
        return {
            "version": STATE_VERSION,
            "path": str(self.path),
            "exists": self.exists(),
            "enabled": sorted(self._enabled),
        }