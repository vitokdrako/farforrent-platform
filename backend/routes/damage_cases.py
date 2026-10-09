"""
Damage Cases API - Кейси шкоди
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from sqlalchemy.orm import Session
from sqlalchemy import text
from database_rentalhub import get_rh_db
from datetime import datetime
import uuid
import jwt
import os

router = APIRouter(prefix="/api/damage-cases", tags=["damage-cases"])

# JWT Configuration (має бути такий самий як в auth.py)
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"

def get_current_user(authorization: str = Header(None)):
    """Extract user info from JWT token"""
    if not authorization or not authorization.startswith('Bearer '):
        print("❌ No authorization header")
        return None
    
    try:
        token = authorization.split(' ')[1]
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"✅ Token decoded: {payload}")
        return {
            'email': payload.get('email'),
            'username': payload.get('username') or payload.get('sub'),
            'user_id': payload.get('user_id')
        }
    except Exception as e:
        print(f"❌ Token decode error: {e}")
        return None


@router.post("/create")
async def create_damage_case(
    data: dict,
    authorization: str = Header(None),
    rh_db: Session = Depends(get_rh_db)
):
    """
    Створити кейс шкоди для товару
    
    action_type:
    - repair: Ремонт (заморожує товар)
    - restoration: Реставрація (заморожує товар)
    - washing: Мийка (заморожує товар)
    - total_loss: Повна втрата (віднімає від кількості)
    """
    try:
        # Отримати поточного користувача
        current_user = get_current_user(authorization)
        created_by = (current_user.get('username') or current_user.get('email')) if current_user else 'Unknown'
        
        product_id = data.get('product_id')
        qty = data.get('qty', 1)
        action_type = data.get('action_type', 'repair')
        description = data.get('description', '')
        estimated_cost = data.get('estimated_cost', 0)
        
        if not product_id or qty <= 0:
            raise HTTPException(status_code=400, detail="Некоректні дані")
        
        # Перевірити наявну кількість товару і frozen
        product_query = text("SELECT quantity, frozen_quantity FROM products WHERE product_id = :pid")
        product = rh_db.execute(product_query, {'pid': product_id}).fetchone()
        
        if not product:
            raise HTTPException(status_code=404, detail="Товар не знайдено")
        
        current_qty = product[0] or 0
        frozen_qty = product[1] or 0
        available_qty = current_qty - frozen_qty
        
        if qty > available_qty:
            raise HTTPException(
                status_code=400,
                detail=f"Недостатньо товару. Доступно: {available_qty} (загалом: {current_qty}, заморожено: {frozen_qty})"
            )
        
        # Створити damage case — записуємо ТІЛЬКИ в product_damage_history
        damage_id = str(uuid.uuid4())
        
        # Маппінг action_type → processing_type
        action_to_processing = {
            'repair': 'restoration',
            'restoration': 'restoration',
            'washing': 'wash',
            'wash': 'wash',
            'laundry': 'laundry',
            'dry_cleaning': 'laundry',
            'total_loss': 'none'
        }
        processing_type = action_to_processing.get(action_type, 'restoration')
        
        # Створити запис в product_damage_history (єдине джерело істини)
        rh_db.execute(text("""
            INSERT INTO product_damage_history (
                id, product_id, sku, product_name, category,
                damage_type, damage_code, severity, 
                processing_type, processing_status,
                qty, processed_qty, estimate_value,
                note, source, created_at, updated_at, created_by
            )
            SELECT 
                :id, :product_id, sku, name, category_name,
                :damage_type, :action_type, 'minor',
                :processing_type, :processing_status,
                :qty, 0, :estimated_cost,
                :notes, 'reaudit', NOW(), NOW(), :created_by
            FROM products
            WHERE product_id = :product_id
        """), {
            "id": damage_id,
            "product_id": product_id,
            "damage_type": description or "З кабінету переобліку",
            "action_type": action_type,
            "processing_type": processing_type,
            "processing_status": 'completed' if action_type == 'total_loss' else 'pending',
            "qty": qty,
            "estimated_cost": estimated_cost,
            "notes": description or "Створено через кейс шкоди",
            "created_by": created_by
        })
        
        # Оновити кількість товару
        if action_type == 'total_loss':
            # Повна втрата — віднімаємо від кількості
            rh_db.execute(text("""
                UPDATE products 
                SET quantity = quantity - :qty,
                    state = 'written_off'
                WHERE product_id = :pid
            """), {'qty': qty, 'pid': product_id})
            message = f"Повна втрата: віднято {qty} од."
        else:
            # Ремонт/Реставрація/Мийка — заморожуємо товар
            rh_db.execute(text("""
                UPDATE products 
                SET frozen_quantity = frozen_quantity + :qty
                WHERE product_id = :pid
            """), {'qty': qty, 'pid': product_id})
            message = f"{action_type.capitalize()}: заморожено {qty} од."
        
        rh_db.commit()
        
        return {
            'success': True,
            'damage_id': damage_id,
            'case_number': damage_id[:8].upper(),
            'message': message,
            'action_type': action_type,
            'qty': qty,
            'frozen_qty': frozen_qty
        }
        
    except HTTPException:
        raise
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.get("/product/{product_id}")
async def get_product_damage_cases(
    product_id: int,
    rh_db: Session = Depends(get_rh_db)
):
    """
    Отримати всі кейси шкоди для товару
    """
    try:
        query = text("""
            SELECT 
                pdh.id,
                pdh.id as damage_id,
                pdh.product_id,
                pdh.product_name,
                pdh.photo_url,
                pdh.processing_type,
                pdh.processing_status,
                pdh.qty,
                (COALESCE(pdh.qty, 1) - COALESCE(pdh.processed_qty, 0)) as remaining,
                pdh.estimate_value,
                pdh.note,
                pdh.created_at,
                CASE WHEN pdh.processing_status IN ('completed', 'returned_to_stock') THEN 'closed' ELSE 'open' END as case_status,
                pdh.note as notes,
                pdh.created_by,
                pdh.sku
            FROM product_damage_history pdh
            WHERE pdh.product_id = :pid
            ORDER BY pdh.created_at DESC
        """)
        
        results = rh_db.execute(query, {'pid': product_id}).fetchall()
        
        cases = []
        for row in results:
            cases.append({
                'id': row[0],
                'damage_id': row[1],
                'product_id': row[2],
                'product_name': row[3],
                'image': row[4],
                'action_type': row[5],
                'status': row[6],
                'qty': row[7],
                'frozen_qty': row[8],
                'estimate_value': float(row[9]) if row[9] else 0,
                'comment': row[10],
                'created_at': row[11].isoformat() if row[11] else None,
                'case_status': row[12],
                'notes': row[13],
                'created_by': row[14],
                'case_number': row[15]
            })
        
        return cases
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.get("/all")
async def get_all_damage_cases(
    rh_db: Session = Depends(get_rh_db)
):
    """
    Отримати всі кейси шкоди з product_damage_history
    """
    try:
        query = text("""
            SELECT 
                pdh.id,
                pdh.id as damage_id,
                pdh.product_id,
                pdh.product_name,
                pdh.photo_url,
                pdh.processing_type,
                pdh.processing_status,
                pdh.qty,
                pdh.processed_qty,
                pdh.estimate_value,
                pdh.note,
                pdh.created_at,
                pdh.source,
                pdh.created_by,
                pdh.sku
            FROM product_damage_history pdh
            WHERE pdh.source = 'reaudit'
            ORDER BY pdh.created_at DESC
        """)
        
        results = rh_db.execute(query).fetchall()
        
        cases = []
        for row in results:
            cases.append({
                'id': row[0],
                'damage_id': row[1],
                'product_id': row[2],
                'product_name': row[3],
                'image': row[4],
                'action_type': row[5],
                'status': row[6],
                'qty': row[7],
                'frozen_qty': row[7] - (row[8] or 0),
                'estimate_value': float(row[9]) if row[9] else 0,
                'comment': row[10],
                'created_at': row[11].isoformat() if row[11] else None,
                'case_status': 'open' if row[6] not in ('completed', 'returned_to_stock') else 'closed',
                'notes': row[10],
                'created_by': row[13],
                'case_number': row[14]
            })
        
        return cases
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.delete("/{damage_id}")
async def delete_damage_case(
    damage_id: str,
    rh_db: Session = Depends(get_rh_db)
):
    """
    Видалити кейс шкоди з product_damage_history (розморожує товар)
    """
    try:
        # Отримати запис з product_damage_history
        query = text("""
            SELECT id, product_id, processing_type, qty, processed_qty
            FROM product_damage_history
            WHERE id = :damage_id
        """)
        
        item = rh_db.execute(query, {'damage_id': damage_id}).fetchone()
        
        if not item:
            raise HTTPException(status_code=404, detail="Кейс не знайдено")
        
        pdh_id, product_id, processing_type, qty, processed_qty = item
        remaining = (qty or 1) - (processed_qty or 0)
        
        # Розморозити товар
        if remaining > 0 and processing_type != 'none':
            rh_db.execute(text("""
                UPDATE products 
                SET frozen_quantity = GREATEST(0, frozen_quantity - :qty)
                WHERE product_id = :pid
            """), {'qty': remaining, 'pid': product_id})
        
        # Позначити як видалений
        rh_db.execute(text("""
            UPDATE product_damage_history 
            SET processing_status = 'deleted', updated_at = NOW()
            WHERE id = :damage_id
        """), {'damage_id': damage_id})
        
        rh_db.commit()
        
        return {
            'success': True,
            'message': f'Кейс видалено. Розморожено {remaining} од.',
            'items_count': 1
        }
        
    except HTTPException:
        raise
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")


@router.put("/{damage_item_id}/complete")
async def complete_damage_case(
    damage_item_id: int,
    rh_db: Session = Depends(get_rh_db)
):
    """
    Завершити кейс шкоди (розморозити товар якщо був заморожений)
    """
    try:
        # Отримати інформацію про кейс
        query = text("""
            SELECT product_id, processing_type, (COALESCE(qty, 1) - COALESCE(processed_qty, 0)) as remaining, processing_status
            FROM product_damage_history
            WHERE id = :id
        """)
        
        result = rh_db.execute(query, {'id': damage_item_id}).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Кейс не знайдено")
        
        product_id, action_type, remaining_qty, status = result
        
        if status == 'completed':
            return {'success': True, 'message': 'Кейс вже завершено'}
        
        # Оновити статус кейсу
        update_query = text("""
            UPDATE product_damage_history 
            SET processing_status = 'completed', updated_at = NOW()
            WHERE id = :id
        """)
        
        rh_db.execute(update_query, {'id': damage_item_id})
        
        # Розморозити товар
        if action_type in ('wash', 'restoration', 'laundry') and remaining_qty > 0:
            unfreeze_query = text("""
                UPDATE products 
                SET frozen_quantity = GREATEST(0, frozen_quantity - :qty)
                WHERE product_id = :pid
            """)
            rh_db.execute(unfreeze_query, {'qty': remaining_qty, 'pid': product_id})
        
        rh_db.commit()
        
        return {
            'success': True,
            'message': 'Кейс завершено',
            'action': 'unfrozen' if action_type != 'total_loss' else 'none'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        rh_db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка: {str(e)}")
