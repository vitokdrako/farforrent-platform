"""
Partial Returns API - API для часткового повернення замовлень
Дозволяє обробляти ситуації коли клієнт повертає не всі товари
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import List, Optional

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/partial-returns", tags=["partial-returns"])


# === PYDANTIC MODELS ===

class PartialReturnItem(BaseModel):
    """Один товар у частковому поверненні"""
    product_id: int
    sku: str
    name: str
    rented_qty: int
    returned_qty: int
    not_returned_qty: int
    action: str  # 'loss' | 'extend'
    daily_rate: Optional[float] = None  # Добова ставка (для extend)
    adjusted_daily_rate: Optional[float] = None  # Скорегована менеджером
    loss_amount: Optional[float] = None  # Сума втрати (для loss)


class PartialReturnRequest(BaseModel):
    """Запит на часткове повернення"""
    items: List[PartialReturnItem]
    manager_notes: Optional[str] = None


class ExtensionInfo(BaseModel):
    """Інформація про продовження оренди"""
    id: int
    order_id: int
    product_id: int
    sku: str
    name: str
    qty: int
    original_end_date: str
    daily_rate: float
    days_extended: int
    total_charged: float
    status: str  # 'active' | 'completed' | 'lost'


# === HELPER FUNCTIONS ===

def ensure_tables_exist(db: Session):
    """Створити таблиці якщо не існують"""
    
    # Додати колонку has_partial_return до orders (якщо не існує)
    try:
        db.execute(text("""
            ALTER TABLE orders ADD COLUMN has_partial_return TINYINT(1) DEFAULT 0
        """))
    except Exception:
        pass  # Колонка вже існує
    
    # Таблиця для продовжень оренди
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS order_extensions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id INT NOT NULL,
            sku VARCHAR(50),
            name VARCHAR(255),
            qty INT DEFAULT 1,
            original_end_date DATE,
            daily_rate DECIMAL(10,2) DEFAULT 0,
            adjusted_daily_rate DECIMAL(10,2) DEFAULT NULL,
            days_extended INT DEFAULT 0,
            total_charged DECIMAL(10,2) DEFAULT 0,
            status ENUM('active', 'completed', 'lost') DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP NULL,
            created_by VARCHAR(100),
            notes TEXT,
            INDEX idx_order_id (order_id),
            INDEX idx_status (status)
        )
    """))
    
    # Таблиця для логу часткових повернень
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS partial_return_log (
            id INT AUTO_INCREMENT PRIMARY KEY,
            order_id INT NOT NULL,
            product_id INT NOT NULL,
            sku VARCHAR(50),
            action ENUM('loss', 'extend', 'returned') NOT NULL,
            qty INT DEFAULT 1,
            amount DECIMAL(10,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(100),
            notes TEXT,
            INDEX idx_order_id (order_id)
        )
    """))
    
    db.commit()


def get_product_daily_rate(db: Session, product_id: int) -> float:
    """
    Отримати добову ставку для товару
    Використовує rental_price як базу (можна налаштувати)
    """
    result = db.execute(text("""
        SELECT rental_price, price FROM products WHERE product_id = :product_id
    """), {"product_id": product_id}).fetchone()
    
    if result:
        rental_price = float(result[0] or 0)
        full_price = float(result[1] or 0)
        
        # Добова ставка = rental_price (ціна за день оренди)
        # Якщо rental_price не вказана, використовуємо 10% від повної ціни
        if rental_price > 0:
            return rental_price
        elif full_price > 0:
            return round(full_price * 0.1, 2)
    
    return 0.0


def get_product_full_price(db: Session, product_id: int) -> float:
    """Отримати повну ціну товару (для втрати)"""
    result = db.execute(text("""
        SELECT price FROM products WHERE product_id = :product_id
    """), {"product_id": product_id}).fetchone()
    
    return float(result[0] or 0) if result else 0.0


# === API ENDPOINTS ===

@router.get("/order/{order_id}/not-returned")
async def get_not_returned_items(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати список неповернених товарів для замовлення
    Використовується для показу модалки часткового повернення
    """
    # Отримати товари з order_items
    result = db.execute(text("""
        SELECT 
            oi.product_id,
            p.sku,
            p.name,
            oi.quantity as rented_qty,
            p.price as full_price,
            p.rental_price as daily_rate,
            p.image_url
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :order_id
    """), {"order_id": order_id})
    
    items = []
    for row in result:
        rented = int(row[3] or 0)
        full_price = float(row[4] or 0)
        daily_rate = float(row[5] or 0)
        
        # Якщо daily_rate не вказана, використовуємо rental_price
        if daily_rate <= 0 and full_price > 0:
            daily_rate = round(full_price * 0.1, 2)
        
        items.append({
            "product_id": row[0],
            "sku": row[1] or "",
            "name": row[2] or "",
            "rented_qty": rented,
            "returned_qty": 0,  # Буде заповнено з frontend
            "not_returned_qty": rented,  # За замовчуванням всі неповернуті
            "full_price": full_price,
            "daily_rate": daily_rate,
            "loss_amount": full_price * rented,
            "image_url": row[6] or ""
        })
    
    return {"order_id": order_id, "items": items}


@router.post("/order/{order_id}/process")
async def process_partial_return(
    order_id: int,
    data: PartialReturnRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Обробити часткове повернення
    
    Для кожного неповерненого товару:
    - action='loss': нарахувати повну вартість як втрату
    - action='extend': створити запис продовження оренди
    """
    ensure_tables_exist(db)
    
    try:
        total_loss_amount = 0.0
        extensions_created = 0
        losses_recorded = 0
        
        # Отримати оригінальну дату закінчення оренди
        order_result = db.execute(text("""
            SELECT rental_end_date, order_number FROM orders WHERE order_id = :order_id
        """), {"order_id": order_id}).fetchone()
        
        original_end_date = order_result[0] if order_result else datetime.now().date()
        order_number = order_result[1] if order_result else f"#{order_id}"
        
        for item in data.items:
            if item.action == 'loss':
                # === ВТРАТА ===
                loss_amount = item.loss_amount or (get_product_full_price(db, item.product_id) * item.not_returned_qty)
                total_loss_amount += loss_amount
                
                # 1. Зменшити кількість товару в products
                db.execute(text("""
                    UPDATE products 
                    SET quantity = GREATEST(0, quantity - :qty)
                    WHERE product_id = :product_id
                """), {
                    "product_id": item.product_id,
                    "qty": item.not_returned_qty
                })
                print(f"[PartialReturn] 📦 Зменшено кількість {item.sku} на {item.not_returned_qty}")
                
                # 2. Записати в product_history (Кабінет переобліку)
                try:
                    db.execute(text("""
                        INSERT INTO product_history (product_id, action, actor, details, created_at)
                        VALUES (:product_id, 'ПОВНА ВТРАТА', 'system', :details, NOW())
                    """), {
                        "product_id": item.product_id,
                        "details": f"Замовлення #{order_number}. Списано {item.not_returned_qty} шт. Сума відшкодування: ₴{loss_amount:.2f}"
                    })
                    print(f"[PartialReturn] 📜 Записано в історію декору")
                except Exception as e:
                    print(f"[PartialReturn] ⚠️ Помилка запису в product_history: {e}")
                
                # 3. Записати в product_damage_history (Кабінет шкоди)
                import uuid
                damage_id = str(uuid.uuid4())
                db.execute(text("""
                    INSERT INTO product_damage_history 
                    (id, product_id, sku, product_name, order_id, order_number, stage, 
                     damage_type, damage_code, severity, fee, fee_per_item, qty, note, created_by)
                    VALUES 
                    (:id, :product_id, :sku, :name, :order_id, :order_number, 'return',
                     'Повна втрата', 'TOTAL_LOSS', 'critical', :fee, :fee_per_item, :qty, :note, 'system')
                """), {
                    "id": damage_id,
                    "product_id": item.product_id,
                    "sku": item.sku,
                    "name": item.name,
                    "order_id": order_id,
                    "order_number": order_number,
                    "fee": loss_amount,
                    "fee_per_item": loss_amount / item.not_returned_qty if item.not_returned_qty > 0 else loss_amount,
                    "qty": item.not_returned_qty,
                    "note": f"Товар не повернуто. Повна втрата. Нараховано ₴{loss_amount:.2f}"
                })
                print(f"[PartialReturn] ⚠️ Записано в кабінет шкоди як 'Повна втрата'")
                
                # 4. Записати в partial_return_log
                db.execute(text("""
                    INSERT INTO partial_return_log 
                    (order_id, product_id, sku, action, qty, amount, notes)
                    VALUES (:order_id, :product_id, :sku, 'loss', :qty, :amount, :notes)
                """), {
                    "order_id": order_id,
                    "product_id": item.product_id,
                    "sku": item.sku,
                    "qty": item.not_returned_qty,
                    "amount": loss_amount,
                    "notes": f"Повна втрата товару. Вартість: ₴{loss_amount:.2f}"
                })
                
                losses_recorded += 1
                print(f"[PartialReturn] 🔴 ВТРАТА: {item.sku} x{item.not_returned_qty} = ₴{loss_amount:.2f}")
                
            elif item.action == 'extend':
                # === ПРОДОВЖЕННЯ ОРЕНДИ ===
                daily_rate = item.adjusted_daily_rate or item.daily_rate or get_product_daily_rate(db, item.product_id)
                
                # ✅ ВИПРАВЛЕННЯ: Перевірити чи продовження вже існує
                existing = db.execute(text("""
                    SELECT id FROM order_extensions 
                    WHERE order_id = :order_id AND sku = :sku AND status = 'active'
                """), {"order_id": order_id, "sku": item.sku}).fetchone()
                
                if existing:
                    # Продовження вже існує - оновити кількість якщо потрібно
                    print(f"[PartialReturn] ℹ️ Продовження для {item.sku} вже існує (ID: {existing[0]}), пропускаємо")
                    continue
                
                db.execute(text("""
                    INSERT INTO order_extensions 
                    (order_id, product_id, sku, name, qty, original_end_date, daily_rate, adjusted_daily_rate, status, notes)
                    VALUES (:order_id, :product_id, :sku, :name, :qty, :original_end_date, :daily_rate, :adjusted_rate, 'active', :notes)
                """), {
                    "order_id": order_id,
                    "product_id": item.product_id,
                    "sku": item.sku,
                    "name": item.name,
                    "qty": item.not_returned_qty,
                    "original_end_date": original_end_date,
                    "daily_rate": daily_rate,
                    "adjusted_rate": item.adjusted_daily_rate,
                    "notes": f"Продовження оренди. Добова ставка: ₴{daily_rate:.2f}"
                })
                
                # Записати в лог
                db.execute(text("""
                    INSERT INTO partial_return_log 
                    (order_id, product_id, sku, action, qty, amount, notes)
                    VALUES (:order_id, :product_id, :sku, 'extend', :qty, :amount, :notes)
                """), {
                    "order_id": order_id,
                    "product_id": item.product_id,
                    "sku": item.sku,
                    "qty": item.not_returned_qty,
                    "amount": daily_rate,
                    "notes": f"Продовження оренди. Добова: ₴{daily_rate:.2f}"
                })
                
                extensions_created += 1
                print(f"[PartialReturn] 🟡 ПРОДОВЖЕННЯ: {item.sku} x{item.not_returned_qty}, ₴{daily_rate:.2f}/день")
        
        # Якщо є втрати - створити фінансову транзакцію з деталями
        if total_loss_amount > 0:
            # Збираємо деталі втрат для опису
            loss_details = []
            for item in data.items:
                if item.action == 'loss':
                    item_loss = item.loss_amount or (get_product_full_price(db, item.product_id) * item.not_returned_qty)
                    loss_details.append(f"{item.sku} x{item.not_returned_qty} = ₴{item_loss:.2f}")
            
            description = f"ПОВНА ВТРАТА товарів. Замовлення #{order_number}. " + "; ".join(loss_details)
            
            db.execute(text("""
                INSERT INTO fin_payments 
                (order_id, payment_type, amount, currency, note, occurred_at)
                VALUES (:order_id, 'loss', :amount, 'UAH', :description, NOW())
            """), {
                "order_id": order_id,
                "amount": total_loss_amount,
                "description": description
            })
            print(f"[PartialReturn] 💰 Створено фінансову транзакцію: {description}")
        
        # Оновити статус замовлення
        if extensions_created > 0:
            # Є продовження - статус partial_return
            db.execute(text("""
                UPDATE orders 
                SET status = 'partial_return',
                    has_partial_return = 1,
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
            
            # Оновити issue_card
            db.execute(text("""
                UPDATE issue_cards 
                SET status = 'partial_return',
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
        else:
            # Тільки втрати - можна закрити як returned
            db.execute(text("""
                UPDATE orders 
                SET status = 'returned',
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
        
        # Додати запис в lifecycle
        db.execute(text("""
            INSERT INTO order_lifecycle (order_id, stage, notes, created_at)
            VALUES (:order_id, :stage, :notes, NOW())
        """), {
            "order_id": order_id,
            "stage": "partial_return" if extensions_created > 0 else "returned",
            "notes": f"Часткове повернення: {losses_recorded} втрат, {extensions_created} продовжень"
        })
        
        db.commit()
        
        return {
            "success": True,
            "order_id": order_id,
            "losses_recorded": losses_recorded,
            "extensions_created": extensions_created,
            "total_loss_amount": total_loss_amount,
            "status": "partial_return" if extensions_created > 0 else "returned"
        }
        
    except Exception as e:
        db.rollback()
        print(f"[PartialReturn] ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}/extensions")
async def get_order_extensions(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """Отримати всі продовження оренди для замовлення"""
    ensure_tables_exist(db)
    
    result = db.execute(text("""
        SELECT 
            id, order_id, product_id, sku, name, qty,
            original_end_date, daily_rate, adjusted_daily_rate,
            days_extended, total_charged, status, created_at, completed_at
        FROM order_extensions
        WHERE order_id = :order_id
        ORDER BY created_at DESC
    """), {"order_id": order_id})
    
    extensions = []
    for row in result:
        # Розрахувати дні прострочення
        original_end = row[6]
        days = 0
        if original_end and row[11] == 'active':
            days = (datetime.now().date() - original_end).days
            if days < 0:
                days = 0
        else:
            days = int(row[9] or 0)
        
        rate = float(row[8] or row[7] or 0)
        total = days * rate * int(row[5] or 1)
        
        extensions.append({
            "id": row[0],
            "order_id": row[1],
            "product_id": row[2],
            "sku": row[3] or "",
            "name": row[4] or "",
            "qty": row[5] or 1,
            "original_end_date": str(row[6]) if row[6] else "",
            "daily_rate": rate,
            "days_extended": days,
            "total_charged": total,
            "status": row[11] or "active",
            "created_at": row[12].isoformat() if row[12] else ""
        })
    
    return {"order_id": order_id, "extensions": extensions}


@router.post("/order/{order_id}/extensions/{extension_id}/complete")
async def complete_extension(
    order_id: int,
    extension_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Завершити продовження (товар повернуто)
    Нарахувати фінальну суму за прострочення
    """
    ensure_tables_exist(db)
    
    try:
        # Отримати дані про продовження
        ext = db.execute(text("""
            SELECT product_id, sku, name, qty, original_end_date, daily_rate, adjusted_daily_rate
            FROM order_extensions
            WHERE id = :ext_id AND order_id = :order_id AND status = 'active'
        """), {"ext_id": extension_id, "order_id": order_id}).fetchone()
        
        if not ext:
            raise HTTPException(status_code=404, detail="Продовження не знайдено")
        
        # Розрахувати дні та суму
        original_end = ext[4]
        days = data.get('days', 0)
        
        if not days and original_end:
            days = (datetime.now().date() - original_end).days
            if days < 0:
                days = 0
        
        rate = float(data.get('adjusted_rate') or ext[6] or ext[5] or 0)
        qty = int(ext[3] or 1)
        total = days * rate * qty
        
        # Можливість корекції суми
        final_amount = float(data.get('final_amount', total))
        
        # Оновити запис
        db.execute(text("""
            UPDATE order_extensions
            SET status = 'completed',
                days_extended = :days,
                total_charged = :total,
                adjusted_daily_rate = :rate,
                completed_at = NOW()
            WHERE id = :ext_id
        """), {
            "ext_id": extension_id,
            "days": days,
            "total": final_amount,
            "rate": rate
        })
        
        # Створити фінансову транзакцію
        if final_amount > 0:
            db.execute(text("""
                INSERT INTO fin_payments 
                (order_id, payment_type, amount, currency, note, occurred_at)
                VALUES (:order_id, 'late', :amount, 'UAH', :description, NOW())
            """), {
                "order_id": order_id,
                "amount": final_amount,
                "description": f"Прострочення оренди {ext[1]} x{qty}: {days} днів × ₴{rate:.2f} = ₴{final_amount:.2f}"
            })
        
        # Записати в лог
        db.execute(text("""
            INSERT INTO partial_return_log 
            (order_id, product_id, sku, action, qty, amount, notes)
            VALUES (:order_id, :product_id, :sku, 'returned', :qty, :amount, :notes)
        """), {
            "order_id": order_id,
            "product_id": ext[0],
            "sku": ext[1],
            "qty": qty,
            "amount": final_amount,
            "notes": f"Повернено після {days} днів прострочення"
        })
        
        # Перевірити чи всі продовження завершені
        active_count = db.execute(text("""
            SELECT COUNT(*) FROM order_extensions 
            WHERE order_id = :order_id AND status = 'active'
        """), {"order_id": order_id}).scalar()
        
        if active_count == 0:
            # Всі товари повернуто - закрити замовлення
            db.execute(text("""
                UPDATE orders 
                SET status = 'returned',
                    has_partial_return = 0,
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
            
            db.execute(text("""
                INSERT INTO order_lifecycle (order_id, stage, notes, created_at)
                VALUES (:order_id, 'returned', 'Всі товари повернуто (після часткового повернення)', NOW())
            """), {"order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "extension_id": extension_id,
            "days": days,
            "amount": final_amount,
            "all_completed": active_count == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[PartialReturn] ❌ Error completing extension: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order/{order_id}/extensions/{extension_id}/mark-lost")
async def mark_extension_lost(
    order_id: int,
    extension_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Позначити товар як втрачений (після продовження)
    """
    ensure_tables_exist(db)
    
    try:
        # Отримати дані
        ext = db.execute(text("""
            SELECT product_id, sku, name, qty, daily_rate
            FROM order_extensions
            WHERE id = :ext_id AND order_id = :order_id AND status = 'active'
        """), {"ext_id": extension_id, "order_id": order_id}).fetchone()
        
        if not ext:
            raise HTTPException(status_code=404, detail="Продовження не знайдено")
        
        # Отримати повну ціну товару
        full_price = get_product_full_price(db, ext[0])
        loss_amount = float(data.get('loss_amount', full_price * int(ext[3] or 1)))
        
        # Оновити статус на 'lost'
        db.execute(text("""
            UPDATE order_extensions
            SET status = 'lost',
                total_charged = :amount,
                completed_at = NOW()
            WHERE id = :ext_id
        """), {
            "ext_id": extension_id,
            "amount": loss_amount
        })
        
        # Створити фінансову транзакцію
        db.execute(text("""
            INSERT INTO fin_payments 
            (order_id, payment_type, amount, currency, note, occurred_at)
            VALUES (:order_id, 'loss', :amount, 'UAH', :description, NOW())
        """), {
            "order_id": order_id,
            "amount": loss_amount,
            "description": f"Втрата товару {ext[1]} x{ext[3]}: ₴{loss_amount:.2f}"
        })
        
        # Записати в лог
        db.execute(text("""
            INSERT INTO partial_return_log 
            (order_id, product_id, sku, action, qty, amount, notes)
            VALUES (:order_id, :product_id, :sku, 'loss', :qty, :amount, :notes)
        """), {
            "order_id": order_id,
            "product_id": ext[0],
            "sku": ext[1],
            "qty": ext[3],
            "amount": loss_amount,
            "notes": f"Позначено як втрата після продовження"
        })
        
        # Перевірити чи всі завершені
        active_count = db.execute(text("""
            SELECT COUNT(*) FROM order_extensions 
            WHERE order_id = :order_id AND status = 'active'
        """), {"order_id": order_id}).scalar()
        
        if active_count == 0:
            db.execute(text("""
                UPDATE orders 
                SET status = 'returned',
                    has_partial_return = 0,
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "extension_id": extension_id,
            "loss_amount": loss_amount,
            "all_completed": active_count == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[PartialReturn] ❌ Error marking lost: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ProcessLossRequest(BaseModel):
    """Запит на обробку втрати — єдиний endpoint списання"""
    product_id: int
    sku: str
    name: str
    qty: int
    loss_amount: float
    order_id: Optional[int] = None
    order_number: Optional[str] = None
    version_id: Optional[int] = None
    skip_damage_record: bool = False
    photo_url: Optional[str] = None
    note: Optional[str] = None
    created_by: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = 'critical'


@router.post("/process-loss")
async def process_loss_from_damage_modal(
    data: ProcessLossRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Обробити повну втрату товару з модалки пошкоджень.
    Зменшує кількість товару та записує в історію.
    """
    ensure_tables_exist(db)
    
    try:
        order_number = data.order_number or (f"#{data.order_id}" if data.order_id else "Невідомо")
        
        # 1. Зменшити кількість товару в products
        db.execute(text("""
            UPDATE products 
            SET quantity = GREATEST(0, quantity - :qty)
            WHERE product_id = :product_id
        """), {
            "product_id": data.product_id,
            "qty": data.qty
        })
        print(f"[ProcessLoss] 📦 Зменшено кількість {data.sku} на {data.qty}")
        
        # 2. Записати в product_history (Кабінет переобліку)
        try:
            db.execute(text("""
                INSERT INTO product_history (product_id, action, actor, details, created_at)
                VALUES (:product_id, 'ПОВНА ВТРАТА', 'system', :details, NOW())
            """), {
                "product_id": data.product_id,
                "details": f"Замовлення {order_number}. Списано {data.qty} шт. Сума відшкодування: ₴{data.loss_amount:.2f}"
            })
            print(f"[ProcessLoss] 📜 Записано в історію декору")
        except Exception as e:
            print(f"[ProcessLoss] ⚠️ Помилка запису в product_history: {e}")
        
        # 3. Записати фінансову транзакцію (якщо є order_id)
        if data.order_id:
            db.execute(text("""
                INSERT INTO fin_payments 
                (order_id, payment_type, amount, currency, note, occurred_at)
                VALUES (:order_id, 'loss', :amount, 'UAH', :description, NOW())
            """), {
                "order_id": data.order_id,
                "amount": data.loss_amount,
                "description": f"ПОВНА ВТРАТА: {data.sku} x{data.qty} = ₴{data.loss_amount:.2f}"
            })
            print(f"[ProcessLoss] 💰 Створено фінансову транзакцію")
        
        # 4. Записати в product_damage_history (якщо не створено раніше через DamageModal)
        if not data.skip_damage_record:
            import uuid
            damage_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO product_damage_history 
                (id, product_id, sku, product_name, category, order_id, order_number, stage, 
                 damage_type, damage_code, severity, fee, fee_per_item, qty, photo_url, note,
                 processing_type, processing_status, created_by, created_at)
                VALUES 
                (:id, :product_id, :sku, :name, :category, :order_id, :order_number, 'return',
                 'Повна втрата', 'TOTAL_LOSS', :severity, :fee, :fee_per_item, :qty, :photo_url, :note,
                 'total_loss', 'written_off', :created_by, NOW())
            """), {
                "id": damage_id,
                "product_id": data.product_id,
                "sku": data.sku,
                "name": data.name,
                "category": data.category or "",
                "order_id": data.order_id,
                "order_number": order_number,
                "severity": data.severity or "critical",
                "fee": data.loss_amount,
                "fee_per_item": data.loss_amount / data.qty if data.qty > 0 else data.loss_amount,
                "qty": data.qty,
                "photo_url": data.photo_url,
                "note": data.note or f"Повна втрата. Сума: ₴{data.loss_amount:.2f}",
                "created_by": data.created_by or "system",
            })
            print(f"[ProcessLoss] 📋 Записано в список списаних (damage_id: {damage_id})")
        else:
            print(f"[ProcessLoss] ℹ️ damage_record пропущено (вже створено через DamageModal)")
        
        # 5. Оновити partial_return_version_items (якщо є version_id)
        if data.version_id:
            # Зменшити qty в версії
            db.execute(text("""
                UPDATE partial_return_version_items 
                SET qty = GREATEST(0, qty - :loss_qty)
                WHERE version_id = :vid AND product_id = :pid
            """), {
                "vid": data.version_id,
                "pid": data.product_id,
                "loss_qty": data.qty
            })
            # Видалити рядки з qty = 0
            db.execute(text("""
                DELETE FROM partial_return_version_items 
                WHERE version_id = :vid AND qty = 0
            """), {"vid": data.version_id})
            # Перевірити чи залишились товари у версії
            remaining = db.execute(text("""
                SELECT COUNT(*) FROM partial_return_version_items 
                WHERE version_id = :vid AND qty > 0
            """), {"vid": data.version_id}).scalar()
            if remaining == 0:
                # Всі товари списані — закриваємо версію
                db.execute(text("""
                    UPDATE partial_return_versions 
                    SET status = 'returned', updated_at = NOW()
                    WHERE version_id = :vid
                """), {"vid": data.version_id})
                print(f"[ProcessLoss] 📋 Версія {data.version_id} закрита — всі товари списані")
            else:
                # Оновити total_price версії
                db.execute(text("""
                    UPDATE partial_return_versions 
                    SET total_price = (
                        SELECT COALESCE(SUM(qty * daily_rate), 0) 
                        FROM partial_return_version_items 
                        WHERE version_id = :vid
                    )
                    WHERE version_id = :vid
                """), {"vid": data.version_id})
            print(f"[ProcessLoss] 📋 Оновлено version_items (version_id: {data.version_id}, залишилось: {remaining})")
        
        # 6. Оновити order_extensions (якщо є)
        if data.order_id:
            db.execute(text("""
                UPDATE order_extensions 
                SET qty = GREATEST(0, qty - :loss_qty)
                WHERE order_id = :oid AND product_id = :pid AND status = 'active'
            """), {
                "oid": data.order_id,
                "pid": data.product_id,
                "loss_qty": data.qty
            })
            # Закрити extensions з qty = 0
            db.execute(text("""
                UPDATE order_extensions 
                SET status = 'completed', notes = CONCAT(COALESCE(notes,''), ' | Списано: повна втрата')
                WHERE order_id = :oid AND product_id = :pid AND qty = 0 AND status = 'active'
            """), {"oid": data.order_id, "pid": data.product_id})
        
        db.commit()
        
        return {
            "success": True,
            "product_id": data.product_id,
            "sku": data.sku,
            "qty_reduced": data.qty,
            "loss_amount": data.loss_amount
        }
        
    except Exception as e:
        db.rollback()
        print(f"[ProcessLoss] ❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))



# === НОВИЙ ENDPOINT: Прийняти товари з продовження ===

class AcceptExtensionItem(BaseModel):
    """Один товар для приймання з продовження"""
    extension_id: Optional[int] = None
    sku: str
    qty: int
    returned_qty: int  # скільки реально повернули


class AcceptExtensionsRequest(BaseModel):
    """Запит на приймання товарів з продовження"""
    items: List[AcceptExtensionItem]
    notes: Optional[str] = None


@router.post("/order/{order_id}/accept-from-extension")
async def accept_items_from_extension(
    order_id: int,
    data: AcceptExtensionsRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Прийняти товари які були на продовженні оренди.
    
    Логіка:
    1. Для кожного товару знайти активне продовження
    2. Розрахувати дні прострочення (від original_end_date до сьогодні)
    3. Створити запис fin_payments з типом 'late' (менеджер може потім скоригувати)
    4. Розморозити товари (повернути в доступні)
    5. Записати в історію (partial_return_log та order_lifecycle)
    6. Якщо всі товари повернуто - закрити замовлення
    """
    ensure_tables_exist(db)
    
    try:
        from datetime import datetime
        today = datetime.now().date()
        
        results = []
        total_late_fee = 0
        items_accepted = 0
        
        for item in data.items:
            # Знайти активне продовження для цього SKU
            ext = db.execute(text("""
                SELECT id, product_id, sku, name, qty, original_end_date, daily_rate, adjusted_daily_rate
                FROM order_extensions 
                WHERE order_id = :order_id 
                  AND sku = :sku 
                  AND status = 'active'
                LIMIT 1
            """), {"order_id": order_id, "sku": item.sku}).fetchone()
            
            if not ext:
                print(f"[AcceptExt] ⚠️ Продовження для {item.sku} не знайдено")
                continue
            
            ext_id, product_id, sku, name, qty, original_end, daily_rate, adj_rate = ext
            
            # Розрахувати дні прострочення
            if original_end:
                days = (today - original_end).days
                if days < 0:
                    days = 0
            else:
                days = 0
            
            # Використати скориговану ставку якщо є
            rate = float(adj_rate or daily_rate or 0)
            returned_qty = item.returned_qty or qty
            
            # Розрахувати суму прострочення
            late_fee = days * rate * returned_qty
            total_late_fee += late_fee
            
            print(f"[AcceptExt] 📦 {sku}: {returned_qty} шт, {days} днів × ₴{rate:.2f} = ₴{late_fee:.2f}")
            
            # Оновити статус продовження
            if returned_qty >= qty:
                # Повністю повернуто - закрити продовження
                db.execute(text("""
                    UPDATE order_extensions
                    SET status = 'completed',
                        days_extended = :days,
                        total_charged = :total,
                        completed_at = NOW()
                    WHERE id = :ext_id
                """), {"ext_id": ext_id, "days": days, "total": late_fee})
            else:
                # Частково повернуто - зменшити кількість
                new_qty = qty - returned_qty
                db.execute(text("""
                    UPDATE order_extensions
                    SET qty = :new_qty
                    WHERE id = :ext_id
                """), {"ext_id": ext_id, "new_qty": new_qty})
            
            # Створити фінансову транзакцію (тип 'late' - прострочення)
            if late_fee > 0:
                db.execute(text("""
                    INSERT INTO fin_payments 
                    (order_id, payment_type, amount, currency, status, note, occurred_at)
                    VALUES (:order_id, 'late', :amount, 'UAH', 'pending', :description, NOW())
                """), {
                    "order_id": order_id,
                    "amount": late_fee,
                    "description": f"Прострочення: {sku} x{returned_qty}: {days} днів × ₴{rate:.2f} = ₴{late_fee:.2f}"
                })
            
            # Записати в лог часткового повернення
            db.execute(text("""
                INSERT INTO partial_return_log 
                (order_id, product_id, sku, action, qty, amount, notes)
                VALUES (:order_id, :product_id, :sku, 'returned', :qty, :amount, :notes)
            """), {
                "order_id": order_id,
                "product_id": product_id,
                "sku": sku,
                "qty": returned_qty,
                "amount": late_fee,
                "notes": f"Повернено після {days} днів прострочення"
            })
            
            # Розморозити товари (повернути в доступні)
            db.execute(text("""
                UPDATE products 
                SET quantity = quantity + :qty
                WHERE product_id = :product_id
            """), {"product_id": product_id, "qty": returned_qty})
            
            items_accepted += 1
            results.append({
                "sku": sku,
                "name": name,
                "qty": returned_qty,
                "days": days,
                "rate": rate,
                "late_fee": late_fee,
                "status": "completed" if returned_qty >= qty else "partial"
            })
        
        # Перевірити чи залишились активні продовження
        active_count = db.execute(text("""
            SELECT COUNT(*) FROM order_extensions 
            WHERE order_id = :order_id AND status = 'active'
        """), {"order_id": order_id}).scalar()
        
        all_completed = active_count == 0
        
        # Записати в lifecycle
        items_list = ", ".join([f"{r['sku']} x{r['qty']}" for r in results])
        db.execute(text("""
            INSERT INTO order_lifecycle 
            (order_id, stage, notes, created_by_name, created_at)
            VALUES (:order_id, :stage, :notes, 'system', NOW())
        """), {
            "order_id": order_id,
            "stage": "items_returned_from_extension",
            "notes": f"Прийнято з продовження: {items_list}. Нараховано прострочення: ₴{total_late_fee:.2f}"
        })
        
        # Якщо всі товари повернуто - можна закривати замовлення
        if all_completed:
            db.execute(text("""
                UPDATE orders 
                SET status = 'returned',
                    has_partial_return = 0,
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
            
            # ✅ ВАЖЛИВО: Оновити issue_card теж!
            db.execute(text("""
                UPDATE issue_cards 
                SET status = 'returned',
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
            
            db.execute(text("""
                INSERT INTO order_lifecycle 
                (order_id, stage, notes, created_by_name, created_at)
                VALUES (:order_id, 'returned', 'Всі товари повернуто (завершено часткове повернення)', 'system', NOW())
            """), {"order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "items_accepted": items_accepted,
            "total_late_fee": total_late_fee,
            "results": results,
            "active_extensions_remaining": active_count,
            "all_completed": all_completed,
            "message": "Всі товари повернуто!" if all_completed else f"Прийнято {items_accepted} позицій. Залишилось {active_count} на продовженні."
        }
        
    except Exception as e:
        db.rollback()
        print(f"[AcceptExt] ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order/{order_id}/extension-summary")
async def get_extension_summary(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати підсумок по продовженнях для замовлення.
    Показує активні та завершені продовження з нарахуваннями.
    """
    ensure_tables_exist(db)
    
    from datetime import datetime
    today = datetime.now().date()
    
    # Активні продовження
    active = db.execute(text("""
        SELECT id, sku, name, qty, original_end_date, daily_rate, adjusted_daily_rate
        FROM order_extensions 
        WHERE order_id = :order_id AND status = 'active'
        ORDER BY sku
    """), {"order_id": order_id}).fetchall()
    
    active_items = []
    total_pending = 0
    
    for row in active:
        ext_id, sku, name, qty, original_end, daily_rate, adj_rate = row
        
        # Розрахувати поточне прострочення
        if original_end:
            days = (today - original_end).days
            if days < 0:
                days = 0
        else:
            days = 0
        
        rate = float(adj_rate or daily_rate or 0)
        pending = days * rate * qty
        total_pending += pending
        
        active_items.append({
            "extension_id": ext_id,
            "sku": sku,
            "name": name,
            "qty": qty,
            "original_end_date": str(original_end) if original_end else None,
            "days_overdue": days,
            "daily_rate": rate,
            "pending_amount": pending
        })
    
    # Завершені продовження
    completed = db.execute(text("""
        SELECT id, sku, name, qty, days_extended, total_charged, completed_at, status
        FROM order_extensions 
        WHERE order_id = :order_id AND status IN ('completed', 'lost')
        ORDER BY completed_at DESC
    """), {"order_id": order_id}).fetchall()
    
    completed_items = []
    total_charged = 0
    
    for row in completed:
        ext_id, sku, name, qty, days, charged, completed_at, status = row
        charged = float(charged or 0)
        total_charged += charged
        
        completed_items.append({
            "extension_id": ext_id,
            "sku": sku,
            "name": name,
            "qty": qty,
            "days_extended": days,
            "amount_charged": charged,
            "completed_at": str(completed_at) if completed_at else None,
            "status": status
        })
    
    return {
        "order_id": order_id,
        "active": {
            "count": len(active_items),
            "items": active_items,
            "total_pending": total_pending
        },
        "completed": {
            "count": len(completed_items),
            "items": completed_items,
            "total_charged": total_charged
        },
        "grand_total": total_pending + total_charged
    }
