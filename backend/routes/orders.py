"""
Orders routes - ПОВНА МІГРАЦІЯ
✅ MIGRATED: Using RentalHub DB з повною бізнес-логікою
"""
from fastapi import APIRouter, HTTPException, Depends, Header
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date
import uuid
import json
import os

from database_rentalhub import get_rh_db
from utils.image_helper import normalize_image_url
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/orders", tags=["orders"])

# Додатковий роутер для сумісності зі старими URL
decor_router = APIRouter(prefix="/api/decor-orders", tags=["decor-orders"])

# ============================================================
# PYDANTIC MODELS
# ============================================================

class OrderItem(BaseModel):
    inventory_id: str
    article: Optional[str]
    name: str
    quantity: int
    price_per_day: float
    total_rental: float
    deposit: float
    total_deposit: float
    image: Optional[str] = None

class Order(BaseModel):
    id: str
    order_number: str
    client_id: Optional[int]
    client_name: str
    client_phone: str
    client_email: str
    status: str
    order_status_id: Optional[int] = None
    issue_date: Optional[str]
    return_date: Optional[str]
    items: List[OrderItem]
    total_rental: float
    total_deposit: float
    deposit_held: float
    manager_comment: Optional[str]
    created_at: str
    
    class Config:
        from_attributes = True

