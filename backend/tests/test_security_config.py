#!/usr/bin/env python3
"""Regression tests для security-конфігурації (Завдання №3, Step 0).

Перевіряють інваріанти, а не бізнес-логіку:
  * JWT-секрет має єдине canonical джерело і НЕ має небезпечного default;
  * у production відсутній секрет — це явна помилка, а не тихий fallback;
  * DB credentials читаються з environment, у коді їх немає;
  * runtime-DDL endpoints за замовчуванням заборонені.

Тести не потребують ані живої БД, ані запущеного сервера.

Запуск:
    cd backend && python -m pytest tests/test_security_config.py -v
    cd backend && python tests/test_security_config.py
"""
import os
import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from core.security import (  # noqa: E402
    JWT_ALGORITHM,
    SecurityConfigError,
    get_jwt_secret,
    get_required_env,
    is_production,
    reset_jwt_secret_cache,
)

# Публічні placeholder-значення, які раніше стояли як default у коді.
LEGACY_INSECURE_SECRETS = (
    "your-secret-key-change-in-production",
    "event-tool-secret-key-change-in-production",
)

# Файли, які раніше дублювали JWT-секрет власним default.
JWT_CONSUMERS = (
    "routes/auth.py",
    "routes/admin.py",
    "routes/tasks.py",
    "routes/damage_cases.py",
    "routes/user_tracking.py",
    "routes/event_tool.py",
    "utils/user_tracking_helper.py",
)


