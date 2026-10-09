"""
Sync API - Manual trigger for OpenCart synchronization
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import subprocess
import os

router = APIRouter(prefix="/api/sync", tags=["sync"])

@router.post("/trigger")
async def trigger_sync():
    """
    Manually trigger synchronization from OpenCart
    """
    try:
        # Run sync script in background
        script_path = "/app/backend/sync_all.py"
        
        if not os.path.exists(script_path):
            raise HTTPException(status_code=404, detail="Sync script not found")
        
        # Start sync process in background using venv python
        process = subprocess.Popen(
            ["/root/.venv/bin/python", script_path],
            cwd="/app/backend",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        return {
            "success": True,
            "message": "Синхронізація запущена у фоновому режимі",
            "pid": process.pid,
            "note": "Перевірте логи через /api/sync/status"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка запуску синхронізації: {str(e)}")


@router.get("/status")
async def get_sync_status():
    """
    Get sync status and last run info
    """
    try:
        # Check if sync process is running
        result = subprocess.run(
            ["pgrep", "-f", "sync_all.py"],
            capture_output=True,
            text=True
        )
        
        is_running = bool(result.stdout.strip())
        
        # Read last lines from log
        log_path = "/var/log/sync.log"
        last_lines = []
        
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                last_lines = f.readlines()[-20:]  # Last 20 lines
        
        return {
            "is_running": is_running,
            "log_file": log_path,
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
