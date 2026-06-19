"""
Адмін-керування фінансами замовлень.

ОДНЕ ДЖЕРЕЛО ПРАВДИ:
- orders.discount_amount, orders.discount_percent, orders.service_fee — суми
- fin_transactions — журнал оплат, повернень, нарахувань (єдиний)
- v_order_finance — view який обʼєднує все для читання

Усі редагування через цей роутер пишуться в правильні таблиці.
fin_payments залишається як legacy mirror — оновлюється тригерами або синхронізується окремо.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, date
import logging

from database_rentalhub import get_rh_db
from utils.user_tracking_helper import get_current_user_dependency

router = APIRouter(prefix="/api/admin/finance", tags=["admin-finance"])
logger = logging.getLogger(__name__)

# Dependency для авторизованого менеджера (any logged-in user — обмежимо по ролі пізніше)
def require_manager(user: dict = Depends(get_current_user_dependency)):
    return user


# ============================================================================
# СПИСОК ФІНАНСІВ ЗАМОВЛЕНЬ — ЧИТАННЯ З VIEW
# ============================================================================
@router.get("/orders")
async def list_orders_finance(
    has_debt: Optional[bool] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_rh_db),
    _user=Depends(require_manager),
):
    """Список фінансових показників замовлень — все з єдиного джерела v_order_finance."""
    sql = "SELECT * FROM v_order_finance WHERE 1=1"
    params = {}
    if has_debt is True:
        sql += " AND debt > 0"
    elif has_debt is False:
        sql += " AND debt = 0"
    if status:
        sql += " AND status = :st"
        params["st"] = status
    if search:
        sql += " AND (order_number LIKE :s OR customer_name LIKE :s)"
        params["s"] = f"%{search}%"
    sql += " ORDER BY debt DESC, order_id DESC LIMIT :lim"
    params["lim"] = max(1, min(limit, 500))

    rows = db.execute(text(sql), params).fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/orders/{order_id}")
async def get_order_finance(
    order_id: int,
    db: Session = Depends(get_rh_db),
    _user=Depends(require_manager),
):
    """Деталі по одному замовленню + всі транзакції."""
    fin = db.execute(text("SELECT * FROM v_order_finance WHERE order_id = :oid"),
                     {"oid": order_id}).fetchone()
    if not fin:
        raise HTTPException(404, "Order not found")

    txs = db.execute(text("""
        SELECT id, tx_type, amount, currency, occurred_at, note,
               status, voided_at, accepted_by_name, created_at
        FROM fin_transactions
        WHERE entity_type = 'order' AND entity_id = :oid
        ORDER BY occurred_at DESC
    """), {"oid": order_id}).fetchall()

    return {
        "summary": dict(fin._mapping),
        "transactions": [dict(t._mapping) for t in txs],
    }


# ============================================================================
# CRUD ТРАНЗАКЦІЙ
# ============================================================================
class TxCreate(BaseModel):
    tx_type: str  # rent_payment | deposit_payment | additional_payment | damage_payment | etc
    amount: float
    occurred_at: Optional[datetime] = None
    note: Optional[str] = ""

ALLOWED_TX_TYPES = {
    'rent_payment', 'deposit_payment', 'deposit_refund',
    'additional_payment', 'damage_payment', 'damage_deduction',
    'late_payment', 'collection', 'charge',
}


@router.post("/orders/{order_id}/transactions")
async def create_transaction(
    order_id: int, payload: TxCreate,
    db: Session = Depends(get_rh_db),
    user=Depends(require_manager),
):
    """Додати транзакцію в fin_transactions (єдине джерело правди)."""
    if payload.tx_type not in ALLOWED_TX_TYPES:
        raise HTTPException(400, f"Invalid tx_type. Allowed: {sorted(ALLOWED_TX_TYPES)}")
    if payload.amount <= 0:
        raise HTTPException(400, "Amount must be positive")

    occ = payload.occurred_at or datetime.now()
    # Записуємо в fin_payments — fin_transactions буде створено тригером
    # (єдиний напрямок sync: fp → tx; запобігає дублікатам)
    payment_type_map = {
        'rent_payment': 'rent', 'deposit_payment': 'deposit',
        'deposit_refund': 'deposit_refund', 'additional_payment': 'additional',
        'damage_payment': 'damage', 'damage_deduction': 'loss',
        'late_payment': 'late', 'collection': 'rent', 'charge': 'damage',
    }
    p_type = payment_type_map.get(payload.tx_type, 'rent')
    ins = db.execute(text("""
        INSERT INTO fin_payments
          (payment_type, method, amount, currency, occurred_at, order_id,
           status, note, accepted_by_name, created_at)
        VALUES (:pt, 'cash', :amt, 'UAH', :occ, :oid, 'posted', :note, :acc, NOW())
    """), {
        "pt": p_type, "amt": payload.amount, "occ": occ,
        "note": payload.note or "", "oid": order_id,
        "acc": user.get("name", None) if isinstance(user, dict) else None or 'Manager',
    })
    db.commit()
    # Повертаємо tx_id з створеного fin_transactions (через тригер)
    tx = db.execute(text("""
        SELECT id FROM fin_transactions WHERE note LIKE :n ORDER BY id DESC LIMIT 1
    """), {"n": f"%[from fp #{ins.lastrowid}]%"}).fetchone()
    return {"id": tx[0] if tx else None, "fp_id": ins.lastrowid, "ok": True}


class TxUpdate(BaseModel):
    amount: Optional[float] = None
    occurred_at: Optional[datetime] = None
    note: Optional[str] = None


@router.patch("/transactions/{tx_id}")
async def update_transaction(
    tx_id: int, payload: TxUpdate,
    db: Session = Depends(get_rh_db),
    user=Depends(require_manager),
):
    """Редагувати транзакцію (виправити суму, дату, примітку)."""
    fields, params = [], {"tx_id": tx_id}
    if payload.amount is not None:
        if payload.amount <= 0:
            raise HTTPException(400, "Amount must be positive")
        fields.append("amount = :amount"); params["amount"] = payload.amount
    if payload.occurred_at is not None:
        fields.append("occurred_at = :occ"); params["occ"] = payload.occurred_at
    if payload.note is not None:
        fields.append("note = :note"); params["note"] = payload.note
    if not fields:
        return {"ok": True, "changed": False}

    db.execute(text(f"UPDATE fin_transactions SET {', '.join(fields)} WHERE id = :tx_id"), params)
    db.commit()
    return {"ok": True}


@router.delete("/transactions/{tx_id}")
async def void_transaction(
    tx_id: int,
    db: Session = Depends(get_rh_db),
    user=Depends(require_manager),
):
    """М'яке видалення — позначаємо voided, але не видаляємо з історії."""
    db.execute(text("""
        UPDATE fin_transactions
        SET voided_at = NOW(), status = 'voided',
            note = CONCAT(COALESCE(note,''), ' [voided by ', :u, ' @ ', DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i'), ']')
        WHERE id = :tx_id
    """), {"tx_id": tx_id, "u": user.get("name", None) if isinstance(user, dict) else None or 'Manager'})
    db.commit()
    return {"ok": True}


