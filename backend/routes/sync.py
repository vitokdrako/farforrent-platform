"""
Sync API - Manual trigger for OpenCart synchronization

Security hardening (без зміни API-контрактів):
  * шляхи інтерпретатора, робочої директорії та логу більше не захардкоджені —
    беруться з environment із безпечним автовизначенням;
  * ім'я скрипта фіксоване константою і не приходить із запиту;
  * реальний шлях скрипта перевіряється на вихід за межі базової директорії
    (захист від path traversal через підміну env);
  * subprocess викликається списком аргументів, shell вимкнений.
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import os
import subprocess
import sys
from pathlib import Path

router = APIRouter(prefix="/api/sync", tags=["sync"])

# Фіксоване ім'я sync-скрипта. Не параметризується запитом.
SYNC_SCRIPT_NAME = "sync_all.py"

# Каталог backend за замовчуванням — той, у якому лежить цей пакет routes/.
_DEFAULT_BASE_DIR = Path(__file__).resolve().parent.parent


def _get_base_dir() -> Path:
    """Робоча директорія sync-скрипта."""
    configured = (os.environ.get("SYNC_BASE_DIR") or "").strip()
    base = Path(configured) if configured else _DEFAULT_BASE_DIR
    return base.resolve()


def _get_python_bin() -> str:
    """Інтерпретатор для запуску sync-скрипта.

    За замовчуванням — той самий Python, що виконує backend (`sys.executable`),
    замість раніше захардкодженого абсолютного шляху до venv.
    """
    configured = (os.environ.get("SYNC_PYTHON_BIN") or "").strip()
    return configured or sys.executable


def _get_log_path() -> Path:
    return Path((os.environ.get("SYNC_LOG_PATH") or "/var/log/sync.log").strip())


def _resolve_sync_script() -> Path:
    """Абсолютний шлях до sync-скрипта з перевіркою межі каталогу.

    Raises:
        HTTPException: 404 — скрипт відсутній; 500 — шлях виходить за межі
            базової директорії або інтерпретатор не знайдено.
    """
    base_dir = _get_base_dir()
    script_path = (base_dir / SYNC_SCRIPT_NAME).resolve()

    # Захист від path traversal: скрипт мусить лежати всередині base_dir.
    if base_dir != script_path.parent:
        raise HTTPException(
            status_code=500,
            detail="Некоректна конфігурація SYNC_BASE_DIR: шлях скрипта поза базовою директорією",
        )

    if not script_path.is_file():
        raise HTTPException(status_code=404, detail="Sync script not found")

    return script_path


@router.post("/trigger")
async def trigger_sync():
    """
    Manually trigger synchronization from OpenCart
    """
    try:
        script_path = _resolve_sync_script()
        base_dir = _get_base_dir()
        python_bin = _get_python_bin()

        if not Path(python_bin).is_file():
            raise HTTPException(
                status_code=500,
                detail="Python-інтерпретатор для sync не знайдено (перевірте SYNC_PYTHON_BIN)",
            )

        # Явний список аргументів, shell вимкнений. Нічого з запиту не потрапляє в команду.
        process = subprocess.Popen(
            [python_bin, str(script_path)],
            cwd=str(base_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )

        return {
            "success": True,
            "message": "Синхронізація запущена у фоновому режимі",
            "pid": process.pid,
            "note": "Перевірте логи через /api/sync/status"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка запуску синхронізації: {str(e)}")


@router.get("/status")
async def get_sync_status():
    """
    Get sync status and last run info
    """
    try:
        # Перевірка, чи процес синхронізації живий. Патерн фіксований константою.
        result = subprocess.run(
            ["pgrep", "-f", SYNC_SCRIPT_NAME],
            capture_output=True,
            text=True,
            shell=False,
        )

        is_running = bool(result.stdout.strip())

        # Read last lines from log
        log_path = _get_log_path()
        last_lines = []

        if log_path.is_file():
            with open(log_path, 'r') as f:
                last_lines = f.readlines()[-20:]  # Last 20 lines

        return {
            "is_running": is_running,
            "log_file": str(log_path),
            "last_log_lines": [line.strip() for line in last_lines],
            "supervisor_status": "Автоматична синхронізація кожні 30 хвилин"
        }

    except Exception as e:
        return {
            "error": str(e),
            "is_running": False
        }


@router.get("/last-sync")
async def get_last_sync_info():
    """
    Get info about last successful sync
    """
    try:
        from sqlalchemy import text
        from database_rentalhub import get_rh_db_sync

        db = get_rh_db_sync()

        # Get last sync times from different tables
        results = {}

        # Products
        row = db.execute(text("SELECT MAX(synced_at) as last_sync, COUNT(*) as total FROM products")).fetchone()
        results['products'] = {
            'last_sync': str(row[0]) if row[0] else None,
            'total_count': row[1]
        }

        # Orders
        row = db.execute(text("SELECT MAX(synced_at) as last_sync, COUNT(*) as total FROM orders")).fetchone()
        results['orders'] = {
            'last_sync': str(row[0]) if row[0] else None,
            'total_count': row[1]
        }

        # Categories
        row = db.execute(text("SELECT MAX(updated_at) as last_sync, COUNT(*) as total FROM categories")).fetchone()
        results['categories'] = {
            'last_sync': str(row[0]) if row[0] else None,
            'total_count': row[1]
        }

        db.close()

        return results

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка отримання інформації: {str(e)}")