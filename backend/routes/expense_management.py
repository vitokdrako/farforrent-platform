"""
Expense Management API - Шаблони, планові платежі, витрати
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from database_rentalhub import get_rh_db
from datetime import datetime, date, timedelta
from typing import Optional
from pydantic import BaseModel

router = APIRouter(prefix="/api/expense-management", tags=["expense-management"])


# ============================================
# EXPENSE TEMPLATES
# ============================================

class TemplateCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    amount: float
    frequency: str = "monthly"  # once, daily, weekly, monthly, quarterly, yearly
    day_of_month: int = 1
    funding_source: str = "general"  # general, damage_pool
    vendor_name: Optional[str] = None


@router.get("/templates")
async def list_templates(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_rh_db)
):
    """Отримати всі шаблони витрат"""
    sql = """
        SELECT 
            t.id, t.name, t.description, t.category_id, t.amount, 
            t.frequency, t.day_of_month, t.funding_source, t.vendor_name,
            t.is_active, t.created_at,
            c.name as category_name, c.code as category_code
        FROM expense_templates t
        LEFT JOIN fin_categories c ON t.category_id = c.id
        WHERE 1=1
    """
    params = {}
    
    if is_active is not None:
        sql += " AND t.is_active = :is_active"
        params["is_active"] = is_active
    
    sql += " ORDER BY t.name"
    
    result = db.execute(text(sql), params)
    templates = []
    
    for row in result:
        templates.append({
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "category_id": row[3],
            "amount": float(row[4]) if row[4] else 0,
            "frequency": row[5],
            "day_of_month": row[6],
            "funding_source": row[7],
            "vendor_name": row[8],
            "is_active": bool(row[9]),
            "created_at": str(row[10]) if row[10] else None,
            "category_name": row[11],
            "category_code": row[12]
        })
    
    return {"templates": templates}


@router.post("/templates")
async def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_rh_db)
):
    """Створити новий шаблон витрати"""
    try:
        db.execute(text("""
            INSERT INTO expense_templates 
            (name, description, category_id, amount, frequency, day_of_month, funding_source, vendor_name, is_active)
            VALUES (:name, :description, :category_id, :amount, :frequency, :day_of_month, :funding_source, :vendor_name, TRUE)
        """), {
            "name": data.name,
            "description": data.description,
            "category_id": data.category_id,
            "amount": data.amount,
            "frequency": data.frequency,
            "day_of_month": data.day_of_month,
            "funding_source": data.funding_source,
            "vendor_name": data.vendor_name
        })
        
        template_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        
        return {"success": True, "template_id": template_id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """Оновити шаблон"""
    try:
        updates = []
        params = {"id": template_id}
        
        fields = ["name", "description", "category_id", "amount", "frequency", 
                  "day_of_month", "funding_source", "vendor_name", "is_active"]
        
        for field in fields:
            if field in data:
                updates.append(f"{field} = :{field}")
                params[field] = data[field]
        
        if updates:
            sql = f"UPDATE expense_templates SET {', '.join(updates)} WHERE id = :id"
            db.execute(text(sql), params)
            db.commit()
        
        return {"success": True}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    db: Session = Depends(get_rh_db)
):
    """Видалити шаблон"""
    try:
        db.execute(text("DELETE FROM expense_templates WHERE id = :id"), {"id": template_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# DUE ITEMS (Заплановані платежі)
# ============================================

class DueItemCreate(BaseModel):
    template_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    category_id: Optional[int] = None
    amount: float
    due_date: str  # YYYY-MM-DD
    funding_source: str = "general"
    vendor_name: Optional[str] = None


@router.get("/due-items")
async def list_due_items(
    status: Optional[str] = None,
    month: Optional[str] = None,  # YYYY-MM
    db: Session = Depends(get_rh_db)
):
    """Отримати заплановані платежі"""
    sql = """
        SELECT 
            d.id, d.template_id, d.name, d.description, d.category_id, d.amount,
            d.due_date, d.funding_source, d.vendor_name, d.status, d.paid_at,
            d.expense_id, d.created_at,
            c.name as category_name, c.code as category_code
        FROM expense_due_items d
        LEFT JOIN fin_categories c ON d.category_id = c.id
        WHERE 1=1
    """
    params = {}
    
    if status:
        sql += " AND d.status = :status"
        params["status"] = status
    
    if month:
        sql += " AND DATE_FORMAT(d.due_date, '%Y-%m') = :month"
        params["month"] = month
    
    sql += " ORDER BY d.due_date, d.name"
    
    result = db.execute(text(sql), params)
    items = []
    
    for row in result:
        due_date = row[6]
        is_overdue = due_date < date.today() if due_date and row[9] == 'pending' else False
        
        items.append({
            "id": row[0],
            "template_id": row[1],
            "name": row[2],
            "description": row[3],
            "category_id": row[4],
            "amount": float(row[5]) if row[5] else 0,
            "due_date": str(due_date) if due_date else None,
            "funding_source": row[7],
            "vendor_name": row[8],
            "status": row[9],
            "paid_at": str(row[10]) if row[10] else None,
            "expense_id": row[11],
            "created_at": str(row[12]) if row[12] else None,
            "category_name": row[13],
            "category_code": row[14],
            "is_overdue": is_overdue
        })
    
    # Update overdue status
    db.execute(text("""
        UPDATE expense_due_items 
        SET status = 'overdue' 
        WHERE status = 'pending' AND due_date < CURDATE()
    """))
    db.commit()
    
    return {"due_items": items}


@router.post("/due-items")
async def create_due_item(
    data: DueItemCreate,
    db: Session = Depends(get_rh_db)
):
    """Створити запланований платіж"""
    try:
        db.execute(text("""
            INSERT INTO expense_due_items 
            (template_id, name, description, category_id, amount, due_date, funding_source, vendor_name, status)
            VALUES (:template_id, :name, :description, :category_id, :amount, :due_date, :funding_source, :vendor_name, 'pending')
        """), {
            "template_id": data.template_id,
            "name": data.name,
            "description": data.description,
            "category_id": data.category_id,
            "amount": data.amount,
            "due_date": data.due_date,
            "funding_source": data.funding_source,
            "vendor_name": data.vendor_name
        })
        
        item_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        db.commit()
        
        return {"success": True, "due_item_id": item_id}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/due-items/generate")
async def generate_due_items(
    month: str,  # YYYY-MM
    db: Session = Depends(get_rh_db)
):
    """Згенерувати планові платежі з шаблонів на місяць"""
    try:
        year, month_num = map(int, month.split('-'))
        
        # Get active templates
        templates = db.execute(text("""
            SELECT id, name, description, category_id, amount, frequency, day_of_month, funding_source, vendor_name
            FROM expense_templates
            WHERE is_active = TRUE
        """)).fetchall()
        
        created = 0
        
        for t in templates:
            template_id, name, description, category_id, amount, frequency, day_of_month, funding_source, vendor_name = t
            
            # Calculate due dates based on frequency
            due_dates = []
            
            if frequency == 'monthly':
                # One payment per month
                day = min(day_of_month, 28)  # Handle months with fewer days
                due_dates.append(date(year, month_num, day))
                
            elif frequency == 'weekly':
                # Every week
                first_day = date(year, month_num, 1)
                last_day = date(year, month_num + 1, 1) - timedelta(days=1) if month_num < 12 else date(year + 1, 1, 1) - timedelta(days=1)
                current = first_day
                while current <= last_day:
                    due_dates.append(current)
                    current += timedelta(weeks=1)
                    
            elif frequency == 'quarterly':
                # Only if it's the quarter month
                if month_num in [1, 4, 7, 10]:
                    day = min(day_of_month, 28)
                    due_dates.append(date(year, month_num, day))
                    
            elif frequency == 'yearly':
                # Only in January
                if month_num == 1:
                    day = min(day_of_month, 28)
                    due_dates.append(date(year, month_num, day))
            
            # Create due items
            for due_date in due_dates:
                # Check if already exists
                existing = db.execute(text("""
                    SELECT id FROM expense_due_items 
                    WHERE template_id = :template_id AND due_date = :due_date
                """), {"template_id": template_id, "due_date": due_date}).fetchone()
                
                if not existing:
                    db.execute(text("""
                        INSERT INTO expense_due_items 
                        (template_id, name, description, category_id, amount, due_date, funding_source, vendor_name, status)
                        VALUES (:template_id, :name, :description, :category_id, :amount, :due_date, :funding_source, :vendor_name, 'pending')
                    """), {
                        "template_id": template_id,
                        "name": name,
                        "description": description,
                        "category_id": category_id,
                        "amount": amount,
                        "due_date": due_date,
                        "funding_source": funding_source,
                        "vendor_name": vendor_name
                    })
                    created += 1
        
        db.commit()
        
        return {"success": True, "created": created, "month": month}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/due-items/{item_id}/pay")
async def pay_due_item(
    item_id: int,
    data: dict,
    db: Session = Depends(get_rh_db)
):
    """Оплатити запланований платіж"""
    try:
        # Get due item
        item = db.execute(text("""
            SELECT name, description, category_id, amount, funding_source, vendor_name
            FROM expense_due_items WHERE id = :id AND status IN ('pending', 'overdue')
        """), {"id": item_id}).fetchone()
        
        if not item:
            raise HTTPException(status_code=404, detail="Платіж не знайдено або вже оплачено")
        
        name, description, category_id, amount, funding_source, vendor_name = item
        method = data.get("method", "cash")
        
        # Create expense record
        db.execute(text("""
            INSERT INTO fin_expenses 
            (expense_type, category_id, amount, method, note, funding_source, due_item_id, status, occurred_at)
            VALUES ('expense', :category_id, :amount, :method, :note, :funding_source, :due_item_id, 'posted', NOW())
        """), {
            "category_id": category_id,
            "amount": amount,
            "method": method,
            "note": f"{name}: {description}" if description else name,
            "funding_source": funding_source,
            "due_item_id": item_id
        })
        
        expense_id = db.execute(text("SELECT LAST_INSERT_ID()")).fetchone()[0]
        
        # Update due item status
        db.execute(text("""
            UPDATE expense_due_items 
            SET status = 'paid', paid_at = NOW(), expense_id = :expense_id
            WHERE id = :id
        """), {"id": item_id, "expense_id": expense_id})
        
        # TODO: Create ledger entry here if needed
        # post_transaction(db, "expense", ...)
        
        db.commit()
        
        return {"success": True, "expense_id": expense_id}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/due-items/{item_id}/cancel")
async def cancel_due_item(
    item_id: int,
    db: Session = Depends(get_rh_db)
):
    """Скасувати запланований платіж"""
    try:
        db.execute(text("""
            UPDATE expense_due_items SET status = 'cancelled' WHERE id = :id
        """), {"id": item_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/due-items/{item_id}")
async def delete_due_item(
    item_id: int,
    db: Session = Depends(get_rh_db)
):
    """Видалити запланований платіж"""
    try:
        db.execute(text("DELETE FROM expense_due_items WHERE id = :id"), {"id": item_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# EXPENSE RECORDS (Записи витрат)
# ============================================

@router.get("/expenses")
async def list_expenses(
    month: Optional[str] = None,  # YYYY-MM
    funding_source: Optional[str] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_rh_db)
):
    """Отримати записи витрат"""
    sql = """
        SELECT 
            e.id, e.expense_type, e.category_id, e.amount, e.method, 
            e.note, e.funding_source, e.due_item_id, e.status, 
            e.occurred_at, e.created_at,
            c.name as category_name, c.code as category_code
        FROM fin_expenses e
        LEFT JOIN fin_categories c ON e.category_id = c.id
        WHERE 1=1
    """
    params = {}
    
    if month:
        sql += " AND DATE_FORMAT(e.occurred_at, '%Y-%m') = :month"
        params["month"] = month
    
    if funding_source:
        sql += " AND e.funding_source = :funding_source"
        params["funding_source"] = funding_source
    
    if category_id:
        sql += " AND e.category_id = :category_id"
        params["category_id"] = category_id
    
    sql += " ORDER BY e.occurred_at DESC, e.id DESC"
    
    result = db.execute(text(sql), params)
    expenses = []
    
    for row in result:
        expenses.append({
            "id": row[0],
            "expense_type": row[1],
            "category_id": row[2],
            "amount": float(row[3]) if row[3] else 0,
            "method": row[4],
            "note": row[5],
            "funding_source": row[6] or 'general',
            "due_item_id": row[7],
            "status": row[8],
            "occurred_at": str(row[9]) if row[9] else None,
            "created_at": str(row[10]) if row[10] else None,
            "category_name": row[11],
            "category_code": row[12]
        })
    
    # Calculate totals
    total = sum(e["amount"] for e in expenses)
    general_total = sum(e["amount"] for e in expenses if e["funding_source"] == 'general')
    damage_total = sum(e["amount"] for e in expenses if e["funding_source"] == 'damage_pool')
    
    return {
        "expenses": expenses,
        "totals": {
            "total": total,
            "general": general_total,
            "damage_pool": damage_total
        }
    }


# ============================================
# DASHBOARD / SUMMARY
# ============================================

@router.get("/summary")
async def get_expense_summary(
    month: Optional[str] = None,  # YYYY-MM
    db: Session = Depends(get_rh_db)
):
    """Зведення по витратах"""
    if not month:
        month = datetime.now().strftime('%Y-%m')
    
    # Due items stats
    due_stats = db.execute(text("""
        SELECT 
            status,
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total
        FROM expense_due_items
        WHERE DATE_FORMAT(due_date, '%Y-%m') = :month
        GROUP BY status
    """), {"month": month}).fetchall()
    
    due_summary = {"pending": 0, "paid": 0, "overdue": 0, "cancelled": 0}
    due_amounts = {"pending": 0, "paid": 0, "overdue": 0, "cancelled": 0}
    
    for row in due_stats:
        status, count, total = row
        due_summary[status] = count
        due_amounts[status] = float(total)
    
    # Expenses by category
    category_stats = db.execute(text("""
        SELECT 
            c.name,
            c.code,
            COUNT(*) as count,
            COALESCE(SUM(e.amount), 0) as total
        FROM fin_expenses e
        LEFT JOIN fin_categories c ON e.category_id = c.id
        WHERE DATE_FORMAT(e.occurred_at, '%Y-%m') = :month
        GROUP BY c.id, c.name, c.code
        ORDER BY total DESC
    """), {"month": month}).fetchall()
    
    by_category = []
    for row in category_stats:
        by_category.append({
            "name": row[0] or "Без категорії",
            "code": row[1],
            "count": row[2],
            "total": float(row[3])
        })
    
    # Expenses by funding source
    funding_stats = db.execute(text("""
        SELECT 
            COALESCE(funding_source, 'general') as source,
            COUNT(*) as count,
            COALESCE(SUM(amount), 0) as total
        FROM fin_expenses
        WHERE DATE_FORMAT(occurred_at, '%Y-%m') = :month
        GROUP BY funding_source
    """), {"month": month}).fetchall()
    
    by_funding = {"general": 0, "damage_pool": 0}
    for row in funding_stats:
        source, count, total = row
        by_funding[source or 'general'] = float(total)
    
    return {
        "month": month,
        "due_items": {
            "counts": due_summary,
            "amounts": due_amounts,
            "total_pending": due_amounts["pending"] + due_amounts["overdue"]
        },
        "expenses": {
            "by_category": by_category,
            "by_funding": by_funding,
            "total": sum(by_funding.values())
        }
    }