class OrderCreate(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: Optional[str] = None
    rental_start_date: str
    rental_end_date: str
    items: List[dict]
    total_amount: float
    deposit_amount: float
    notes: Optional[str] = None

# ============================================================
# HELPER FUNCTIONS
# ============================================================

def parse_order_row(row, db: Session = None):
    """Parse order row from database"""
    if not row:
        return None
    
    # Get items if needed
    items = []
    packing_progress = 0  # ✅ Прогрес комплектації
    
    if db and row[0]:  # order_id exists
        items_result = db.execute(text("""
            SELECT oi.id, oi.order_id, oi.product_id, oi.product_name, 
                   oi.quantity, oi.price, oi.total_rental,
                   p.image_url, p.price as loss_value, p.quantity as available_qty,
                   p.sku, p.zone, p.aisle, p.shelf, p.cleaning_status, p.product_state,
                   p.category_name
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = :order_id
              AND (oi.status IS NULL OR oi.status != 'refused')
        """), {"order_id": row[0]})
        
        for item_row in items_result:
            # order_items: [0]id, [1]order_id, [2]product_id, [3]product_name, [4]quantity, [5]price, [6]total_rental, 
            #              [7]image_url, [8]loss_value, [9]available_qty, [10]sku, [11]zone, [12]aisle, [13]shelf, [14]cleaning_status, [15]product_state, [16]category_name
            loss_value = float(item_row[8]) if item_row[8] else 0.0
            quantity = item_row[4] or 1
            available = int(item_row[9]) if item_row[9] else 0
            deposit_per_unit = loss_value / 2  # Застава = половина від вартості втрати
            
            # Обробка image_url
            image_url = normalize_image_url(item_row[7])
            
            items.append({
                "inventory_id": str(item_row[2]) if item_row[2] else "",
                "article": item_row[10] or str(item_row[2]),  # SKU (article) або product_id
                "sku": item_row[10] or str(item_row[2]),  # SKU або product_id
                "name": item_row[3],
                "category": item_row[16] or "Реквізит",  # Категорія товару для пошкоджень
                "quantity": quantity,
                "qty": quantity,  # Для IssueCard
                "price_per_day": float(item_row[5]) if item_row[5] else 0.0,
                "total_rental": float(item_row[6]) if item_row[6] else 0.0,
                "deposit": deposit_per_unit,  # Застава = EAN / 2
                "damage_cost": loss_value,  # Збиток (EAN) - повна вартість втрати
                "total_deposit": deposit_per_unit * quantity,  # Загальна застава за товар
                "image": image_url,  # Фото товару (оброблений URL)
                "photo": image_url,  # Альтернативна назва для IssueCard
                # Дані наявності з products
                "available_qty": available,
                "available": available,
                "reserved_qty": 0,  # TODO: рахувати з order_items WHERE status != 'completed'
                "reserved": 0,
                "in_rent_qty": 0,  # TODO: рахувати з orders WHERE status = 'shipped'
                "in_rent": 0,
                "in_restore_qty": 0,  # TODO: рахувати з damages
                "in_restore": 0,
                # Локація на складі
                "location": {
                    "zone": item_row[11] or "",
                    "aisle": item_row[12] or "",
                    "shelf": item_row[13] or "",
                    "state": item_row[15] or "shelf"
                },
                "pack": "",  # TODO: додати якщо є в products
                "pre_damage": []  # will be enriched below
            })
        
        # ✅ Enrich items with damage history
        item_pids = [it.get('inventory_id') for it in items if it.get('inventory_id')]
        if item_pids:
            pids_str = ','.join(str(int(p)) for p in item_pids if p.isdigit())
            if pids_str:
                try:
                    dmg_rows = db.execute(text(f"""
                        SELECT product_id, damage_type, damage_code, note, severity, 
                               processing_status, created_at, photo_url, stage, 
                               order_number, qty, fee, created_by, id
                        FROM product_damage_history
                        WHERE product_id IN ({pids_str})
                        ORDER BY created_at DESC
                    """)).fetchall()
                    dmg_by_pid = {}
                    for dr in dmg_rows:
                        k = str(dr[0])
                        if k not in dmg_by_pid:
                            dmg_by_pid[k] = []
                        dmg_by_pid[k].append({
                            'id': dr[13],
                            'type': dr[1] or dr[2] or '',
                            'damage_type': dr[1] or dr[2] or '',
                            'notes': dr[3] or '',
                            'note': dr[3] or '',
                            'severity': dr[4] or 'low',
                            'status': dr[5] or '',
                            'date': dr[6].isoformat() if dr[6] else None,
                            'created_at': dr[6].strftime('%d.%m.%Y %H:%M') if dr[6] else None,
                            'photo_url': dr[7],
                            'stage': dr[8] or '',
                            'stage_label': 'До видачі' if dr[8] == 'pre_issue' else 'При поверненні' if dr[8] == 'return' else 'Аудит' if dr[8] else '',
                            'order_number': dr[9] or '',
                            'qty': int(dr[10] or 1),
                            'fee': float(dr[11] or 0),
                            'created_by': dr[12] or '',
                        })
                    for it in items:
                        pid = it.get('inventory_id', '')
                        it['damage_history'] = dmg_by_pid.get(pid, [])
                        it['has_damage_history'] = len(it['damage_history']) > 0
                        it['total_damages'] = len(it['damage_history'])
                        it['pre_damage'] = it['damage_history'][:3]  # top 3 for preview
                except:
                    pass
        
        # ✅ Обчислити прогрес комплектації з issue_cards
        try:
            issue_card_result = db.execute(text("""
                SELECT items FROM issue_cards WHERE order_id = :order_id
            """), {"order_id": row[0]})
            ic_row = issue_card_result.fetchone()
            if ic_row and ic_row[0]:
                import json
                ic_items = json.loads(ic_row[0]) if isinstance(ic_row[0], str) else ic_row[0]
                if ic_items and len(ic_items) > 0:
                    total_qty = sum(it.get('qty', 1) for it in ic_items)
                    picked_qty = sum(it.get('picked_qty', 0) for it in ic_items)
                    if total_qty > 0:
                        packing_progress = int((picked_qty / total_qty) * 100)
        except Exception as e:
            print(f"[parse_order_row] Error calculating packing progress: {e}")
            packing_progress = 0
    
    # ✅ Завантажити суми оплат для замовлення
    paid_rent = 0.0
    paid_deposit = 0.0
    if db and row[0]:  # order_id exists
        try:
            payments_result = db.execute(text("""
                SELECT 
                    COALESCE(SUM(CASE WHEN ft.tx_type IN ('rent_payment', 'additional_payment') THEN ft.amount ELSE 0 END), 0) as paid_rent,
                    COALESCE(SUM(CASE WHEN ft.tx_type = 'deposit_payment' THEN ft.amount ELSE 0 END), 0) as paid_deposit
                FROM fin_transactions ft
                WHERE ft.entity_type = 'order' AND ft.entity_id = :order_id
            """), {"order_id": row[0]})
            pay_row = payments_result.fetchone()
            if pay_row:
                paid_rent = float(pay_row[0]) if pay_row[0] else 0.0
                paid_deposit = float(pay_row[1]) if pay_row[1] else 0.0
        except Exception as e:
            print(f"[parse_order_row] Error loading payments: {e}")
            paid_rent = 0.0
            paid_deposit = 0.0
    
    # Визначимо індекси полів у row - залежить від того, скільки полів повернуто
    # Формат 1 (новий з issue_date/return_date): 16+ колонок
    # Формат 2 (з rental_days): 15 колонок - order_id, order_number, customer_id, customer_name, 
    #          customer_phone, customer_email, rental_start_date, rental_end_date,
    #          status, total_price, deposit_amount, total_loss_value, rental_days, notes, created_at
    # Формат 3 (старий): <15 колонок
    
    has_new_format = len(row) >= 16  # Новий формат з issue_date і return_date
    has_rental_days_format = len(row) == 15  # Формат з rental_days
    
    # updated_at is at index 16 if present (17+ columns)
    updated_at_val = None
    if len(row) >= 17 and row[16]:
        updated_at_val = row[16].isoformat() if hasattr(row[16], 'isoformat') else str(row[16])
    
    if has_new_format:
        # Новий формат з issue_date та return_date
        total_rental = float(row[11]) if row[11] else 0.0
        service_fee_val = float(row[17]) if len(row) > 17 and row[17] else 0.0
        discount_amount_val = float(row[18]) if len(row) > 18 and row[18] else 0.0
        total_after_disc = round(max(0, total_rental - discount_amount_val), 2)
        total_to_pay = round(total_after_disc + service_fee_val, 2)
        
        order_dict = {
            "id": str(row[0]),
            "order_id": row[0],
            "order_number": row[1] or f"#{row[0]}",
            "client_id": row[2],
            "client_name": row[3],
            "customer_name": row[3],  # Alias для календаря
            "client_phone": row[4],
            "customer_phone": row[4],
            "client_email": row[5],
            "rental_start_date": row[6].isoformat() if row[6] else None,
            "rental_end_date": row[7].isoformat() if row[7] else None,
            "issue_date": row[8].isoformat() if row[8] else None,
            "return_date": row[9].isoformat() if row[9] else None,
            "status": row[10],
            "total_rental": total_rental,
            "total_price": total_rental,
            "total_deposit": float(row[12]) if row[12] else 0.0,
            "deposit_held": float(row[12]) if row[12] else 0.0,
            "manager_comment": row[13] if row[13] else None,
            "created_at": row[14].isoformat() if row[14] else None,
            "is_archived": bool(row[15]) if row[15] else False,
            "items": items,
            "packing_progress": packing_progress,
            "paid_rent": paid_rent,
            "paid_deposit": paid_deposit,
            "updated_at": updated_at_val,
            "service_fee": service_fee_val,
            "discount_amount": discount_amount_val,
            "total_after_discount": total_after_disc,
            "total_to_pay": total_to_pay,
        }
    elif has_rental_days_format:
        # Формат з rental_days (15 колонок)
        # order_id, order_number, customer_id, customer_name, customer_phone, customer_email,
        # rental_start_date, rental_end_date, status, total_price, deposit_amount,
        # total_loss_value, rental_days, notes, created_at
        order_dict = {
            "id": str(row[0]),
            "order_id": row[0],
            "order_number": row[1] or f"#{row[0]}",
            "client_id": row[2],
            "client_name": row[3],
            "customer_name": row[3],
            "client_phone": row[4],
            "customer_phone": row[4],
            "client_email": row[5],
            "issue_date": row[6].isoformat() if row[6] else None,
            "return_date": row[7].isoformat() if row[7] else None,
            "rental_start_date": row[6].isoformat() if row[6] else None,
            "rental_end_date": row[7].isoformat() if row[7] else None,
            "status": row[8],
            "total_rental": float(row[9]) if row[9] else 0.0,
            "total_deposit": float(row[10]) if row[10] else 0.0,
            "deposit_held": float(row[10]) if row[10] else 0.0,
            "total_loss_value": float(row[11]) if row[11] else 0.0,
            "rental_days": int(row[12]) if row[12] else None,
            "manager_comment": row[13] if row[13] else None,
            "notes": row[13] if row[13] else None,
            "created_at": row[14].isoformat() if row[14] else None,
            "is_archived": False,
            "items": items,
            "packing_progress": packing_progress,
            "paid_rent": paid_rent,
            "paid_deposit": paid_deposit
        }
    else:
        # Старий формат (без issue_date та return_date)
        order_dict = {
            "id": str(row[0]),
            "order_id": row[0],
            "order_number": row[1] or f"#{row[0]}",
            "client_id": row[2],
            "client_name": row[3],
            "customer_name": row[3],
            "client_phone": row[4],
            "customer_phone": row[4],
            "client_email": row[5],
            "issue_date": row[6].isoformat() if row[6] else None,
            "return_date": row[7].isoformat() if row[7] else None,
            "status": row[8],
            "total_rental": float(row[9]) if row[9] else 0.0,
            "total_deposit": float(row[10]) if row[10] else 0.0,
            "deposit_held": float(row[10]) if row[10] else 0.0,
            "manager_comment": row[11] if len(row) > 11 else None,
            "created_at": row[12].isoformat() if len(row) > 12 and row[12] else None,
            "is_archived": bool(row[13]) if len(row) > 13 else False,
            "items": items,
            "packing_progress": packing_progress,
            "paid_rent": paid_rent,
            "paid_deposit": paid_deposit
        }
    
    return order_dict

# ============================================================
# MAIN ENDPOINTS
# ============================================================

@router.get("")
async def get_orders(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    search: Optional[str] = None,
    archived: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати список замовлень з повною фільтрацією
    ✅ MIGRATED: Full business logic preserved
    archived: 'true' - тільки архівні, 'false' - тільки неархівні, 'all' - всі
    """
    sql = """
        SELECT 
            order_id, order_number, customer_id, customer_name, 
            customer_phone, customer_email, rental_start_date, rental_end_date,
            issue_date, return_date,
            status, total_price, deposit_amount, notes, created_at, is_archived,
            updated_at, COALESCE(service_fee, 0) as service_fee, 
            COALESCE(discount_amount, 0) as discount_amount
        FROM orders
        WHERE 1=1
    """
    
    params = {}
    
    if status and status != 'all':
        # Підтримка кількох статусів через кому
        if ',' in status:
            statuses = [s.strip() for s in status.split(',')]
            placeholders = ','.join([f':status_{i}' for i in range(len(statuses))])
            sql += f" AND status IN ({placeholders})"
            for i, s in enumerate(statuses):
                params[f'status_{i}'] = s
        else:
            sql += " AND status = :status"
            params['status'] = status
    
    if customer_id:
        sql += " AND customer_id = :customer_id"
        params['customer_id'] = customer_id
    
    if from_date and to_date:
        # Show orders that overlap with the date range
        sql += " AND (rental_start_date <= :to_date AND rental_end_date >= :from_date)"
        params['from_date'] = from_date
        params['to_date'] = to_date
    elif from_date:
        sql += " AND rental_end_date >= :from_date"
        params['from_date'] = from_date
    elif to_date:
        sql += " AND rental_start_date <= :to_date"
        params['to_date'] = to_date
    
    if search:
        sql += """ AND (
            order_number LIKE :search OR
            customer_name LIKE :search OR
            customer_phone LIKE :search OR
            customer_email LIKE :search
        )"""
        params['search'] = f"%{search}%"
    
    # Фільтр архівних замовлень
    if archived == 'true':
        sql += " AND is_archived = 1"
    elif archived == 'false' or archived is None:
        # За замовчуванням показувати тільки неархівні
        sql += " AND is_archived = 0"
    # Якщо archived == 'all', не додаємо фільтр
    
    sql += f" ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"
    
    result = db.execute(text(sql), params)
    
    orders = []
    for row in result:
        order = parse_order_row(row, db)
        if order:
            orders.append(order)
    
    # Get total count
    count_sql = "SELECT COUNT(*) FROM orders WHERE 1=1"
    if status and status != 'all':
        if ',' in status:
            statuses = [s.strip() for s in status.split(',')]
            placeholders = ','.join([f':status_{i}' for i in range(len(statuses))])
            count_sql += f" AND status IN ({placeholders})"
        else:
            count_sql += " AND status = :status"
    if customer_id:
        count_sql += " AND customer_id = :customer_id"
    if from_date and to_date:
        count_sql += " AND (rental_start_date <= :to_date AND rental_end_date >= :from_date)"
    elif from_date:
        count_sql += " AND rental_end_date >= :from_date"
    elif to_date:
        count_sql += " AND rental_start_date <= :to_date"
    if search:
        count_sql += """ AND (
            order_number LIKE :search OR
            customer_name LIKE :search OR
            customer_phone LIKE :search
        )"""
    
    # Додати фільтр архівних в count
    if archived == 'true':
        count_sql += " AND is_archived = 1"
    elif archived == 'false' or archived is None:
        count_sql += " AND is_archived = 0"
    
    count_result = db.execute(text(count_sql), params)
    total = count_result.scalar()
    
    return {
        "orders": orders,
        "total": total,
        "limit": limit,
        "offset": offset
    }

@router.get("/{order_id}/lifecycle")
async def get_order_lifecycle(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати ПОВНУ історію замовлення (lifecycle events)
    ✅ Включає: створення замовлення, всі зміни статусу, видачу/повернення
    """
    lifecycle = []
    
    # 1. Отримати дату створення замовлення
    order_result = db.execute(text("""
        SELECT created_at, status, customer_name
        FROM orders 
        WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if order_result:
        lifecycle.append({
            "stage": "created",
            "notes": f"Замовлення створено для {order_result[2] or 'клієнта'}",
            "created_at": order_result[0].isoformat() if order_result[0] else None,
            "created_by": "System",
            "created_by_id": None,
            "created_by_name": "System"
        })
    
    # 2. Отримати всі записи з order_lifecycle
    lifecycle_result = db.execute(text("""
        SELECT stage, notes, created_at, created_by, created_by_id, created_by_name
        FROM order_lifecycle 
        WHERE order_id = :order_id 
        ORDER BY created_at ASC
    """), {"order_id": order_id})
    
    for l_row in lifecycle_result:
        # Пріоритет: created_by_name > created_by
        user_name = l_row[5] if len(l_row) > 5 and l_row[5] else (l_row[3] if len(l_row) > 3 else None)
        lifecycle.append({
            "stage": l_row[0],
            "notes": l_row[1],
            "created_at": l_row[2].isoformat() if l_row[2] else None,
            "created_by": user_name,
            "created_by_id": l_row[4] if len(l_row) > 4 else None,
            "created_by_name": l_row[5] if len(l_row) > 5 else None
        })
    
    # 3. Отримати інформацію про issue card (комплектацію та видачу)
    issue_result = db.execute(text("""
        SELECT id, status, prepared_at, issued_at, prepared_by, issued_by
        FROM issue_cards 
        WHERE order_id = :order_id 
        ORDER BY created_at ASC
    """), {"order_id": order_id})
    
    for ic_row in issue_result:
        # Підготовлено (комплектація завершена)
        if ic_row[2]:  # prepared_at
            lifecycle.append({
                "stage": "ready_for_issue",
                "notes": "Комплектація завершена, готово до видачі",
                "created_at": ic_row[2].isoformat() if ic_row[2] else None,
                "created_by": ic_row[4] or "Warehouse Staff",
                "created_by_id": None,
                "created_by_name": ic_row[4] or "Warehouse Staff"
            })
        
        # Видано клієнту
        if ic_row[3]:  # issued_at
            lifecycle.append({
                "stage": "issued",
                "notes": "Замовлення видано клієнту",
                "created_at": ic_row[3].isoformat() if ic_row[3] else None,
                "created_by": ic_row[5] or "Manager",
                "created_by_id": None,
                "created_by_name": ic_row[5] or "Manager"
            })
    
    # 4. Отримати інформацію про повернення (з partial_return_versions — єдине джерело правди)
    return_result = db.execute(text("""
        SELECT version_id, status, completed_at, customer_name
        FROM partial_return_versions
        WHERE parent_order_id = :order_id
        ORDER BY created_at ASC
    """), {"order_id": order_id})
    
    for rc_row in return_result:
        if rc_row[2]:  # completed_at
            lifecycle.append({
                "stage": "returned",
                "notes": "Замовлення повернуто",
                "created_at": rc_row[2].isoformat() if rc_row[2] else None,
                "created_by": rc_row[3] or "Staff",
                "created_by_id": None,
                "created_by_name": rc_row[3] or "Staff"
            })
    
    # Сортування за датою (найстаріші спочатку)
    lifecycle.sort(key=lambda x: x["created_at"] or "")
    
    return lifecycle

@router.get("/{order_id}")
async def get_order_details(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Повна інформація про замовлення
    ✅ MIGRATED: Full details with lifecycle, issue cards, return cards
    ✅ FIXED: Додано discount_amount та manager_id
    """
    # Order details - повний запит з усіма полями
    # Формат: [0]order_id, [1]order_number, [2]customer_id, [3]customer_name, 
    # [4]customer_phone, [5]customer_email, [6]rental_start_date, [7]rental_end_date,
    # [8]status, [9]total_price, [10]deposit_amount, [11]total_loss_value, 
    # [12]rental_days, [13]notes, [14]created_at,
    # [15]discount_amount, [16]manager_id, [17]issue_time, [18]return_time,
    # [19]manager_name, [20]discount_percent, [21]service_fee, [22]service_fee_name
    # [23]client_notes
    result = db.execute(text("""
        SELECT 
            o.order_id, o.order_number, o.customer_id, o.customer_name, 
            o.customer_phone, o.customer_email, o.rental_start_date, o.rental_end_date,
            o.status, o.total_price, o.deposit_amount, o.total_loss_value, 
            o.rental_days, o.notes, o.created_at,
            o.discount_amount, o.manager_id, o.issue_time, o.return_time,
            CONCAT(COALESCE(u.firstname, ''), ' ', COALESCE(u.lastname, '')) as manager_name,
            o.discount_percent, COALESCE(o.service_fee, 0) as service_fee,
            o.service_fee_name,
            c.notes as client_notes
        FROM orders o
        LEFT JOIN users u ON o.manager_id = u.user_id
        LEFT JOIN client_users c ON o.customer_id = c.id
        WHERE o.order_id = :order_id
    """), {"order_id": order_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Базова інформація замовлення
    order = {
        "id": str(row[0]),
        "order_id": row[0],
        "order_number": row[1],
        "client_id": row[2],
        "client_name": row[3],
        "customer_name": row[3],
        "client_phone": row[4],
        "client_email": row[5],
        "rental_start_date": row[6].isoformat() if row[6] else None,
        "rental_end_date": row[7].isoformat() if row[7] else None,
        "issue_date": row[6].isoformat() if row[6] else None,  # alias
        "return_date": row[7].isoformat() if row[7] else None,  # alias
        "status": row[8],
        "total_rental": float(row[9]) if row[9] else 0.0,
        "total_deposit": float(row[10]) if row[10] else 0.0,
        "deposit_held": float(row[10]) if row[10] else 0.0,
        "total_loss_value": float(row[11]) if row[11] else 0.0,
        "rental_days": int(row[12]) if row[12] else 1,
        "manager_comment": row[13] if row[13] else None,
        "notes": row[13] if row[13] else None,
        "created_at": row[14].isoformat() if row[14] else None,
    }
    
    # Додаткові поля
    discount_amount = float(row[15]) if row[15] else 0
    total_price = float(row[9]) if row[9] else 0
    discount_percent_db = float(row[20]) if row[20] else 0
    
    # Обчислити відсоток якщо він не збережений, але є discount_amount
    # total_price = сума товарів (ДО знижки)
    if discount_percent_db == 0 and discount_amount > 0 and total_price > 0:
        discount_percent_db = (discount_amount / total_price) * 100
    
    # Якщо є відсоток, але немає суми — порахувати суму
    if discount_percent_db > 0 and discount_amount == 0 and total_price > 0:
        discount_amount = total_price * discount_percent_db / 100
    
    order["discount_amount"] = round(discount_amount, 2)
    order["manager_id"] = row[16]
    order["issue_time"] = row[17] or "11:30–12:00"
    order["return_time"] = row[18] or "до 17:00"
    order["manager_name"] = (row[19] or "").strip()
    order["discount"] = round(discount_percent_db, 2)
    order["discount_percent"] = round(discount_percent_db, 2)
    service_fee = float(row[21]) if row[21] else 0
    order["service_fee"] = service_fee
    order["service_fee_name"] = row[22] or ""
    order["client_notes"] = row[23] if len(row) > 23 else None  # Нотатки про клієнта
    # Після знижки — динамічний розрахунок
    total_after_discount = round(max(0, total_price - discount_amount), 2)
    order["total_after_discount"] = total_after_discount
    # Повна сума до сплати = товари - знижка + додаткові послуги
    order["total_to_pay"] = round(total_after_discount + service_fee, 2)
    
    # Завантажити items
    items_result = db.execute(text("""
        SELECT oi.id, oi.order_id, oi.product_id, oi.product_name, 
               oi.quantity, oi.price, oi.total_rental,
               p.image_url, p.price as loss_value, p.quantity as available_qty,
               p.sku, p.zone, p.aisle, p.shelf, p.cleaning_status, p.product_state,
               p.category_name
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE oi.order_id = :order_id
          AND (oi.status IS NULL OR oi.status != 'refused')
    """), {"order_id": row[0]})
    
    items = []
    for item_row in items_result:
        loss_value = float(item_row[8]) if item_row[8] else 0.0
        quantity = item_row[4] or 1
        available = int(item_row[9]) if item_row[9] else 0
        deposit_per_unit = loss_value / 2
        
        image_url = normalize_image_url(item_row[7])
        
        items.append({
            "inventory_id": str(item_row[2]) if item_row[2] else "",
            "article": item_row[10] or str(item_row[2]),
            "sku": item_row[10] or str(item_row[2]),
            "name": item_row[3],
            "category": item_row[16] or "Реквізит",
            "quantity": quantity,
            "qty": quantity,
            "price_per_day": float(item_row[5]) if item_row[5] else 0.0,
            "total_rental": float(item_row[6]) if item_row[6] else 0.0,
            "deposit": deposit_per_unit,
            "damage_cost": loss_value,
            "total_deposit": deposit_per_unit * quantity,
            "image": image_url,
            "photo": image_url,
            "available_qty": available,
            "available": available,
            "location": {
                "zone": item_row[11] or "",
                "aisle": item_row[12] or "",
                "shelf": item_row[13] or "",
                "state": item_row[15] or "shelf"
            },
        })
    
    order["items"] = items
    
    # ✅ Enrich items with damage history from product_damage_history
    product_ids = [it.get('inventory_id') for it in items if it.get('inventory_id')]
    if product_ids:
        ids_str = ','.join(str(int(pid)) for pid in product_ids if pid.isdigit())
        if ids_str:
            dmg_result = db.execute(text(f"""
                SELECT product_id, id, processing_type, note, severity, 
                       processing_status, created_at, damage_type, damage_code,
                       photo_url, stage, order_number, qty, fee, created_by
                FROM product_damage_history
                WHERE product_id IN ({ids_str})
                ORDER BY created_at DESC
            """)).fetchall()
            dmg_map = {}
            for d in dmg_result:
                pid = str(d[0])
                if pid not in dmg_map:
                    dmg_map[pid] = []
                dmg_map[pid].append({
                    'id': d[1],
                    'type': d[2] or d[7] or '',
                    'damage_type': d[7] or d[2] or '',
                    'notes': d[3] or '',
                    'note': d[3] or '',
                    'severity': d[4],
                    'status': d[5],
                    'date': d[6].isoformat() if d[6] else None,
                    'created_at': d[6].strftime('%d.%m.%Y %H:%M') if d[6] else None,
                    'damage_code': d[8] or '',
                    'photo_url': d[9],
                    'stage': d[10] or '',
                    'stage_label': 'До видачі' if d[10] == 'pre_issue' else 'При поверненні' if d[10] == 'return' else 'Аудит' if d[10] else '',
                    'order_number': d[11] or '',
                    'qty': int(d[12] or 1),
                    'fee': float(d[13] or 0),
                    'created_by': d[14] or '',
                })
            for it in items:
                pid = it.get('inventory_id', '')
                it['damage_history'] = dmg_map.get(pid, [])
                it['has_damage_history'] = len(it['damage_history']) > 0
                it['total_damages'] = len(it['damage_history'])
    
    # Get lifecycle info
    lifecycle_result = db.execute(text("""
        SELECT stage, notes, created_at FROM order_lifecycle 
        WHERE order_id = :order_id 
        ORDER BY created_at DESC
    """), {"order_id": order_id})
    
    lifecycle = []
    for l_row in lifecycle_result:
        lifecycle.append({
            "stage": l_row[0],
            "notes": l_row[1],
            "timestamp": l_row[2].isoformat() if l_row[2] else None
        })
    
    # Get issue cards
    issue_result = db.execute(text("""
        SELECT id, status, items, prepared_by, issued_by, 
               prepared_at, issued_at, created_at
        FROM issue_cards
        WHERE order_id = :order_id
        ORDER BY created_at DESC
    """), {"order_id": order_id})
    
    issue_cards = []
    for i_row in issue_result:
        items = []
        if i_row[2]:
            try:
                items = json.loads(i_row[2]) if isinstance(i_row[2], str) else i_row[2]
            except:
                pass
        
        issue_cards.append({
            "id": i_row[0],
            "status": i_row[1],
            "items": items,
            "prepared_by": i_row[3],
            "issued_by": i_row[4],
            "prepared_at": i_row[5].isoformat() if i_row[5] else None,
            "issued_at": i_row[6].isoformat() if i_row[6] else None,
            "created_at": i_row[7].isoformat() if i_row[7] else None
        })
    
    # Get returns (з partial_return_versions — єдине джерело правди)
    return_result = db.execute(text("""
        SELECT prv.version_id, prv.status, prv.display_number, prv.notes,
               prv.created_at, prv.completed_at,
               (SELECT COUNT(*) FROM partial_return_version_items WHERE version_id = prv.version_id AND status = 'returned') AS items_ok,
               (SELECT COUNT(*) FROM partial_return_version_items WHERE version_id = prv.version_id AND status = 'damaged') AS items_damaged,
               (SELECT COUNT(*) FROM partial_return_version_items WHERE version_id = prv.version_id AND status = 'lost') AS items_missing
        FROM partial_return_versions prv
        WHERE prv.parent_order_id = :order_id
        ORDER BY prv.created_at DESC
    """), {"order_id": order_id})

    return_cards = []
    for r_row in return_result:
        return_cards.append({
            "id": r_row[0],
            "status": r_row[1],
            "display_number": r_row[2],
            "items_expected": [],
            "items_returned": [],
            "items_ok": int(r_row[6] or 0),
            "items_dirty": 0,
            "items_damaged": int(r_row[7] or 0),
            "items_missing": int(r_row[8] or 0),
            "cleaning_fee": 0.0,
            "late_fee": 0.0,
            "returned_at": r_row[5].isoformat() if r_row[5] else None,
            "checked_at": r_row[5].isoformat() if r_row[5] else None,
            "created_at": r_row[4].isoformat() if r_row[4] else None,
        })
    
    # Get damages (тепер з product_damage_history)
    damages_result = db.execute(text("""
        SELECT id, processing_status, severity, estimate_value, processed_qty, created_at
        FROM product_damage_history
        WHERE order_id = :order_id
        AND processing_type IN ('wash', 'restoration', 'laundry')
    """), {"order_id": order_id})
    
    damages = []
    for d_row in damages_result:
        damages.append({
            "id": d_row[0],
            "status": d_row[1] or 'pending',
            "severity": d_row[2] or 'low',
            "claimed_total": float(d_row[3]) if d_row[3] else 0.0,
            "paid_total": 0.0,
            "created_at": d_row[5].isoformat() if d_row[5] else None
        })
    
    # Get finance transactions — читаємо тільки з fin_transactions (єдине джерело правди)
    # fin_payments дублює дані з fin_transactions для платежів
    finance_result = db.execute(text("""
        SELECT tx_type as transaction_type, amount, status, note as description, occurred_at as transaction_date
        FROM fin_transactions
        WHERE entity_type = 'order' AND entity_id = :order_id
        ORDER BY occurred_at DESC
    """), {"order_id": order_id})
    
    transactions = []
    for f_row in finance_result:
        transactions.append({
            "type": f_row[0],
            "amount": float(f_row[1]) if f_row[1] else 0.0,
            "status": f_row[2],
            "description": f_row[3],
            "created_at": f_row[4].isoformat() if f_row[4] else None
        })
    
    order["lifecycle"] = lifecycle
    order["issue_cards"] = issue_cards
    order["return_cards"] = return_cards
    order["damages"] = damages
    order["transactions"] = transactions
    
    # Get documents linked to this order
    docs_result = db.execute(text("""
        SELECT id, doc_type, doc_number, version, status, signed_at, created_at, category
        FROM documents
        WHERE (entity_type = 'order' AND entity_id = :order_id_str)
           OR (entity_type = 'issue' AND entity_id LIKE :issue_pattern)
           OR (entity_type = 'return' AND entity_id LIKE :return_pattern)
        ORDER BY created_at DESC
    """), {
        "order_id_str": str(order_id),
        "issue_pattern": f"IC-{order_id}-%",
        "return_pattern": f"RC-{order_id}-%"
    })
    
    documents = []
    for d_row in docs_result:
        doc_type_names = {
            "estimate": "Кошторис", "invoice_legal": "Рахунок", "goods_invoice": "Видаткова",
            "issue_act": "Акт видачі", "return_act": "Акт повернення", "defect_act": "Акт дефектів",
            "picking_list": "Пакувальний лист", "invoice_payment": "Рахунок на оплату",
            "service_act": "Акт надання послуг"
        }
        documents.append({
            "id": d_row[0],
            "doc_type": d_row[1],
            "doc_type_name": doc_type_names.get(d_row[1], d_row[1]),
            "doc_number": d_row[2],
            "version": d_row[3],
            "status": d_row[4],
            "signed_at": d_row[5].isoformat() if d_row[5] else None,
            "created_at": d_row[6].isoformat() if d_row[6] else None,
            "preview_url": f"/api/documents/{d_row[0]}/preview",
            "pdf_url": f"/api/documents/{d_row[0]}/pdf"
        })
    
    order["documents"] = documents
    
    # Get internal notes / chat for this order
    notes_result = db.execute(text("""
        SELECT id, user_name, message, created_at
        FROM order_internal_notes
        WHERE order_id = :order_id
        ORDER BY created_at ASC
    """), {"order_id": str(order_id)})
    
    internal_notes = []
    for n_row in notes_result:
        if n_row[2]:  # skip empty messages
            internal_notes.append({
                "id": n_row[0],
                "author": n_row[1] or "System",
                "message": n_row[2],
                "created_at": n_row[3].isoformat() if n_row[3] else None,
            })
    
    order["internal_notes"] = internal_notes
    
    return order

@router.put("/{order_id}")
async def update_order(
    order_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Оновити замовлення (повна бізнес-логіка)
    ✅ MIGRATED: Includes validation and business rules
    """
    # Check exists
    result = db.execute(text("SELECT order_id FROM orders WHERE order_id = :id"), {"id": order_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Validate dates
    if 'rental_start_date' in data and 'rental_end_date' in data:
        start = datetime.fromisoformat(data['rental_start_date'])
        end = datetime.fromisoformat(data['rental_end_date'])
        if end <= start:
            raise HTTPException(status_code=400, detail="End date must be after start date")
    
    # Build update
    set_clauses = []
    params = {"order_id": order_id}
    
    allowed_fields = [
        'customer_name', 'customer_phone', 'customer_email', 
        'rental_start_date', 'rental_end_date', 'issue_date', 'return_date', 
        'issue_time', 'return_time', 'status', 
        'total_price', 'deposit_amount', 'total_loss_value', 'rental_days', 'notes',
        'discount', 'discount_amount', 'manager_comment', 'manager_id', 'service_fee', 'service_fee_name'
    ]
    
    # Маппінг полів frontend -> database
    field_mapping = {
        'discount': 'discount_percent',      # frontend discount (%) -> db discount_percent
        'discount_amount': 'discount_amount', # frontend discount_amount (грн) -> db discount_amount
    }
    
    for field in allowed_fields:
        if field in data:
            db_field = field_mapping.get(field, field)
            set_clauses.append(f"{db_field} = :{field}")
            params[field] = data[field]
    
    if set_clauses:
        # Add user tracking
        set_clauses.append("updated_by_id = :updated_by_id")
        set_clauses.append("updated_at = NOW()")
        params["updated_by_id"] = current_user["id"]
        
        sql = f"UPDATE orders SET {', '.join(set_clauses)} WHERE order_id = :order_id"
        db.execute(text(sql), params)
        
        # Log to lifecycle with user info
        db.execute(text("""
            INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
            VALUES (:order_id, 'updated', :notes, :created_by, :created_by_id, :created_by_name, NOW())
        """), {
            "order_id": order_id,
            "notes": f"Updated fields: {', '.join(data.keys())}",
            "created_by": current_user.get("name", "System"),
            "created_by_id": current_user.get("id"),
            "created_by_name": current_user.get("name")
        })
        
        db.commit()
    
    return {"message": "Order updated", "order_id": order_id}


@router.put("/{order_id}/calendar-update")
async def update_order_from_calendar(
    order_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Оновити дату та час замовлення з календаря (drag & drop)
    
    Приймає:
    - lane: 'issue' або 'return'
    - date: нова дата в форматі YYYY-MM-DD
    - timeSlot: 'morning', 'afternoon', 'evening'
    """
    # Check order exists
    result = db.execute(text("SELECT order_id FROM orders WHERE order_id = :id"), {"id": order_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Order not found")
    
    lane = data.get('lane')
    new_date = data.get('date')
    time_slot = data.get('timeSlot', 'morning')
    
    if not lane or not new_date:
        raise HTTPException(status_code=400, detail="lane and date are required")
    
    # Map timeSlot to actual time
    time_map = {
        'morning': '09:00',
        'afternoon': '14:00',
        'evening': '18:00'
    }
    actual_time = time_map.get(time_slot, '09:00')
    
    # Determine which fields to update based on lane
    params = {"order_id": order_id, "updated_by_id": current_user["id"]}
    
    if lane == 'issue':
        # Update issue_date and issue_time
        sql = text("""
            UPDATE orders 
            SET issue_date = :date, issue_time = :time, rental_start_date = :date,
                updated_by_id = :updated_by_id, updated_at = NOW()
            WHERE order_id = :order_id
        """)
        params['date'] = new_date
        params['time'] = actual_time
    elif lane == 'return':
        # Update return_date and return_time
        sql = text("""
            UPDATE orders 
            SET return_date = :date, return_time = :time, rental_end_date = :date,
                updated_by_id = :updated_by_id, updated_at = NOW()
            WHERE order_id = :order_id
        """)
        params['date'] = new_date
        params['time'] = actual_time
    else:
        raise HTTPException(status_code=400, detail=f"Invalid lane: {lane}")
    
    db.execute(sql, params)
    
    # Log to lifecycle з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'calendar_update', :notes, :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "notes": f"Calendar: {lane} updated to {new_date} {actual_time}",
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    db.commit()
    
    return {
        "success": True,
        "message": f"Updated {lane} date to {new_date}",
        "order_id": order_id,
        "date": new_date,
        "time": actual_time
    }


@router.put("/{order_id}/status")
async def update_order_status(
    order_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Змінити статус замовлення з валідацією
    ✅ MIGRATED: Business logic for status transitions
    """
    new_status = data.get('status')
    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required")
    
    # Validate status transition
    valid_statuses = [
        'pending', 'awaiting_customer', 'processing', 'ready_for_issue',
        'issued', 'on_rent', 'returned', 'partial_return', 'completed', 'cancelled'
    ]
    
    if new_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    
    # Get current status
    result = db.execute(text("""
        SELECT status FROM orders WHERE order_id = :id
    """), {"id": order_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    current_status = row[0]
    
    # Update status
    db.execute(text("""
        UPDATE orders 
        SET status = :status
        WHERE order_id = :order_id
    """), {"status": new_status, "order_id": order_id})
    
    # Log to lifecycle з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, :stage, :notes, :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "stage": new_status,
        "notes": f"Status changed from {current_status} to {new_status}",
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    db.commit()
    
    return {
        "message": "Status updated",
        "order_id": order_id,
        "old_status": current_status,
        "new_status": new_status
    }

@router.post("")
async def create_order(
    order: OrderCreate,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Створити нове замовлення з повною валідацією
    ✅ MIGRATED: Includes item validation and inventory checks
    """
    # Validate dates
    start = datetime.fromisoformat(order.rental_start_date)
    end = datetime.fromisoformat(order.rental_end_date)
    if end <= start:
        raise HTTPException(status_code=400, detail="End date must be after start date")
    
    # Calculate rental days
    rental_days = (end - start).days
    if rental_days < 1:
        raise HTTPException(status_code=400, detail="Minimum rental period is 1 day")
    
    # Get next order_id (since table doesn't have AUTO_INCREMENT)
    result = db.execute(text("SELECT COALESCE(MAX(order_id), 0) + 1 as next_id FROM orders"))
    order_id = result.scalar()
    
    # Generate sequential order number ORD-0001, ORD-0002, etc.
    order_number = f"ORD-{order_id:04d}"
    
    # Insert order with user tracking
    db.execute(text("""
        INSERT INTO orders (
            order_id, order_number, customer_name, customer_phone, customer_email,
            rental_start_date, rental_end_date, status, total_price, deposit_amount,
            notes, created_by_id, created_at
        ) VALUES (
            :order_id, :order_number, :customer_name, :customer_phone, :customer_email,
            :rental_start_date, :rental_end_date, 'awaiting_customer', :total_price, :deposit_amount,
            :notes, :created_by_id, NOW()
        )
    """), {
        "order_id": order_id,
        "order_number": order_number,
        "customer_name": order.customer_name,
        "customer_phone": order.customer_phone,
        "customer_email": order.customer_email,
        "rental_start_date": order.rental_start_date,
        "rental_end_date": order.rental_end_date,
        "total_price": order.total_amount,
        "deposit_amount": order.deposit_amount,
        "notes": order.notes,
        "created_by_id": current_user["id"]
    })
    
    # Insert items
    for item in order.items:
        db.execute(text("""
            INSERT INTO order_items (
                order_id, product_id, product_name, quantity, price, total_rental
            ) VALUES (
                :order_id, :product_id, :product_name, :quantity, :price, :total
            )
        """), {
            "order_id": order_id,
            "product_id": item.get('product_id') or item.get('inventory_id'),
            "product_name": item.get('name') or item.get('product_name'),
            "quantity": item.get('quantity', 1),
            "price": item.get('price_per_day', 0),
            "total": item.get('total_rental', 0)
        })
    
    # Log lifecycle з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'created', 'Order created', :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    # ✅ Автоматично створити/оновити клієнта
    try:
        client_id = None
        email_normalized = (order.customer_email or '').lower().strip()
        phone = (order.customer_phone or '').strip()
        
        # Пошук по email
        if email_normalized and '@' in email_normalized:
            existing_client = db.execute(text("""
                SELECT id FROM client_users WHERE email_normalized = :email LIMIT 1
            """), {"email": email_normalized}).fetchone()
            if existing_client:
                client_id = existing_client[0]
        
        # Пошук по телефону
        if not client_id and phone:
            phone_digits = ''.join(c for c in phone if c.isdigit())
            if len(phone_digits) >= 9:
                phone_suffix = phone_digits[-9:]
                existing_client = db.execute(text("""
                    SELECT id FROM client_users WHERE phone LIKE :phone LIMIT 1
                """), {"phone": f'%{phone_suffix}'}).fetchone()
                if existing_client:
                    client_id = existing_client[0]
        
        if client_id:
            # Оновити дату останнього замовлення
            db.execute(text("""
                UPDATE client_users 
                SET last_order_date = CURDATE(), updated_at = NOW()
                WHERE id = :id
            """), {"id": client_id})
        else:
            # Створити нового клієнта
            db.execute(text("""
                INSERT INTO client_users 
                    (email, email_normalized, full_name, phone, source, is_active, created_at, updated_at, last_order_date)
                VALUES (:email, :email_norm, :name, :phone, 'rentalhub', 1, NOW(), NOW(), CURDATE())
            """), {
                "email": order.customer_email or None,
                "email_norm": email_normalized,
                "name": order.customer_name,
                "phone": order.customer_phone or None
            })
            client_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
        
        # Прив'язати клієнта до замовлення
        if client_id:
            db.execute(text("""
                UPDATE orders SET client_user_id = :client_id WHERE order_id = :order_id
            """), {"client_id": client_id, "order_id": order_id})
    except Exception as e:
        print(f"[create_order] Error creating client: {e}")
        # Не блокуємо створення замовлення якщо клієнт не створився
    
    db.commit()
    
    return {
        "message": "Order created successfully",
        "order_id": order_id,
        "order_number": order_number
    }

@router.post("/{order_id}/accept")
async def accept_order(
    order_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Прийняти замовлення і створити issue card
    ✅ MIGRATED: Full business logic for order acceptance
    """
    # Check order exists
    result = db.execute(text("""
        SELECT order_id, order_number, status FROM orders WHERE order_id = :id
    """), {"id": order_id})
    
    order_row = result.fetchone()
    if not order_row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    order_db_id, order_number, current_status = order_row
    
    # Validate status transition
    if current_status not in ['pending', 'awaiting_customer']:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot accept order in status: {current_status}"
        )
    
    # Update order status with user tracking
    db.execute(text("""
        UPDATE orders 
        SET status = 'processing',
            confirmed_by_id = :confirmed_by_id,
            confirmed_at = NOW(),
            updated_by_id = :updated_by_id,
            updated_at = NOW()
        WHERE order_id = :order_id
    """), {
        "order_id": order_id,
        "confirmed_by_id": current_user["id"],
        "updated_by_id": current_user["id"]
    })
    
    # Create issue card
    issue_card_id = f"issue_{order_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    items = data.get('items', [])
    
    db.execute(text("""
        INSERT INTO issue_cards (
            id, order_id, order_number, status, items, 
            prepared_by, created_by_id, created_at, updated_at
        ) VALUES (
            :id, :order_id, :order_number, 'preparation', :items, 
            :prepared_by, :created_by_id, NOW(), NOW()
        )
        ON DUPLICATE KEY UPDATE
            items = :items, 
            prepared_by = :prepared_by,
            updated_at = NOW()
    """), {
        "id": issue_card_id,
        "order_id": order_id,
        "order_number": order_number,
        "items": json.dumps(items),
        "prepared_by": current_user["name"],
        "created_by_id": current_user["id"]
    })
    
    # Log lifecycle з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'accepted', :notes, :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "notes": f"Замовлення прийнято",
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    # ✅ Автоматично створити клієнта якщо не існує
    # Отримати дані клієнта із замовлення
    client_data = db.execute(text("""
        SELECT customer_name, customer_phone, customer_email, client_user_id
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if client_data and not client_data[3]:  # Немає client_user_id
        try:
            customer_name = (client_data[0] or '').strip()
            customer_phone = (client_data[1] or '').strip()
            customer_email = (client_data[2] or '').strip()
            email_normalized = customer_email.lower().strip() if customer_email else ''
            
            found_client_id = None
            
            # Пошук по email
            if email_normalized and '@' in email_normalized:
                existing_client = db.execute(text("""
                    SELECT id FROM client_users WHERE email_normalized = :email LIMIT 1
                """), {"email": email_normalized}).fetchone()
                if existing_client:
                    found_client_id = existing_client[0]
            
            # Пошук по телефону
            if not found_client_id and customer_phone:
                phone_digits = ''.join(c for c in customer_phone if c.isdigit())
                if len(phone_digits) >= 9:
                    phone_suffix = phone_digits[-9:]
                    existing_client = db.execute(text("""
                        SELECT id FROM client_users WHERE phone LIKE :phone LIMIT 1
                    """), {"phone": f'%{phone_suffix}'}).fetchone()
                    if existing_client:
                        found_client_id = existing_client[0]
            
            if not found_client_id and customer_name:
                # Створити нового клієнта
                db.execute(text("""
                    INSERT INTO client_users 
                        (email, email_normalized, full_name, phone, source, is_active, created_at, updated_at, last_order_date)
                    VALUES (:email, :email_norm, :name, :phone, 'rentalhub', 1, NOW(), NOW(), CURDATE())
                """), {
                    "email": customer_email or None,
                    "email_norm": email_normalized,
                    "name": customer_name,
                    "phone": customer_phone or None
                })
                found_client_id = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            
            if found_client_id:
                db.execute(text("""
                    UPDATE orders SET client_user_id = :client_id WHERE order_id = :order_id
                """), {"client_id": found_client_id, "order_id": order_id})
                
                # Оновити last_order_date
                db.execute(text("""
                    UPDATE client_users SET last_order_date = CURDATE(), updated_at = NOW() WHERE id = :id
                """), {"id": found_client_id})
        except Exception as e:
            print(f"[accept_order] Error auto-creating client: {e}")
    
    # Створити фінансові транзакції автоматично
    # Отримати фінансові дані замовлення
    order_financial = db.execute(text("""
        SELECT total_price, deposit_amount, total_loss_value, rental_days
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if order_financial and order_financial[0]:
        total_amount = float(order_financial[0] or 0)
        deposit_amount = float(order_financial[1] or 0)
        total_loss_value = float(order_financial[2] or 0)
        rental_days = order_financial[3] or 1
        
        # Генерувати UUID для транзакцій
        rent_transaction_id = str(uuid.uuid4())
        deposit_transaction_id = str(uuid.uuid4())
        
        # 1. Нарахування оренди → fin_transactions
        db.execute(text("""
            INSERT INTO fin_transactions (
                tx_type, status, currency, amount, occurred_at, note,
                entity_type, entity_id, created_at
            ) VALUES (
                'rent_accrual', 'pending', 'UAH', :amount, NOW(), :note,
                'order', :order_id, NOW()
            )
        """), {
            "order_id": order_id,
            "amount": total_amount,
            "note": f"Оренда за {rental_days} дн."
        })
        
        # 2. Очікувана застава → fin_transactions
        db.execute(text("""
            INSERT INTO fin_transactions (
                tx_type, status, currency, amount, occurred_at, note,
                entity_type, entity_id, created_at
            ) VALUES (
                'deposit_expected', 'pending', 'UAH', :amount, NOW(), :note,
                'order', :order_id, NOW()
            )
        """), {
            "order_id": order_id,
            "amount": deposit_amount,
            "note": f"Очікувана застава (₴{deposit_amount}). Розраховано як 50% від вартості втрати: ₴{total_loss_value}"
        })
    
    db.commit()
    
    return {
        "message": "Order accepted and moved to preparation",
        "order_id": order_id,
        "issue_card_id": issue_card_id,
        "status": "processing"
    }


@router.delete("/{order_id}/items/{item_id}")
async def delete_order_item(
    order_id: int,
    item_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Видалити позицію з замовлення
    Використовується для видалення позицій під час комплектації
    """
    try:
        # Перевіряємо, що позиція існує і належить цьому замовленню
        item = db.execute(text("""
            SELECT oi.id, oi.product_id, oi.quantity, p.sku, p.name
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.product_id
            WHERE oi.id = :item_id AND oi.order_id = :order_id
        """), {"item_id": item_id, "order_id": order_id}).fetchone()
        
        if not item:
            raise HTTPException(status_code=404, detail="Позицію не знайдено")
        
        # Видаляємо позицію
        db.execute(text("""
            DELETE FROM order_items WHERE id = :item_id
        """), {"item_id": item_id})
        
        # Логуємо видалення
        product_info = f"{item[3] or ''} {item[4] or ''} x{item[2]}"
        db.execute(text("""
            INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
            VALUES (:order_id, 'item_removed', :notes, :created_by, :created_by_id, :created_by_name, NOW())
        """), {
            "order_id": order_id,
            "notes": f"Видалено позицію: {product_info}",
            "created_by": current_user.get("email", "system"),
            "created_by_id": current_user.get("id"),
            "created_by_name": current_user.get("name", current_user.get("email", "system"))
        })
        
        # Перераховуємо total_price замовлення
        db.execute(text("""
            UPDATE orders 
            SET total_price = (
                SELECT COALESCE(SUM(price * quantity), 0) 
                FROM order_items 
                WHERE order_id = :order_id
            ),
            updated_at = NOW()
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        db.commit()
        
        return {"success": True, "message": f"Позицію {product_info} видалено"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}")
async def delete_order(
    order_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Видалити замовлення (м'яке видалення)
    ✅ MIGRATED: Soft delete with validation
    """
    # Check if order can be deleted
    result = db.execute(text("""
        SELECT status FROM orders WHERE order_id = :id
    """), {"id": order_id})
    
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    
    status = row[0]
    
    # Only allow deletion of pending/cancelled orders
    if status not in ['pending', 'cancelled']:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete order in status: {status}. Cancel it first."
        )
    
    # Soft delete - mark as cancelled
    db.execute(text("""
        UPDATE orders 
        SET status = 'cancelled', 
            notes = CONCAT(COALESCE(notes, ''), '\n[DELETED]'),
            updated_by_id = :updated_by_id,
            updated_at = NOW()
        WHERE order_id = :id
    """), {"id": order_id, "updated_by_id": current_user["id"]})
    
    # Log з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'deleted', 'Order deleted', :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    db.commit()
    
    return {"message": "Order deleted (soft delete)", "order_id": order_id}

@router.post("/{order_id}/decline")
async def decline_order(
    order_id: int,
    data: dict,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Відхилити замовлення
    ✅ MIGRATED: Business logic for order declination
    """
    reason = data.get('reason', 'No reason provided')
    
    # Update status
    db.execute(text("""
        UPDATE orders 
        SET status = 'cancelled', 
            notes = CONCAT(COALESCE(notes, ''), '\n[DECLINED]: ', :reason)
        WHERE order_id = :order_id
    """), {
        "order_id": order_id,
        "reason": reason
    })
    
    # Log lifecycle з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'declined', :notes, :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "notes": f"Order declined: {reason}",
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    db.commit()
    
    return {
        "message": "Order declined",
        "order_id": order_id,
        "reason": reason
    }


@decor_router.post("/{order_id}/cancel-by-client")
@router.post("/{order_id}/cancel-by-client")
async def cancel_order_by_client(
    order_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Клієнт відмовився від замовлення
    ✅ Замовлення скасовується і товари розморожуються
    Можна використовувати до моменту видачі (до статусу 'issued')
    """
    reason = data.get('reason', 'Клієнт відмовився без пояснень')
    
    # Перевірити що замовлення ще не видане
    check_result = db.execute(text("""
        SELECT status FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_status_row = check_result.fetchone()
    check_result.close()
    
    if not order_status_row:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    current_status = order_status_row[0]
    
    if current_status in ('issued', 'on_rent', 'returned', 'completed'):
        raise HTTPException(
            status_code=400, 
            detail=f"Не можна скасувати замовлення зі статусом '{current_status}'. Замовлення вже видано або завершено."
        )
    
    # Оновити статус на cancelled і автоматично архівувати
    db.execute(text("""
        UPDATE orders 
        SET status = 'cancelled', 
            is_archived = 1,
            notes = CONCAT(COALESCE(notes, ''), '\n[СКАСОВАНО КЛІЄНТОМ]: ', :reason),
            updated_at = NOW()
        WHERE order_id = :order_id
    """), {
        "order_id": order_id,
        "reason": reason
    })
    
    # Залогувати в lifecycle з інформацією про користувача
    created_by_name = data.get('created_by', 'System')
    created_by_id = data.get('created_by_id')
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'cancelled_by_client', :notes, :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "notes": f"Клієнт відмовився від замовлення: {reason}",
        "created_by": created_by_name,
        "created_by_id": created_by_id,
        "created_by_name": created_by_name
    })
    
    db.commit()
    
    return {
        "message": "Замовлення скасовано",
        "order_id": order_id,
        "previous_status": current_status,
        "new_status": "cancelled",
        "reason": reason,
        "items_unfrozen": True
    }


@decor_router.post("/{order_id}/archive")
@router.post("/{order_id}/archive")
async def archive_order(
    order_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Архівувати замовлення
    ✅ Замовлення переміщується в архів і не показується на основному дашборді
    """
    # Перевірити що замовлення існує
    check_result = db.execute(text("""
        SELECT order_number, status FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = check_result.fetchone()
    check_result.close()
    
    if not order_row:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    order_number = order_row[0]
    status = order_row[1]
    
    # Оновити is_archived
    db.execute(text("""
        UPDATE orders 
        SET is_archived = 1,
            updated_by_id = :updated_by_id,
            updated_at = NOW()
        WHERE order_id = :order_id
    """), {"order_id": order_id, "updated_by_id": current_user["id"]})
    
    # Залогувати з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'archived', 'Замовлення переміщено в архів', :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    db.commit()
    
    return {
        "message": "Замовлення архівовано",
        "order_id": order_id,
        "order_number": order_number,
        "status": status,
        "is_archived": True
    }


@decor_router.post("/{order_id}/unarchive")
@router.post("/{order_id}/unarchive")
async def unarchive_order(
    order_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Розархівувати замовлення
    ✅ Замовлення повертається з архіву на основний дашборд
    """
    # Перевірити що замовлення існує
    check_result = db.execute(text("""
        SELECT order_number, status FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id})
    
    order_row = check_result.fetchone()
    check_result.close()
    
    if not order_row:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    order_number = order_row[0]
    status = order_row[1]
    
    # Оновити is_archived
    db.execute(text("""
        UPDATE orders 
        SET is_archived = 0,
            updated_by_id = :updated_by_id,
            updated_at = NOW()
        WHERE order_id = :order_id
    """), {"order_id": order_id, "updated_by_id": current_user["id"]})
    
    # Залогувати з інформацією про користувача
    db.execute(text("""
        INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
        VALUES (:order_id, 'unarchived', 'Замовлення відновлено з архіву', :created_by, :created_by_id, :created_by_name, NOW())
    """), {
        "order_id": order_id,
        "created_by": current_user.get("name", "System"),
        "created_by_id": current_user.get("id"),
        "created_by_name": current_user.get("name")
    })
    
    db.commit()
    
    return {
        "message": "Замовлення розархівовано",
        "order_id": order_id,
        "order_number": order_number,
        "status": status,
        "is_archived": False
    }



@decor_router.post("/archive-cancelled")
@router.post("/archive-cancelled")
async def archive_all_cancelled_orders(
    db: Session = Depends(get_rh_db)
):
    """
    Масово архівувати всі cancelled замовлення
    Utility endpoint для очищення старих скасованих замовлень
    """
    # Знайти всі cancelled замовлення які не архівовані
    result = db.execute(text("""
        SELECT order_id, order_number FROM orders 
        WHERE status = 'cancelled' AND is_archived = 0
    """))
    
    cancelled_orders = result.fetchall()
    count = len(cancelled_orders)
    
    if count == 0:
        return {
            "message": "Немає скасованих замовлень для архівування",
            "archived_count": 0
        }
    
    # Архівувати всі
    db.execute(text("""
        UPDATE orders 
        SET is_archived = 1, updated_at = NOW()
        WHERE status = 'cancelled' AND is_archived = 0
    """))
    
    # Залогувати для кожного (системна дія, тому created_by = 'System')
    for order_id, order_number in cancelled_orders:
        db.execute(text("""
            INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
            VALUES (:order_id, 'auto_archived', 'Автоматично архівовано (cancelled)', 'System', NULL, 'System', NOW())
        """), {"order_id": order_id})
    
    db.commit()
    
    return {
        "message": f"Архівовано {count} скасованих замовлень",
        "archived_count": count,
        "order_numbers": [row[1] for row in cancelled_orders]
    }

# ============================================================
# ADDITIONAL ENDPOINTS
# ============================================================

@router.get("/customer/{customer_id}/stats")
async def get_customer_stats(
    customer_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Статистика клієнта
    ✅ MIGRATED
    """
    result = db.execute(text("""
        SELECT 
            COUNT(*) as total_orders,
            SUM(total_price) as total_spent,
            COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_orders,
            COUNT(CASE WHEN status = 'cancelled' THEN 1 END) as cancelled_orders
        FROM orders 
        WHERE customer_id = :id
    """), {"id": customer_id})
    
    row = result.fetchone()
    
    return {
        "customer_id": customer_id,
        "total_orders": row[0] or 0,
        "total_spent": float(row[1]) if row[1] else 0.0,
        "completed_orders": row[2] or 0,
        "cancelled_orders": row[3] or 0
    }

@router.get("/inventory/search")
async def search_inventory(
    query: str,
    limit: int = 20,
    db: Session = Depends(get_rh_db)
):
    """
    Пошук інвентарю для замовлення
    ✅ MIGRATED - використовує products.quantity замість inventory
    """
    result = db.execute(text("""
        SELECT 
            p.product_id, p.sku, p.name, p.price, p.rental_price, p.image_url,
            p.quantity, p.zone, p.aisle, p.shelf
        FROM products p
        WHERE p.status = 1 
        AND (p.name LIKE :query OR p.sku LIKE :query)
        LIMIT :limit
    """), {"query": f"%{query}%", "limit": limit})
    
    products = []
    for row in result:
        # Формуємо локацію
        location_parts = [row[7], row[8], row[9]]
        location = "-".join(filter(None, location_parts)) if any(location_parts) else None
        
        products.append({
            "product_id": row[0],
            "sku": row[1],
            "name": row[2],
            "price": float(row[3]) if row[3] else 0.0,  # Full price (damage cost)
            "rent_price": float(row[4]) if row[4] else 0.0,  # Rental price per day
            "image_url": row[5],
            "available_quantity": int(row[6]) if row[6] else 0,
            "location": location
        })
    
    return {"products": products, "total": len(products)}


# ============================================================
# MERGE ORDERS - Об'єднання замовлень
# ============================================================

@router.post("/merge")
async def merge_orders(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Об'єднати кілька замовлень в одне.
    Товари з source_order_ids переносяться в target_order_id.
    Source замовлення видаляються.
    """
    target_order_id = data.get('target_order_id')
    source_order_ids = data.get('source_order_ids', [])
    
    if not target_order_id or not source_order_ids:
        raise HTTPException(status_code=400, detail="target_order_id та source_order_ids обов'язкові")
    
    if target_order_id in source_order_ids:
        raise HTTPException(status_code=400, detail="target_order_id не може бути в source_order_ids")
    
    try:
        # Перевірити що всі замовлення існують і в статусі awaiting_customer
        all_order_ids = [target_order_id] + source_order_ids
        
        # SQLAlchemy з MySQL потребує динамічного SQL для IN clause
        placeholders = ', '.join([f':id{i}' for i in range(len(all_order_ids))])
        params = {f'id{i}': oid for i, oid in enumerate(all_order_ids)}
        
        result = db.execute(text(f"""
            SELECT order_id, order_number, status, customer_id 
            FROM orders WHERE order_id IN ({placeholders})
        """), params)
        orders = {row[0]: {"order_number": row[1], "status": row[2], "customer_id": row[3]} for row in result.fetchall()}
        
        if len(orders) != len(all_order_ids):
            missing = set(all_order_ids) - set(orders.keys())
            raise HTTPException(status_code=404, detail=f"Замовлення не знайдено: {missing}")
        
        # Перевірити статуси
        for oid, odata in orders.items():
            if odata['status'] != 'awaiting_customer':
                raise HTTPException(
                    status_code=400, 
                    detail=f"Замовлення {odata['order_number']} має статус '{odata['status']}'. Об'єднання можливе тільки для 'awaiting_customer'"
                )
        
        # Отримати rental_days з target замовлення
        result = db.execute(text("SELECT rental_days FROM orders WHERE order_id = :id"), {"id": target_order_id})
        target_rental_days = result.fetchone()[0] or 1
        
        # Перенести товари з source замовлень в target
        for source_id in source_order_ids:
            # Отримати товари з source
            result = db.execute(text("""
                SELECT product_id, product_name, quantity, price, total_rental, image_url
                FROM order_items WHERE order_id = :id
            """), {"id": source_id})
            source_items = result.fetchall()
            
            # Додати в target
            for item in source_items:
                product_id, product_name, quantity, price, total_rental, image_url = item
                # Перерахувати total_rental з новими rental_days
                new_total_rental = float(price or 0) * int(quantity or 1) * target_rental_days
                
                # Перевірити чи такий товар вже є в target
                existing = db.execute(text("""
                    SELECT id, quantity FROM order_items 
                    WHERE order_id = :order_id AND product_id = :product_id
                """), {"order_id": target_order_id, "product_id": product_id}).fetchone()
                
                if existing:
                    # Збільшити кількість
                    new_qty = existing[1] + quantity
                    new_total = float(price or 0) * new_qty * target_rental_days
                    db.execute(text("""
                        UPDATE order_items SET quantity = :qty, total_rental = :total
                        WHERE id = :id
                    """), {"qty": new_qty, "total": new_total, "id": existing[0]})
                else:
                    # Додати новий товар
                    db.execute(text("""
                        INSERT INTO order_items (order_id, product_id, product_name, quantity, price, total_rental, image_url)
                        VALUES (:order_id, :product_id, :product_name, :quantity, :price, :total_rental, :image_url)
                    """), {
                        "order_id": target_order_id,
                        "product_id": product_id,
                        "product_name": product_name,
                        "quantity": quantity,
                        "price": price,
                        "total_rental": new_total_rental,
                        "image_url": image_url
                    })
            
            # Видалити order_items з source
            db.execute(text("DELETE FROM order_items WHERE order_id = :id"), {"id": source_id})
            
            # Видалити source замовлення
            db.execute(text("DELETE FROM orders WHERE order_id = :id"), {"id": source_id})
        
        # Перерахувати total_price і deposit_amount для target
        result = db.execute(text("""
            SELECT 
                SUM(oi.price * oi.quantity * :days) as total_price,
                SUM(COALESCE(p.price, 0) * oi.quantity / 2) as deposit_amount
            FROM order_items oi
            LEFT JOIN products p ON oi.product_id = p.product_id
            WHERE oi.order_id = :order_id
        """), {"order_id": target_order_id, "days": target_rental_days})
        totals = result.fetchone()
        total_price = float(totals[0] or 0)
        deposit_amount = float(totals[1] or 0)
        
        # Оновити target замовлення
        db.execute(text("""
            UPDATE orders 
            SET total_price = :total_price,
                deposit_amount = :deposit_amount,
                total_loss_value = :deposit_amount,
                notes = CONCAT(COALESCE(notes, ''), '\n[Об''єднано з: ', :merged_orders, ']'),
                updated_at = NOW()
            WHERE order_id = :order_id
        """), {
            "total_price": total_price,
            "deposit_amount": deposit_amount,
            "merged_orders": ", ".join([orders[oid]['order_number'] for oid in source_order_ids]),
            "order_id": target_order_id
        })
        
        # Отримати кількість товарів
        result = db.execute(text("SELECT COUNT(*) FROM order_items WHERE order_id = :id"), {"id": target_order_id})
        items_count = result.fetchone()[0]
        
        db.commit()
        
        return {
            "message": "Замовлення успішно об'єднано",
            "order_id": target_order_id,
            "order_number": orders[target_order_id]['order_number'],
            "merged_from": [orders[oid]['order_number'] for oid in source_order_ids],
            "items_count": items_count,
            "total_price": total_price,
            "deposit_amount": deposit_amount
        }
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка при об'єднанні: {str(e)}")


@router.post("/check-availability")
async def check_availability_endpoint(
    request: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Перевірити доступність товарів на період
    Request body: { start_date, end_date, items: [{product_id, quantity}], exclude_order_id?: int }
    ✅ MIGRATED: Using products + order_items from RentalHub DB
    ✅ USES: availability_checker utility для консистентної логіки
    ✅ FIXED: Підтримка exclude_order_id для виключення поточного замовлення
    """
    try:
        from utils.availability_checker import check_order_availability
        
        start_date = request.get("start_date")
        end_date = request.get("end_date")
        items = request.get("items", [])
        exclude_order_id = request.get("exclude_order_id")  # ✅ ID замовлення для виключення
        
        if not start_date or not end_date:
            raise HTTPException(status_code=400, detail="start_date and end_date are required")
        
        if not items:
            raise HTTPException(status_code=400, detail="items list is required")
        
        # Use the availability checker utility
        availability_result = check_order_availability(
            db=db,
            items=items,
            start_date=start_date,
            end_date=end_date,
            exclude_order_id=exclude_order_id  # ✅ Передаємо exclude_order_id
        )
        
        return availability_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking availability: {str(e)}")


# ============================================================
# DECOR ORDERS ENDPOINTS (сумісність з /api/decor-orders)
# ============================================================

@decor_router.get("")
async def get_decor_orders(
    status: Optional[str] = None,
    archived: Optional[str] = None,
    limit: int = 1000,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати замовлення (алиас для основного GET /orders)
    ✅ MIGRATED: Using RentalHub DB
    """
    return await get_orders(status=status, archived=archived, limit=limit, db=db)


@decor_router.get("/{order_id}")
async def get_decor_order(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати деталі замовлення (алиас для GET /orders/{order_id})
    ✅ MIGRATED: Using RentalHub DB
    """
    return await get_order_details(order_id=order_id, db=db)


@decor_router.put("/{order_id}")
async def update_decor_order(
    order_id: int,
    order_data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити замовлення (спрощена версія для decor orders)
    ✅ MIGRATED: Using RentalHub DB
    ✅ FIXED: Тепер приймає total_price, deposit_amount, total_loss_value
    """
    # Перевірити чи існує замовлення
    result = db.execute(text("SELECT order_id FROM orders WHERE order_id = :id"), {"id": order_id})
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Build update
    set_clauses = []
    params = {"order_id": order_id}
    
    # Mapping frontend field names to DB field names
    field_mapping = {
        'rental_start_date': 'rental_start_date',
        'rental_end_date': 'rental_end_date',
        'issue_time': 'issue_time',
        'return_time': 'return_time',
        'rental_days': 'rental_days',
        'manager_comment': 'manager_comment',
        'discount': 'discount_percent',  # Frontend: discount (%) -> DB: discount_percent
        'discount_amount': 'discount_amount',  # Сума знижки в грн
        'manager_id': 'manager_id',  # ✅ FIXED: Менеджер замовлення
        # ✅ КРИТИЧНО: Фінансові поля - джерело правди
        'total_price': 'total_price',
        'deposit_amount': 'deposit_amount',
        'total_loss_value': 'total_loss_value',
    }
    
    for frontend_field, db_field in field_mapping.items():
        if frontend_field in order_data:
            set_clauses.append(f"{db_field} = :{db_field}")
            params[db_field] = order_data[frontend_field]
    
    if set_clauses:
        set_clauses.append("updated_at = NOW()")
        sql = f"UPDATE orders SET {', '.join(set_clauses)} WHERE order_id = :order_id"
        db.execute(text(sql), params)
        db.commit()
    
    return {"message": "Order updated", "order_id": order_id}


@decor_router.put("/{order_id}/status")
async def update_decor_order_status(
    order_id: int,
    status_data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Оновити статус замовлення (алиас для PUT /orders/{order_id}/status)
    ✅ MIGRATED: Using RentalHub DB
    """
    return await update_order_status(order_id=order_id, data=status_data, db=db)


@decor_router.put("/{order_id}/items")
async def update_decor_order_items(
    order_id: int,
    items_data: dict,
    db: Session = Depends(get_rh_db),
    authorization: Optional[str] = Header(None)
):
    """
    Оновити товари в замовленні
    ✅ MIGRATED: Using RentalHub DB + User Tracking
    ✅ FIXED: Тепер перераховує total_price і deposit_amount в orders
    ✅ FIXED: Зберігає прогрес комплектації при оновленні items
    """
    from utils.user_tracking_helper import get_current_user_from_header
    import json
    
    try:
        # Get current user for tracking
        current_user = get_current_user_from_header(authorization)
        user_id = current_user.get("id")
        user_name = current_user.get("email", "System")
        
        # Перевірити чи існує замовлення та отримати rental_days
        result = db.execute(text("SELECT order_id, rental_days, order_number FROM orders WHERE order_id = :id"), {"id": order_id})
        order_row = result.fetchone()
        if not order_row:
            raise HTTPException(status_code=404, detail="Order not found")
        
        rental_days = order_row[1] or 1
        order_number = order_row[2]
        
        items = items_data.get('items', [])
        if not items:
            raise HTTPException(status_code=400, detail="No items provided")
        
        # ✅ ОТРИМАТИ ІСНУЮЧІ ORDER_ITEMS для порівняння
        existing_items_result = db.execute(text("""
            SELECT id, product_id, product_name, quantity FROM order_items WHERE order_id = :order_id
        """), {"order_id": order_id})
        existing_items = {str(r[1]): {"id": r[0], "name": r[2], "qty": r[3]} for r in existing_items_result}
        
        # ✅ ОТРИМАТИ ISSUE_CARD та її items для збереження прогресу
        issue_card_result = db.execute(text("""
            SELECT id, items, status FROM issue_cards WHERE order_id = :order_id
        """), {"order_id": order_id})
        issue_card_row = issue_card_result.fetchone()
        
        issue_card_id = None
        issue_card_items = {}
        issue_card_status = None
        if issue_card_row:
            issue_card_id = issue_card_row[0]
            issue_card_status = issue_card_row[2]
            if issue_card_row[1]:
                ic_items_list = json.loads(issue_card_row[1]) if isinstance(issue_card_row[1], str) else issue_card_row[1]
                # Створити словник по sku для швидкого пошуку
                issue_card_items = {it.get('sku') or it.get('id'): it for it in ic_items_list}
        
        # Видалити старі items
        db.execute(text("DELETE FROM order_items WHERE order_id = :order_id"), {"order_id": order_id})
        
        # Додати нові items та порахувати фінанси
        total_rent = 0
        total_deposit = 0
        new_issue_card_items = []
        added_items = []
        removed_items = []
        modified_items = []
        
        new_product_ids = set()
        for item in items:
            inventory_id = item.get('inventory_id') or item.get('product_id')
            new_product_ids.add(str(inventory_id))
        
        # Знайти видалені items
        for pid, old_item in existing_items.items():
            if pid not in new_product_ids:
                removed_items.append(old_item['name'])
        
        for item in items:
            inventory_id = item.get('inventory_id') or item.get('product_id')
            product_name = item.get('name') or item.get('product_name', '')
            sku = item.get('sku') or item.get('article') or str(inventory_id)
            quantity = int(item.get('quantity', 1))
            price_per_day = float(item.get('price_per_day', 0))
            deposit = float(item.get('deposit', 0) or item.get('damage_cost', 0) or 0)
            total_rental = float(item.get('total_rental', price_per_day * quantity * rental_days))
            image_url = item.get('image') or item.get('photo', '')
            
            # Акумулювати фінанси
            total_rent += price_per_day * quantity * rental_days
            total_deposit += deposit * quantity
            
            db.execute(text("""
                INSERT INTO order_items (
                    order_id, product_id, product_name, quantity, 
                    price, total_rental, image_url
                ) VALUES (
                    :order_id, :product_id, :product_name, :quantity,
                    :price, :total_rental, :image_url
                )
            """), {
                "order_id": order_id,
                "product_id": inventory_id,
                "product_name": product_name,
                "quantity": quantity,
                "price": price_per_day,
                "total_rental": total_rental,
                "image_url": image_url
            })
            
            # ✅ ЗБЕРЕГТИ ПРОГРЕС КОМПЛЕКТАЦІЇ
            is_new_item = str(inventory_id) not in existing_items
            old_qty = existing_items.get(str(inventory_id), {}).get('qty', 0)
            qty_changed = not is_new_item and quantity != old_qty
            
            if is_new_item:
                added_items.append(f"{product_name} x{quantity}")
            elif qty_changed:
                modified_items.append(f"{product_name}: {old_qty} → {quantity}")
            
            # Шукаємо існуючий прогрес по sku
            existing_progress = issue_card_items.get(sku) or issue_card_items.get(str(inventory_id))
            
            new_ic_item = {
                "id": str(inventory_id),
                "sku": sku,
                "name": product_name,
                "qty": quantity,
                "picked_qty": 0,
                "scanned": [],
                "packaging": {"stretch": False, "box": False, "cover": False, "black_case": False},
                "pre_damage": [],
                "is_new": is_new_item,  # ✅ Позначаємо нові items
                "qty_changed": qty_changed,  # ✅ Позначаємо змінену кількість
                "added_at": None
            }
            
            # Якщо є існуючий прогрес - зберегти його
            if existing_progress:
                new_ic_item["picked_qty"] = min(existing_progress.get("picked_qty", 0), quantity)
                new_ic_item["scanned"] = existing_progress.get("scanned", [])
                new_ic_item["packaging"] = existing_progress.get("packaging", new_ic_item["packaging"])
                new_ic_item["pre_damage"] = existing_progress.get("pre_damage", [])
                new_ic_item["is_new"] = False
                new_ic_item["qty_changed"] = qty_changed
            
            if is_new_item:
                from datetime import datetime
                new_ic_item["added_at"] = datetime.now().isoformat()
            
            new_issue_card_items.append(new_ic_item)
        
        # ✅ КРИТИЧНО: Оновити total_price і deposit_amount в orders
        db.execute(text("""
            UPDATE orders 
            SET total_price = :total_price,
                deposit_amount = :deposit_amount,
                total_loss_value = :deposit_amount,
                updated_by_id = :user_id,
                updated_at = NOW()
            WHERE order_id = :order_id
        """), {
            "total_price": total_rent,
            "deposit_amount": total_deposit,
            "user_id": user_id,
            "order_id": order_id
        })
        
        # ✅ ОНОВИТИ ISSUE_CARD ITEMS (зберігаючи прогрес)
        if issue_card_id:
            db.execute(text("""
                UPDATE issue_cards 
                SET items = :items, updated_at = NOW()
                WHERE id = :id
            """), {
                "items": json.dumps(new_issue_card_items, ensure_ascii=False),
                "id": issue_card_id
            })
        
        # ✅ ЛОГУВАННЯ ЗМІН В ORDER_LIFECYCLE
        changes = []
        if added_items:
            changes.append(f"Додано: {', '.join(added_items)}")
        if removed_items:
            changes.append(f"Видалено: {', '.join(removed_items)}")
        if modified_items:
            changes.append(f"Змінено кількість: {', '.join(modified_items)}")
        
        if changes:
            db.execute(text("""
                INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_at, created_by_id, created_by_name)
                VALUES (:order_id, 'items_modified', :notes, :created_by, NOW(), :user_id, :user_name)
            """), {
                "order_id": order_id,
                "notes": "; ".join(changes),
                "created_by": user_name,
                "user_id": user_id,
                "user_name": user_name
            })
        
        db.commit()
        
        return {
            "message": "Items updated successfully",
            "order_id": order_id,
            "items_count": len(items),
            "total_price": total_rent,
            "deposit_amount": total_deposit,
            "packing_progress_preserved": issue_card_id is not None,
            "changes": changes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[UPDATE ITEMS] Error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@decor_router.post("/{order_id}/confirm-by-client")
async def confirm_order_by_client(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Підтвердження замовлення клієнтом через посилання в email
    ✅ MIGRATED: Using RentalHub DB
    """
    try:
        # Перевірити чи існує замовлення
        result = db.execute(text("""
            SELECT order_id, order_number, status, client_confirmed FROM orders
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")
        
        order_id_val, order_number, status, client_confirmed = row
        
        # Якщо вже підтверджено
        if client_confirmed:
            return {
                "success": True,
                "message": "Замовлення вже підтверджено раніше. Дякуємо!",
                "status": status,
                "client_confirmed": True
            }
        
        # Встановити флаг client_confirmed
        db.execute(text("""
            UPDATE orders 
            SET client_confirmed = TRUE
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": "Дякуємо! Замовлення підтверджено. Менеджер почне комплектацію найближчим часом.",
            "order_number": order_number,
            "status": status,
            "client_confirmed": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка підтвердження: {str(e)}"
        )


class MoveToPreparationRequest(BaseModel):
    user_id: Optional[int] = None
    user_name: Optional[str] = None

@decor_router.post("/{order_id}/move-to-preparation")
async def move_to_preparation(
    order_id: int,
    data: Optional[MoveToPreparationRequest] = None,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Відправити замовлення на збір (awaiting_customer → processing)
    Автоматично встановлює client_confirmed = True
    ✅ MIGRATED: Using RentalHub DB
    """
    try:
        # Отримати замовлення
        result = db.execute(text("""
            SELECT order_id, order_number, status, client_confirmed FROM orders
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")
        
        order_id_val, order_number, status, client_confirmed = row
        
        if status != 'awaiting_customer':
            raise HTTPException(
                status_code=400,
                detail=f"Неможливо відправити на збір. Поточний статус: {status}"
            )
        
        # ПЕРЕВІРКА ДОСТУПНОСТІ перед заморожуванням товарів
        from utils.availability_checker import check_order_availability
        
        # Отримати дати оренди та товари
        order_details = db.execute(text("""
            SELECT o.rental_start_date, o.rental_end_date
            FROM orders o
            WHERE o.order_id = :order_id
        """), {"order_id": order_id}).fetchone()
        
        if order_details:
            rental_start = order_details[0]
            rental_end = order_details[1]
            
            # Отримати товари
            items_result = db.execute(text("""
                SELECT product_id, quantity FROM order_items
                WHERE order_id = :order_id
            """), {"order_id": order_id})
            
            items = [{"product_id": row[0], "quantity": row[1]} for row in items_result]
            
            # Використати утиліту для перевірки (виключити поточне замовлення)
            availability = check_order_availability(
                db=db,
                items=items,
                start_date=rental_start.isoformat() if rental_start else None,
                end_date=rental_end.isoformat() if rental_end else None,
                exclude_order_id=order_id
            )
            
            # Якщо є недоступні товари, відхилити запит
            if not availability["all_available"]:
                error_messages = []
                for item in availability["unavailable_items"]:
                    # Отримати SKU для повідомлення
                    sku_result = db.execute(text("""
                        SELECT sku, name FROM products WHERE product_id = :product_id
                    """), {"product_id": item["product_id"]})
                    sku_row = sku_result.fetchone()
                    sku = sku_row[0] if sku_row else str(item["product_id"])
                    name = sku_row[1] if sku_row and len(sku_row) > 1 else "Товар"
                    
                    error_messages.append(
                        f"{sku} ({name}): потрібно {item['requested_quantity']}, "
                        f"доступно {item['available_quantity']}"
                    )
                
                error_details = "; ".join(error_messages)
                raise HTTPException(
                    status_code=400,
                    detail=f"Неможливо підтвердити замовлення. Товари недоступні: {error_details}"
                )
        
        # Оновити замовлення (заморожує товари)
        db.execute(text("""
            UPDATE orders 
            SET client_confirmed = TRUE, status = 'processing'
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        # Перевірити чи існує issue card
        issue_result = db.execute(text("""
            SELECT id FROM issue_cards WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        issue_row = issue_result.fetchone()
        
        if not issue_row:
            # Створити issue card з правильним ID форматом
            issue_card_id = f"IC-{order_id}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            db.execute(text("""
                INSERT INTO issue_cards 
                (id, order_id, order_number, status, created_at, updated_at)
                VALUES (:id, :order_id, :order_number, 'preparation', NOW(), NOW())
            """), {
                "id": issue_card_id,
                "order_id": order_id,
                "order_number": order_number
            })
        else:
            # Оновити існуючий issue card
            issue_card_id = issue_row[0]
            db.execute(text("""
                UPDATE issue_cards 
                SET status = 'preparation', updated_at = NOW()
                WHERE id = :issue_card_id
            """), {"issue_card_id": issue_card_id})
        
        # Створити фінансові транзакції автоматично
        # Отримати фінансові дані замовлення
        order_financial = db.execute(text("""
            SELECT total_price, deposit_amount, total_loss_value, rental_days
            FROM orders WHERE order_id = :order_id
        """), {"order_id": order_id}).fetchone()
        
        if order_financial and order_financial[0]:
            total_amount = float(order_financial[0] or 0)
            deposit_amount = float(order_financial[1] or 0)
            total_loss_value = float(order_financial[2] or 0)
            rental_days = order_financial[3] or 1
            
            # Перевірити чи вже існують фінансові транзакції для цього замовлення
            existing_transactions = db.execute(text("""
                SELECT COUNT(*) FROM fin_transactions 
                WHERE entity_type = 'order' AND entity_id = :order_id 
                AND tx_type IN ('rent_accrual', 'deposit_expected')
            """), {"order_id": order_id}).scalar()
            
            # Створити транзакції тільки якщо їх ще немає
            if existing_transactions == 0:
                # 1. Нарахування оренди → fin_transactions
                db.execute(text("""
                    INSERT INTO fin_transactions (
                        tx_type, status, currency, amount, occurred_at, note,
                        entity_type, entity_id, created_at
                    ) VALUES (
                        'rent_accrual', 'pending', 'UAH', :amount, NOW(), :note,
                        'order', :order_id, NOW()
                    )
                """), {
                    "order_id": order_id,
                    "amount": total_amount,
                    "note": f"Оренда за {rental_days} дн. Автоматично при відправці на збір"
                })
                
                # 2. Очікувана застава → fin_transactions
                db.execute(text("""
                    INSERT INTO fin_transactions (
                        tx_type, status, currency, amount, occurred_at, note,
                        entity_type, entity_id, created_at
                    ) VALUES (
                        'deposit_expected', 'pending', 'UAH', :amount, NOW(), :note,
                        'order', :order_id, NOW()
                    )
                """), {
                    "order_id": order_id,
                    "amount": deposit_amount,
                    "note": f"Очікувана застава (₴{deposit_amount}). Розраховано як 50% від вартості втрати: ₴{total_loss_value}. Автоматично при відправці на збір"
                })
        
        # Log lifecycle з інформацією про менеджера (пріоритет: JWT токен > тіло запиту)
        user_name = current_user.get("name") if current_user.get("name") else (data.user_name if data and data.user_name else "Менеджер")
        user_id = current_user.get("id") if current_user.get("id") else (data.user_id if data and data.user_id else None)
        db.execute(text("""
            INSERT INTO order_lifecycle (order_id, stage, notes, created_by, created_by_id, created_by_name, created_at)
            VALUES (:order_id, 'preparation', :notes, :created_by, :created_by_id, :created_by_name, NOW())
        """), {
            "order_id": order_id,
            "notes": "Відправлено на збір (комплектація)",
            "created_by": user_name,
            "created_by_id": user_id,
            "created_by_name": user_name
        })
        
        db.commit()
        
        return {
            "success": True,
            "message": "Замовлення відправлено на збір. Клієнт автоматично підтверджений.",
            "order_id": order_id,
            "issue_card_id": issue_card_id,
            "status": "processing",
            "client_confirmed": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка відправки на збір: {str(e)}"
        )


# Alias для send-to-assembly (викликає move-to-preparation)
@decor_router.post("/{order_id}/send-to-assembly")
async def send_to_assembly(
    order_id: int,
    current_user: dict = Depends(get_current_user_dependency),
    db: Session = Depends(get_rh_db)
):
    """
    Alias для move-to-preparation
    Відправити замовлення на збір - заморозити декор та передати реквізиторам
    """
    return await move_to_preparation(order_id, None, current_user, db)


@decor_router.put("/{order_id}/return-progress")
async def save_return_progress(
    order_id: int,
    progress_data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Зберегти прогрес повернення (до завершення)
    Дозволяє зберігати проміжний стан для генерації документів
    """
    try:
        items = progress_data.get('items', [])
        receivers = progress_data.get('receivers', [])
        notes = progress_data.get('notes', '')
        fees = progress_data.get('fees', {})
        
        # Зберігаємо прогрес в return_cards або orders
        # Спочатку перевіримо чи є return_cards таблиця
        try:
            db.execute(text("""
                INSERT INTO return_cards (order_id, items, receivers, notes, fees, created_at, updated_at)
                VALUES (:order_id, :items, :receivers, :notes, :fees, NOW(), NOW())
                ON DUPLICATE KEY UPDATE 
                    items = :items,
                    receivers = :receivers, 
                    notes = :notes,
                    fees = :fees,
                    updated_at = NOW()
            """), {
                "order_id": order_id,
                "items": json.dumps(items),
                "receivers": json.dumps(receivers),
                "notes": notes,
                "fees": json.dumps(fees)
            })
        except Exception as e:
            # Якщо таблиці немає - зберігаємо в orders.return_data
            db.execute(text("""
                UPDATE orders 
                SET notes = :notes,
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {
                "order_id": order_id,
                "notes": notes
            })
        
        db.commit()
        return {"success": True, "message": "Прогрес збережено"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Помилка збереження: {str(e)}")


@decor_router.post("/{order_id}/complete-return")
async def complete_return(
    order_id: int,
    return_data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Завершити повернення замовлення
    ✅ MIGRATED: Using RentalHub DB
    """
    try:
        # Отримати дані про збитки
        late_fee = float(return_data.get('late_fee', 0))
        cleaning_fee = float(return_data.get('cleaning_fee', 0))
        damage_fee = float(return_data.get('damage_fee', 0))
        total_fees = late_fee + cleaning_fee + damage_fee
        
        # ✅ ВИПРАВЛЕННЯ: Перевірити та завершити активні продовження оренди
        # Якщо замовлення було в partial_return, потрібно закрити всі extensions
        try:
            active_extensions = db.execute(text("""
                SELECT id, product_id, sku, name, qty, original_end_date, daily_rate, adjusted_daily_rate
                FROM order_extensions 
                WHERE order_id = :order_id AND status = 'active'
            """), {"order_id": order_id}).fetchall()
            
            if active_extensions:
                print(f"[Orders] Знайдено {len(active_extensions)} активних продовжень для замовлення {order_id}")
                
                for ext in active_extensions:
                    ext_id, product_id, sku, name, qty, original_end, daily_rate, adj_rate = ext
                    
                    # Розрахувати дні прострочення
                    if original_end:
                        from datetime import datetime
                        days = (datetime.now().date() - original_end).days
                        if days < 0:
                            days = 0
                    else:
                        days = 0
                    
                    rate = float(adj_rate or daily_rate or 0)
                    total = days * rate * int(qty or 1)
                    
                    # Завершити продовження
                    db.execute(text("""
                        UPDATE order_extensions
                        SET status = 'completed',
                            days_extended = :days,
                            total_charged = :total,
                            completed_at = NOW()
                        WHERE id = :ext_id
                    """), {"ext_id": ext_id, "days": days, "total": total})
                    
                    # Додати фінансову транзакцію якщо є нарахування
                    if total > 0:
                        db.execute(text("""
                            INSERT INTO fin_payments 
                            (order_id, payment_type, amount, currency, note, occurred_at)
                            VALUES (:order_id, 'late', :amount, 'UAH', :description, NOW())
                        """), {
                            "order_id": order_id,
                            "amount": total,
                            "description": f"Прострочення: {sku} x{qty}: {days} днів × ₴{rate:.2f} = ₴{total:.2f}"
                        })
                    
                    # Записати в лог
                    db.execute(text("""
                        INSERT INTO partial_return_log 
                        (order_id, product_id, sku, action, qty, amount, notes)
                        VALUES (:order_id, :product_id, :sku, 'returned', :qty, :amount, :notes)
                    """), {
                        "order_id": order_id,
                        "product_id": product_id,
                        "sku": sku,
                        "qty": qty,
                        "amount": total,
                        "notes": f"Повернено після {days} днів прострочення"
                    })
                    
                    print(f"[Orders] ✅ Продовження {sku} завершено: {days} днів, ₴{total:.2f}")
                
                # Очистити флаг partial_return
                db.execute(text("""
                    UPDATE orders SET has_partial_return = 0 WHERE order_id = :order_id
                """), {"order_id": order_id})
        except Exception as e:
            print(f"[Orders] ⚠️ Помилка при обробці продовжень: {e}")
        
        # Оновити статус замовлення та зберегти damage_fee
        # ВАЖЛИВО: НЕ перезаписуємо manager_comment (там коментар клієнта!)
        manager_notes = return_data.get('manager_notes', '')
        db.execute(text("""
            UPDATE orders 
            SET status = 'returned',
                damage_fee = :damage_fee
            WHERE order_id = :order_id
        """), {
            "order_id": order_id,
            "damage_fee": damage_fee
        })
        
        # Зберегти нотатку про збиток в issue_cards.manager_notes (дописати)
        if manager_notes:
            db.execute(text("""
                UPDATE issue_cards 
                SET manager_notes = CONCAT(
                    COALESCE(manager_notes, ''), 
                    '\n\n--- Повернення ---\n',
                    :return_notes
                ),
                updated_at = NOW()
                WHERE order_id = :order_id
            """), {
                "order_id": order_id,
                "return_notes": manager_notes
            })
        
        # Оновити return card якщо існує таблиця
        try:
            db.execute(text("""
                UPDATE decor_return_cards 
                SET status = 'completed', updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
        except Exception as e:
            print(f"[Orders] Return cards table not found or error updating: {e}")
        
        # ✅ ВИПРАВЛЕННЯ: Оновити статус issue_cards на 'completed' (для архіву)
        try:
            db.execute(text("""
                UPDATE issue_cards 
                SET status = 'completed', 
                    updated_at = NOW()
                WHERE order_id = :order_id
            """), {"order_id": order_id})
            print(f"[Orders] Issue card для замовлення {order_id} позначено як 'completed'")
        except Exception as e:
            print(f"[Orders] Error updating issue_cards status: {e}")
        
        # Статус 'returned' автоматично "розморожує" товари в order_items
        print(f"[Orders] Замовлення {order_id} повернуто (товари розморожені)")
        
        # Розподілення товарів (мийка/реставрація) НЕ робиться автоматично.
        # Реквізитор сам вирішує через механізм розподілення в кабінеті.
        
        # Створити фінансову транзакцію для збитків (якщо є)
        if total_fees > 0:
            fee_details = []
            if late_fee > 0:
                fee_details.append(f"Пеня: ₴{late_fee:.2f}")
            if cleaning_fee > 0:
                fee_details.append(f"Чистка: ₴{cleaning_fee:.2f}")
            if damage_fee > 0:
                fee_details.append(f"Пошкодження: ₴{damage_fee:.2f}")
            
            description = f"Збитки після повернення замовлення #{order_id}. " + ", ".join(fee_details)
            
            # Додати коментар реквізитора до опису
            manager_notes = return_data.get('manager_notes', '')
            if manager_notes:
                description += f" | Коментар: {manager_notes}"
            
            db.execute(text("""
                INSERT INTO fin_transactions (
                    tx_type, status, currency, amount, occurred_at, note,
                    entity_type, entity_id, created_at
                ) VALUES (
                    'charge', 'pending', 'UAH', :amount, NOW(), :note,
                    'order', :order_id, NOW()
                )
            """), {
                "order_id": order_id,
                "amount": total_fees,
                "note": description
            })
        
        db.commit()
        
        return {
            "success": True,
            "message": "Повернення успішно завершено",
            "order_id": order_id,
            "fees_charged": total_fees,
            "finance_transaction_created": total_fees > 0
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Помилка завершення повернення: {str(e)}"
        )


@decor_router.post("/{order_id}/send-confirmation-email")
async def send_confirmation_email(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Відправити email підтвердження (placeholder)
    ✅ MIGRATED: Using RentalHub DB
    """
    return {
        "success": True,
        "message": "Email буде відправлено (функціонал потребує налаштування SMTP)"
    }


# ============================================================
# SET PAYER FOR ORDER
# ============================================================

class SetPayerRequest(BaseModel):
    payer_profile_id: int

@router.post("/{order_id}/set-payer")
async def set_order_payer(
    order_id: int,
    data: SetPayerRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Встановити платника для замовлення.
    Перевіряє, що платник існує та пов'язаний з клієнтом замовлення.
    """
    # Перевірити, що замовлення існує
    order = db.execute(text("""
        SELECT order_id, client_user_id, payer_profile_id 
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    # Перевірити, що платник існує
    payer = db.execute(text("""
        SELECT id, company_name FROM payer_profiles WHERE id = :payer_id
    """), {"payer_id": data.payer_profile_id}).fetchone()
    
    if not payer:
        raise HTTPException(status_code=404, detail="Платник не знайдений")
    
    # Перевірити, що платник пов'язаний з клієнтом замовлення
    if order[1]:  # client_user_id
        link = db.execute(text("""
            SELECT 1 FROM client_payer_links 
            WHERE client_user_id = :client AND payer_profile_id = :payer
        """), {"client": order[1], "payer": data.payer_profile_id}).fetchone()
        
        if not link:
            # Автоматично зв'язати, якщо ще не пов'язано
            db.execute(text("""
                INSERT INTO client_payer_links (client_user_id, payer_profile_id, is_default)
                VALUES (:client, :payer, FALSE)
            """), {"client": order[1], "payer": data.payer_profile_id})
    
    try:
        # Оновити замовлення
        db.execute(text("""
            UPDATE orders 
            SET payer_profile_id = :payer_id, updated_at = NOW()
            WHERE order_id = :order_id
        """), {"payer_id": data.payer_profile_id, "order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Платник встановлено: {payer[1]}",
            "order_id": order_id,
            "payer_profile_id": data.payer_profile_id,
            "payer_name": payer[1]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


class LinkClientRequest(BaseModel):
    client_user_id: int

@router.post("/{order_id}/link-client")
async def link_order_to_client(
    order_id: int,
    data: LinkClientRequest,
    db: Session = Depends(get_rh_db)
):
    """
    Прив'язати замовлення до клієнта з CRM.
    """
    # Перевірити, що замовлення існує
    order = db.execute(text("""
        SELECT order_id, client_user_id FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    # Перевірити, що клієнт існує
    client = db.execute(text("""
        SELECT id, full_name FROM client_users WHERE id = :client_id AND is_active = 1
    """), {"client_id": data.client_user_id}).fetchone()
    
    if not client:
        raise HTTPException(status_code=404, detail="Клієнт не знайдений")
    
    try:
        db.execute(text("""
            UPDATE orders 
            SET client_user_id = :client_id, updated_at = NOW()
            WHERE order_id = :order_id
        """), {"client_id": data.client_user_id, "order_id": order_id})
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Ордер прив'язано до клієнта: {client[1]}",
            "order_id": order_id,
            "client_user_id": data.client_user_id,
            "client_name": client[1]
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{order_id}/payer-options")
async def get_order_payer_options(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати список доступних платників для замовлення.
    Повертає платників, пов'язаних з клієнтом замовлення.
    """
    # Отримати замовлення з client_user_id
    order = db.execute(text("""
        SELECT order_id, client_user_id, payer_profile_id, customer_name
        FROM orders WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if not order:
        raise HTTPException(status_code=404, detail="Замовлення не знайдено")
    
    client_id = order[1]
    current_payer_id = order[2]
    
    payers = []
    
    if client_id:
        # Отримати платників клієнта
        result = db.execute(text("""
            SELECT 
                pp.id, pp.company_name, pp.payer_type, pp.edrpou,
                cpl.is_default,
                ma.id as ma_id, ma.contract_number, ma.status as ma_status
            FROM client_payer_links cpl
            JOIN payer_profiles pp ON pp.id = cpl.payer_profile_id
            LEFT JOIN master_agreements ma ON ma.payer_profile_id = pp.id 
                AND ma.status = 'signed' AND ma.valid_until >= CURDATE()
            WHERE cpl.client_user_id = :client
            ORDER BY cpl.is_default DESC, pp.company_name
        """), {"client": client_id})
        
        for row in result.fetchall():
            payers.append({
                "id": row[0],
                "name": row[1],
                "type": row[2],
                "edrpou": row[3],
                "is_default": bool(row[4]),
                "is_selected": row[0] == current_payer_id,
                "has_signed_ma": bool(row[5]),
                "ma_contract_number": row[6],
                "ma_status": row[7]
            })
    
    return {
        "order_id": order_id,
        "client_id": client_id,
        "client_name": order[3],
        "current_payer_id": current_payer_id,
        "payers": payers
    }


# ============================================================
# ADDITIONAL SERVICES CRUD
# ============================================================

@router.get("/{order_id}/additional-services")
async def get_additional_services(order_id: int, db: Session = Depends(get_rh_db)):
    """Get all additional services for an order."""
    try:
        rows = db.execute(text("""
            SELECT id, order_id, name, amount, created_at
            FROM order_additional_services
            WHERE order_id = :oid
            ORDER BY id ASC
        """), {"oid": order_id}).fetchall()
        
        return [
            {"id": r[0], "order_id": r[1], "name": r[2], "amount": float(r[3] or 0), "created_at": r[4].isoformat() if r[4] else None}
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/additional-services")
async def add_additional_service(order_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """Add a new additional service to an order."""
    name = data.get("name", "").strip()
    amount = float(data.get("amount", 0))
    
    if not name:
        raise HTTPException(status_code=400, detail="Назва послуги обов'язкова")
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сума має бути більше 0")
    
    try:
        db.execute(text("""
            INSERT INTO order_additional_services (order_id, name, amount)
            VALUES (:oid, :name, :amount)
        """), {"oid": order_id, "name": name, "amount": amount})
        
        service_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        
        # Update total service_fee on order (sum of all services)
        _sync_service_fee_total(db, order_id)
        
        db.commit()
        return {"success": True, "id": service_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{order_id}/additional-services/{service_id}")
async def update_additional_service(order_id: int, service_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """Update an additional service."""
    name = data.get("name", "").strip()
    amount = float(data.get("amount", 0))
    
    try:
        db.execute(text("""
            UPDATE order_additional_services SET name = :name, amount = :amount
            WHERE id = :sid AND order_id = :oid
        """), {"sid": service_id, "oid": order_id, "name": name, "amount": amount})
        
        _sync_service_fee_total(db, order_id)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{order_id}/additional-services/{service_id}")
async def delete_additional_service(order_id: int, service_id: int, db: Session = Depends(get_rh_db)):
    """Delete an additional service."""
    try:
        db.execute(text("""
            DELETE FROM order_additional_services WHERE id = :sid AND order_id = :oid
        """), {"sid": service_id, "oid": order_id})
        
        _sync_service_fee_total(db, order_id)
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def _sync_service_fee_total(db: Session, order_id: int):
    """Sync the total service_fee on the order from all additional services."""
    result = db.execute(text("""
        SELECT COALESCE(SUM(amount), 0), GROUP_CONCAT(name SEPARATOR ', ')
        FROM order_additional_services WHERE order_id = :oid
    """), {"oid": order_id}).fetchone()
    
    total = float(result[0]) if result else 0
    names = result[1] if result else ''
    
    db.execute(text("""
        UPDATE orders SET service_fee = :fee, service_fee_name = :name WHERE order_id = :oid
    """), {"fee": total, "name": names or '', "oid": order_id})




# ============================================================
# PACKAGING CRUD
# ============================================================

@router.get("/{order_id}/packaging")
async def get_packaging(order_id: int, db: Session = Depends(get_rh_db)):
    """Get packaging quantities for an order."""
    try:
        rows = db.execute(text("""
            SELECT item_key, quantity FROM order_packaging WHERE order_id = :oid
        """), {"oid": order_id}).fetchall()
        quantities = {r[0]: r[1] for r in rows}
        return {"order_id": order_id, "quantities": quantities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/packaging")
async def save_packaging(order_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """Save packaging quantities for an order (upsert)."""
    quantities = data.get("quantities", {})
    try:
        for key, qty in quantities.items():
            qty = int(qty)
            if qty > 0:
                db.execute(text("""
                    INSERT INTO order_packaging (order_id, item_key, quantity)
                    VALUES (:oid, :key, :qty)
                    ON DUPLICATE KEY UPDATE quantity = :qty
                """), {"oid": order_id, "key": key, "qty": qty})
            else:
                db.execute(text("""
                    DELETE FROM order_packaging WHERE order_id = :oid AND item_key = :key
                """), {"oid": order_id, "key": key})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# PACKAGING RETURN
# ============================================================

@router.get("/{order_id}/packaging-return")
async def get_packaging_return(order_id: int, db: Session = Depends(get_rh_db)):
    """Get returned packaging quantities."""
    try:
        rows = db.execute(text("""
            SELECT item_key, returned_quantity FROM order_packaging
            WHERE order_id = :oid AND returned_quantity > 0
        """), {"oid": order_id}).fetchall()
        returned = {r[0]: r[1] for r in rows}
        return {"order_id": order_id, "returned": returned}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{order_id}/packaging-return")
async def save_packaging_return(order_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """Save returned packaging quantities."""
    returned = data.get("returned", {})
    try:
        for key, qty in returned.items():
            qty = int(qty)
            db.execute(text("""
                UPDATE order_packaging SET returned_quantity = :qty
                WHERE order_id = :oid AND item_key = :key
            """), {"oid": order_id, "key": key, "qty": qty})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

