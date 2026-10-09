"""
Price Sync API - синхронізація цін з OpenCart
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from database import get_db as get_oc_db
from database_rentalhub import get_rh_db
import logging

router = APIRouter(prefix="/api/price-sync", tags=["price-sync"])

# Стан синхронізації
sync_status = {
    "is_running": False,
    "total": 0,
    "processed": 0,
    "updated": 0,
    "errors": 0,
    "message": ""
}

def sync_prices_background():
    """
    Синхронізація цін в фоні:
    - ean (OpenCart) -> price (RentalHub) - ціна купівлі
    - price (OpenCart) -> rental_price (RentalHub) - ціна оренди
    """
    global sync_status
    
    try:
        sync_status["is_running"] = True
        sync_status["message"] = "Завантаження даних з OpenCart..."
        
        # Отримати дані з OpenCart
        from database import SessionLocal as OCSessionLocal
        from database_rentalhub import RHSessionLocal
        
        oc_db = OCSessionLocal()
        rh_db = RHSessionLocal()
        
        # Запит до OpenCart
        oc_query = text("""
            SELECT product_id, ean, price 
            FROM oc_product 
            WHERE ean IS NOT NULL AND ean != ''
            LIMIT 7000
        """)
        
        results = oc_db.execute(oc_query).fetchall()
        sync_status["total"] = len(results)
        sync_status["message"] = f"Оновлення {len(results)} товарів..."
        
        # Оновлення батчами
        batch_size = 100
        for i in range(0, len(results), batch_size):
            batch = results[i:i+batch_size]
            
            for row in batch:
                product_id, ean, price = row
                try:
                    # Перетворити ean в числове значення
                    price_value = float(ean) if ean and str(ean).replace('.','').replace('-','').isdigit() else 0
                    rental_value = float(price) if price else 0
                    
                    # Оновити в RentalHub
                    update_query = text("""
                        UPDATE products 
                        SET price = :price, rental_price = :rental 
                        WHERE product_id = :pid
                    """)
                    
                    result = rh_db.execute(update_query, {
                        'price': price_value,
                        'rental': rental_value,
                        'pid': product_id
                    })
                    
                    if result.rowcount > 0:
                        sync_status["updated"] += 1
                        
                except Exception as e:
                    logging.error(f"Error updating product {product_id}: {e}")
                    sync_status["errors"] += 1
                
                sync_status["processed"] += 1
            
            # Commit кожен батч
            rh_db.commit()
        
        oc_db.close()
        rh_db.close()
        
        sync_status["message"] = f"✅ Завершено! Оновлено {sync_status['updated']} товарів"
        sync_status["is_running"] = False
        
    except Exception as e:
        sync_status["message"] = f"❌ Помилка: {str(e)}"
        sync_status["is_running"] = False
        logging.error(f"Price sync error: {e}")


@router.post("/start")
async def start_price_sync(background_tasks: BackgroundTasks):
    """
    Запустити синхронізацію цін
    """
    global sync_status
    
    if sync_status["is_running"]:
        return {
            "success": False,
            "message": "Синхронізація вже виконується",
            "status": sync_status
        }
    
    # Скинути статус
    sync_status = {
        "is_running": True,
        "total": 0,
        "processed": 0,
        "updated": 0,
        "errors": 0,
        "message": "Запуск..."
    }
    
    # Запустити в фоні
    background_tasks.add_task(sync_prices_background)
    
    return {
        "success": True,
        "message": "Синхронізація запущена",
        "status": sync_status
    }


@router.get("/status")
async def get_sync_status():
    """
    Отримати статус синхронізації
    """
    return sync_status
