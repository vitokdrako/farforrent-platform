"""
Test safety guard. Refuses to run E2E tests against the LIVE/PROD cloud DB.

Usage in tests:
    from tests._safety import assert_not_production
    assert_not_production()
"""
import os
import sys
from pathlib import Path

# Завантажуємо .env ДО перевірки (інакше RH_DB_HOST буде порожнім → захист не спрацює)
try:
    from dotenv import load_dotenv
    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
    if _ENV_FILE.exists():
        load_dotenv(_ENV_FILE)
except Exception:
    pass

# Hosts considered "production" — running destructive tests against them is forbidden
_PROD_HOSTS = {"farforre.mysql.tools"}
# Same host but explicitly approved as test DB → bypass
_TEST_DB_NAMES = {"farforre_rentalhub_test", "farforre_test", "rentalhub_test"}


def assert_not_production():
    """
    Raise if current DB looks like production.
    Bypass: set ENV `I_KNOW_THIS_IS_PROD=1` or use --i-know-prod CLI flag.
    """
    host = os.environ.get("RH_DB_HOST", "")
    dbname = os.environ.get("RH_DB_DATABASE", "")

    if dbname in _TEST_DB_NAMES:
        return  # explicitly a test database

    is_prod = host in _PROD_HOSTS

    bypass = (
        os.environ.get("I_KNOW_THIS_IS_PROD") == "1"
        or "--i-know-prod" in sys.argv
        or "--allow-prod" in sys.argv
    )

    if is_prod and not bypass:
        print("\n" + "=" * 72)
        print("🛑 ВІДМОВА ЗАПУСКАТИ ТЕСТ ПРОТИ ПРОД-БД!")
        print("=" * 72)
        print(f"   Поточна БД: {host}/{dbname}")
        print(f"   Прод хости: {', '.join(_PROD_HOSTS)}")
        print()
        print("Варіанти:")
        print("  1. Запустити на VPS з локальною копією БД (рекомендовано):")
        print("     cd /var/www/farforrent/backend")
        print("     export RH_DB_HOST=127.0.0.1")
        print("     export RH_DB_DATABASE=farforre_rentalhub")
        print("     python3 tests/test_full_order_cycle.py")
        print()
        print("  2. Створити окрему test-DB у тому ж cloud-MySQL:")
        print(f"     CREATE DATABASE {sorted(_TEST_DB_NAMES)[0]}; — потім вказати у .env")
        print()
        print("  3. Якщо ти впевнений, що знаєш що робиш:")
        print("     export I_KNOW_THIS_IS_PROD=1")
        print("     # або додати  --i-know-prod  до команди запуску")
        print("=" * 72 + "\n")
        sys.exit(2)
    elif is_prod and bypass:
        print(f"⚠️  Запуск проти PROD ({host}/{dbname}) з вашого підтвердження. "
              f"Hard-cleanup ОБОВ'ЯЗКОВИЙ після завершення.")