# ============================================================================
# РЕДАГУВАННЯ ЗНИЖКИ (єдиний механізм — orders.discount_amount)
# ============================================================================
class DiscountUpdate(BaseModel):
    discount_amount: Optional[float] = None
    discount_percent: Optional[float] = None
    reason: Optional[str] = ""


@router.put("/orders/{order_id}/discount")
async def set_order_discount(
    order_id: int, payload: DiscountUpdate,
    db: Session = Depends(get_rh_db),
    user=Depends(require_manager),
):
    """Встановити знижку (одна правда — orders.discount_amount)."""
    o = db.execute(text("SELECT total_price, discount_amount, discount_percent FROM orders WHERE order_id = :oid"),
                   {"oid": order_id}).fetchone()
    if not o:
        raise HTTPException(404, "Order not found")

    old_amount, old_pct = float(o[1] or 0), float(o[2] or 0)
    new_amount = old_amount
    new_pct = old_pct

    # Якщо передано %, рахуємо amount автоматично
    if payload.discount_percent is not None:
        new_pct = payload.discount_percent
        new_amount = round(float(o[0] or 0) * new_pct / 100, 2)
    if payload.discount_amount is not None:
        new_amount = payload.discount_amount
        # Перерахунок % якщо є total
        if o[0] and float(o[0]) > 0:
            new_pct = round(new_amount / float(o[0]) * 100, 2)

    if new_amount < 0:
        raise HTTPException(400, "Discount cannot be negative")
    if new_amount > float(o[0] or 0):
        raise HTTPException(400, f"Discount ({new_amount}) cannot exceed total ({o[0]})")

    db.execute(text("""
        UPDATE orders
        SET discount_amount = :da, discount_percent = :dp,
            manager_comment = CONCAT(COALESCE(manager_comment, ''),
                CASE WHEN manager_comment IS NULL OR manager_comment='' THEN '' ELSE '\n' END,
                '[Discount] ', :oa, '→', :da, ' (',
                CASE WHEN :reason = '' THEN 'без коментаря' ELSE :reason END,
                ') by ', :u, ' @ ', DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i'))
        WHERE order_id = :oid
    """), {
        "da": new_amount, "dp": new_pct, "oa": old_amount,
        "reason": payload.reason or "",
        "u": user.get("name", None) if isinstance(user, dict) else None or 'Manager',
        "oid": order_id,
    })
    db.commit()
    return {"ok": True, "discount_amount": new_amount, "discount_percent": new_pct}


