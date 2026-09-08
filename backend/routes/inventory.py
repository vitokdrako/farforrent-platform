"""
Inventory routes - MySQL version
✅ MIGRATED: Using RentalHub DB
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from datetime import datetime

from database_rentalhub import get_rh_db  # ✅ Using RentalHub DB
from services.availability import AvailabilityService

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

# ============================================================
# PYDANTIC MODELS
# ============================================================

class InventoryItem(BaseModel):
    id: str
    article: str
    name: str
    category: Optional[str]
    price_per_day: float
    quantity: int
    image_url: Optional[str]
    description: Optional[str]
    replacement_price: Optional[float]
    damage_category: Optional[str]

# ============================================================
# API ENDPOINTS
# ============================================================

@router.get("")
async def get_inventory(
    category: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_rh_db)  # ✅ MIGRATED
):
    """
    Get inventory from RentalHub DB
    ✅ MIGRATED: Using products + inventory tables
    """
    
    # ✅ Build SQL query - location from products table
    sql_query = """
        SELECT 
            p.product_id, p.sku, p.name, p.price, p.rental_price, p.image_url, p.description,
            p.quantity, p.zone, p.aisle, p.shelf
        FROM products p
        WHERE p.status = 1
    """
    
    params = {}
    
    # Search by SKU or name
    if search:
        sql_query += " AND (p.sku LIKE :search OR p.name LIKE :search)"
        params['search'] = f"%{search}%"
    
    sql_query += f" LIMIT {limit}"
    
    result_db = db.execute(text(sql_query), params)
    
    result = []
    for row in result_db:
        product_id, sku, name, price, rental_price, image_url, description, quantity, zone, aisle, shelf = row
        
        result.append({
            "id": str(product_id),
            "article": sku or str(product_id),
            "name": name or f"Product {product_id}",
            "category": None,
            "price_per_day": float(rental_price) if rental_price else 0.0,  # Ціна оренди за день
            "damage_cost": float(price) if price else 0.0,  # Ціна купівлі (вартість збитків)
            "quantity": quantity or 0,
            "image_url": image_url,
            "description": description,
            "replacement_price": float(price) if price else None,
            "damage_category": None,
            "location": f"{zone}-{aisle}-{shelf}" if zone else None
        })
    
    return result

@router.get("/{item_id}")
async def get_inventory_item(item_id: str, db: Session = Depends(get_rh_db)):  # ✅ MIGRATED
    """
    Get single inventory item
    ✅ MIGRATED: Using RentalHub DB
    """
    
    try:
        # ✅ Query from RentalHub DB - location from products table
        result_db = db.execute(text("""
            SELECT 
                p.product_id, p.sku, p.name, p.price, p.rental_price, p.image_url, p.description,
                p.quantity, p.zone, p.aisle, p.shelf, p.cleaning_status, p.product_state
            FROM products p
            WHERE p.product_id = :product_id
        """), {"product_id": int(item_id)})
        
        row = result_db.fetchone()
    except ValueError:
        row = None
    
    if not row:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # ✅ Parse row data
    (product_id, sku, name, price, rental_price, image_url, description, 
     quantity, zone, aisle, shelf, cleaning_status, product_state) = row
    
    return {
        "id": str(product_id),
        "article": sku or str(product_id),
        "name": name or f"Product {product_id}",
        "category": None,
        "price_per_day": float(rental_price) if rental_price else 0.0,  # Ціна оренди
        "damage_cost": float(price) if price else 0.0,  # Ціна купівлі
        "quantity": quantity or 0,
        "image_url": image_url,
        "description": description,
        "replacement_price": float(price) if price else None,
        "damage_category": None,
        "location": {
            "zone": zone,
            "aisle": aisle,
            "shelf": shelf
        },
        "cleaning_status": cleaning_status,
        "product_state": product_state
    }


# ============================================================
# SEND TO PROCESSING (WASH / REPAIR / LAUNDRY)
# ============================================================

class SendToProcessingRequest(BaseModel):
    product_id: int
    sku: str
    quantity: int = 1
    action_type: str  # wash, repair, laundry
    notes: Optional[str] = None
    source: str = 'reaudit'


@router.post("/send-to-processing")
async def send_to_processing(
    data: SendToProcessingRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Відправити товар на обробку (мийка/реставрація/хімчистка)
    - Заморожує вказану кількість
    - Оновлює статус товару
    """
    import uuid
    
    action_labels = {
        'wash': 'На мийці',
        'repair': 'На реставрації',
        'laundry': 'На хімчистці',
        'write_off': 'Списано'
    }
    
    if data.action_type not in action_labels:
        raise HTTPException(status_code=400, detail=f"Invalid action_type: {data.action_type}")
    
    # Стан складу читається через канонічний AvailabilityService — власного
    # SQL-розрахунку в цьому роуті більше немає (Завдання №11, точка G).
    #
    # Стара формула: available = products.quantity - products.frozen_quantity.
    # Вона не бачила ні замовлень, ні soft-резервів, ні періоду аренди.
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot = AvailabilityService(db).get_availability(
        product_id=data.product_id,
        start_date=today,
        end_date=today,
        quantity=data.quantity,
    )

    if not snapshot["product_exists"]:
        raise HTTPException(status_code=404, detail="Product not found")

    sku = snapshot["sku"]
    name = snapshot["product_name"]
    frozen_qty = snapshot["on_processing_quantity"]

    # ПОРІГ БЛОКУВАННЯ свідомо залишений фізичним: скільки одиниць реально
    # лежить на складі й ще не в обробці. Відправка на мийку — операція з
    # фізичним товаром, тому броня на майбутню дату не має її забороняти:
    # інакше комірник не змив би товар, який завтра їде до клієнта.
    available_qty = max(0, snapshot["total_quantity"] - frozen_qty)

    if data.quantity > available_qty:
        raise HTTPException(
            status_code=400, 
            detail=f"Недостатньо доступної кількості. Доступно: {available_qty}, запитано: {data.quantity}"
        )

    # Канонічна доступність на сьогодні йде у відповідь як попередження:
    # оператор має бачити, що товар потрібен активному замовленню, навіть
    # якщо операцію не заблоковано.
    canonical_available = snapshot["available_quantity"]
    conflicts_with_reservations = data.quantity > canonical_available
    
    # Маппінг action_type до state в БД
    action_to_state = {
        'wash': 'on_wash',
        'repair': 'on_repair',
        'laundry': 'on_laundry'
    }
    
    # Списання. ЗНАЙДЕНО ПРИ МІГРАЦІЇ (Завдання №11, точка G): ця гілка ніколи
    # не працювала — вона читає `current_qty`, яка в функції не визначена
    # (розпаковувалася `quantity`). Тобто будь-який виклик з
    # `action_type='write_off'` завершувався `NameError` -> HTTP 500 ще до
    # будь-яких моїх змін.
    #
    # Гілку свідомо НЕ «оживлено»: вона зменшує `products.quantity`, а це саме
    # той клас операцій, який власник виніс в окремий Inventory Quantity
    # Semantics Audit (Завдання №12). Увімкнути списання тут означало б
    # почати змінювати фізичні залишки складу без окремого рішення.
    #
    # Тому непрацездатність зафіксована явно, замість падіння з NameError:
    # факт «списання через цей endpoint не підтримується» тепер видно
    # оператору, а не лише в трейсбеку.
    if data.action_type == 'write_off':
        raise HTTPException(
            status_code=501,
            detail=(
                "Списання через цей endpoint не підтримується. "
                "Використайте оформлення пошкодження/списання у Damage Hub."
            ),
        )
    else:
        # Заморозити товар для обробки
        new_state = action_to_state.get(data.action_type, 'processing')
        new_frozen_qty = (frozen_qty or 0) + data.quantity
        db.execute(text("""
            UPDATE products 
            SET frozen_quantity = :frozen_qty,
                state = :new_state
            WHERE product_id = :product_id
        """), {
            "frozen_qty": new_frozen_qty,
            "product_id": data.product_id,
            "new_state": new_state
        })
    
    # Записати в processing_queue (або інша таблиця для черги обробки)
    # Спочатку перевіримо чи існує таблиця
    try:
        queue_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO processing_queue 
            (id, product_id, sku, quantity, action_type, status, notes, source, created_at)
            VALUES
            (:id, :product_id, :sku, :quantity, :action_type, 'pending', :notes, :source, NOW())
        """), {
            "id": queue_id,
            "product_id": data.product_id,
            "sku": data.sku,
            "quantity": data.quantity,
            "action_type": data.action_type,
            "notes": data.notes,
            "source": data.source
        })
    except Exception as e:
        # Якщо таблиці немає - створимо її
        if "doesn't exist" in str(e) or "1146" in str(e):
            db.execute(text("""
                CREATE TABLE IF NOT EXISTS processing_queue (
                    id VARCHAR(36) PRIMARY KEY,
                    product_id INT NOT NULL,
                    sku VARCHAR(100),
                    quantity INT DEFAULT 1,
                    action_type VARCHAR(50) NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    notes TEXT,
                    source VARCHAR(50),
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    completed_at DATETIME,
                    completed_by VARCHAR(100)
                )
            """))
            db.commit()
            
            # Повторити вставку
            queue_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO processing_queue 
                (id, product_id, sku, quantity, action_type, status, notes, source, created_at)
                VALUES
                (:id, :product_id, :sku, :quantity, :action_type, 'pending', :notes, :source, NOW())
            """), {
                "id": queue_id,
                "product_id": data.product_id,
                "sku": data.sku,
                "quantity": data.quantity,
                "action_type": data.action_type,
                "notes": data.notes,
                "source": data.source
            })
    
    db.commit()
    
    # Для хімчистки - також додати запис в product_damage_history
    # щоб товар з'явився в черзі хімчистки в Damage Hub
    if data.action_type == 'laundry':
        try:
            pdh_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO product_damage_history (
                    id, product_id, sku, product_name, category,
                    damage_type, processing_type, processing_status,
                    qty, processed_qty, note, created_at, created_by
                )
                SELECT 
                    :id, :product_id, :sku, name, category_name,
                    'Внутрішня обробка', 'laundry', 'pending',
                    :qty, 0, :notes, NOW(), 'system'
                FROM products
                WHERE product_id = :product_id
            """), {
                "id": pdh_id,
                "product_id": data.product_id,
                "sku": data.sku,
                "qty": data.quantity,
                "notes": data.notes or "Відправлено з кабінету переобліку"
            })
            db.commit()
        except Exception as e:
            print(f"[Inventory] Warning: Could not add to product_damage_history: {e}")
    
    return {
        "success": True,
        "message": f"{data.quantity} шт '{name}' відправлено на {action_labels[data.action_type].lower()}",
        "queue_id": queue_id,
        "product_id": data.product_id,
        "sku": data.sku,
        "quantity": data.quantity,
        "action_type": data.action_type,
        "new_frozen_quantity": new_frozen_qty,
        # Additive-поля з канонічного розрахунку. Історичні ключі вище не
        # змінені, тому наявний UI переобліку працює як раніше.
        "canonical_available_quantity": canonical_available,
        "physical_available_quantity": available_qty,
        "conflicts_with_reservations": conflicts_with_reservations,
        "reserved_quantity": snapshot["reserved_quantity"],
        "soft_reserved_quantity": snapshot["soft_reserved_quantity"]
    }