class _EnvSandbox:
    """Тимчасово підмінює environment і скидає кеш секрету."""

    def __init__(self, **overrides):
        self._overrides = overrides
        self._saved = {}

    def __enter__(self):
        for key, value in self._overrides.items():
            self._saved[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_jwt_secret_cache()
        return self

    def __exit__(self, *exc_info):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        reset_jwt_secret_cache()
        return False


# ---------------------------------------------------------------------------
# JWT configuration
# ---------------------------------------------------------------------------


def test_jwt_algorithm_unchanged():
    """Формат токена не змінено: алгоритм і далі HS256."""
    assert JWT_ALGORITHM == "HS256"


def test_jwt_secret_read_from_environment():
    """Секрет береться з JWT_SECRET_KEY."""
    with _EnvSandbox(JWT_SECRET_KEY="a" * 48, EVENT_JWT_SECRET=None):
        assert get_jwt_secret() == "a" * 48


def test_jwt_secret_supports_legacy_alias():
    """Legacy EVENT_JWT_SECRET підтримується (щоб не зламати client-токени)."""
    with _EnvSandbox(JWT_SECRET_KEY=None, EVENT_JWT_SECRET="b" * 48):
        assert get_jwt_secret() == "b" * 48


def test_missing_secret_fails_loudly_in_production():
    """У production відсутній секрет — помилка, а не передбачуваний default."""
    with _EnvSandbox(
        JWT_SECRET_KEY=None, EVENT_JWT_SECRET=None, ENVIRONMENT="production", ENV=None
    ):
        assert is_production() is True
        try:
            get_jwt_secret()
        except SecurityConfigError:
            return
        raise AssertionError("Очікувався SecurityConfigError при відсутньому секреті")


def test_legacy_placeholder_rejected_in_production():
    """Старий публічний placeholder не приймається як валідний секрет."""
    for insecure in LEGACY_INSECURE_SECRETS:
        with _EnvSandbox(
            JWT_SECRET_KEY=insecure, EVENT_JWT_SECRET=None, ENVIRONMENT="production", ENV=None
        ):
            try:
                get_jwt_secret()
            except SecurityConfigError:
                continue
            raise AssertionError(f"Placeholder '{insecure[:12]}...' помилково прийнято")


def test_dev_environment_gets_random_secret_not_default():
    """У dev секрет генерується випадково, а не береться з коду."""
    with _EnvSandbox(
        JWT_SECRET_KEY=None, EVENT_JWT_SECRET=None, ENVIRONMENT="development", ENV=None
    ):
        first = get_jwt_secret()
        assert first not in LEGACY_INSECURE_SECRETS
        assert len(first) >= 32
        reset_jwt_secret_cache()
        assert get_jwt_secret() != first, "секрет має бути випадковим, не константним"


def test_no_hardcoded_jwt_default_left_in_sources():
    """Жоден consumer не містить власного JWT-default."""
    offenders = []
    for rel_path in JWT_CONSUMERS:
        source = (BACKEND_DIR / rel_path).read_text(encoding="utf-8")
        for insecure in LEGACY_INSECURE_SECRETS:
            if insecure in source:
                offenders.append(rel_path)
    assert not offenders, f"Небезпечний JWT-default залишився у: {offenders}"


def test_jwt_consumers_use_canonical_source():
    """Усі consumer-и імпортують секрет з core.security."""
    missing = [
        rel_path
        for rel_path in JWT_CONSUMERS
        if "core.security" not in (BACKEND_DIR / rel_path).read_text(encoding="utf-8")
    ]
    assert not missing, f"Файли не використовують canonical source: {missing}"


# ---------------------------------------------------------------------------
# Database credentials
# ---------------------------------------------------------------------------


def test_get_required_env_raises_when_absent():
    """Обов'язкова змінна без значення дає явну помилку."""
    with _EnvSandbox(RENTALOS_TEST_ABSENT_VAR=None):
        try:
            get_required_env("RENTALOS_TEST_ABSENT_VAR")
        except SecurityConfigError as exc:
            assert "RENTALOS_TEST_ABSENT_VAR" in str(exc)
            return
        raise AssertionError("Очікувався SecurityConfigError")


def test_get_required_env_returns_value():
    with _EnvSandbox(RENTALOS_TEST_PRESENT_VAR="value-1"):
        assert get_required_env("RENTALOS_TEST_PRESENT_VAR") == "value-1"


def test_db_modules_have_no_hardcoded_credentials():
    """У DB-модулях і скриптах немає inline host/user/password."""
    # Патерн: присвоєння рядкового літерала змінній з credential-семантикою.
    credential_assign = re.compile(
        r"^\s*(?:RH_|OC_|DB_|MYSQL_)?(?:PASSWORD|PASSWD|USER|USERNAME|HOST|DATABASE)"
        r"\s*=\s*[\"'][^\"']+[\"']",
        re.MULTILINE,
    )
    checked = ("database_rentalhub.py", "database.py", "scripts/migrate_images.py")
    offenders = {}
    for rel_path in checked:
        source = (BACKEND_DIR / rel_path).read_text(encoding="utf-8")
        hits = credential_assign.findall(source)
        if hits:
            offenders[rel_path] = len(hits)
    assert not offenders, f"Знайдено inline credentials: {offenders}"


def test_rentalhub_credentials_are_env_driven():
    """RentalHub-підключення читає всі credentials з environment."""
    source = (BACKEND_DIR / "database_rentalhub.py").read_text(encoding="utf-8")
    for var in ("RH_DB_HOST", "RH_DB_USERNAME", "RH_DB_PASSWORD", "RH_DB_DATABASE"):
        assert var in source, f"{var} не читається з environment"
    assert "get_required_env" in source


def test_env_example_documents_required_keys():
    """Шаблон .env.example містить усі обов'язкові ключі."""
    template = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    for key in (
        "JWT_SECRET_KEY",
        "RH_DB_HOST",
        "RH_DB_USERNAME",
        "RH_DB_PASSWORD",
        "RH_DB_DATABASE",
        "ALLOW_RUNTIME_MIGRATIONS",
        "MIGRATION_TOKEN",
    ):
        assert key in template, f"{key} відсутній у .env.example"


def test_env_example_has_no_real_secret_values():
    """Шаблон не містить реальних значень — лише порожні ключі."""
    template = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    for line in template.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() in {"RH_DB_PASSWORD", "OC_DB_PASSWORD", "JWT_SECRET_KEY", "MIGRATION_TOKEN"}:
            assert value.strip() == "", f"{key} у .env.example не має містити значення"


# ---------------------------------------------------------------------------
# Runtime DDL guard
# ---------------------------------------------------------------------------


def test_runtime_migrations_disabled_by_default():
    """Без явного вимикача DDL по HTTP заборонено."""
    from core.migration_guard import runtime_migrations_enabled

    with _EnvSandbox(ALLOW_RUNTIME_MIGRATIONS=None):
        assert runtime_migrations_enabled() is False


def test_runtime_migrations_flag_can_be_enabled():
    from core.migration_guard import runtime_migrations_enabled

    with _EnvSandbox(ALLOW_RUNTIME_MIGRATIONS="true"):
        assert runtime_migrations_enabled() is True


def test_migrations_router_is_guarded():
    """Router міграцій має router-level dependency (шляхи не змінені)."""
    source = (BACKEND_DIR / "routes" / "migrations.py").read_text(encoding="utf-8")
    assert "require_migration_access" in source
    assert "dependencies=[Depends(require_migration_access)]" in source
    assert 'prefix="/api/migrations"' in source, "prefix не має змінюватися"


# ---------------------------------------------------------------------------
# subprocess safety
# ---------------------------------------------------------------------------


def test_sync_has_no_hardcoded_interpreter_path():
    """sync.py більше не містить захардкодженого шляху до venv."""
    source = (BACKEND_DIR / "routes" / "sync.py").read_text(encoding="utf-8")
    assert "/root/.venv/bin/python" not in source
    assert "shell=True" not in source
    assert 'prefix="/api/sync"' in source, "prefix не має змінюватися"


def test_no_os_system_in_migration_runner():
    """apply_all_migrations.py не використовує os.system."""
    source = (BACKEND_DIR / "apply_all_migrations.py").read_text(encoding="utf-8")
    assert "os.system(" not in source
    assert "MYSQL_PWD" in source, "пароль mysqldump має йти через env, не через argv"


def _run_all():
    """Мінімальний runner, щоб файл працював і без pytest."""
    tests = [
        (name, obj)
        for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    passed, failed = 0, []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  ✓ {name}")
        except AssertionError as exc:
            failed.append((name, str(exc)))
            print(f"  ✗ {name}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed.append((name, f"{type(exc).__name__}: {exc}"))
            print(f"  ✗ {name}: {type(exc).__name__}: {exc}")
    print(f"\n{passed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    print("Security configuration regression tests\n" + "-" * 40)
    sys.exit(_run_all())