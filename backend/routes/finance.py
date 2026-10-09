"""
Finance API - Rental Finance Engine
Buckets, Ledger, Payments, Deposits, Expenses, Payroll
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel
from decimal import Decimal
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/finance", tags=["finance"])

# Додатковий роутер для сумісності з ManagerDashboard
manager_router = APIRouter(prefix="/api/manager/finance", tags=["finance-manager"])


# ============================================================
# PYDANTIC MODELS
# ============================================================

class PaymentCreate(BaseModel):
    payment_type: str  # rent | additional | deposit | damage | refund
    method: str  # cash | card | iban | online | p2p | bank
    amount: float
    order_id: Optional[int] = None
    damage_case_id: Optional[int] = None
    payer_name: Optional[str] = None
    payer_contact: Optional[str] = None
    occurred_at: Optional[str] = None
    note: Optional[str] = None
    description: Optional[str] = None  # Назва донарахування (для additional)
    accepted_by_id: Optional[int] = None  # ID користувача який прийняв
    accepted_by_name: Optional[str] = None  # Ім'я користувача
    annex_id: Optional[int] = None  # P1: Link to order_annexes for legal documents

class ExpenseCreate(BaseModel):
    expense_type: str = "expense"  # expense | investment
    category_code: str
    amount: float
    method: str  # cash | card | iban
    vendor_id: Optional[int] = None
    order_id: Optional[int] = None
    employee_id: Optional[int] = None
    occurred_at: Optional[str] = None
    note: Optional[str] = None
    receipt_file_key: Optional[str] = None

class DepositCreate(BaseModel):
    order_id: Optional[int] = None
    client_user_id: Optional[int] = None
    expected_amount: float
    actual_amount: float
    currency: str = "UAH"
    exchange_rate: Optional[float] = None
    method: str = "cash"
    note: Optional[str] = None
    accepted_by_id: Optional[int] = None
    accepted_by_name: Optional[str] = None

class VendorCreate(BaseModel):
    name: str
    vendor_type: str = "service"  # service | cleaning | repair | delivery
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    iban: Optional[str] = None
    note: Optional[str] = None

class EmployeeCreate(BaseModel):
    name: str
    role: str  # manager | courier | cleaner | assistant
    phone: Optional[str] = None
    email: Optional[str] = None
    base_salary: float = 0
    hire_date: Optional[str] = None
    note: Optional[str] = None

class PayrollCreate(BaseModel):
    employee_id: int
    period_start: str
    period_end: str
    base_amount: float
    bonus: float = 0
    deduction: float = 0
    method: str = "cash"
    note: Optional[str] = None


# ============================================================
# HELPER: LEDGER POSTING
# ============================================================

def get_account_id(db: Session, code: str, retry: int = 3) -> int:
    """Get account ID by code with retry for connection issues"""
    for attempt in range(retry):
        try:
            result = db.execute(text("SELECT id FROM fin_accounts WHERE code = :code"), {"code": code})
            row = result.fetchone()
            if not row:
                raise ValueError(f"Account not found: {code}")
            return row[0]
        except Exception as e:
            if attempt < retry - 1 and "Lost connection" in str(e):
                import time
                time.sleep(0.5)
                continue
            raise

def post_transaction(
    db: Session,
    tx_type: str,
    amount: float,
    debit_account: str,
    credit_account: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    category_id: Optional[int] = None,
    order_id: Optional[int] = None,
    damage_case_id: Optional[int] = None,
    vendor_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    note: Optional[str] = None,
    occurred_at: Optional[datetime] = None
) -> int:
    """Create a ledger transaction with double-entry bookkeeping."""
    if occurred_at is None:
        occurred_at = datetime.now()
    
    db.execute(text("""
        INSERT INTO fin_transactions (tx_type, amount, occurred_at, entity_type, entity_id, category_id, note)
        VALUES (:tx_type, :amount, :occurred_at, :entity_type, :entity_id, :category_id, :note)
    """), {
        "tx_type": tx_type, "amount": amount, "occurred_at": occurred_at,
        "entity_type": entity_type, "entity_id": entity_id, "category_id": category_id, "note": note
    })
    
    result = db.execute(text("SELECT LAST_INSERT_ID()"))
    tx_id = result.fetchone()[0]
    
    debit_acc_id = get_account_id(db, debit_account)
    credit_acc_id = get_account_id(db, credit_account)
    
    # Debit entry
    db.execute(text("""
        INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id, damage_case_id, vendor_id, employee_id)
        VALUES (:tx_id, :account_id, 'D', :amount, :order_id, :damage_case_id, :vendor_id, :employee_id)
    """), {"tx_id": tx_id, "account_id": debit_acc_id, "amount": amount,
           "order_id": order_id, "damage_case_id": damage_case_id, "vendor_id": vendor_id, "employee_id": employee_id})
    
    # Credit entry
    db.execute(text("""
        INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id, damage_case_id, vendor_id, employee_id)
        VALUES (:tx_id, :account_id, 'C', :amount, :order_id, :damage_case_id, :vendor_id, :employee_id)
    """), {"tx_id": tx_id, "account_id": credit_acc_id, "amount": amount,
           "order_id": order_id, "damage_case_id": damage_case_id, "vendor_id": vendor_id, "employee_id": employee_id})
    
    return tx_id


# ============================================================
# ACCOUNTS & CATEGORIES
# ============================================================

@router.get("/accounts")
async def list_accounts(db: Session = Depends(get_rh_db)):
    """List all financial accounts/buckets with balances"""
    result = db.execute(text("""
        SELECT a.id, a.code, a.name, a.kind, a.currency, a.is_active,
            COALESCE((SELECT SUM(CASE WHEN direction = 'D' THEN amount ELSE -amount END) 
                      FROM fin_ledger_entries WHERE account_id = a.id), 0) as balance
        FROM fin_accounts a WHERE a.is_active = 1
        ORDER BY CASE a.kind WHEN 'asset' THEN 1 WHEN 'income' THEN 2 WHEN 'expense' THEN 3 ELSE 4 END, a.code
    """))
    return [{"id": r[0], "code": r[1], "name": r[2], "kind": r[3], "currency": r[4], 
             "is_active": bool(r[5]), "balance": float(r[6] or 0)} for r in result]

@router.get("/categories")
async def list_categories(type: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """List expense/income categories with hierarchy"""
    query = "SELECT id, type, code, name, is_active, parent_id FROM fin_categories WHERE is_active = 1"
    params = {}
    if type:
        query += " AND type = :type"
        params["type"] = type
    query += " ORDER BY COALESCE(parent_id, id), parent_id IS NOT NULL, name"
    result = db.execute(text(query), params)
    
    all_cats = []
    for r in result:
        all_cats.append({
            "id": r[0], "type": r[1], "code": r[2], "name": r[3],
            "is_active": bool(r[4]), "parent_id": r[5]
        })
    
    # Build hierarchy: parents with children
    parents = [c for c in all_cats if c["parent_id"] is None]
    children_map = {}
    for c in all_cats:
        if c["parent_id"]:
            children_map.setdefault(c["parent_id"], []).append(c)
    
    for p in parents:
        p["children"] = children_map.get(p["id"], [])
    
    return {"categories": all_cats, "tree": parents}


# ============================================================
# DASHBOARD / OVERVIEW
# ============================================================

@router.get("/payouts-stats")
async def get_payouts_stats(db: Session = Depends(get_rh_db)):
    """Payout statistics for Finance Hub:
    - Каса з ренти (з врахуванням витрат)
    - Каса зі шкоди (з врахуванням витрат)
    - Безготівка з ренти (з врахуванням витрат)
    - Безготівка зі шкоди (з врахуванням витрат)
    """
    try:
        # === ГОТІВКА ===
        # Cash income from rent
        rent_cash_income = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'rent' AND method = 'cash' AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # Cash income from damage
        damage_cash_income = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'damage' AND method = 'cash' AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # Cash expenses from rent budget
        rent_cash_expenses = db.execute(text("""
            SELECT COALESCE(SUM(e.amount), 0) FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE e.method = 'cash' AND (c.code = 'RENT_EXPENSE' OR c.code = 'RENT_CASH_EXPENSE')
        """)).fetchone()[0]
        
        # Cash expenses from damage budget
        damage_cash_expenses = db.execute(text("""
            SELECT COALESCE(SUM(e.amount), 0) FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE e.method = 'cash' AND c.code = 'DAMAGE_EXPENSE'
        """)).fetchone()[0]
        
        # Cash deposits (внесення готівки)
        rent_cash_deposits = db.execute(text("""
            SELECT COALESCE(SUM(e.amount), 0) FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE c.code = 'RENT_CASH_DEPOSIT'
        """)).fetchone()[0]
        
        damage_cash_deposits = db.execute(text("""
            SELECT COALESCE(SUM(e.amount), 0) FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE c.code = 'DAMAGE_CASH_DEPOSIT'
        """)).fetchone()[0]
        
        # === БЕЗГОТІВКА ===
        # Bank income from rent
        rent_bank_income = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'rent' AND method IN ('card', 'bank') AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # Bank income from damage
        damage_bank_income = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'damage' AND method IN ('card', 'bank') AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # Bank expenses from rent budget
        rent_bank_expenses = db.execute(text("""
            SELECT COALESCE(SUM(e.amount), 0) FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE e.method = 'bank' AND (c.code = 'RENT_BANK_EXPENSE')
        """)).fetchone()[0]
        
        # Bank expenses from damage budget
        damage_bank_expenses = db.execute(text("""
            SELECT COALESCE(SUM(e.amount), 0) FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE e.method = 'bank' AND c.code = 'DAMAGE_BANK_EXPENSE'
        """)).fetchone()[0]
        
        # === DUE AMOUNTS ===
        due_damage = db.execute(text("""
            SELECT COALESCE(SUM(fee), 0) - COALESCE(
                (SELECT SUM(amount) FROM fin_payments WHERE payment_type = 'damage'), 0
            ) FROM product_damage_history WHERE fee > 0
        """)).fetchone()[0]
        
        # === CALCULATE BALANCES ===
        # Готівка = доходи - витрати + внесення
        rent_cash_balance = float(rent_cash_income or 0) - float(rent_cash_expenses or 0) + float(rent_cash_deposits or 0)
        damage_cash_balance = float(damage_cash_income or 0) - float(damage_cash_expenses or 0) + float(damage_cash_deposits or 0)
        
        # Безготівка = доходи - витрати
        rent_bank_balance = float(rent_bank_income or 0) - float(rent_bank_expenses or 0)
        damage_bank_balance = float(damage_bank_income or 0) - float(damage_bank_expenses or 0)
        
        # Total rent revenue
        rent_revenue = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments WHERE payment_type = 'rent'
        """)).fetchone()[0]
        
        return {
            # Готівка балансі (з врахуванням витрат)
            "rent_cash_balance": rent_cash_balance,
            "damage_cash_balance": damage_cash_balance,
            "total_cash_balance": rent_cash_balance + damage_cash_balance,
            
            # Безготівка балансі (з врахуванням витрат)
            "rent_bank_balance": rent_bank_balance,
            "damage_bank_balance": damage_bank_balance,
            "bank_balance": rent_bank_balance + damage_bank_balance,
            
            # Витрати окремо
            "rent_cash_expenses": float(rent_cash_expenses or 0),
            "damage_cash_expenses": float(damage_cash_expenses or 0),
            "rent_bank_expenses": float(rent_bank_expenses or 0),
            "damage_bank_expenses": float(damage_bank_expenses or 0),
            
            # Внесення
            "rent_cash_deposits": float(rent_cash_deposits or 0),
            "damage_cash_deposits": float(damage_cash_deposits or 0),
            
            # Due
            "total_due": float(due_damage or 0) if due_damage and due_damage > 0 else 0,
            "due_damage": float(due_damage or 0) if due_damage and due_damage > 0 else 0,
            
            # Legacy fields for compatibility
            "rent_expenses": float(rent_cash_expenses or 0),
            "damage_expenses": float(damage_cash_expenses or 0),
            "rent_bank": float(rent_bank_income or 0),
            "damage_bank": float(damage_bank_income or 0),
            "total_rent_revenue": float(rent_revenue or 0),
            "cash_balance": rent_cash_balance + damage_cash_balance,
            "total_active_balance": rent_cash_balance + damage_cash_balance + rent_bank_balance + damage_bank_balance
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_dashboard(period: str = "month", db: Session = Depends(get_rh_db)):
    """Financial dashboard overview."""
    
    date_filter = ""
    if period == "day": date_filter = "AND t.occurred_at >= CURDATE()"
    elif period == "week": date_filter = "AND t.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
    elif period == "month": date_filter = "AND t.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)"
    elif period == "year": date_filter = "AND t.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 365 DAY)"
    
    # Rent revenue
    rent = db.execute(text(f"""
        SELECT COALESCE(SUM(e.amount), 0) FROM fin_ledger_entries e
        JOIN fin_accounts a ON a.id = e.account_id JOIN fin_transactions t ON t.id = e.tx_id
        WHERE a.code = 'RENT_REV' AND e.direction = 'C' AND t.status = 'posted' {date_filter}
    """)).fetchone()[0]
    
    # Damage compensation
    damage = db.execute(text(f"""
        SELECT COALESCE(SUM(e.amount), 0) FROM fin_ledger_entries e
        JOIN fin_accounts a ON a.id = e.account_id JOIN fin_transactions t ON t.id = e.tx_id
        WHERE a.code = 'DMG_COMP' AND e.direction = 'C' AND t.status = 'posted' {date_filter}
    """)).fetchone()[0]
    
    # Expenses
    expenses = db.execute(text(f"""
        SELECT COALESCE(SUM(e.amount), 0) FROM fin_ledger_entries e
        JOIN fin_accounts a ON a.id = e.account_id JOIN fin_transactions t ON t.id = e.tx_id
        WHERE a.kind = 'expense' AND e.direction = 'D' AND t.status = 'posted' {date_filter}
    """)).fetchone()[0]
    
    # Deposits
    dep = db.execute(text("""
        SELECT COALESCE(SUM(held_amount), 0), COALESCE(SUM(used_amount), 0), COALESCE(SUM(refunded_amount), 0)
        FROM fin_deposit_holds WHERE status IN ('holding', 'partially_used')
    """)).fetchone()
    
    # Cash balance
    cash = db.execute(text("""
        SELECT COALESCE(SUM(CASE WHEN direction = 'D' THEN amount ELSE -amount END), 0)
        FROM fin_ledger_entries e JOIN fin_accounts a ON a.id = e.account_id WHERE a.code IN ('CASH', 'BANK')
    """)).fetchone()[0]
    
    return {
        "period": period,
        "metrics": {
            "net_profit": float(rent or 0) + float(damage or 0) - float(expenses or 0),
            "rent_revenue": float(rent or 0),
            "damage_compensation": float(damage or 0),
            "operating_expenses": float(expenses or 0),
            "cash_balance": float(cash or 0),
        },
        "deposits": {
            "held": float(dep[0] or 0),
            "used": float(dep[1] or 0),
            "refunded": float(dep[2] or 0),
            "available_to_refund": float(dep[0] or 0) - float(dep[1] or 0) - float(dep[2] or 0)
        }
    }


# ============================================================
# PAYMENTS
# ============================================================

@router.get("/payments")
async def list_payments(payment_type: Optional[str] = None, order_id: Optional[int] = None,
                        limit: int = 50, offset: int = 0, db: Session = Depends(get_rh_db)):
    query = """SELECT id, payment_type, method, amount, currency, payer_name, occurred_at, 
               order_id, damage_case_id, status, note, accepted_by_id, accepted_by_name 
               FROM fin_payments WHERE 1=1"""
    params = {"limit": limit, "offset": offset}
    if payment_type: query += " AND payment_type = :payment_type"; params["payment_type"] = payment_type
    if order_id: query += " AND order_id = :order_id"; params["order_id"] = order_id
    query += " ORDER BY occurred_at DESC LIMIT :limit OFFSET :offset"
    result = db.execute(text(query), params)
    return {"payments": [{"id": r[0], "payment_type": r[1], "method": r[2], "amount": float(r[3]),
                          "currency": r[4], "payer_name": r[5], "occurred_at": r[6].isoformat() if r[6] else None,
                          "order_id": r[7], "damage_case_id": r[8], "status": r[9], "note": r[10],
                          "accepted_by_id": r[11], "accepted_by_name": r[12]} for r in result]}

@router.post("/payments")
async def create_payment(data: PaymentCreate):
    """Record a new payment with ledger entries using direct connection."""
    import pymysql
    from datetime import datetime
    import os
    
    # === P1: ANNEX VALIDATION (optional for rent mode) ===
    # IF deal_mode = "rent" AND payment_type = "rent" - try to use annex_id if available
    if data.payment_type == "rent" and data.order_id:
        conn_check = pymysql.connect(
            host=os.environ.get('RH_DB_HOST', 'farforre.mysql.tools'),
            port=int(os.environ.get('RH_DB_PORT', 3306)),
            user=os.environ.get('RH_DB_USERNAME', 'farforre_rentalhub'),
            password=os.environ.get('RH_DB_PASSWORD', '-nu+3Gp54L'),
            database=os.environ.get('RH_DB_DATABASE', 'farforre_rentalhub'),
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        try:
            cursor_check = conn_check.cursor()
            cursor_check.execute("""
                SELECT deal_mode, active_annex_id FROM orders WHERE order_id = %s
            """, (data.order_id,))
            order_row = cursor_check.fetchone()
            
            # Тільки для режиму rent з договором - спробуємо взяти annex_id
            if order_row and order_row.get('deal_mode') == 'rent':
                if not data.annex_id and order_row.get('active_annex_id'):
                    data.annex_id = order_row['active_annex_id']
                # НЕ блокуємо оплату якщо немає annex_id - це опціонально
        finally:
            conn_check.close()
    
    # Direct MySQL connection
    conn = pymysql.connect(
        host=os.environ.get('RH_DB_HOST', 'farforre.mysql.tools'),
        port=int(os.environ.get('RH_DB_PORT', 3306)),
        user=os.environ.get('RH_DB_USERNAME', 'farforre_rentalhub'),
        password=os.environ.get('RH_DB_PASSWORD', '-nu+3Gp54L'),
        database=os.environ.get('RH_DB_DATABASE', 'farforre_rentalhub'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    
    try:
        cursor = conn.cursor()
        occurred_at = datetime.fromisoformat(data.occurred_at) if data.occurred_at else datetime.now()
        
        mapping = {
            "rent": ("CASH" if data.method == "cash" else "BANK", "RENT_REV"),
            "additional": ("CASH" if data.method == "cash" else "BANK", "RENT_REV"),  # Донарахування → дохід
            "deposit": ("CASH" if data.method == "cash" else "BANK", "DEP_LIAB"),
            "damage": ("CASH" if data.method == "cash" else "BANK", "DMG_COMP"),
            "late": ("CASH" if data.method == "cash" else "BANK", "RENT_REV"),  # Прострочення → дохід
            "refund": ("DEP_LIAB", "CASH" if data.method == "cash" else "BANK"),
        }
        if data.payment_type not in mapping:
            raise HTTPException(status_code=400, detail=f"Invalid payment_type: {data.payment_type}")
        
        debit_acc, credit_acc = mapping[data.payment_type]
        
        # Get account IDs
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (debit_acc,))
        debit_acc_id = cursor.fetchone()['id']
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (credit_acc,))
        credit_acc_id = cursor.fetchone()['id']
        
        # Create transaction with user info
        cursor.execute("""
            INSERT INTO fin_transactions (tx_type, amount, occurred_at, entity_type, entity_id, note, accepted_by_id, accepted_by_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (f"{data.payment_type}_payment", data.amount, occurred_at, 
              "order" if data.order_id else None, data.order_id or data.damage_case_id, data.note,
              data.accepted_by_id, data.accepted_by_name))
        tx_id = cursor.lastrowid
        
        # Create ledger entries (double-entry)
        cursor.execute("""
            INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id)
            VALUES (%s, %s, 'D', %s, %s)
        """, (tx_id, debit_acc_id, data.amount, data.order_id))
        
        cursor.execute("""
            INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id)
            VALUES (%s, %s, 'C', %s, %s)
        """, (tx_id, credit_acc_id, data.amount, data.order_id))
        
        # Create payment record with user info, description, and annex_id
        cursor.execute("""
            INSERT INTO fin_payments (payment_type, method, amount, payer_name, occurred_at, order_id, damage_case_id, tx_id, note, accepted_by_id, accepted_by_name, description, annex_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data.payment_type, data.method, data.amount, data.payer_name, occurred_at,
              data.order_id, data.damage_case_id, tx_id, data.note, data.accepted_by_id, data.accepted_by_name, data.description, data.annex_id))
        payment_id = cursor.lastrowid
        
        conn.commit()
        return {"success": True, "payment_id": payment_id, "tx_id": tx_id, "annex_id": data.annex_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ============================================================
# EXPENSES
# ============================================================

@router.get("/expenses")
async def list_expenses(category_code: Optional[str] = None, expense_type: Optional[str] = None,
                        limit: int = 50, offset: int = 0, db: Session = Depends(get_rh_db)):
    query = """SELECT e.id, e.expense_type, c.code, c.name, e.amount, e.currency, e.method, e.occurred_at, e.note, e.order_id, e.employee_id, e.vendor_id, e.status
               FROM fin_expenses e JOIN fin_categories c ON c.id = e.category_id WHERE 1=1"""
    params = {"limit": limit, "offset": offset}
    if category_code: query += " AND c.code = :category_code"; params["category_code"] = category_code
    if expense_type: query += " AND e.expense_type = :expense_type"; params["expense_type"] = expense_type
    query += " ORDER BY e.occurred_at DESC LIMIT :limit OFFSET :offset"
    result = db.execute(text(query), params)
    return {"expenses": [{"id": r[0], "expense_type": r[1], "category_code": r[2], "category_name": r[3],
                          "amount": float(r[4]), "currency": r[5], "method": r[6],
                          "occurred_at": r[7].isoformat() if r[7] else None, "note": r[8],
                          "order_id": r[9], "employee_id": r[10], "vendor_id": r[11], "status": r[12]} for r in result]}

@router.post("/expenses")
async def create_expense(data: ExpenseCreate):
    """Record a new expense with ledger entries using direct connection."""
    import pymysql
    import os
    
    conn = pymysql.connect(
        host=os.environ.get('RH_DB_HOST', 'farforre.mysql.tools'),
        port=int(os.environ.get('RH_DB_PORT', 3306)),
        user=os.environ.get('RH_DB_USERNAME', 'farforre_rentalhub'),
        password=os.environ.get('RH_DB_PASSWORD', '-nu+3Gp54L'),
        database=os.environ.get('RH_DB_DATABASE', 'farforre_rentalhub'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    
    try:
        cursor = conn.cursor()
        occurred_at = datetime.fromisoformat(data.occurred_at) if data.occurred_at else datetime.now()
        
        # Find category
        cursor.execute("SELECT id, type FROM fin_categories WHERE code = %s", (data.category_code,))
        cat = cursor.fetchone()
        if not cat:
            raise HTTPException(status_code=400, detail=f"Category not found: {data.category_code}")
        
        debit_acc = "INV_ASSETS" if data.expense_type == "investment" else ("VENDORS" if data.vendor_id else "OPEX")
        credit_acc = "CASH" if data.method == "cash" else "BANK"
        
        # Get account IDs
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (debit_acc,))
        debit_acc_id = cursor.fetchone()['id']
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (credit_acc,))
        credit_acc_id = cursor.fetchone()['id']
        
        # Create transaction
        cursor.execute("""
            INSERT INTO fin_transactions (tx_type, amount, occurred_at, entity_type, entity_id, category_id, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            "expense" if data.expense_type == "expense" else "investment_purchase",
            data.amount, occurred_at,
            "order" if data.order_id else None, data.order_id,
            cat['id'], data.note
        ))
        tx_id = cursor.lastrowid
        
        # Ledger entries
        cursor.execute("""
            INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id, vendor_id, employee_id)
            VALUES (%s, %s, 'D', %s, %s, %s, %s)
        """, (tx_id, debit_acc_id, data.amount, data.order_id, data.vendor_id, data.employee_id))
        cursor.execute("""
            INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id, vendor_id, employee_id)
            VALUES (%s, %s, 'C', %s, %s, %s, %s)
        """, (tx_id, credit_acc_id, data.amount, data.order_id, data.vendor_id, data.employee_id))
        
        # Create expense record
        cursor.execute("""
            INSERT INTO fin_expenses (expense_type, category_id, amount, method, vendor_id, occurred_at, note, order_id, employee_id, receipt_file_key, tx_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'posted')
        """, (data.expense_type, cat['id'], data.amount, data.method, data.vendor_id,
              occurred_at, data.note, data.order_id, data.employee_id, data.receipt_file_key, tx_id))
        expense_id = cursor.lastrowid
        
        conn.commit()
        return {"success": True, "expense_id": expense_id, "tx_id": tx_id}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ============================================================
# SIMPLE EXPENSES (for Finance Hub quick actions)
# ============================================================

class SimpleExpenseCreate(BaseModel):
    amount: float
    description: str
    category: str  # "rent_cash", "damage_cash", "rent_bank", "damage_bank"
    operation_type: str = "expense"  # "expense" or "deposit" (внесення)
    created_by_id: Optional[int] = None
    created_by_name: Optional[str] = None

@router.post("/expenses/simple")
async def create_simple_expense(data: SimpleExpenseCreate, db: Session = Depends(get_rh_db)):
    """Simple expense/deposit creation for Finance Hub."""
    try:
        # Map category to codes
        category_map = {
            # Витрати готівка
            "rent_cash": ("RENT_CASH_EXPENSE", "Витрати готівка (оренда)", "cash"),
            "damage_cash": ("DAMAGE_EXPENSE", "Витрати готівка (шкода)", "cash"),
            # Витрати безготівка
            "rent_bank": ("RENT_BANK_EXPENSE", "Витрати безготівка (оренда)", "bank"),
            "damage_bank": ("DAMAGE_BANK_EXPENSE", "Витрати безготівка (шкода)", "bank"),
            # Внесення готівка
            "rent_cash_deposit": ("RENT_CASH_DEPOSIT", "Внесення готівка (оренда)", "cash"),
            "damage_cash_deposit": ("DAMAGE_CASH_DEPOSIT", "Внесення готівка (шкода)", "cash"),
        }
        
        # Determine actual category based on operation_type
        actual_category = data.category
        if data.operation_type == "deposit" and data.category in ["rent_cash", "damage_cash"]:
            actual_category = f"{data.category}_deposit"
        
        if actual_category not in category_map:
            raise HTTPException(status_code=400, detail=f"Invalid category: {actual_category}")
        
        category_code, category_name, method = category_map[actual_category]
        
        # Check if category exists, if not create it
        cat = db.execute(text("SELECT id FROM fin_categories WHERE code = :code"), {"code": category_code}).fetchone()
        if not cat:
            db.execute(text("""
                INSERT INTO fin_categories (code, name, type) 
                VALUES (:code, :name, :type)
            """), {
                "code": category_code, 
                "name": category_name,
                "type": "income" if data.operation_type == "deposit" else "expense"
            })
            db.commit()
            cat = db.execute(text("SELECT id FROM fin_categories WHERE code = :code"), {"code": category_code}).fetchone()
        
        category_id = cat[0]
        expense_type = "income" if data.operation_type == "deposit" else "expense"
        
        # Insert record
        db.execute(text("""
            INSERT INTO fin_expenses (expense_type, category_id, amount, method, occurred_at, note, status)
            VALUES (:expense_type, :category_id, :amount, :method, NOW(), :note, 'posted')
        """), {
            "expense_type": expense_type,
            "category_id": category_id,
            "amount": data.amount,
            "method": method,
            "note": f"{data.description} (by {data.created_by_name or 'system'})"
        })
        expense_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        
        db.commit()
        return {"success": True, "expense_id": expense_id, "operation_type": expense_type}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# COLLECTION (Інкасація - вилучення грошей з каси)
# ============================================================

class CollectionCreate(BaseModel):
    amount: float
    method: str = "cash"  # cash | bank
    note: Optional[str] = None
    collected_by: Optional[str] = None

@router.post("/collection")
async def create_collection(data: CollectionCreate):
    """Інкасація — вилучення грошей з каси (готівка або безготівка)."""
    import pymysql
    import os
    
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Сума має бути більше 0")
    
    conn = pymysql.connect(
        host=os.environ.get('RH_DB_HOST', 'farforre.mysql.tools'),
        port=int(os.environ.get('RH_DB_PORT', 3306)),
        user=os.environ.get('RH_DB_USERNAME', 'farforre_rentalhub'),
        password=os.environ.get('RH_DB_PASSWORD', '-nu+3Gp54L'),
        database=os.environ.get('RH_DB_DATABASE', 'farforre_rentalhub'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    
    try:
        cursor = conn.cursor()
        method_label = "готівка" if data.method == "cash" else "безготівка"
        
        # Ensure COLLECTION category exists
        cursor.execute("SELECT id FROM fin_categories WHERE code = 'COLLECTION'")
        cat = cursor.fetchone()
        if not cat:
            cursor.execute("""
                INSERT INTO fin_categories (code, name, type) 
                VALUES ('COLLECTION', 'Інкасація', 'expense')
            """)
            conn.commit()
            cursor.execute("SELECT id FROM fin_categories WHERE code = 'COLLECTION'")
            cat = cursor.fetchone()
        
        category_id = cat['id']
        
        # Credit account (source) = CASH or BANK
        credit_acc = "CASH" if data.method == "cash" else "BANK"
        # Debit account = owner withdrawal
        debit_acc = "OPEX"
        
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (debit_acc,))
        debit_acc_row = cursor.fetchone()
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (credit_acc,))
        credit_acc_row = cursor.fetchone()
        
        if not debit_acc_row or not credit_acc_row:
            raise HTTPException(status_code=500, detail="Accounts not configured")
        
        # Create transaction
        note_text = f"Інкасація ({method_label})"
        if data.note:
            note_text += f": {data.note}"
        if data.collected_by:
            note_text += f" (by {data.collected_by})"
        
        cursor.execute("""
            INSERT INTO fin_transactions (tx_type, amount, occurred_at, note)
            VALUES ('collection', %s, NOW(), %s)
        """, (data.amount, note_text))
        tx_id = cursor.lastrowid
        
        # Ledger entries
        cursor.execute("""
            INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount)
            VALUES (%s, %s, 'D', %s)
        """, (tx_id, debit_acc_row['id'], data.amount))
        cursor.execute("""
            INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount)
            VALUES (%s, %s, 'C', %s)
        """, (tx_id, credit_acc_row['id'], data.amount))
        
        # Create expense record
        cursor.execute("""
            INSERT INTO fin_expenses (expense_type, category_id, amount, method, occurred_at, note, status)
            VALUES ('collection', %s, %s, %s, NOW(), %s, 'posted')
        """, (category_id, data.amount, data.method, note_text))
        expense_id = cursor.lastrowid
        
        conn.commit()
        return {"success": True, "expense_id": expense_id, "tx_id": tx_id, "amount": data.amount, "method": data.method}
    except HTTPException:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@router.get("/collections")
async def list_collections(period: str = "month", db: Session = Depends(get_rh_db)):
    """Список інкасацій за період."""
    date_filter = ""
    if period == "day":
        date_filter = "AND e.occurred_at >= CURDATE()"
    elif period == "week":
        date_filter = "AND e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
    elif period == "month":
        date_filter = "AND MONTH(e.occurred_at) = MONTH(CURDATE()) AND YEAR(e.occurred_at) = YEAR(CURDATE())"
    
    rows = db.execute(text(f"""
        SELECT e.id, e.amount, e.method, e.occurred_at, e.note
        FROM fin_expenses e
        WHERE e.expense_type = 'collection' AND e.status = 'posted'
        {date_filter}
        ORDER BY e.occurred_at DESC
    """)).fetchall()
    
    items = []
    total_cash = 0
    total_bank = 0
    for r in rows:
        amt = float(r[1] or 0)
        method = r[2] or 'cash'
        if method == 'cash':
            total_cash += amt
        else:
            total_bank += amt
        items.append({
            "id": r[0], "amount": amt, "method": method,
            "date": r[3].isoformat() if r[3] else None, "note": r[4],
        })
    
    return {"items": items, "total_cash": total_cash, "total_bank": total_bank, "total": total_cash + total_bank, "count": len(items)}

@router.get("/expenses/all")
async def list_all_expenses(limit: int = 100, db: Session = Depends(get_rh_db)):
    """List all expenses for Finance Hub operations view."""
    try:
        result = db.execute(text("""
            SELECT e.id, e.expense_type, c.code as category, c.name as category_name,
                   e.amount, e.method, e.occurred_at, e.note, e.status
            FROM fin_expenses e 
            LEFT JOIN fin_categories c ON c.id = e.category_id
            ORDER BY e.occurred_at DESC
            LIMIT :limit
        """), {"limit": limit})
        
        expenses = []
        for r in result:
            expenses.append({
                "id": r[0],
                "expense_type": r[1],
                "category": r[2] or "OTHER",
                "category_name": r[3] or "Інше",
                "amount": float(r[4] or 0),
                "method": r[5],
                "created_at": r[6].isoformat() if r[6] else None,
                "description": r[7] or "",
                "status": r[8]
            })
        
        return {"expenses": expenses}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DEPOSITS
# ============================================================

@router.get("/deposit-hold")
async def get_deposit_for_order(order_id: int = Query(..., description="Order ID"), db: Session = Depends(get_rh_db)):
    """Get single deposit hold for a specific order - optimized endpoint for LeftRailFinance"""
    result = db.execute(text("""
        SELECT d.id, d.order_id, d.held_amount, d.used_amount, d.refunded_amount, d.status, 
               d.opened_at, d.closed_at, d.note, o.order_number, o.customer_name,
               d.actual_amount, d.currency, d.exchange_rate, d.expected_amount
        FROM fin_deposit_holds d 
        LEFT JOIN orders o ON o.order_id = d.order_id 
        WHERE d.order_id = :order_id
        LIMIT 1
    """), {"order_id": order_id})
    
    r = result.fetchone()
    if not r:
        return None  # No deposit for this order
    
    currency = r[12] or 'UAH'
    actual_amount = float(r[11]) if r[11] else float(r[2])
    
    return {
        "id": r[0], "order_id": r[1], 
        "held_amount": float(r[2]),
        "actual_amount": actual_amount,
        "currency": currency,
        "exchange_rate": float(r[13]) if r[13] else 1.0,
        "expected_amount": float(r[14]) if r[14] else 0,
        "used_amount": float(r[3]), "refunded_amount": float(r[4]),
        "available": float(r[2]) - float(r[3]) - float(r[4]),
        "status": r[5], "opened_at": r[6].isoformat() if r[6] else None,
        "closed_at": r[7].isoformat() if r[7] else None, "note": r[8],
        "order_number": r[9], "customer_name": r[10],
        "display_amount": f"{actual_amount:,.0f} {currency}" if currency != 'UAH' else f"₴{actual_amount:,.0f}"
    }


@router.get("/deposits")
async def list_deposits(status: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """List deposit holds with order info and currency"""
    query = """SELECT d.id, d.order_id, d.held_amount, d.used_amount, d.refunded_amount, d.status, 
               d.opened_at, d.closed_at, d.note, o.order_number, o.customer_name,
               d.actual_amount, d.currency, d.exchange_rate, d.expected_amount
               FROM fin_deposit_holds d LEFT JOIN orders o ON o.order_id = d.order_id WHERE 1=1"""
    params = {}
    if status: query += " AND d.status = :status"; params["status"] = status
    query += " ORDER BY d.opened_at DESC"
    result = db.execute(text(query), params)
    deposits = []
    for r in result:
        currency = r[12] or 'UAH'
        actual_amount = float(r[11]) if r[11] else float(r[2])
        deposits.append({
            "id": r[0], "order_id": r[1], 
            "held_amount": float(r[2]),  # UAH еквівалент
            "actual_amount": actual_amount,  # Фактична сума у валюті
            "currency": currency,
            "exchange_rate": float(r[13]) if r[13] else 1.0,
            "expected_amount": float(r[14]) if r[14] else 0,
            "used_amount": float(r[3]), "refunded_amount": float(r[4]),
            "available": float(r[2]) - float(r[3]) - float(r[4]),
            "status": r[5], "opened_at": r[6].isoformat() if r[6] else None,
            "closed_at": r[7].isoformat() if r[7] else None, "note": r[8],
            "order_number": r[9], "customer_name": r[10],
            "display_amount": f"{actual_amount:,.0f} {currency}" if currency != 'UAH' else f"₴{actual_amount:,.0f}"
        })
    return deposits

@router.post("/deposits/{deposit_id}/use")
async def use_deposit(deposit_id: int, amount: float, damage_case_id: Optional[int] = None,
                      note: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """Use deposit for damage compensation"""
    dep = db.execute(text("SELECT order_id, held_amount, used_amount, refunded_amount FROM fin_deposit_holds WHERE id = :id"), {"id": deposit_id}).fetchone()
    if not dep: raise HTTPException(status_code=404, detail="Deposit not found")
    
    available = float(dep[1]) - float(dep[2]) - float(dep[3])
    if amount > available: raise HTTPException(status_code=400, detail=f"Not enough deposit. Available: {available}")
    
    try:
        tx_id = post_transaction(db, "deposit_hold_used", amount, "DEP_LIAB", "DMG_COMP",
                                 "damage_case" if damage_case_id else "order", damage_case_id or dep[0],
                                 order_id=dep[0], damage_case_id=damage_case_id, note=note or "Утримання із застави")
        
        new_used = float(dep[2]) + amount
        new_status = "partially_used" if (float(dep[1]) - new_used - float(dep[3])) > 0 else "fully_used"
        db.execute(text("UPDATE fin_deposit_holds SET used_amount = :used, status = :status WHERE id = :id"),
                  {"used": new_used, "status": new_status, "id": deposit_id})
        
        db.execute(text("INSERT INTO fin_deposit_events (deposit_id, event_type, amount, occurred_at, damage_case_id, tx_id, note) VALUES (:deposit_id, 'used_for_damage', :amount, NOW(), :damage_case_id, :tx_id, :note)"),
                  {"deposit_id": deposit_id, "amount": amount, "damage_case_id": damage_case_id, "tx_id": tx_id, "note": note})
        
        db.commit()
        return {"success": True, "tx_id": tx_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/deposits/{deposit_id}/refund")
async def refund_deposit(deposit_id: int, amount: float, method: str = "cash",
                         note: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """Refund deposit to customer (works for both order-linked and client-only deposits)"""
    dep = db.execute(text("SELECT order_id, held_amount, used_amount, refunded_amount, client_user_id FROM fin_deposit_holds WHERE id = :id"), {"id": deposit_id}).fetchone()
    if not dep: raise HTTPException(status_code=404, detail="Deposit not found")
    
    available = float(dep[1]) - float(dep[2]) - float(dep[3])
    if amount > available: raise HTTPException(status_code=400, detail=f"Not enough to refund. Available: {available}")
    
    try:
        credit_acc = "CASH" if method == "cash" else "BANK"
        order_id = dep[0]
        client_user_id = dep[4]
        entity_type = "order" if order_id else ("client" if client_user_id else "deposit")
        entity_id = order_id or client_user_id or deposit_id
        tx_id = post_transaction(db, "deposit_refund", amount, "DEP_LIAB", credit_acc, entity_type, entity_id,
                                 order_id=order_id, note=note or "Повернення застави")
        
        new_refunded = float(dep[3]) + amount
        remaining = float(dep[1]) - float(dep[2]) - new_refunded
        new_status = "refunded" if remaining <= 0 else "partially_used"
        db.execute(text("UPDATE fin_deposit_holds SET refunded_amount = :refunded, status = :status, closed_at = CASE WHEN :remaining <= 0 THEN NOW() ELSE closed_at END WHERE id = :id"),
                  {"refunded": new_refunded, "status": new_status, "remaining": remaining, "id": deposit_id})
        
        db.execute(text("INSERT INTO fin_deposit_events (deposit_id, event_type, amount, occurred_at, tx_id, note) VALUES (:deposit_id, 'refunded', :amount, NOW(), :tx_id, :note)"),
                  {"deposit_id": deposit_id, "amount": amount, "tx_id": tx_id, "note": note})
        
        db.commit()
        return {"success": True, "tx_id": tx_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# LEDGER
# ============================================================

@router.get("/ledger")
async def list_transactions(tx_type: Optional[str] = None, account_code: Optional[str] = None,
                            date_from: Optional[str] = None, date_to: Optional[str] = None,
                            limit: int = 50, offset: int = 0, db: Session = Depends(get_rh_db)):
    """List ledger transactions"""
    query = """SELECT DISTINCT t.id, t.tx_type, t.amount, t.currency, t.occurred_at, t.entity_type, t.entity_id, t.note, t.status
               FROM fin_transactions t LEFT JOIN fin_ledger_entries e ON e.tx_id = t.id LEFT JOIN fin_accounts a ON a.id = e.account_id
               WHERE t.status = 'posted'"""
    params = {"limit": limit, "offset": offset}
    if tx_type: query += " AND t.tx_type = :tx_type"; params["tx_type"] = tx_type
    if account_code: query += " AND a.code = :account_code"; params["account_code"] = account_code
    if date_from: query += " AND t.occurred_at >= :date_from"; params["date_from"] = date_from
    if date_to: query += " AND t.occurred_at <= :date_to"; params["date_to"] = date_to
    query += " ORDER BY t.occurred_at DESC LIMIT :limit OFFSET :offset"
    
    result = db.execute(text(query), params)
    transactions = []
    for row in result:
        entries = db.execute(text("SELECT a.code, a.name, e.direction, e.amount FROM fin_ledger_entries e JOIN fin_accounts a ON a.id = e.account_id WHERE e.tx_id = :tx_id"), {"tx_id": row[0]})
        transactions.append({
            "id": row[0], "tx_type": row[1], "amount": float(row[2]), "currency": row[3],
            "occurred_at": row[4].isoformat() if row[4] else None, "entity_type": row[5],
            "entity_id": row[6], "note": row[7], "status": row[8],
            "entries": [{"account_code": e[0], "account_name": e[1], "direction": e[2], "amount": float(e[3])} for e in entries]
        })
    return {"transactions": transactions}


@router.post("/migrate-tables")
async def migrate_tables(db: Session = Depends(get_rh_db)):
    """Migrate tables to correct structure"""
    results = []
    
    try:
        # Rename old tables instead of dropping (to avoid FK issues)
        try:
            db.execute(text("RENAME TABLE hr_employees TO hr_employees_old_backup"))
        except:
            pass
        try:
            db.execute(text("RENAME TABLE hr_payroll TO hr_payroll_old_backup"))
        except:
            pass
        try:
            db.execute(text("RENAME TABLE fin_vendors TO fin_vendors_old_backup"))
        except:
            pass
        db.execute(text("""
            CREATE TABLE rh_employees (
                id INT AUTO_INCREMENT PRIMARY KEY,
                emp_name VARCHAR(200) NOT NULL,
                emp_role VARCHAR(50) DEFAULT 'other',
                emp_phone VARCHAR(50),
                emp_email VARCHAR(100),
                emp_salary DECIMAL(12,2) DEFAULT 0,
                emp_hire_date DATE,
                emp_note TEXT,
                emp_active BOOLEAN DEFAULT TRUE,
                emp_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        results.append("rh_employees: OK")
        
        # Recreate hr_payroll
        db.execute(text("""
            CREATE TABLE hr_payroll (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                base_amount DECIMAL(12,2) NOT NULL,
                bonus DECIMAL(12,2) DEFAULT 0,
                deduction DECIMAL(12,2) DEFAULT 0,
                total_amount DECIMAL(12,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                method VARCHAR(20) DEFAULT 'cash',
                paid_at TIMESTAMP NULL,
                tx_id INT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        results.append("hr_payroll: OK")
        
        # Drop and recreate fin_vendors
        db.execute(text("DROP TABLE IF EXISTS fin_vendors"))
        db.execute(text("""
            CREATE TABLE fin_vendors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                vendor_type VARCHAR(50) DEFAULT 'service',
                contact_name VARCHAR(100),
                phone VARCHAR(50),
                email VARCHAR(100),
                address TEXT,
                iban VARCHAR(50),
                balance DECIMAL(12,2) DEFAULT 0,
                note TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        results.append("fin_vendors: OK")
        
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        db.commit()
        return {"success": True, "results": results}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}



# ============================================================
# VENDORS
# ============================================================

@router.get("/vendors")
async def list_vendors(vendor_type: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """List all vendors"""
    try:
        # Ensure table has proper structure
        db.execute(text("DROP TABLE IF EXISTS fin_vendors_old"))
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS fin_vendors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                vendor_type VARCHAR(50) DEFAULT 'service',
                contact_name VARCHAR(100),
                phone VARCHAR(50),
                email VARCHAR(100),
                address TEXT,
                iban VARCHAR(50),
                balance DECIMAL(12,2) DEFAULT 0,
                note TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
    except Exception as e:
        print(f"Vendors table setup: {e}")
    
    try:
        result = db.execute(text("SELECT id, name, vendor_type, contact_name, phone, email, address, iban, balance, note, is_active, created_at FROM fin_vendors WHERE is_active = TRUE ORDER BY name"))
        vendors = [{"id": r[0], "name": r[1], "vendor_type": r[2] or 'service', "contact_name": r[3],
                    "phone": r[4], "email": r[5], "address": r[6], "iban": r[7],
                    "balance": float(r[8] or 0), "note": r[9], "is_active": r[10],
                    "created_at": r[11].isoformat() if r[11] else None} for r in result]
    except Exception as e:
        # Table might exist with different structure - try simpler query
        try:
            result = db.execute(text("SELECT id, name FROM fin_vendors"))
            vendors = [{"id": r[0], "name": r[1], "vendor_type": 'service', "contact_name": None,
                        "phone": None, "email": None, "address": None, "iban": None,
                        "balance": 0, "note": None, "is_active": True, "created_at": None} for r in result]
        except:
            vendors = []
    return {"vendors": vendors}

@router.post("/vendors")
async def create_vendor(data: VendorCreate, db: Session = Depends(get_rh_db)):
    """Create a new vendor"""
    try:
        # Ensure table has correct structure
        db.execute(text("DROP TABLE IF EXISTS fin_vendors"))
        db.execute(text("""
            CREATE TABLE fin_vendors (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                vendor_type VARCHAR(50) DEFAULT 'service',
                contact_name VARCHAR(100),
                phone VARCHAR(50),
                email VARCHAR(100),
                address TEXT,
                iban VARCHAR(50),
                balance DECIMAL(12,2) DEFAULT 0,
                note TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
    except Exception as e:
        print(f"Create vendors table: {e}")
    
    try:
        db.execute(text("""
            INSERT INTO fin_vendors (name, vendor_type, contact_name, phone, email, address, iban, note)
            VALUES (:name, :vendor_type, :contact_name, :phone, :email, :address, :iban, :note)
        """), {"name": data.name, "vendor_type": data.vendor_type, "contact_name": data.contact_name,
               "phone": data.phone, "email": data.email, "address": data.address,
               "iban": data.iban, "note": data.note})
        vendor_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        return {"success": True, "vendor_id": vendor_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/vendors/{vendor_id}")
async def update_vendor(vendor_id: int, data: VendorCreate, db: Session = Depends(get_rh_db)):
    """Update vendor"""
    try:
        db.execute(text("""
            UPDATE fin_vendors SET name = :name, vendor_type = :vendor_type, contact_name = :contact_name,
            phone = :phone, email = :email, address = :address, iban = :iban, note = :note WHERE id = :id
        """), {"id": vendor_id, **data.dict()})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# EMPLOYEES & PAYROLL
# ============================================================

@router.get("/employees")
async def list_employees(role: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """List all employees"""
    try:
        result = db.execute(text("SELECT id, emp_name, emp_role, emp_phone, emp_email, emp_salary, emp_hire_date, emp_note, emp_active, emp_created FROM rh_employees WHERE emp_active = TRUE ORDER BY emp_name"))
        employees = [{"id": r[0], "name": r[1], "role": r[2] or 'other', "phone": r[3], "email": r[4],
                      "base_salary": float(r[5] or 0), "hire_date": r[6].isoformat() if r[6] else None,
                      "note": r[7], "is_active": r[8], "created_at": r[9].isoformat() if r[9] else None} for r in result]
    except Exception as e:
        print(f"List employees error: {e}")
        employees = []
    return {"employees": employees}

@router.post("/employees")
async def create_employee(data: EmployeeCreate, db: Session = Depends(get_rh_db)):
    """Create a new employee"""
    try:
        hire_date = datetime.fromisoformat(data.hire_date).date() if data.hire_date else date.today()
        db.execute(text("""
            INSERT INTO rh_employees (emp_name, emp_role, emp_phone, emp_email, emp_salary, emp_hire_date, emp_note)
            VALUES (:name, :role, :phone, :email, :base_salary, :hire_date, :note)
        """), {"name": data.name, "role": data.role, "phone": data.phone, "email": data.email,
               "base_salary": data.base_salary, "hire_date": hire_date, "note": data.note})
        employee_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        return {"success": True, "employee_id": employee_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/payroll")
async def list_payroll(employee_id: Optional[int] = None, status: Optional[str] = None,
                       period: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """List payroll records"""
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS hr_payroll (
                id INT AUTO_INCREMENT PRIMARY KEY,
                employee_id INT NOT NULL,
                period_start DATE NOT NULL,
                period_end DATE NOT NULL,
                base_amount DECIMAL(12,2) NOT NULL,
                bonus DECIMAL(12,2) DEFAULT 0,
                deduction DECIMAL(12,2) DEFAULT 0,
                total_amount DECIMAL(12,2) DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                method VARCHAR(20) DEFAULT 'cash',
                paid_at TIMESTAMP NULL,
                tx_id INT NULL,
                note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.commit()
    except Exception as e:
        print(f"Payroll table setup: {e}")
    
    try:
        result = db.execute(text("""
            SELECT p.id, p.employee_id, e.emp_name, p.period_start, p.period_end, p.base_amount, p.bonus, p.deduction, 
                   (p.base_amount + COALESCE(p.bonus, 0) - COALESCE(p.deduction, 0)) as total_amount, 
                   p.status, p.method, p.paid_at, p.note, p.created_at
            FROM hr_payroll p LEFT JOIN rh_employees e ON e.id = p.employee_id 
            ORDER BY p.period_start DESC
        """))
        payroll = [{"id": r[0], "employee_id": r[1], "employee_name": r[2],
                    "period_start": r[3].isoformat() if r[3] else None,
                    "period_end": r[4].isoformat() if r[4] else None,
                    "base_amount": float(r[5] or 0), "bonus": float(r[6] or 0),
                    "deduction": float(r[7] or 0), "total_amount": float(r[8] or 0),
                    "status": r[9] or 'pending', "method": r[10] or 'cash',
                    "paid_at": r[11].isoformat() if r[11] else None,
                    "note": r[12], "created_at": r[13].isoformat() if r[13] else None} for r in result]
    except:
        payroll = []
    return {"payroll": payroll}

@router.post("/payroll")
async def create_payroll(data: PayrollCreate, db: Session = Depends(get_rh_db)):
    """Create payroll record"""
    try:
        period_start = datetime.fromisoformat(data.period_start).date()
        period_end = datetime.fromisoformat(data.period_end).date()
        db.execute(text("""
            INSERT INTO hr_payroll (employee_id, period_start, period_end, base_amount, bonus, deduction, method, note)
            VALUES (:employee_id, :period_start, :period_end, :base_amount, :bonus, :deduction, :method, :note)
        """), {"employee_id": data.employee_id, "period_start": period_start, "period_end": period_end,
               "base_amount": data.base_amount, "bonus": data.bonus, "deduction": data.deduction,
               "method": data.method, "note": data.note})
        payroll_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        return {"success": True, "payroll_id": payroll_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/payroll/{payroll_id}/pay")
async def pay_payroll(payroll_id: int, db: Session = Depends(get_rh_db)):
    """Process payroll payment with ledger entry"""
    rec = db.execute(text("SELECT employee_id, total_amount, method, status FROM hr_payroll WHERE id = :id"), {"id": payroll_id}).fetchone()
    if not rec:
        raise HTTPException(status_code=404, detail="Payroll record not found")
    if rec[3] == "paid":
        raise HTTPException(status_code=400, detail="Already paid")
    
    try:
        credit_acc = "CASH" if rec[2] == "cash" else "BANK"
        tx_id = post_transaction(db, "payroll_payment", float(rec[1]), "PAYROLL_EXP", credit_acc,
                                 "employee", rec[0], employee_id=rec[0], note=f"Зарплата #{payroll_id}")
        
        db.execute(text("UPDATE hr_payroll SET status = 'paid', paid_at = NOW(), tx_id = :tx_id WHERE id = :id"),
                  {"tx_id": tx_id, "id": payroll_id})
        db.commit()
        return {"success": True, "tx_id": tx_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/search/orders")
async def search_orders_for_deposit(q: str = "", db: Session = Depends(get_rh_db)):
    """Search orders for deposit modal"""
    rows = db.execute(text("""
        SELECT order_id, order_number, customer_name, customer_phone, total_price, deposit_amount, status
        FROM orders
        WHERE (order_number LIKE :q OR customer_name LIKE :q OR customer_phone LIKE :q)
        AND status NOT IN ('cancelled')
        ORDER BY order_id DESC LIMIT 20
    """), {"q": f"%{q}%"}).fetchall()
    return [{"order_id": r[0], "order_number": r[1], "customer_name": r[2], "phone": r[3],
             "total_price": float(r[4] or 0), "deposit_amount": float(r[5] or 0), "status": r[6]} for r in rows]


@router.get("/search/clients")
async def search_clients_for_deposit(q: str = "", db: Session = Depends(get_rh_db)):
    """Search clients for deposit modal"""
    rows = db.execute(text("""
        SELECT id, full_name, phone, payer_type, company
        FROM client_users
        WHERE (full_name LIKE :q OR phone LIKE :q OR company LIKE :q)
        ORDER BY id DESC LIMIT 20
    """), {"q": f"%{q}%"}).fetchall()
    return [{"id": r[0], "full_name": r[1], "phone": r[2], "payer_type": r[3], "company": r[4]} for r in rows]


# ============================================================
# DEPOSIT WITH CURRENCY
# ============================================================

@router.post("/deposits/create")
async def create_deposit_with_currency(data: DepositCreate):
    """Create deposit with multi-currency support using direct connection."""
    import pymysql
    from datetime import datetime
    import os
    
    conn = pymysql.connect(
        host=os.environ.get('RH_DB_HOST', 'farforre.mysql.tools'),
        port=int(os.environ.get('RH_DB_PORT', 3306)),
        user=os.environ.get('RH_DB_USERNAME', 'farforre_rentalhub'),
        password=os.environ.get('RH_DB_PASSWORD', '-nu+3Gp54L'),
        database=os.environ.get('RH_DB_DATABASE', 'farforre_rentalhub'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False
    )
    
    try:
        cursor = conn.cursor()
        occurred_at = datetime.now()
        
        if not data.order_id and not data.client_user_id:
            raise HTTPException(400, "Вкажіть ордер або клієнта")
        
        # Convert foreign currency to UAH equivalent
        uah_amount = data.actual_amount
        if data.currency != "UAH" and data.exchange_rate:
            uah_amount = data.actual_amount * data.exchange_rate
        
        # Determine accounts
        debit_acc = "CASH" if data.method == "cash" else "BANK"
        
        # Get account IDs
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", (debit_acc,))
        debit_acc_id = cursor.fetchone()['id']
        cursor.execute("SELECT id FROM fin_accounts WHERE code = %s", ("DEP_LIAB",))
        credit_acc_id = cursor.fetchone()['id']
        
        entity_type = "order" if data.order_id else "client"
        entity_id = data.order_id or data.client_user_id
        
        # Create transaction
        cursor.execute("""
            INSERT INTO fin_transactions (tx_type, amount, occurred_at, entity_type, entity_id, note, accepted_by_id, accepted_by_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, ("deposit_payment", uah_amount, occurred_at, entity_type, entity_id, data.note or f"Застава {data.currency}",
              data.accepted_by_id, data.accepted_by_name))
        tx_id = cursor.lastrowid
        
        # Create ledger entries
        cursor.execute("INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id) VALUES (%s, %s, 'D', %s, %s)",
                      (tx_id, debit_acc_id, uah_amount, data.order_id))
        cursor.execute("INSERT INTO fin_ledger_entries (tx_id, account_id, direction, amount, order_id) VALUES (%s, %s, 'C', %s, %s)",
                      (tx_id, credit_acc_id, uah_amount, data.order_id))
        
        # Check existing deposit by order_id or client_user_id
        if data.order_id:
            cursor.execute("SELECT id FROM fin_deposit_holds WHERE order_id = %s", (data.order_id,))
        elif data.client_user_id:
            cursor.execute("SELECT id FROM fin_deposit_holds WHERE client_user_id = %s AND order_id IS NULL AND status = 'held'", (data.client_user_id,))
        else:
            existing = None
        existing = cursor.fetchone() if data.order_id or data.client_user_id else None
        
        if existing:
            cursor.execute("""
                UPDATE fin_deposit_holds SET held_amount = held_amount + %s, 
                    actual_amount = %s, currency = %s, exchange_rate = %s, expected_amount = %s
                WHERE id = %s
            """, (uah_amount, data.actual_amount, data.currency, data.exchange_rate, data.expected_amount, existing['id']))
            deposit_id = existing['id']
        else:
            cursor.execute("""
                INSERT INTO fin_deposit_holds (order_id, client_user_id, held_amount, actual_amount, currency, exchange_rate, expected_amount, opened_at, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (data.order_id, data.client_user_id, uah_amount, data.actual_amount, data.currency, data.exchange_rate, data.expected_amount, occurred_at, data.note))
            deposit_id = cursor.lastrowid
        
        # Record deposit event
        cursor.execute("""
            INSERT INTO fin_deposit_events (deposit_id, event_type, amount, occurred_at, tx_id, note) 
            VALUES (%s, 'received', %s, %s, %s, %s)
        """, (deposit_id, uah_amount, occurred_at, tx_id, f"{data.actual_amount} {data.currency}" if data.currency != "UAH" else None))
        
        # Create payment record with user info
        cursor.execute("""
            INSERT INTO fin_payments (payment_type, method, amount, currency, order_id, occurred_at, note, tx_id, accepted_by_id, accepted_by_name)
            VALUES ('deposit', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (data.method, uah_amount, data.currency, data.order_id, occurred_at, data.note, tx_id, 
              data.accepted_by_id, data.accepted_by_name))
        
        conn.commit()
        return {"success": True, "deposit_id": deposit_id, "tx_id": tx_id, "uah_amount": uah_amount}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()



# ============================================================
# MANAGER DASHBOARD ENDPOINTS (для сумісності з ManagerDashboard)
# ============================================================

@manager_router.get("/summary")
async def get_manager_finance_summary(db: Session = Depends(get_rh_db)):
    """
    Фінансовий підсумок для ManagerDashboard KPI.
    Використовує ту саму логіку що й Finance Hub для консистентності.
    """
    try:
        # 1. Виручка з оренди (готівка + безготівка)
        rent_revenue = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'rent' AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # 2. Компенсації за шкоду
        damage_revenue = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'damage' AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # 3. Застави в холді (сума по валютах в грн еквіваленті)
        deposits_held = db.execute(text("""
            SELECT COALESCE(SUM(held_amount - used_amount - refunded_amount), 0)
            FROM fin_deposit_holds 
            WHERE status IN ('holding', 'partially_used')
        """)).fetchone()[0]
        
        # 4. Кількість активних застав
        deposits_count = db.execute(text("""
            SELECT COUNT(*) FROM fin_deposit_holds 
            WHERE status IN ('holding', 'partially_used')
        """)).fetchone()[0]
        
        # 5. Готівка в касі (оренда)
        rent_cash = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'rent' AND method = 'cash' AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # 6. Готівка в касі (шкода)
        damage_cash = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE payment_type = 'damage' AND method = 'cash' AND status IN ('completed', 'confirmed')
        """)).fetchone()[0]
        
        # Загальна виручка
        total_revenue = float(rent_revenue or 0) + float(damage_revenue or 0)
        
        return {
            "total_revenue": total_revenue,
            "deposits_held": float(deposits_held or 0),
            "deposits_count": int(deposits_count or 0),
            "rent_paid": total_revenue,
            "unpaid_balance": 0,
            "rent_revenue": float(rent_revenue or 0),
            "damage_revenue": float(damage_revenue or 0),
            "rent_cash": float(rent_cash or 0),
            "damage_cash": float(damage_cash or 0)
        }
        
    except Exception as e:
        # Повертаємо нулі у випадку помилки
        return {
            "total_revenue": 0,
            "deposits_held": 0,
            "deposits_count": 0,
            "rent_paid": 0,
            "unpaid_balance": 0,
            "error": str(e)
        }


@manager_router.get("/orders-with-finance")
async def get_orders_with_finance(
    status: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати замовлення з фінансовою інформацією для Finance Cabinet.
    Включає damage_due для відображення бейджу шкоди.
    """
    try:
        # Запит до orders з фінансовими даними та шкодою
        query = """
            SELECT 
                o.order_id, o.order_number, o.customer_name, o.customer_phone,
                o.status, o.total_price, o.deposit_amount,
                o.rental_start_date, o.rental_end_date,
                COALESCE(d.held_amount, 0) as deposit_held,
                COALESCE(d.used_amount, 0) as deposit_used,
                COALESCE(d.refunded_amount, 0) as deposit_refunded,
                COALESCE((SELECT SUM(amount) FROM fin_payments WHERE order_id = o.order_id AND payment_type = 'rent'), 0) as rent_paid,
                COALESCE((SELECT SUM(fee) FROM product_damage_history WHERE order_id = o.order_id), 0) as damage_total,
                COALESCE((SELECT SUM(amount) FROM fin_payments WHERE order_id = o.order_id AND payment_type = 'damage'), 0) as damage_paid,
                COALESCE(o.discount_amount, 0) as discount_amount,
                COALESCE(o.discount_percent, 0) as discount_percent,
                COALESCE(o.service_fee, 0) as service_fee,
                o.service_fee_name
            FROM orders o
            LEFT JOIN fin_deposit_holds d ON d.order_id = o.order_id
            WHERE o.is_archived = FALSE
        """
        
        if status:
            query += f" AND o.status = '{status}'"
        
        query += " ORDER BY o.created_at DESC LIMIT :limit"
        
        result = db.execute(text(query), {"limit": limit})
        
        orders = []
        for row in result:
            damage_total = float(row[13] or 0)
            damage_paid = float(row[14] or 0)
            damage_due = max(0, damage_total - damage_paid)
            discount_amount = float(row[15] or 0)
            discount_percent = float(row[16] or 0)
            service_fee = float(row[17] or 0)
            service_fee_name = row[18] or ""
            
            orders.append({
                "order_id": row[0],
                "order_number": row[1],
                "client_name": row[2],
                "customer_name": row[2],
                "customer_phone": row[3],
                "status": row[4],
                "total_rental": float(row[5] or 0),
                "total_deposit": float(row[6] or 0),
                "rental_start_date": str(row[7]) if row[7] else None,
                "rental_end_date": str(row[8]) if row[8] else None,
                "deposit_held": float(row[9] or 0),
                "deposit_used": float(row[10] or 0),
                "deposit_refunded": float(row[11] or 0),
                "rent_paid": float(row[12] or 0),
                "damage_total": damage_total,
                "damage_paid": damage_paid,
                "damage_due": damage_due,
                "discount_amount": discount_amount,
                "discount_percent": discount_percent,
                "service_fee": service_fee,
                "service_fee_name": service_fee_name
            })
        
        return {"orders": orders, "total": len(orders)}
        
    except Exception as e:
        return {"orders": [], "total": 0, "error": str(e)}


# ============================================================
# ORDER CHARGES SUMMARY (Damage + Late fees)
# ============================================================

@router.get("/order/{order_id}/charges")
async def get_order_charges(order_id: int, db: Session = Depends(get_rh_db)):
    """
    Отримати підсумок донарахувань для замовлення:
    - Шкода (damage) - з product_damage_history + оплати
    - Прострочення (late) - з fin_payments типу 'late'
    """
    try:
        # === ШКОДА ===
        # Загальна сума шкоди з product_damage_history
        damage_total = db.execute(text("""
            SELECT COALESCE(SUM(fee), 0) FROM product_damage_history WHERE order_id = :order_id
        """), {"order_id": order_id}).scalar() or 0
        
        # Оплачено за шкоду
        damage_paid = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
            WHERE order_id = :order_id AND payment_type = 'damage' AND status IN ('completed', 'confirmed', 'pending')
        """), {"order_id": order_id}).scalar() or 0
        
        # Деталі шкоди
        damage_items = db.execute(text("""
            SELECT pdh.id, pdh.product_id, p.sku, p.name, pdh.damage_type, pdh.qty, pdh.fee, pdh.note, pdh.created_at
            FROM product_damage_history pdh
            LEFT JOIN products p ON p.product_id = pdh.product_id
            WHERE pdh.order_id = :order_id
            ORDER BY pdh.created_at DESC
        """), {"order_id": order_id})
        
        damage_list = [{
            "id": r[0], "product_id": r[1], "sku": r[2], "name": r[3],
            "damage_type": r[4], "qty": r[5], "fee": float(r[6] or 0),
            "note": r[7], "created_at": r[8].isoformat() if r[8] else None
        } for r in damage_items]
        
        # === ПРОСТРОЧЕННЯ ===
        # Записи прострочення (pending - ще не оплачені, completed/confirmed - оплачені)
        late_payments = db.execute(text("""
            SELECT id, amount, status, note, occurred_at, accepted_by_name
            FROM fin_payments 
            WHERE order_id = :order_id AND payment_type = 'late'
            ORDER BY occurred_at DESC
        """), {"order_id": order_id})
        
        late_list = [{
            "id": r[0], "amount": float(r[1] or 0), "status": r[2],
            "note": r[3], "occurred_at": r[4].isoformat() if r[4] else None,
            "accepted_by": r[5]
        } for r in late_payments]
        
        late_charged = sum(l["amount"] for l in late_list if l["status"] == "pending")
        late_paid = sum(l["amount"] for l in late_list if l["status"] in ("completed", "confirmed"))
        # Нарахування (pending) = що менеджер вирішив стягнути
        # Оплата (confirmed) = що клієнт сплатив
        # Due = нарахування - оплата
        late_due = max(0, late_charged - late_paid)
        
        return {
            "order_id": order_id,
            "damage": {
                "total": float(damage_total),
                "paid": float(damage_paid),
                "due": max(0, float(damage_total) - float(damage_paid)),
                "items": damage_list
            },
            "late": {
                "total": late_charged,
                "paid": late_paid,
                "due": late_due,
                "items": late_list
            },
            "grand_total_due": max(0, float(damage_total) - float(damage_paid)) + late_due
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "damage": {"total": 0, "paid": 0, "due": 0, "items": []}, 
                "late": {"total": 0, "paid": 0, "due": 0, "items": []}, "grand_total_due": 0}


@router.post("/order/{order_id}/charges/add")
async def add_order_charge(order_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """
    Додати ручне донарахування для замовлення
    data: { type: 'damage' | 'late', amount: float, note: str }
    """
    charge_type = data.get("type", "late")
    amount = float(data.get("amount", 0))
    note = data.get("note", "")
    
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сума має бути більше 0")
    
    try:
        if charge_type == "damage":
            # Для шкоди - додаємо в product_damage_history (UUID id, без прив'язки до товару)
            import uuid
            new_id = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO product_damage_history (id, order_id, product_id, stage, damage_type, qty, fee, note, created_at, source)
                VALUES (:id, :order_id, 0, 'return', 'manual_charge', 1, :fee, :note, NOW(), 'manager_charge')
            """), {"id": new_id, "order_id": order_id, "fee": amount, "note": note or "Ручне донарахування шкоди"})
        else:
            # Для прострочення - додаємо в fin_payments з типом 'late'
            db.execute(text("""
                INSERT INTO fin_payments (order_id, payment_type, amount, currency, status, note, occurred_at)
                VALUES (:order_id, 'late', :amount, 'UAH', 'pending', :note, NOW())
            """), {"order_id": order_id, "amount": amount, "note": note or "Ручне донарахування прострочення"})
        
        db.commit()
        return {"success": True, "type": charge_type, "amount": amount}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/order/{order_id}/charges/{charge_id}")
async def update_order_charge(order_id: int, charge_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """
    Оновити суму донарахування
    data: { type: 'damage' | 'late', amount: float, note: str }
    """
    charge_type = data.get("type", "late")
    amount = float(data.get("amount", 0))
    note = data.get("note")
    
    try:
        if charge_type == "damage":
            db.execute(text("""
                UPDATE product_damage_history SET fee = :fee, note = COALESCE(:note, note) WHERE id = :id
            """), {"id": charge_id, "fee": amount, "note": note})
        else:
            db.execute(text("""
                UPDATE fin_payments SET amount = :amount, note = COALESCE(:note, note) WHERE id = :id AND payment_type = 'late'
            """), {"id": charge_id, "amount": amount, "note": note})
        
        db.commit()
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/order/{order_id}/charges/{charge_id}")
async def delete_order_charge(order_id: int, charge_id: int, charge_type: str = "late", db: Session = Depends(get_rh_db)):
    """
    Видалити донарахування
    """
    try:
        if charge_type == "damage":
            db.execute(text("DELETE FROM product_damage_history WHERE id = :id"), {"id": charge_id})
        else:
            db.execute(text("DELETE FROM fin_payments WHERE id = :id AND payment_type = 'late'"), {"id": charge_id})
        
        db.commit()
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/order/{order_id}/charges/{charge_id}/pay")
async def pay_order_charge(order_id: int, charge_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """
    Оплатити донарахування (late fee)
    data: { method: 'cash' | 'card' | 'bank' }
    """
    method = data.get("method", "cash")
    
    try:
        # Отримати запис
        charge = db.execute(text("""
            SELECT amount, note FROM fin_payments WHERE id = :id AND payment_type = 'late' AND status = 'pending'
        """), {"id": charge_id}).fetchone()
        
        if not charge:
            raise HTTPException(status_code=404, detail="Донарахування не знайдено або вже оплачено")
        
        # Оновити статус на оплачено
        db.execute(text("""
            UPDATE fin_payments SET status = 'confirmed', method = :method WHERE id = :id
        """), {"id": charge_id, "method": method})
        
        db.commit()
        return {"success": True, "amount": float(charge[0])}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# DISCOUNT MANAGEMENT (Управління знижкою)
# ============================================================

@router.get("/order/{order_id}/discount")
async def get_order_discount(order_id: int, db: Session = Depends(get_rh_db)):
    """
    Отримати знижку замовлення з фін кабінету.
    Якщо запису немає - повертає дані з orders.
    """
    try:
        # Спочатку шукаємо в fin_payments
        fin_discount = db.execute(text("""
            SELECT id, amount, note, status, occurred_at, accepted_by_name
            FROM fin_payments 
            WHERE order_id = :order_id AND payment_type = 'discount'
            ORDER BY occurred_at DESC LIMIT 1
        """), {"order_id": order_id}).fetchone()
        
        if fin_discount:
            return {
                "source": "finance",
                "id": fin_discount[0],
                "amount": float(fin_discount[1] or 0),
                "note": fin_discount[2],
                "status": fin_discount[3],
                "recorded_at": fin_discount[4].isoformat() if fin_discount[4] else None,
                "recorded_by": fin_discount[5]
            }
        
        # Якщо немає в fin_payments - беремо з orders
        order_discount = db.execute(text("""
            SELECT discount_amount, discount_percent FROM orders WHERE order_id = :order_id
        """), {"order_id": order_id}).fetchone()
        
        if order_discount:
            amount = float(order_discount[0] or 0)
            percent = float(order_discount[1] or 0)
            return {
                "source": "order",
                "id": None,
                "amount": amount,
                "percent": percent,
                "note": f"Знижка {percent}%" if percent > 0 else "Знижка",
                "status": "pending"  # Ще не записана у фін кабінет
            }
        
        return {"source": None, "amount": 0, "note": None}
        
    except Exception as e:
        return {"error": str(e), "amount": 0}


@router.put("/order/{order_id}/discount")
async def update_order_discount(order_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """
    Оновити знижку замовлення у фін кабінеті.
    Якщо запису немає - створює новий.
    data: { amount: float, note: str }
    """
    amount = float(data.get("amount", 0))
    note = data.get("note", "Знижка")
    user_name = data.get("user_name", "System")
    user_id = data.get("user_id")
    
    try:
        # Перевіряємо чи є існуючий запис
        existing = db.execute(text("""
            SELECT id FROM fin_payments 
            WHERE order_id = :order_id AND payment_type = 'discount'
            LIMIT 1
        """), {"order_id": order_id}).fetchone()
        
        if existing:
            # Оновлюємо існуючий
            db.execute(text("""
                UPDATE fin_payments 
                SET amount = :amount, note = :note, occurred_at = NOW()
                WHERE id = :id
            """), {"id": existing[0], "amount": amount, "note": note})
        else:
            # Створюємо новий
            db.execute(text("""
                INSERT INTO fin_payments (order_id, payment_type, amount, currency, status, note, occurred_at, accepted_by_id, accepted_by_name)
                VALUES (:order_id, 'discount', :amount, 'UAH', 'confirmed', :note, NOW(), :user_id, :user_name)
            """), {
                "order_id": order_id,
                "amount": amount,
                "note": note,
                "user_id": user_id,
                "user_name": user_name
            })
        
        # Також оновлюємо в orders для синхронізації
        db.execute(text("""
            UPDATE orders SET discount_amount = :amount WHERE order_id = :order_id
        """), {"order_id": order_id, "amount": amount})
        
        db.commit()
        return {"success": True, "amount": amount}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ADMIN FINANCE MANAGEMENT ENDPOINTS
# ============================================================

@router.get("/admin/expense-categories")
async def list_expense_categories(db: Session = Depends(get_rh_db)):
    """Отримати всі категорії витрат для адмін панелі"""
    try:
        result = db.execute(text("""
            SELECT id, type, code, name, is_active 
            FROM fin_categories 
            ORDER BY type, name
        """))
        return [{"id": r[0], "type": r[1], "code": r[2], "name": r[3], "is_active": bool(r[4])} for r in result]
    except:
        return []


@router.post("/admin/expense-categories")
async def create_expense_category(data: dict, db: Session = Depends(get_rh_db)):
    """Створити нову категорію витрат"""
    try:
        db.execute(text("""
            INSERT INTO fin_categories (type, code, name, is_active)
            VALUES (:type, :code, :name, TRUE)
        """), {"type": data.get("type", "expense"), "code": data.get("code"), "name": data.get("name")})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/admin/expense-categories/{category_id}")
async def update_expense_category(category_id: int, data: dict, db: Session = Depends(get_rh_db)):
    """Оновити категорію витрат"""
    try:
        db.execute(text("""
            UPDATE fin_categories SET name = :name, code = :code, is_active = :is_active WHERE id = :id
        """), {"id": category_id, "name": data.get("name"), "code": data.get("code"), "is_active": data.get("is_active", True)})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/expense-categories/{category_id}")
async def delete_expense_category(category_id: int, db: Session = Depends(get_rh_db)):
    """Видалити категорію витрат"""
    try:
        db.execute(text("UPDATE fin_categories SET is_active = FALSE WHERE id = :id"), {"id": category_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# FINANCE HUB 2.0 - NEW ENDPOINTS
# ============================================================

@router.get("/hub/overview")
async def get_hub_overview(db: Session = Depends(get_rh_db)):
    """
    Finance Hub 2.0 - Головний огляд
    Готівка = фактичний залишок каси (з cash_summaries)
    Після закриття місяця — виручка/витрати скидаються на 0 (інкасація)
    """
    try:
        _ensure_monthly_reports_table(db)
        
        # Визначити "робочий" місяць: якщо поточний місяць закрито — показуємо наступний
        from datetime import date
        today = date.today()
        current_year, current_month = today.year, today.month
        
        closed_check = db.execute(text("""
            SELECT id FROM monthly_reports WHERE year = :y AND month = :m
        """), {"y": current_year, "m": current_month}).fetchone()
        
        if closed_check:
            # Поточний місяць закрито — показуємо наступний (виручка/витрати = 0)
            if current_month == 12:
                work_year, work_month = current_year + 1, 1
            else:
                work_year, work_month = current_year, current_month + 1
        else:
            work_year, work_month = current_year, current_month
        
        result = db.execute(text("""
            SELECT 
                -- Безготівка (накопичена)
                (SELECT COALESCE(SUM(CASE WHEN method = 'bank' AND payment_type IN ('rent', 'additional', 'damage', 'late') THEN amount ELSE 0 END), 0)
                 - COALESCE(SUM(CASE WHEN method = 'bank' AND payment_type = 'refund' THEN amount ELSE 0 END), 0)
                 FROM fin_payments WHERE status IN ('completed', 'confirmed')) as bank_balance,
                -- Виручка робочого місяця
                (SELECT COALESCE(SUM(amount), 0) FROM fin_payments 
                 WHERE status IN ('completed', 'confirmed') 
                 AND payment_type IN ('rent', 'additional', 'damage', 'late')
                 AND MONTH(occurred_at) = :wm AND YEAR(occurred_at) = :wy) as month_revenue,
                -- Витрати робочого місяця
                (SELECT COALESCE(SUM(amount), 0) FROM fin_expenses 
                 WHERE status = 'posted' AND MONTH(occurred_at) = :wm2 AND YEAR(occurred_at) = :wy2) as month_expenses,
                -- Кількість ордерів
                (SELECT COUNT(*) FROM orders WHERE status NOT IN ('cancelled', 'archived')) as total_orders
        """), {"wm": work_month, "wy": work_year, "wm2": work_month, "wy2": work_year})
        
        row = result.fetchone()
        
        # Готівка = фактичний залишок каси з cash_summaries
        cash_row = db.execute(text("""
            SELECT actual_cash FROM cash_summaries 
            ORDER BY date DESC LIMIT 1
        """)).fetchone()
        
        if cash_row:
            cash = float(cash_row[0] or 0)
        else:
            cash_fallback = db.execute(text("""
                SELECT COALESCE(SUM(CASE WHEN payment_type IN ('rent', 'additional', 'damage', 'late') THEN amount ELSE 0 END), 0)
                     - COALESCE(SUM(CASE WHEN payment_type = 'refund' THEN amount ELSE 0 END), 0)
                FROM fin_payments WHERE method = 'cash' AND status IN ('completed', 'confirmed')
            """)).fetchone()
            cash = float(cash_fallback[0] or 0) if cash_fallback else 0
        
        # Застави по валютах
        deposits_result = db.execute(text("""
            SELECT 
                currency,
                COALESCE(SUM(actual_amount), 0) as amount,
                COALESCE(SUM(held_amount), 0) as uah,
                COALESCE(SUM(used_amount), 0) as used,
                COALESCE(SUM(refunded_amount), 0) as refunded,
                COUNT(*) as cnt
            FROM fin_deposit_holds
            WHERE status IN ('held', 'partial', 'holding', 'partially_used')
            GROUP BY currency
        """))
        
        deposits_by_currency = {}
        for r in deposits_result:
            available = float(r[1] or 0) - float(r[3] or 0) - float(r[4] or 0)
            deposits_by_currency[r[0]] = {
                "amount": float(r[1] or 0),
                "uah_equivalent": float(r[2] or 0),
                "available": available if available > 0 else 0,
                "count": r[5] or 0
            }
        
        bank = float(row[0] or 0) if row else 0
        revenue = float(row[1] or 0) if row else 0
        expenses = float(row[2] or 0) if row else 0
        total_orders = int(row[3] or 0) if row else 0
        
        month_label = f"{work_month:02d}/{work_year}"
        
        return {
            "cash": {"balance": cash, "currency": "UAH"},
            "bank": {"balance": bank, "currency": "UAH"},
            "deposits": deposits_by_currency,
            "month": {
                "revenue": {"total": revenue},
                "expenses": expenses,
                "profit": revenue - expenses,
                "label": month_label,
                "closed": bool(closed_check),
            },
            "orders": {
                "total": total_orders,
                "fully_paid": 0,
                "with_debt": 0
            }
        }
    except Exception as e:
        print(f"[Finance Hub] Error in overview: {e}")
        # Return empty data on error
        return {
            "cash": {"balance": 0, "currency": "UAH"},
            "bank": {"balance": 0, "currency": "UAH"},
            "deposits": {},
            "month": {"revenue": {"total": 0}, "expenses": 0, "profit": 0},
            "orders": {"total": 0, "fully_paid": 0, "with_debt": 0}
        }


@router.get("/hub/order-timeline/{order_id}")
async def get_order_timeline(order_id: int, db: Session = Depends(get_rh_db)):
    """
    Finance Hub 2.0 - Таймлайн всіх операцій по ордеру
    """
    try:
        events = []
        
        # Платежі
        try:
            payments = db.execute(text("""
                SELECT id, payment_type, method, amount, description, accepted_by_name, created_at, status
                FROM fin_payments
                WHERE order_id = :order_id
                ORDER BY created_at DESC
            """), {"order_id": order_id})
            
            type_labels = {
                "rent": "Оплата оренди",
                "additional": "Донарахування",
                "damage": "Оплата шкоди",
                "refund": "Повернення"
            }
            
            for p in payments:
                events.append({
                    "id": f"payment_{p[0]}",
                    "type": "payment",
                    "subtype": p[1],
                    "icon": "✓" if p[7] == "completed" else "⏳",
                    "title": type_labels.get(p[1], p[1] or "Оплата"),
                    "description": p[4] if p[4] else None,
                    "amount": float(p[3]) if p[3] else 0,
                    "method": p[2],
                    "user": p[5],
                    "timestamp": p[6].isoformat() if p[6] else None,
                    "status": p[7],
                    "tone": "ok" if p[7] == "completed" else "warn"
                })
        except Exception as e:
            print(f"[Timeline] Error loading payments: {e}")
        
        # Застави
        try:
            deposits = db.execute(text("""
                SELECT id, actual_amount, currency, held_amount, used_amount, refunded_amount, 
                       method, accepted_by_name, created_at, status
                FROM fin_deposits
                WHERE order_id = :order_id
                ORDER BY created_at DESC
            """), {"order_id": order_id})
            
            for d in deposits:
                # Прийом застави
                events.append({
                    "id": f"deposit_{d[0]}",
                    "type": "deposit_in",
                    "icon": "🔒",
                    "title": "Застава прийнята",
                    "amount": float(d[1]) if d[1] else 0,
                    "currency": d[2] or "UAH",
                    "uah_amount": float(d[3]) if d[3] else 0,
                    "method": d[6],
                    "user": d[7],
                    "timestamp": d[8].isoformat() if d[8] else None,
                    "status": d[9],
                    "tone": "info"
                })
                
                # Утримання
                if d[4] and float(d[4]) > 0:
                    events.append({
                        "id": f"deposit_use_{d[0]}",
                        "type": "deposit_use",
                        "icon": "⚠️",
                        "title": "Утримано із застави",
                        "amount": float(d[4]),
                        "currency": "UAH",
                        "timestamp": d[8].isoformat() if d[8] else None,
                        "tone": "warn"
                    })
                
                # Повернення
                if d[5] and float(d[5]) > 0:
                    events.append({
                        "id": f"deposit_refund_{d[0]}",
                        "type": "deposit_out",
                        "icon": "💰",
                        "title": "Застава повернута",
                        "amount": float(d[5]),
                        "currency": "UAH",
                        "timestamp": d[8].isoformat() if d[8] else None,
                        "tone": "ok"
                    })
        except Exception as e:
            print(f"[Timeline] Error loading deposits: {e}")
        
        # Шкода (не оплачена) - тільки якщо таблиця існує
        try:
            damages = db.execute(text("""
                SELECT id, product_name, damage_type, fee, created_at
                FROM product_damage_history
                WHERE order_id = :order_id AND fee > 0 AND stage = 'return'
                ORDER BY created_at DESC
            """), {"order_id": order_id})
            
            for dm in damages:
                events.append({
                    "id": f"damage_{dm[0]}",
                    "type": "damage",
                    "icon": "🔧",
                    "title": f"Шкода: {dm[2] or 'дефект'}",
                    "description": dm[1],
                    "amount": float(dm[3]) if dm[3] else 0,
                    "timestamp": dm[4].isoformat() if dm[4] else None,
                    "tone": "danger"
                })
        except Exception as e:
            print(f"[Timeline] Error loading damages: {e}")
        
        # Сортуємо по часу (новіші зверху)
        events.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
        
        return {"order_id": order_id, "events": events}
    except Exception as e:
        print(f"[Timeline] Fatal error: {e}")
        return {"order_id": order_id, "events": []}


@router.get("/hub/monthly-report")
async def get_monthly_report(
    year: int = None, 
    month: int = None,
    db: Session = Depends(get_rh_db)
):
    """
    Finance Hub 2.0 - Місячний звіт
    """
    try:
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month
        
        # Доходи по типах
        income = db.execute(text("""
            SELECT 
                payment_type,
                method,
                COUNT(*) as count,
                SUM(amount) as total
            FROM fin_payments
            WHERE status = 'completed'
            AND MONTH(created_at) = :month AND YEAR(created_at) = :year
            GROUP BY payment_type, method
        """), {"month": month, "year": year})
        
        income_breakdown = {}
        for r in income:
            ptype = r[0]
            if ptype not in income_breakdown:
                income_breakdown[ptype] = {"cash": 0, "bank": 0, "total": 0, "count": 0}
            income_breakdown[ptype][r[1]] = float(r[3] or 0)
            income_breakdown[ptype]["total"] += float(r[3] or 0)
            income_breakdown[ptype]["count"] += r[2]
        
        # Витрати по категоріях
        expenses = db.execute(text("""
            SELECT 
                c.name as category,
                e.method,
                COUNT(*) as count,
                SUM(e.amount) as total
            FROM fin_expenses e
            LEFT JOIN fin_categories c ON c.id = e.category_id
            WHERE e.status = 'posted'
            AND MONTH(e.occurred_at) = :month AND YEAR(e.occurred_at) = :year
            GROUP BY c.name, e.method
        """), {"month": month, "year": year})
        
        expenses_breakdown = {}
        for r in expenses:
            cat = r[0] or "Без категорії"
            if cat not in expenses_breakdown:
                expenses_breakdown[cat] = {"cash": 0, "bank": 0, "total": 0, "count": 0}
            expenses_breakdown[cat][r[1] or "cash"] = float(r[3] or 0)
            expenses_breakdown[cat]["total"] += float(r[3] or 0)
            expenses_breakdown[cat]["count"] += r[2]
        
        # Зарплати
        payroll = db.execute(text("""
            SELECT 
                e.name as employee,
                SUM(p.base_amount + p.bonus - p.deduction) as total
            FROM fin_payroll p
            JOIN fin_employees e ON e.id = p.employee_id
            WHERE p.status = 'paid'
            AND MONTH(p.paid_at) = :month AND YEAR(p.paid_at) = :year
            GROUP BY e.name
        """), {"month": month, "year": year})
        
        payroll_breakdown = {r[0]: float(r[1] or 0) for r in payroll}
        
        # Інкасації
        encashments = db.execute(text("""
            SELECT 
                SUM(amount) as total,
                COUNT(*) as count
            FROM fin_encashments
            WHERE status = 'completed'
            AND MONTH(created_at) = :month AND YEAR(created_at) = :year
        """), {"month": month, "year": year}).fetchone()
        
        # Підсумки
        total_income = sum(v["total"] for v in income_breakdown.values())
        total_expenses = sum(v["total"] for v in expenses_breakdown.values())
        total_payroll = sum(payroll_breakdown.values())
        
        return {
            "period": {"year": year, "month": month},
            "income": {
                "breakdown": income_breakdown,
                "total": total_income
            },
            "expenses": {
                "breakdown": expenses_breakdown,
                "total": total_expenses
            },
            "payroll": {
                "breakdown": payroll_breakdown,
                "total": total_payroll
            },
            "encashments": {
                "total": float(encashments[0] or 0) if encashments else 0,
                "count": encashments[1] or 0 if encashments else 0
            },
            "summary": {
                "gross_income": total_income,
                "total_costs": total_expenses + total_payroll,
                "net_profit": total_income - total_expenses - total_payroll
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hub/encashment")
async def create_encashment(
    amount: float,
    note: str = None,
    db: Session = Depends(get_rh_db)
):
    """
    Finance Hub 2.0 - Інкасація (зняття готівки)
    """
    try:
        user = "Система"  # TODO: отримати з токена
        
        db.execute(text("""
            INSERT INTO fin_encashments (amount, note, created_by, status, created_at)
            VALUES (:amount, :note, :created_by, 'completed', NOW())
        """), {"amount": amount, "note": note, "created_by": user})
        
        db.commit()
        
        return {"success": True, "message": f"Інкасація ₴{amount} проведена"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# FINANCE HUB 2.0 - SNAPSHOT API (ФАЗА 1)
# Один запит замість 6+ для правої панелі ордера
# ============================================================

@router.get("/orders/{order_id}/snapshot")
async def get_order_finance_snapshot(order_id: int, db: Session = Depends(get_rh_db)):
    """
    📊 Finance Snapshot API - Всі фінансові дані ордера одним запитом.
    
    Замінює:
    - GET /payments?order_id=X
    - GET /deposits (пошук по order_id)  
    - GET /order/X/charges (damage + late)
    - GET /documents/entity/order/X
    - GET /order/X/discount
    - Рахунки totals з order
    
    Returns: payments, deposit, damage, late, totals, documents, timeline, payer_profile
    """
    import hashlib
    from datetime import datetime
    
    try:
        # === 1. ORDER BASE INFO ===
        order_row = db.execute(text("""
            SELECT o.order_id, o.order_number, o.customer_name, o.customer_phone,
                   o.status, o.total_price, o.deposit_amount, 
                   o.rental_start_date, o.rental_end_date,
                   COALESCE(o.discount_amount, 0) as discount_amount,
                   COALESCE(o.discount_percent, 0) as discount_percent,
                   o.payer_profile_id, o.created_at, o.deal_mode
            FROM orders o WHERE o.order_id = :order_id
        """), {"order_id": order_id}).fetchone()
        
        if not order_row:
            raise HTTPException(status_code=404, detail="Замовлення не знайдено")
        
        is_image_project = order_row[13] == 'image_project'
        
        # === 2. PAYMENTS (all types) ===
        payments_rows = db.execute(text("""
            SELECT id, payment_type, method, amount, currency, 
                   payer_name, occurred_at, note, status,
                   accepted_by_id, accepted_by_name, description
            FROM fin_payments 
            WHERE order_id = :order_id
            ORDER BY occurred_at DESC
        """), {"order_id": order_id})
        
        payments = []
        rent_paid = 0
        damage_paid = 0
        late_paid = 0
        advance_paid = 0
        
        for p in payments_rows:
            payment = {
                "id": p[0], "payment_type": p[1], "method": p[2],
                "amount": float(p[3] or 0), "currency": p[4] or "UAH",
                "payer_name": p[5], 
                "occurred_at": p[6].isoformat() if p[6] else None,
                "note": p[7], "status": p[8],
                "accepted_by_id": p[9], "accepted_by_name": p[10],
                "description": p[11]
            }
            payments.append(payment)
            
            # Accumulate by type
            if p[8] in ('completed', 'confirmed'):
                if p[1] == 'rent':
                    rent_paid += float(p[3] or 0)
                elif p[1] in ('damage', 'loss'):
                    damage_paid += float(p[3] or 0)
                elif p[1] == 'late':
                    late_paid += float(p[3] or 0)
                elif p[1] == 'advance':
                    advance_paid += float(p[3] or 0)
                elif p[1] == 'additional':
                    rent_paid += float(p[3] or 0)  # Донарахування → rent
        
        # === 3. DEPOSIT ===
        deposit_row = db.execute(text("""
            SELECT id, held_amount, used_amount, refunded_amount, status,
                   actual_amount, currency, exchange_rate, expected_amount,
                   opened_at, closed_at, note
            FROM fin_deposit_holds 
            WHERE order_id = :order_id
            LIMIT 1
        """), {"order_id": order_id}).fetchone()
        
        deposit = None
        if deposit_row:
            currency = deposit_row[6] or 'UAH'
            actual = float(deposit_row[5]) if deposit_row[5] else float(deposit_row[1])
            used = float(deposit_row[2] or 0)
            refunded = float(deposit_row[3] or 0)
            available = float(deposit_row[1]) - used - refunded
            
            deposit = {
                "id": deposit_row[0],
                "held_amount": float(deposit_row[1]),
                "actual_amount": actual,
                "currency": currency,
                "exchange_rate": float(deposit_row[7]) if deposit_row[7] else 1.0,
                "expected_amount": float(deposit_row[8]) if deposit_row[8] else 0,
                "used_amount": used,
                "refunded_amount": refunded,
                "available": available,
                "status": deposit_row[4],
                "opened_at": deposit_row[9].isoformat() if deposit_row[9] else None,
                "closed_at": deposit_row[10].isoformat() if deposit_row[10] else None,
                "note": deposit_row[11],
                "display_amount": f"{actual:,.0f} {currency}" if currency != 'UAH' else f"₴{actual:,.0f}"
            }
            # Додати events із fin_deposit_events
            dep_events = db.execute(text("""
                SELECT event_type, amount, occurred_at, note
                FROM fin_deposit_events WHERE deposit_id = :dep_id
                ORDER BY occurred_at DESC
            """), {"dep_id": deposit_row[0]}).fetchall()
            deposit["events"] = [
                {"event_type": e[0], "amount": float(e[1] or 0), 
                 "date": e[2].isoformat() if e[2] else None, "note": e[3]}
                for e in dep_events
            ]
        
        # === 4. DAMAGE ===
        damage_total = db.execute(text("""
            SELECT COALESCE(SUM(fee), 0) FROM product_damage_history WHERE order_id = :order_id
        """), {"order_id": order_id}).scalar() or 0
        
        damage_items_rows = db.execute(text("""
            SELECT pdh.id, pdh.product_id, p.sku, p.name, pdh.damage_type, 
                   pdh.qty, pdh.fee, pdh.note, pdh.created_at
            FROM product_damage_history pdh
            LEFT JOIN products p ON p.product_id = pdh.product_id
            WHERE pdh.order_id = :order_id
            ORDER BY pdh.created_at DESC
        """), {"order_id": order_id})
        
        damage_items = [{
            "id": r[0], "product_id": r[1], "sku": r[2], "name": r[3],
            "damage_type": r[4], "qty": r[5], "fee": float(r[6] or 0),
            "note": r[7], "created_at": r[8].isoformat() if r[8] else None
        } for r in damage_items_rows]
        
        damage = {
            "total": float(damage_total),
            "paid": damage_paid,
            "due": max(0, float(damage_total) - damage_paid),
            "items": damage_items
        }
        
        # === 4b. DEPOSIT COVERAGE FOR DAMAGE ===
        # Утримання із застави покриває шкоду — враховуємо в due
        deposit_used_for_damage = 0
        if deposit and deposit.get("events"):
            for ev in deposit["events"]:
                if ev["event_type"] == "used_for_damage":
                    deposit_used_for_damage += ev["amount"]
        
        # Шкода покрита = прямі оплати + утримання із застави
        damage_covered = damage_paid + deposit_used_for_damage
        damage["deposit_covered"] = deposit_used_for_damage
        damage["due"] = max(0, float(damage_total) - damage_covered)
        
        # === 5. LATE FEES ===
        late_rows = db.execute(text("""
            SELECT id, amount, status, note, occurred_at, accepted_by_name
            FROM fin_payments 
            WHERE order_id = :order_id AND payment_type = 'late'
            ORDER BY occurred_at DESC
        """), {"order_id": order_id})
        
        late_items = [{
            "id": r[0], "amount": float(r[1] or 0), "status": r[2],
            "note": r[3], "occurred_at": r[4].isoformat() if r[4] else None,
            "accepted_by": r[5]
        } for r in late_rows]
        
        late_charged = sum(l["amount"] for l in late_items if l["status"] == "pending")
        late_paid_total = sum(l["amount"] for l in late_items if l["status"] in ("completed", "confirmed"))
        # Нарахування (pending) = що менеджер вирішив стягнути
        # Оплата (confirmed) = що клієнт сплатив
        # Due = нарахування - оплата
        late_due_calc = max(0, late_charged - late_paid_total)
        
        late = {
            "total": late_charged,
            "paid": late_paid_total,
            "due": late_due_calc,
            "items": late_items
        }
        
        # === 6. DOCUMENTS (latest versions only) ===
        docs_rows = db.execute(text("""
            SELECT d.id, d.doc_type, d.entity_id, d.version, d.status, 
                   d.created_at, d.doc_number
            FROM documents d
            INNER JOIN (
                SELECT doc_type, MAX(version) as max_version
                FROM documents
                WHERE entity_type = 'order' AND entity_id = :order_id
                GROUP BY doc_type
            ) latest ON d.doc_type = latest.doc_type AND d.version = latest.max_version
            WHERE d.entity_type = 'order' AND d.entity_id = :order_id
        """), {"order_id": str(order_id)})
        
        documents = [{
            "id": r[0], "doc_type": r[1], "entity_id": r[2], "version": r[3],
            "status": r[4], "created_at": r[5].isoformat() if r[5] else None,
            "doc_number": r[6]
        } for r in docs_rows]
        
        # === 7. PAYER PROFILE ===
        payer_profile = None
        if order_row[11]:  # payer_profile_id
            payer_row = db.execute(text("""
                SELECT id, payer_type, company_name, edrpou, iban, bank_name,
                       director_name, address, is_vat_payer
                FROM payer_profiles WHERE id = :id AND is_active = TRUE
            """), {"id": order_row[11]}).fetchone()
            
            if payer_row:
                payer_profile = {
                    "id": payer_row[0], "payer_type": payer_row[1],
                    "company_name": payer_row[2], "edrpou": payer_row[3],
                    "iban": payer_row[4], "bank_name": payer_row[5],
                    "director_name": payer_row[6], "address": payer_row[7],
                    "is_vat_payer": bool(payer_row[8])
                }
        
        # === 8. TOTALS ===
        # Визначаємо чи total_price зберігає ціну ДО чи ПІСЛЯ знижки
        # Якщо є платіж типу 'discount' - знижка записана окремо, total_price = ДО знижки
        total_price_stored = float(order_row[5] or 0)
        discount = float(order_row[9] or 0)
        
        has_discount_payment = any(p['payment_type'] == 'discount' for p in payments)
        
        if has_discount_payment and discount > 0:
            # total_price = ціна ДО знижки, знижка записана окремою оплатою
            rental_before_discount = total_price_stored
            total_after_discount = total_price_stored - discount
        else:
            # total_price = ціна ПІСЛЯ знижки (або без знижки)
            rental_before_discount = total_price_stored + discount
            total_after_discount = total_price_stored
        
        # Іміджевий проєкт: обнулити всі борги
        if is_image_project:
            damage["total"] = 0
            damage["due"] = 0
            damage["items"] = []
            damage["deposit_covered"] = 0
            late["total"] = 0
            late["due"] = 0
            late["items"] = []
            total_after_discount = 0
            discount = rental_before_discount
        
        rent_due = max(0, total_after_discount - rent_paid - advance_paid)
        
        # Іміджевий проєкт: примусово обнулити борг
        if is_image_project:
            rent_due = 0
        
        totals = {
            "rental_total": rental_before_discount,
            "discount": discount,
            "discount_percent": float(order_row[10] or 0),
            "rental_after_discount": total_after_discount,
            "rent_paid": rent_paid,
            "advance_paid": advance_paid,
            "rent_due": rent_due,
            "deposit_expected": float(order_row[6] or 0),
            "deposit_held": deposit["held_amount"] if deposit else 0,
            "deposit_available": deposit["available"] if deposit else 0,
            "deposit_used_for_damage": deposit_used_for_damage,
            "damage_total": damage["total"],
            "damage_paid": damage["paid"],
            "damage_deposit_covered": damage.get("deposit_covered", 0),
            "damage_due": damage["due"],
            "late_total": late["total"],
            "late_paid": late["paid"],
            "late_due": late["due"],
            "grand_total_due": rent_due + damage["due"] + late["due"]
        }
        
        # === 9. TIMELINE (для UI) ===
        timeline = []
        
        # Payments to timeline
        for p in payments:
            type_labels = {
                "rent": "Оренда", "additional": "Донарахування", 
                "damage": "Шкода", "deposit": "Застава", "late": "Прострочення",
                "advance": "Передплата"
            }
            timeline.append({
                "id": f"pay_{p['id']}", 
                "type": "payment",
                "at": p["occurred_at"],
                "label": p["note"] or type_labels.get(p["payment_type"], p["payment_type"]),
                "amount": p["amount"],
                "status": "done" if p["status"] in ('completed', 'confirmed') else "pending",
                "meta": f"{p['method']} · {p.get('accepted_by_name', '')}"
            })
        
        # Deposit events to timeline
        if deposit:
            if deposit["used_amount"] > 0:
                timeline.append({
                    "id": "dep_used", "type": "deposit_use",
                    "at": deposit["closed_at"],
                    "label": "Утримано із застави",
                    "amount": -deposit["used_amount"],
                    "status": "warn", "meta": "компенсація"
                })
            if deposit["refunded_amount"] > 0:
                timeline.append({
                    "id": "dep_refund", "type": "deposit_refund",
                    "at": deposit["closed_at"],
                    "label": "Застава повернута",
                    "amount": deposit["refunded_amount"],
                    "status": "done", "meta": ""
                })
        
        # Pending damage
        if damage["due"] > 0:
            timeline.append({
                "id": "dmg_due", "type": "damage_pending",
                "at": None, "label": "Шкода (очікує)",
                "amount": damage["due"], "status": "warn",
                "meta": ", ".join([d["name"] or "—" for d in damage_items[:3]])
            })
        
        # Sort timeline by date (newest first, pending last)
        timeline.sort(key=lambda x: (x["at"] is None, x["at"] or ""), reverse=True)
        
        # === 10. SNAPSHOT METADATA ===
        snapshot_time = datetime.now().isoformat()
        data_hash = hashlib.md5(f"{order_id}_{rent_paid}_{deposit}_{damage['due']}_{late['due']}".encode()).hexdigest()[:8]
        
        return {
            "order_id": order_id,
            "order_number": order_row[1],
            "customer_name": order_row[2],
            "customer_phone": order_row[3],
            "status": order_row[4],
            "rental_dates": {
                "start": str(order_row[7]) if order_row[7] else None,
                "end": str(order_row[8]) if order_row[8] else None
            },
            "payments": payments,
            "deposit": deposit,
            "damage": damage,
            "late": late,
            "totals": totals,
            "documents": documents,
            "payer_profile": payer_profile,
            "timeline": timeline,
            "deal_mode": order_row[13] or "rent",
            "_meta": {
                "snapshot_at": snapshot_time,
                "version": data_hash,
                "source": "snapshot_api_v1"
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# OPTIMIZED PAYOUTS STATS (ФАЗА 1)
# 12 SQL → 2 SQL з SUM(CASE WHEN)
# ============================================================

@router.get("/payouts-stats-v2")
async def get_payouts_stats_optimized(db: Session = Depends(get_rh_db)):
    """
    Оптимізована версія payouts-stats: 2 SQL запити замість 12.
    Використовує SUM(CASE WHEN ...) для агрегації.
    """
    try:
        # === ОДИН ЗАПИТ ДЛЯ ВСІХ PAYMENTS ===
        payments_stats = db.execute(text("""
            SELECT 
                SUM(CASE WHEN payment_type = 'rent' AND method = 'cash' AND status IN ('completed', 'confirmed') THEN amount ELSE 0 END) as rent_cash,
                SUM(CASE WHEN payment_type = 'rent' AND method IN ('card', 'bank') AND status IN ('completed', 'confirmed') THEN amount ELSE 0 END) as rent_bank,
                SUM(CASE WHEN payment_type = 'damage' AND method = 'cash' AND status IN ('completed', 'confirmed') THEN amount ELSE 0 END) as damage_cash,
                SUM(CASE WHEN payment_type = 'damage' AND method IN ('card', 'bank') AND status IN ('completed', 'confirmed') THEN amount ELSE 0 END) as damage_bank,
                SUM(CASE WHEN payment_type = 'rent' AND status IN ('completed', 'confirmed') THEN amount ELSE 0 END) as total_rent
            FROM fin_payments
        """)).fetchone()
        
        rent_cash_income = float(payments_stats[0] or 0)
        rent_bank_income = float(payments_stats[1] or 0)
        damage_cash_income = float(payments_stats[2] or 0)
        damage_bank_income = float(payments_stats[3] or 0)
        total_rent = float(payments_stats[4] or 0)
        
        # === ОДИН ЗАПИТ ДЛЯ ВСІХ EXPENSES ===
        expenses_stats = db.execute(text("""
            SELECT 
                SUM(CASE WHEN c.code IN ('RENT_EXPENSE', 'RENT_CASH_EXPENSE') AND e.method = 'cash' THEN e.amount ELSE 0 END) as rent_cash_exp,
                SUM(CASE WHEN c.code = 'DAMAGE_EXPENSE' AND e.method = 'cash' THEN e.amount ELSE 0 END) as damage_cash_exp,
                SUM(CASE WHEN c.code = 'RENT_BANK_EXPENSE' AND e.method = 'bank' THEN e.amount ELSE 0 END) as rent_bank_exp,
                SUM(CASE WHEN c.code = 'DAMAGE_BANK_EXPENSE' AND e.method = 'bank' THEN e.amount ELSE 0 END) as damage_bank_exp,
                SUM(CASE WHEN c.code = 'RENT_CASH_DEPOSIT' THEN e.amount ELSE 0 END) as rent_cash_dep,
                SUM(CASE WHEN c.code = 'DAMAGE_CASH_DEPOSIT' THEN e.amount ELSE 0 END) as damage_cash_dep
            FROM fin_expenses e
            LEFT JOIN fin_categories c ON c.id = e.category_id
        """)).fetchone()
        
        rent_cash_expenses = float(expenses_stats[0] or 0)
        damage_cash_expenses = float(expenses_stats[1] or 0)
        rent_bank_expenses = float(expenses_stats[2] or 0)
        damage_bank_expenses = float(expenses_stats[3] or 0)
        rent_cash_deposits = float(expenses_stats[4] or 0)
        damage_cash_deposits = float(expenses_stats[5] or 0)
        
        # === DEPOSITS HELD ===
        deposits_held = db.execute(text("""
            SELECT 
                SUM(CASE WHEN currency = 'UAH' OR currency IS NULL THEN held_amount - used_amount - refunded_amount ELSE 0 END) as uah,
                SUM(CASE WHEN currency = 'USD' THEN actual_amount - COALESCE(used_amount/exchange_rate, 0) - COALESCE(refunded_amount/exchange_rate, 0) ELSE 0 END) as usd,
                SUM(CASE WHEN currency = 'EUR' THEN actual_amount - COALESCE(used_amount/exchange_rate, 0) - COALESCE(refunded_amount/exchange_rate, 0) ELSE 0 END) as eur
            FROM fin_deposit_holds 
            WHERE status IN ('holding', 'partially_used')
        """)).fetchone()
        
        # === CALCULATE BALANCES ===
        rent_cash_balance = rent_cash_income - rent_cash_expenses + rent_cash_deposits
        damage_cash_balance = damage_cash_income - damage_cash_expenses + damage_cash_deposits
        rent_bank_balance = rent_bank_income - rent_bank_expenses
        damage_bank_balance = damage_bank_income - damage_bank_expenses
        
        return {
            # Готівка балансі
            "rent_cash_balance": rent_cash_balance,
            "damage_cash_balance": damage_cash_balance,
            "total_cash_balance": rent_cash_balance + damage_cash_balance,
            
            # Безготівка балансі
            "rent_bank_balance": rent_bank_balance,
            "damage_bank_balance": damage_bank_balance,
            "bank_balance": rent_bank_balance + damage_bank_balance,
            
            # Витрати
            "rent_cash_expenses": rent_cash_expenses,
            "damage_cash_expenses": damage_cash_expenses,
            "rent_bank_expenses": rent_bank_expenses,
            "damage_bank_expenses": damage_bank_expenses,
            
            # Внесення
            "rent_cash_deposits": rent_cash_deposits,
            "damage_cash_deposits": damage_cash_deposits,
            
            # Застави по валютах
            "deposits_by_currency": {
                "UAH": float(deposits_held[0] or 0),
                "USD": float(deposits_held[1] or 0),
                "EUR": float(deposits_held[2] or 0)
            },
            
            # Legacy fields
            "total_rent_revenue": total_rent,
            "cash_balance": rent_cash_balance + damage_cash_balance,
            "total_active_balance": rent_cash_balance + damage_cash_balance + rent_bank_balance + damage_bank_balance,
            
            # Meta
            "_optimized": True,
            "_queries": 3
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# KASA (CASH REGISTER) - 3-column view
# ============================================================

@router.get("/kasa")
async def get_kasa_data(
    period: str = "month",
    db: Session = Depends(get_rh_db)
):
    """
    Каса — три колонки:
    1. Дохід (оплати оренди): готівка/безготівка, ордер, дата
    2. Депозити: прийняті/повернуті/утримані
    3. Витрати: опис, сума, метод, дата
    """
    try:
        # Date filter
        date_filter_payments = ""
        date_filter_expenses = ""
        params = {}
        
        if period == "day":
            date_filter_payments = "AND p.occurred_at >= CURDATE()"
            date_filter_expenses = "AND e.occurred_at >= CURDATE()"
        elif period == "week":
            date_filter_payments = "AND p.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
            date_filter_expenses = "AND e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif period == "month":
            date_filter_payments = "AND MONTH(p.occurred_at) = MONTH(CURDATE()) AND YEAR(p.occurred_at) = YEAR(CURDATE())"
            date_filter_expenses = "AND MONTH(e.occurred_at) = MONTH(CURDATE()) AND YEAR(e.occurred_at) = YEAR(CURDATE())"
        elif period == "all":
            pass  # no filter
        
        # === 1. INCOME (rent/damage/late/additional payments) ===
        income_rows = db.execute(text(f"""
            SELECT p.id, p.payment_type, p.method, p.amount, p.currency,
                   p.occurred_at, p.note, p.status,
                   p.accepted_by_name, p.description,
                   o.order_number, o.customer_name, p.order_id
            FROM fin_payments p
            LEFT JOIN orders o ON o.order_id = p.order_id
            WHERE p.payment_type IN ('rent', 'additional', 'damage', 'late')
            AND p.status IN ('completed', 'confirmed')
            {date_filter_payments}
            ORDER BY p.occurred_at DESC
        """))
        
        income = []
        income_cash_total = 0
        income_bank_total = 0
        for r in income_rows:
            amt = float(r[3] or 0)
            method = r[2] or 'cash'
            if method == 'cash':
                income_cash_total += amt
            else:
                income_bank_total += amt
            
            type_labels = {"rent": "Оренда", "additional": "Донарахування", "damage": "Шкода", "late": "Прострочення"}
            income.append({
                "id": r[0],
                "type": r[1],
                "type_label": type_labels.get(r[1], r[1]),
                "method": method,
                "amount": amt,
                "currency": r[4] or "UAH",
                "date": r[5].isoformat() if r[5] else None,
                "note": r[6],
                "status": r[7],
                "accepted_by": r[8],
                "description": r[9],
                "order_number": r[10],
                "customer_name": r[11],
                "order_id": r[12],
            })
        
        # === 2. DEPOSITS (always ALL — no date/month filtering) ===
        deposit_rows = db.execute(text("""
            SELECT d.id, d.order_id, d.held_amount, d.actual_amount, d.currency,
                   d.exchange_rate, d.used_amount, d.refunded_amount, d.status,
                   d.opened_at, d.closed_at, d.note,
                   o.order_number, o.customer_name,
                   d.expected_amount, d.client_user_id,
                   cu.full_name as client_name,
                   (SELECT p.method FROM fin_payments p 
                    WHERE p.payment_type = 'deposit' AND p.status IN ('completed','confirmed')
                    AND (p.order_id = d.order_id OR (d.order_id IS NULL AND p.amount = d.held_amount 
                         AND p.occurred_at >= d.opened_at - INTERVAL 1 MINUTE 
                         AND p.occurred_at <= d.opened_at + INTERVAL 1 MINUTE))
                    ORDER BY p.occurred_at DESC LIMIT 1) as payment_method
            FROM fin_deposit_holds d
            LEFT JOIN orders o ON o.order_id = d.order_id
            LEFT JOIN client_users cu ON cu.id = d.client_user_id
            ORDER BY FIELD(d.status, 'holding', 'held', 'partially_used', 'fully_used', 'refunded'), d.opened_at DESC
        """))
        
        deposits = []
        deposits_held_total = 0
        deposits_refunded_total = 0
        deposits_used_total = 0
        for r in deposit_rows:
            held = float(r[2] or 0)
            actual = float(r[3] or 0) if r[3] else held
            used = float(r[6] or 0)
            refunded = float(r[7] or 0)
            available = held - used - refunded
            currency = r[4] or 'UAH'
            
            deposits_held_total += held
            deposits_refunded_total += refunded
            deposits_used_total += used
            
            deposits.append({
                "id": r[0],
                "order_id": r[1],
                "held_amount": held,
                "actual_amount": actual,
                "currency": currency,
                "exchange_rate": float(r[5]) if r[5] else 1.0,
                "used_amount": used,
                "refunded_amount": refunded,
                "available": max(0, available),
                "status": r[8],
                "opened_at": r[9].isoformat() if r[9] else None,
                "closed_at": r[10].isoformat() if r[10] else None,
                "note": r[11],
                "order_number": r[12],
                "customer_name": r[13] or (r[16] if r[16] else None),
                "expected_amount": float(r[14] or 0),
                "client_user_id": r[15],
                "client_name": r[16],
                "method": r[17] or "cash",
            })
        
        # Deposit payments (to know cash/bank)
        dep_payments = db.execute(text(f"""
            SELECT p.method, SUM(p.amount) as total
            FROM fin_payments p
            WHERE p.payment_type = 'deposit'
            AND p.status IN ('completed', 'confirmed')
            {date_filter_payments}
            GROUP BY p.method
        """))
        dep_by_method = {}
        for r in dep_payments:
            dep_by_method[r[0] or 'cash'] = float(r[1] or 0)
        
        # === 3. EXPENSES ===
        expense_rows = db.execute(text(f"""
            SELECT e.id, e.expense_type, c.code, c.name, e.amount, e.currency,
                   e.method, e.occurred_at, e.note, e.status, e.order_id,
                   pc.name as parent_name, pc.code as parent_code
            FROM fin_expenses e
            LEFT JOIN fin_categories c ON c.id = e.category_id
            LEFT JOIN fin_categories pc ON pc.id = c.parent_id
            WHERE e.status = 'posted'
            {date_filter_expenses}
            ORDER BY e.occurred_at DESC
        """))
        
        expenses = []
        expenses_cash_total = 0
        expenses_bank_total = 0
        for r in expense_rows:
            amt = float(r[4] or 0)
            method = r[6] or 'cash'
            if method == 'cash':
                expenses_cash_total += amt
            else:
                expenses_bank_total += amt
            
            expenses.append({
                "id": r[0],
                "expense_type": r[1],
                "category_code": r[2],
                "category_name": r[3] or "Без категорії",
                "amount": amt,
                "currency": r[5] or "UAH",
                "method": method,
                "date": r[7].isoformat() if r[7] else None,
                "note": r[8],
                "status": r[9],
                "order_id": r[10],
                "parent_category": r[11],
                "parent_code": r[12],
            })
        
        # Refund payments (to show in expenses column)
        refund_rows = db.execute(text(f"""
            SELECT p.id, p.method, p.amount, p.occurred_at, p.note,
                   o.order_number, o.customer_name, p.order_id
            FROM fin_payments p
            LEFT JOIN orders o ON o.order_id = p.order_id
            WHERE p.payment_type = 'refund'
            AND p.status IN ('completed', 'confirmed')
            {date_filter_payments}
            ORDER BY p.occurred_at DESC
        """))
        
        refunds = []
        for r in refund_rows:
            amt = float(r[2] or 0)
            method = r[1] or 'cash'
            if method == 'cash':
                expenses_cash_total += amt
            else:
                expenses_bank_total += amt
            refunds.append({
                "id": r[0],
                "method": method,
                "amount": amt,
                "date": r[3].isoformat() if r[3] else None,
                "note": r[4],
                "order_number": r[5],
                "customer_name": r[6],
                "order_id": r[7],
            })
        
        # Collection (Інкасація) totals
        collection_rows = db.execute(text(f"""
            SELECT e.method, SUM(e.amount) as total
            FROM fin_expenses e
            WHERE e.expense_type = 'collection' AND e.status = 'posted'
            {date_filter_expenses}
            GROUP BY e.method
        """)).fetchall()
        collection_cash = 0
        collection_bank = 0
        for r in collection_rows:
            if (r[0] or 'cash') == 'cash':
                collection_cash += float(r[1] or 0)
            else:
                collection_bank += float(r[1] or 0)
        
        # === CLOSED MONTHS: summaries only (items stay in their arrays) ===
        _ensure_monthly_reports_table(db)
        closed_months_data = []
        
        closed_reports = db.execute(text("""
            SELECT year, month, report_data FROM monthly_reports ORDER BY year, month
        """)).fetchall()
        
        closed_periods = set()
        month_names_ua = ['','Січень','Лютий','Березень','Квітень','Травень','Червень',
                          'Липень','Серпень','Вересень','Жовтень','Листопад','Грудень']
        for cr in closed_reports:
            cy, cm = cr[0], cr[1]
            closed_periods.add((cy, cm))
            try:
                import json as json_mod
                rd = json_mod.loads(cr[2]) if cr[2] else {}
            except:
                rd = {}
            cash_reg = rd.get("cash_register", {})
            closed_months_data.append({
                "year": cy, "month": cm,
                "label": f"{month_names_ua[cm]} {cy}",
                "income_total": rd.get("income", {}).get("total", 0),
                "income_cash": rd.get("income", {}).get("cash", 0),
                "income_bank": rd.get("income", {}).get("bank", 0),
                "income_count": rd.get("income", {}).get("count", 0),
                "expenses_total": rd.get("expenses", {}).get("total", 0),
                "expenses_cash": rd.get("expenses", {}).get("cash", 0),
                "deposits_held": rd.get("deposits", {}).get("total_held", 0),
                "deposits_refunded": rd.get("deposits", {}).get("total_refunded", 0),
                "deposits_count": rd.get("deposits", {}).get("opened_count", 0),
                "closing_cash": cash_reg.get("closing_balance", 0),
                "opening_cash": cash_reg.get("opening_balance", 0),
                "net_total": rd.get("summary", {}).get("net_total", 0),
            })
        
        # Mark each item with its closed status (frontend will group them)
        def mark_closed_period(item, date_key="date"):
            d = item.get(date_key)
            if not d: return item
            try:
                from datetime import datetime as dt
                parsed = dt.fromisoformat(d) if isinstance(d, str) else d
                item["_closed"] = (parsed.year, parsed.month) in closed_periods
                item["_period"] = f"{parsed.year}-{parsed.month:02d}"
            except:
                item["_closed"] = False
            return item
        
        for i in income: mark_closed_period(i, "date")
        for e in expenses: mark_closed_period(e, "date")
        # Deposits are completely decoupled from monthly closing — no _closed/_period marking
        
        # Carry-over balance from last closed month
        carry_over_balance = 0
        if closed_months_data:
            carry_over_balance = closed_months_data[-1].get("closing_cash", 0)
        
        # Recalculate totals from OPEN items only (excluding closed months)
        open_income = [i for i in income if not i.get("_closed")]
        open_expenses = [e for e in expenses if not e.get("_closed")]
        open_refunds = [r for r in refunds if not r.get("_closed")]
        
        open_income_cash = sum(i["amount"] for i in open_income if i["method"] == "cash")
        open_income_bank = sum(i["amount"] for i in open_income if i["method"] != "cash")
        open_expenses_cash = sum(e["amount"] for e in open_expenses if e.get("method") == "cash")
        open_expenses_bank = sum(e["amount"] for e in open_expenses if e.get("method") != "cash")
        open_refunds_cash = sum(r["amount"] for r in open_refunds if r.get("method") == "cash")
        open_refunds_bank = sum(r["amount"] for r in open_refunds if r.get("method") != "cash")
        
        # Active deposits (held/holding) always count
        active_deposits = [d for d in deposits if d.get("status") in ("held", "holding")]
        active_held = sum(float(d.get("held_amount", 0)) for d in active_deposits)
        active_refunded = sum(float(d.get("refunded_amount", 0)) for d in active_deposits)
        active_used = sum(float(d.get("used_amount", 0)) for d in active_deposits)
        
        return {
            "period": period,
            "income": {
                "items": income,
                "cash_total": open_income_cash,
                "bank_total": open_income_bank,
                "total": open_income_cash + open_income_bank,
                "count": len(open_income),
            },
            "deposits": {
                "items": deposits,
                "held_total": active_held,
                "refunded_total": active_refunded,
                "used_total": active_used,
                "available_total": active_held - active_refunded - active_used,
                "cash_received": dep_by_method.get('cash', 0),
                "bank_received": dep_by_method.get('bank', 0),
                "count": len(deposits),
            },
            "expenses": {
                "items": expenses,
                "refunds": refunds,
                "cash_total": open_expenses_cash + open_refunds_cash,
                "bank_total": open_expenses_bank + open_refunds_bank,
                "total": open_expenses_cash + open_expenses_bank + open_refunds_cash + open_refunds_bank,
                "count": len(open_expenses) + len(open_refunds),
            },
            "collection": {
                "cash_total": collection_cash,
                "bank_total": collection_bank,
                "total": collection_cash + collection_bank,
            },
            "closed_months": closed_months_data,
            "carry_over_balance": carry_over_balance,
            "summary": {
                "net_cash": open_income_cash - open_expenses_cash - open_refunds_cash,
                "net_bank": open_income_bank - open_expenses_bank - open_refunds_bank,
                "net_total": (open_income_cash + open_income_bank) - (open_expenses_cash + open_expenses_bank + open_refunds_cash + open_refunds_bank),
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))



# ============================================================
# MONTHLY CLOSE (Закриття місяця)
# ============================================================

def _ensure_monthly_reports_table(db: Session):
    """Create monthly_reports table if not exists"""
    db.execute(text("""
        CREATE TABLE IF NOT EXISTS monthly_reports (
            id INT AUTO_INCREMENT PRIMARY KEY,
            year INT NOT NULL,
            month INT NOT NULL,
            report_data JSON NOT NULL,
            closed_by VARCHAR(255),
            closed_by_id INT,
            closed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            note TEXT,
            UNIQUE KEY uk_year_month (year, month)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """))
    db.commit()


@router.post("/close-month")
async def close_month(
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """
    Закрити місяць: зібрати всі фінансові дані за вказаний місяць,
    зберегти як звіт в БД. Фіксує залишок каси.
    data: { year, month, closing_cash_balance, note?, closed_by?, closed_by_id? }
    """
    _ensure_monthly_reports_table(db)
    
    year = data.get("year")
    month = data.get("month")
    note = data.get("note", "")
    closed_by = data.get("closed_by", "")
    closed_by_id = data.get("closed_by_id")
    closing_cash = data.get("closing_cash_balance")  # actual cash at end of month
    
    if not year or not month:
        raise HTTPException(status_code=400, detail="Вкажіть рік та місяць")
    
    # Check if already closed
    existing = db.execute(text("""
        SELECT id FROM monthly_reports WHERE year = :year AND month = :month
    """), {"year": year, "month": month}).fetchone()
    
    if existing:
        raise HTTPException(status_code=409, detail=f"Місяць {month:02d}/{year} вже закрито")
    
    # === COLLECT ALL DATA FOR THE MONTH ===
    month_start = f"{year}-{month:02d}-01"
    if month == 12:
        month_end = f"{year+1}-01-01"
    else:
        month_end = f"{year}-{month+1:02d}-01"
    
    params = {"month_start": month_start, "month_end": month_end}
    
    # 1. INCOME
    income_rows = db.execute(text("""
        SELECT payment_type, method, SUM(amount) as total, COUNT(*) as cnt
        FROM fin_payments
        WHERE payment_type IN ('rent', 'additional', 'damage', 'late')
        AND status IN ('completed', 'confirmed')
        AND occurred_at >= :month_start AND occurred_at < :month_end
        GROUP BY payment_type, method
    """), params).fetchall()
    
    income_by_type = {}
    income_by_method = {"cash": 0, "bank": 0}
    income_total = 0
    income_count = 0
    for r in income_rows:
        ptype = r[0]
        method = r[1] or 'cash'
        amt = float(r[2] or 0)
        cnt = int(r[3] or 0)
        
        if ptype not in income_by_type:
            income_by_type[ptype] = {"cash": 0, "bank": 0, "total": 0, "count": 0}
        income_by_type[ptype][method if method in ("cash", "bank") else "bank"] += amt
        income_by_type[ptype]["total"] += amt
        income_by_type[ptype]["count"] += cnt
        
        income_by_method[method if method in ("cash", "bank") else "bank"] += amt
        income_total += amt
        income_count += cnt
    
    # 2. DEPOSITS
    deposits_data = db.execute(text("""
        SELECT 
            COUNT(*) as cnt,
            COALESCE(SUM(held_amount), 0) as total_held,
            COALESCE(SUM(used_amount), 0) as total_used,
            COALESCE(SUM(refunded_amount), 0) as total_refunded
        FROM fin_deposit_holds
        WHERE opened_at >= :month_start AND opened_at < :month_end
    """), params).fetchone()
    
    deposits_closed = db.execute(text("""
        SELECT COUNT(*), COALESCE(SUM(refunded_amount), 0)
        FROM fin_deposit_holds
        WHERE closed_at >= :month_start AND closed_at < :month_end
    """), params).fetchone()
    
    deposit_payments = db.execute(text("""
        SELECT method, SUM(amount) as total
        FROM fin_payments
        WHERE payment_type = 'deposit'
        AND status IN ('completed', 'confirmed')
        AND occurred_at >= :month_start AND occurred_at < :month_end
        GROUP BY method
    """), params).fetchall()
    dep_by_method = {}
    for r in deposit_payments:
        dep_by_method[r[0] or 'cash'] = float(r[1] or 0)

    deposit_refund_payments = db.execute(text("""
        SELECT method, SUM(amount) as total
        FROM fin_payments
        WHERE payment_type = 'deposit_refund'
        AND status IN ('completed', 'confirmed')
        AND occurred_at >= :month_start AND occurred_at < :month_end
        GROUP BY method
    """), params).fetchall()
    dep_refund_by_method = {}
    for r in deposit_refund_payments:
        dep_refund_by_method[r[0] or 'cash'] = float(r[1] or 0)
    
    # 3. EXPENSES
    expenses_rows = db.execute(text("""
        SELECT e.expense_type, c.name, e.method, SUM(e.amount) as total, COUNT(*) as cnt
        FROM fin_expenses e
        LEFT JOIN fin_categories c ON c.id = e.category_id
        WHERE e.status = 'posted'
        AND e.occurred_at >= :month_start AND e.occurred_at < :month_end
        GROUP BY e.expense_type, c.name, e.method
    """), params).fetchall()
    
    expenses_by_category = {}
    expenses_by_method = {"cash": 0, "bank": 0}
    expenses_total = 0
    expenses_count = 0
    collection_total = 0
    for r in expenses_rows:
        etype = r[0]
        cat_name = r[1] or "Без категорії"
        method = r[2] or 'cash'
        amt = float(r[3] or 0)
        cnt = int(r[4] or 0)
        
        if etype == 'collection':
            collection_total += amt
            continue
        
        key = cat_name
        if key not in expenses_by_category:
            expenses_by_category[key] = {"cash": 0, "bank": 0, "total": 0, "count": 0}
        expenses_by_category[key][method if method in ("cash", "bank") else "bank"] += amt
        expenses_by_category[key]["total"] += amt
        expenses_by_category[key]["count"] += cnt
        
        expenses_by_method[method if method in ("cash", "bank") else "bank"] += amt
        expenses_total += amt
        expenses_count += cnt
    
    # 4. REFUNDS
    refunds_data = db.execute(text("""
        SELECT method, SUM(amount) as total, COUNT(*) as cnt
        FROM fin_payments
        WHERE payment_type = 'refund'
        AND status IN ('completed', 'confirmed')
        AND occurred_at >= :month_start AND occurred_at < :month_end
        GROUP BY method
    """), params).fetchall()
    
    refunds_by_method = {"cash": 0, "bank": 0}
    refunds_total = 0
    refunds_count = 0
    for r in refunds_data:
        method = r[0] or 'cash'
        amt = float(r[1] or 0)
        cnt = int(r[2] or 0)
        refunds_by_method[method if method in ("cash", "bank") else "bank"] += amt
        refunds_total += amt
        refunds_count += cnt
    
    # 5. ENCASHMENTS (transfers in/out of safe)
    encashments_rows = db.execute(text("""
        SELECT SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as total_in,
               SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as total_out,
               COUNT(*) as cnt
        FROM fin_encashments
        WHERE status = 'completed'
        AND created_at >= :month_start AND created_at < :month_end
    """), params).fetchone()
    
    # 6. ORDERS COUNT
    orders_count = db.execute(text("""
        SELECT COUNT(DISTINCT order_id) FROM fin_payments
        WHERE status IN ('completed', 'confirmed')
        AND occurred_at >= :month_start AND occurred_at < :month_end
    """), params).scalar() or 0
    
    # 7. CASH REGISTER BALANCES
    # Opening balance: last day of previous month from cash_summaries, or 0
    prev_month_end = month_start  # first day of this month = last moment of prev month
    opening_row = db.execute(text("""
        SELECT actual_cash FROM cash_summaries 
        WHERE date < :d ORDER BY date DESC LIMIT 1
    """), {"d": prev_month_end}).fetchone()
    opening_cash = float(opening_row[0]) if opening_row else 0
    
    # Closing: use provided value or last cash_summary for this month
    if closing_cash is not None:
        closing_cash = float(closing_cash)
    else:
        closing_row = db.execute(text("""
            SELECT actual_cash FROM cash_summaries 
            WHERE date >= :start AND date < :end ORDER BY date DESC LIMIT 1
        """), {"start": month_start, "end": month_end}).fetchone()
        closing_cash = float(closing_row[0]) if closing_row else 0
    
    # === BUILD REPORT ===
    import json as json_mod
    report = {
        "period": {"year": year, "month": month, "label": f"{month:02d}/{year}"},
        "income": {
            "total": income_total,
            "cash": income_by_method["cash"],
            "bank": income_by_method["bank"],
            "count": income_count,
            "by_type": {
                "rent": income_by_type.get("rent", {"total": 0, "cash": 0, "bank": 0, "count": 0}),
                "damage": income_by_type.get("damage", {"total": 0, "cash": 0, "bank": 0, "count": 0}),
                "late": income_by_type.get("late", {"total": 0, "cash": 0, "bank": 0, "count": 0}),
                "additional": income_by_type.get("additional", {"total": 0, "cash": 0, "bank": 0, "count": 0}),
            }
        },
        "deposits": {
            "opened_count": int(deposits_data[0] or 0),
            "total_held": float(deposits_data[1] or 0),
            "total_used": float(deposits_data[2] or 0),
            "total_refunded": float(deposits_data[3] or 0),
            "closed_count": int(deposits_closed[0] or 0),
            "closed_refunded": float(deposits_closed[1] or 0),
            "received_cash": dep_by_method.get("cash", 0),
            "received_bank": dep_by_method.get("bank", 0),
            "refunded_cash": dep_refund_by_method.get("cash", 0),
            "refunded_bank": dep_refund_by_method.get("bank", 0),
        },
        "expenses": {
            "total": expenses_total,
            "cash": expenses_by_method["cash"],
            "bank": expenses_by_method["bank"],
            "count": expenses_count,
            "by_category": expenses_by_category,
        },
        "refunds": {
            "total": refunds_total,
            "cash": refunds_by_method["cash"],
            "bank": refunds_by_method["bank"],
            "count": refunds_count,
        },
        "encashments": {
            "in": float(encashments_rows[0] or 0) if encashments_rows else 0,
            "out": float(encashments_rows[1] or 0) if encashments_rows else 0,
            "count": int(encashments_rows[2] or 0) if encashments_rows else 0,
        },
        "collection": {"total": collection_total},
        "orders_count": orders_count,
        "cash_register": {
            "opening_balance": opening_cash,
            "closing_balance": closing_cash,
        },
        "summary": {
            "net_cash": income_by_method["cash"] - expenses_by_method["cash"] - refunds_by_method["cash"],
            "net_bank": income_by_method["bank"] - expenses_by_method["bank"] - refunds_by_method["bank"],
            "net_total": income_total - expenses_total - refunds_total,
        }
    }
    
    # Save to DB
    db.execute(text("""
        INSERT INTO monthly_reports (year, month, report_data, closed_by, closed_by_id, note)
        VALUES (:year, :month, :report_data, :closed_by, :closed_by_id, :note)
    """), {
        "year": year, "month": month,
        "report_data": json_mod.dumps(report, ensure_ascii=False),
        "closed_by": closed_by,
        "closed_by_id": closed_by_id,
        "note": note,
    })
    
    # Save closing balance to cash_summaries for next month's opening
    last_day = f"{year}-{month:02d}-" + ("31" if month in (1,3,5,7,8,10,12) else "30" if month in (4,6,9,11) else "28")
    db.execute(text("""
        INSERT INTO cash_summaries (date, system_cash, actual_cash, difference, note, created_by)
        VALUES (:d, :bal, :bal, 0, :note, 'close-month')
        ON DUPLICATE KEY UPDATE actual_cash = :bal2
    """), {"d": last_day, "bal": closing_cash, "bal2": closing_cash, "note": f"Закриття {month:02d}/{year}"})
    
    db.commit()
    
    return {"success": True, "report": report}


@router.get("/monthly-reports")
async def get_monthly_reports(db: Session = Depends(get_rh_db)):
    """Отримати список всіх закритих місяців"""
    _ensure_monthly_reports_table(db)
    
    rows = db.execute(text("""
        SELECT id, year, month, report_data, closed_by, closed_by_id, closed_at, note
        FROM monthly_reports
        ORDER BY year DESC, month DESC
    """)).fetchall()
    
    import json
    return [{
        "id": r[0],
        "year": r[1],
        "month": r[2],
        "report": json.loads(r[3]) if isinstance(r[3], str) else r[3],
        "closed_by": r[4],
        "closed_by_id": r[5],
        "closed_at": r[6].isoformat() if r[6] else None,
        "note": r[7],
    } for r in rows]


@router.get("/monthly-reports/{report_id}")
async def get_monthly_report_detail(report_id: int, db: Session = Depends(get_rh_db)):
    """Отримати деталі конкретного місячного звіту"""
    _ensure_monthly_reports_table(db)
    
    row = db.execute(text("""
        SELECT id, year, month, report_data, closed_by, closed_by_id, closed_at, note
        FROM monthly_reports WHERE id = :id
    """), {"id": report_id}).fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Звіт не знайдено")
    
    import json
    return {
        "id": row[0],
        "year": row[1],
        "month": row[2],
        "report": json.loads(row[3]) if isinstance(row[3], str) else row[3],
        "closed_by": row[4],
        "closed_by_id": row[5],
        "closed_at": row[6].isoformat() if row[6] else None,
        "note": row[7],
    }


@router.delete("/monthly-reports/{report_id}")
async def delete_monthly_report(report_id: int, db: Session = Depends(get_rh_db)):
    """Видалити (відкрити) закритий місяць - тільки для адміна"""
    _ensure_monthly_reports_table(db)
    
    db.execute(text("DELETE FROM monthly_reports WHERE id = :id"), {"id": report_id})
    db.commit()
    return {"success": True}



# ============================================================
# PLAN: Expected Income (План надходжень)
# ============================================================

@router.get("/expected-income")
async def get_expected_income(
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_rh_db)
):
    """
    Неоплачені/частково оплачені замовлення за обраний місяць.
    Показує скільки грошей має зайти.
    """
    from datetime import datetime as dt
    now = dt.now()
    target_month = month or now.month
    target_year = year or now.year
    
    try:
        # All orders with event START in the target month (each order belongs to ONE month only)
        rows = db.execute(text("""
            SELECT o.order_id, o.order_number, o.customer_name, o.status,
                   o.total_price, o.discount_amount, o.service_fee,
                   o.rental_start_date, o.rental_end_date,
                   CONCAT(u.firstname, ' ', u.lastname),
                   COALESCE((SELECT SUM(p.amount) FROM fin_payments p 
                             WHERE p.order_id = o.order_id 
                             AND p.payment_type IN ('rent','additional')
                             AND p.status IN ('completed','confirmed')), 0) as paid_amount,
                   (SELECT p.method FROM fin_payments p 
                    WHERE p.order_id = o.order_id 
                    AND p.payment_type IN ('rent','additional')
                    AND p.status IN ('completed','confirmed')
                    ORDER BY p.occurred_at DESC LIMIT 1) as last_method,
                   (SELECT MAX(p.occurred_at) FROM fin_payments p 
                    WHERE p.order_id = o.order_id 
                    AND p.payment_type IN ('rent','additional')
                    AND p.status IN ('completed','confirmed')) as last_paid_at,
                   (SELECT SUM(p.amount) FROM fin_payments p 
                    WHERE p.order_id = o.order_id 
                    AND p.payment_type IN ('rent','additional')
                    AND p.status IN ('completed','confirmed')
                    AND p.method = 'cash') as paid_cash,
                   (SELECT SUM(p.amount) FROM fin_payments p 
                    WHERE p.order_id = o.order_id 
                    AND p.payment_type IN ('rent','additional')
                    AND p.status IN ('completed','confirmed')
                    AND p.method != 'cash') as paid_bank
            FROM orders o
            LEFT JOIN users u ON u.user_id = o.manager_id
            WHERE o.status NOT IN ('cancelled', 'deleted')
            AND MONTH(o.rental_start_date) = :month AND YEAR(o.rental_start_date) = :year
            ORDER BY o.rental_start_date ASC
        """), {"month": target_month, "year": target_year})
        
        items = []
        total_expected = 0
        total_paid = 0
        total_debt = 0
        
        for r in rows:
            price = float(r[4] or 0)
            discount = float(r[5] or 0)
            service_fee = float(r[6] or 0)
            order_total = price - discount + service_fee
            if order_total <= 0:
                order_total = price
            paid = float(r[10] or 0)
            debt = max(0, order_total - paid)
            
            total_expected += order_total
            total_paid += paid
            total_debt += debt
            
            items.append({
                "order_id": r[0],
                "order_number": r[1],
                "customer_name": r[2],
                "status": r[3],
                "order_total": order_total,
                "paid": paid,
                "debt": debt,
                "rental_start": r[7].isoformat() if r[7] else None,
                "rental_end": r[8].isoformat() if r[8] else None,
                "manager": r[9],
                "payment_status": "paid" if debt == 0 else ("partial" if paid > 0 else "unpaid"),
                "last_method": r[11],
                "last_paid_at": r[12].isoformat() if r[12] else None,
                "paid_cash": float(r[13] or 0),
                "paid_bank": float(r[14] or 0),
            })
        
        return {
            "month": target_month,
            "year": target_year,
            "items": items,
            "summary": {
                "total_expected": total_expected,
                "total_paid": total_paid,
                "total_debt": total_debt,
                "orders_count": len(items),
                "paid_count": sum(1 for i in items if i["payment_status"] == "paid"),
                "unpaid_count": sum(1 for i in items if i["payment_status"] == "unpaid"),
                "partial_count": sum(1 for i in items if i["payment_status"] == "partial"),
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# EVENING CASH SUMMARY (Щовечірнє зведення)
# ============================================================

@router.post("/cash-summary")
async def create_cash_summary(data: dict, db: Session = Depends(get_rh_db)):
    """Зберегти щовечірнє зведення каси: РХ vs ФАКТ"""
    try:
        # Ensure table exists
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS cash_summaries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                system_cash DECIMAL(12,2) NOT NULL DEFAULT 0,
                actual_cash DECIMAL(12,2) NOT NULL DEFAULT 0,
                difference DECIMAL(12,2) NOT NULL DEFAULT 0,
                note TEXT,
                created_by VARCHAR(128),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_date (date)
            )
        """))
        db.commit()
        
        # Calculate system cash balance for today:
        # carry_over from last closed month + current month income - current month expenses
        from datetime import date, datetime
        today = date.today()
        cur_month_start = today.replace(day=1)
        
        # Get carry_over from last closed monthly report
        carry_row = db.execute(text("""
            SELECT report_data FROM monthly_reports
            ORDER BY year DESC, month DESC LIMIT 1
        """)).fetchone()
        carry_over = 0
        if carry_row and carry_row[0]:
            import json
            rd = json.loads(carry_row[0]) if isinstance(carry_row[0], str) else carry_row[0]
            cr = rd.get("cash_register", {})
            carry_over = float(cr.get("closing_balance", 0))
        
        # Current month cash income (rent, additional, late, damage)
        month_cash_in = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments
            WHERE method='cash' AND status IN ('completed','confirmed')
            AND payment_type IN ('rent','additional','late','damage')
            AND occurred_at >= :month_start
        """), {"month_start": cur_month_start}).scalar() or 0
        
        # Current month cash expenses
        month_cash_out = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_expenses
            WHERE method='cash' AND status='posted'
            AND occurred_at >= :month_start
        """), {"month_start": cur_month_start}).scalar() or 0
        
        # Current month cash refunds
        month_cash_refunds = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) FROM fin_payments
            WHERE payment_type IN ('deposit_refund','refund') AND method='cash'
            AND status IN ('completed','confirmed')
            AND occurred_at >= :month_start
        """), {"month_start": cur_month_start}).scalar() or 0
        
        system_cash = carry_over + float(month_cash_in) - float(month_cash_out) - float(month_cash_refunds)
        
        actual_cash = float(data.get("actual_cash", 0))
        difference = actual_cash - system_cash
        
        db.execute(text("""
            INSERT INTO cash_summaries (date, system_cash, actual_cash, difference, note, created_by)
            VALUES (:date, :sys, :actual, :diff, :note, :by)
            ON DUPLICATE KEY UPDATE system_cash=:sys, actual_cash=:actual, difference=:diff, note=:note, created_by=:by
        """), {
            "date": today, "sys": system_cash, "actual": actual_cash,
            "diff": difference, "note": data.get("note", ""),
            "by": data.get("created_by", "")
        })
        db.commit()
        
        return {
            "success": True,
            "date": today.isoformat(),
            "system_cash": system_cash,
            "actual_cash": actual_cash,
            "difference": difference,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cash-summaries")
async def get_cash_summaries(limit: int = 30, db: Session = Depends(get_rh_db)):
    """Історія зведень каси"""
    try:
        db.execute(text("""
            CREATE TABLE IF NOT EXISTS cash_summaries (
                id INT AUTO_INCREMENT PRIMARY KEY,
                date DATE NOT NULL,
                system_cash DECIMAL(12,2) NOT NULL DEFAULT 0,
                actual_cash DECIMAL(12,2) NOT NULL DEFAULT 0,
                difference DECIMAL(12,2) NOT NULL DEFAULT 0,
                note TEXT,
                created_by VARCHAR(128),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY uq_date (date)
            )
        """))
        db.commit()
        
        rows = db.execute(text("""
            SELECT id, date, system_cash, actual_cash, difference, note, created_by, created_at
            FROM cash_summaries ORDER BY date DESC LIMIT :limit
        """), {"limit": limit})
        
        return [
            {
                "id": r[0], "date": r[1].isoformat() if r[1] else None,
                "system_cash": float(r[2]), "actual_cash": float(r[3]),
                "difference": float(r[4]), "note": r[5],
                "created_by": r[6], "created_at": r[7].isoformat() if r[7] else None,
            }
            for r in rows
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# EVENT MANAGERS (Список івент-менеджерів)
# ============================================================

@router.get("/event-managers")
async def list_event_managers(db: Session = Depends(get_rh_db)):
    """Список івент-менеджерів (з клієнтів)"""
    rows = db.execute(text("""
        SELECT em.id, em.client_user_id, em.name, em.is_active
        FROM event_managers em WHERE em.is_active = 1
        ORDER BY em.name
    """))
    return [{"id": r[0], "client_user_id": r[1], "name": r[2]} for r in rows]


@router.get("/available-managers")
async def list_available_managers(q: Optional[str] = None, db: Session = Depends(get_rh_db)):
    """Пошук клієнтів для додавання як івент-менеджерів"""
    query = """
        SELECT cu.id, cu.full_name, cu.phone
        FROM client_users cu
        WHERE cu.id NOT IN (SELECT client_user_id FROM event_managers WHERE is_active = 1)
    """
    params = {}
    if q:
        query += " AND cu.full_name LIKE :q"
        params["q"] = f"%{q}%"
    query += " ORDER BY cu.full_name LIMIT 20"
    rows = db.execute(text(query), params)
    return [{"client_user_id": r[0], "name": r[1], "phone": r[2]} for r in rows]


@router.post("/event-managers")
async def add_event_manager(data: dict, db: Session = Depends(get_rh_db)):
    """Додати івент-менеджера"""
    client_user_id = data.get("client_user_id")
    name = data.get("name", "")
    if not client_user_id:
        raise HTTPException(status_code=400, detail="client_user_id required")
    try:
        db.execute(text("""
            INSERT INTO event_managers (client_user_id, name, is_active) VALUES (:cid, :name, 1)
            ON DUPLICATE KEY UPDATE is_active = 1, name = :name
        """), {"cid": client_user_id, "name": name})
        db.commit()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/event-managers/{client_user_id}")
async def remove_event_manager(client_user_id: int, db: Session = Depends(get_rh_db)):
    """Видалити івент-менеджера"""
    db.execute(text("UPDATE event_managers SET is_active = 0 WHERE client_user_id = :cid"), {"cid": client_user_id})
    db.commit()
    return {"success": True}


# ============================================================
# MANAGER DEBTS (Борги менеджерів)
# ============================================================

@router.get("/manager-debts")
async def get_manager_debts(db: Session = Depends(get_rh_db)):
    """Борги замовлень згруповані по івент-менеджерах (тільки обрані менеджери)"""
    try:
        # Список обраних менеджерів (клієнтів)
        mgr_rows = db.execute(text(
            "SELECT client_user_id, name FROM event_managers WHERE is_active = 1"
        ))
        selected_managers = {r[0]: r[1] for r in mgr_rows}
        
        if not selected_managers:
            return {"managers": [], "total_debt": 0, "managers_count": 0}
        
        mgr_ids = list(selected_managers.keys())
        placeholders = ",".join(str(m) for m in mgr_ids)
        
        rows = db.execute(text(f"""
            SELECT o.order_id, o.order_number, o.customer_name, o.status,
                   o.total_price, o.discount_amount, o.service_fee,
                   o.rental_start_date, o.client_user_id,
                   COALESCE((SELECT SUM(p.amount) FROM fin_payments p 
                             WHERE p.order_id = o.order_id 
                             AND p.payment_type IN ('rent','additional')
                             AND p.status IN ('completed','confirmed')), 0) as paid_amount
            FROM orders o
            WHERE o.status NOT IN ('cancelled', 'deleted')
            AND o.client_user_id IN ({placeholders})
            HAVING paid_amount < (o.total_price - COALESCE(o.discount_amount,0) + COALESCE(o.service_fee,0))
            ORDER BY o.client_user_id, o.rental_start_date
        """))
        
        managers = {}
        for r in rows:
            price = float(r[4] or 0)
            discount = float(r[5] or 0)
            service_fee = float(r[6] or 0)
            order_total = price - discount + service_fee
            if order_total <= 0:
                order_total = price
            paid = float(r[9] or 0)
            debt = max(0, order_total - paid)
            
            if debt <= 0:
                continue
            
            mgr_id = r[8]
            manager_name = selected_managers.get(mgr_id, f"Клієнт #{mgr_id}")
            if manager_name not in managers:
                managers[manager_name] = {"manager": manager_name, "total_debt": 0, "orders": []}
            
            managers[manager_name]["total_debt"] += debt
            managers[manager_name]["orders"].append({
                "order_id": r[0],
                "order_number": r[1],
                "customer_name": r[2],
                "status": r[3],
                "order_total": order_total,
                "paid": paid,
                "debt": debt,
                "rental_start": r[7].isoformat() if r[7] else None,
            })
        
        result = sorted(managers.values(), key=lambda x: -x["total_debt"])
        total_all = sum(m["total_debt"] for m in result)
        
        return {
            "managers": result,
            "total_debt": total_all,
            "managers_count": len(result),
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# EXPENSE REPORT (Звіт по статтях витрат)
# ============================================================

@router.get("/expense-report")
async def get_expense_report(
    period: str = "month",
    category_code: Optional[str] = None,
    parent_code: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Звіт по статтях витрат з фільтрами"""
    try:
        date_filter = ""
        if period == "day":
            date_filter = "AND e.occurred_at >= CURDATE()"
        elif period == "week":
            date_filter = "AND e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)"
        elif period == "month":
            date_filter = "AND MONTH(e.occurred_at) = MONTH(CURDATE()) AND YEAR(e.occurred_at) = YEAR(CURDATE())"
        elif period == "quarter":
            date_filter = "AND e.occurred_at >= DATE_SUB(CURDATE(), INTERVAL 3 MONTH)"
        elif period == "year":
            date_filter = "AND YEAR(e.occurred_at) = YEAR(CURDATE())"
        
        cat_filter = ""
        params = {}
        if category_code:
            cat_filter = "AND c.code = :cat_code"
            params["cat_code"] = category_code
        if parent_code:
            cat_filter = "AND (pc.code = :parent_code OR c.code = :parent_code)"
            params["parent_code"] = parent_code
        
        # Summary by parent category
        group_rows = db.execute(text(f"""
            SELECT COALESCE(pc.code, c.code) as grp_code, COALESCE(pc.name, c.name) as grp_name,
                   SUM(e.amount) as total,
                   COUNT(*) as cnt
            FROM fin_expenses e
            LEFT JOIN fin_categories c ON c.id = e.category_id
            LEFT JOIN fin_categories pc ON pc.id = c.parent_id
            WHERE e.status = 'posted' AND e.expense_type != 'collection'
            {date_filter} {cat_filter}
            GROUP BY grp_code, grp_name
            ORDER BY total DESC
        """), params)
        
        by_group = [{"code": r[0], "name": r[1] or "Без категорії", "total": float(r[2]), "count": r[3]} for r in group_rows]
        
        # Detail by subcategory
        detail_rows = db.execute(text(f"""
            SELECT c.code, c.name, COALESCE(pc.code, c.code) as parent_code, COALESCE(pc.name, c.name) as parent_name,
                   SUM(e.amount) as total, COUNT(*) as cnt
            FROM fin_expenses e
            LEFT JOIN fin_categories c ON c.id = e.category_id
            LEFT JOIN fin_categories pc ON pc.id = c.parent_id
            WHERE e.status = 'posted' AND e.expense_type != 'collection'
            {date_filter} {cat_filter}
            GROUP BY c.code, c.name, parent_code, parent_name
            ORDER BY parent_name, total DESC
        """), params)
        
        by_detail = [{"code": r[0], "name": r[1] or "Без категорії", "parent_code": r[2], "parent_name": r[3], "total": float(r[4]), "count": r[5]} for r in detail_rows]
        
        # Individual expense items
        item_rows = db.execute(text(f"""
            SELECT e.id, e.amount, e.method, e.occurred_at, e.note,
                   c.code as cat_code, c.name as cat_name,
                   COALESCE(pc.code, c.code) as parent_code,
                   COALESCE(pc.name, c.name) as parent_name,
                   e.funding_source
            FROM fin_expenses e
            LEFT JOIN fin_categories c ON c.id = e.category_id
            LEFT JOIN fin_categories pc ON pc.id = c.parent_id
            WHERE e.status = 'posted' AND e.expense_type != 'collection'
            {date_filter} {cat_filter}
            ORDER BY e.occurred_at DESC
        """), params)
        
        items = [{
            "id": r[0], "amount": float(r[1]), "method": r[2], 
            "occurred_at": r[3].isoformat() if r[3] else None,
            "note": r[4] or "",
            "cat_code": r[5], "cat_name": r[6] or "Без категорії",
            "parent_code": r[7], "parent_name": r[8] or "Без категорії",
            "funding_source": r[9],
        } for r in item_rows]
        
        grand_total = sum(g["total"] for g in by_group)
        
        return {
            "period": period,
            "by_group": by_group,
            "by_detail": by_detail,
            "items": items,
            "grand_total": grand_total,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