# ============================================================================
# СПИСАННЯ БОРГУ (як я робив для 7535/7741/7751)
# ============================================================================
class WriteoffPayload(BaseModel):
    amount: float
    reason: str


@router.post("/orders/{order_id}/writeoff")
async def writeoff_debt(
    order_id: int, payload: WriteoffPayload,
    db: Session = Depends(get_rh_db),
    user=Depends(require_manager),
):
    """Списати борг — збільшити discount_amount на amount + комент в manager_comment."""
    if payload.amount <= 0:
        raise HTTPException(400, "Amount must be positive")

    o = db.execute(text("SELECT discount_amount, total_price FROM orders WHERE order_id = :oid"),
                   {"oid": order_id}).fetchone()
    if not o:
        raise HTTPException(404, "Order not found")

    new_discount = float(o[0] or 0) + payload.amount
    if new_discount > float(o[1] or 0):
        raise HTTPException(400, f"Total discount ({new_discount}) would exceed order total ({o[1]})")

    db.execute(text("""
        UPDATE orders
        SET discount_amount = :nd,
            manager_comment = CONCAT(COALESCE(manager_comment, ''),
                CASE WHEN manager_comment IS NULL OR manager_comment='' THEN '' ELSE '\n' END,
                '[Writeoff ₴', :amt, '] ', :reason,
                ' by ', :u, ' @ ', DATE_FORMAT(NOW(), '%Y-%m-%d %H:%i'))
        WHERE order_id = :oid
    """), {
        "nd": new_discount, "amt": payload.amount, "reason": payload.reason,
        "u": user.get("name", None) if isinstance(user, dict) else None or 'Manager', "oid": order_id,
    })

    # Запис у history
    try:
        db.execute(text("""
            INSERT INTO order_lifecycle (order_id, stage, notes, created_by_name, created_at)
            VALUES (:oid, 'debt_writeoff', :note, :u, NOW())
        """), {"oid": order_id, "note": f"Списано ₴{payload.amount}: {payload.reason}",
               "u": user.get("name", None) if isinstance(user, dict) else None or 'Manager'})
    except Exception:
        pass

    db.commit()
    return {"ok": True, "new_discount_amount": new_discount}
