"""
Export API - Експорт даних в Excel/CSV
Endpoints для експорту фінансових даних та кейсів шкоди
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional
from datetime import datetime, date
import csv
import io

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/export", tags=["Export"])


def make_csv_response(data: list, filename: str, columns: list) -> StreamingResponse:
    """Create CSV response from data with UTF-8 BOM for Excel compatibility"""
    output = io.StringIO()
    
    # Write UTF-8 BOM for Excel compatibility
    output.write('\ufeff')
    
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    
    # Write header with Ukrainian column names
    writer.writerow(columns)
    
    # Write data rows
    for row in data:
        writer.writerow(row)
    
    output.seek(0)
    
    # Create response with proper headers for download
    response = StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8"
    )
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    
    return response


# ============================================
# FINANCE CONSOLE EXPORTS
# ============================================

@router.get("/ledger")
async def export_ledger(
    month: Optional[str] = None,  # YYYY-MM
    db: Session = Depends(get_rh_db)
):
    """Експорт транзакцій (Ledger) в CSV"""
    
    where_clause = ""
    params = {}
    
    if month:
        where_clause = "WHERE DATE_FORMAT(t.occurred_at, '%Y-%m') = :month"
        params["month"] = month
    
    query = f"""
        SELECT 
            DATE_FORMAT(t.occurred_at, '%Y-%m-%d %H:%i') as date,
            t.tx_type,
            t.amount,
            t.note,
            t.entity_type,
            t.accepted_by_name
        FROM fin_transactions t
        {where_clause}
        ORDER BY t.occurred_at DESC
    """
    
    rows = db.execute(text(query), params).fetchall()
    
    data = []
    for row in rows:
        data.append([
            row[0] or "",  # date
            row[1] or "",  # tx_type
            str(row[2]) if row[2] else "0",  # amount
            row[3] or "",  # note
            row[4] or "",  # entity_type
            row[5] or "",  # accepted_by_name
        ])
    
    columns = ["Дата", "Тип операції", "Сума (₴)", "Примітка", "Тип сутності", "Автор"]
    filename = f"ledger_{month or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return make_csv_response(data, filename, columns)


@router.get("/expenses")
async def export_expenses(
    month: Optional[str] = None,  # YYYY-MM
    db: Session = Depends(get_rh_db)
):
    """Експорт витрат в CSV"""
    
    where_clause = ""
    params = {}
    
    if month:
        where_clause = "WHERE DATE_FORMAT(e.occurred_at, '%Y-%m') = :month"
        params["month"] = month
    
    query = f"""
        SELECT 
            DATE_FORMAT(e.occurred_at, '%Y-%m-%d') as date,
            e.expense_type,
            c.name as category_name,
            e.amount,
            e.method,
            COALESCE(e.funding_source, 'general') as funding_source,
            e.note,
            e.status
        FROM fin_expenses e
        LEFT JOIN fin_categories c ON e.category_id = c.id
        {where_clause}
        ORDER BY e.occurred_at DESC
    """
    
    rows = db.execute(text(query), params).fetchall()
    
    funding_map = {"general": "Каса", "damage_pool": "Бюджет шкоди"}
    method_map = {"cash": "Готівка", "bank": "Безготівка"}
    
    data = []
    for row in rows:
        data.append([
            row[0] or "",  # date
            row[1] or "",  # expense_type
            row[2] or "Без категорії",  # category_name
            str(row[3]) if row[3] else "0",  # amount
            method_map.get(row[4], row[4] or ""),  # method
            funding_map.get(row[5], row[5] or ""),  # funding_source
            row[6] or "",  # note
            row[7] or "",  # status
        ])
    
    columns = ["Дата", "Тип", "Категорія", "Сума (₴)", "Метод", "Джерело", "Примітка", "Статус"]
    filename = f"expenses_{month or 'all'}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return make_csv_response(data, filename, columns)


@router.get("/orders-finance")
async def export_orders_finance(
    status: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Експорт ордерів з фінансовими даними"""
    
    where_clause = "WHERE o.is_archived = FALSE"
    params = {}
    
    if status:
        where_clause += " AND o.status = :status"
        params["status"] = status
    
    query = f"""
        SELECT 
            o.order_number,
            o.status,
            o.customer_name,
            o.customer_phone,
            o.total_price as total_rental,
            o.deposit_amount as total_deposit,
            o.damage_fee,
            DATE_FORMAT(o.created_at, '%Y-%m-%d') as created_date
        FROM orders o
        {where_clause}
        ORDER BY o.created_at DESC
        LIMIT 1000
    """
    
    rows = db.execute(text(query), params).fetchall()
    
    status_map = {
        "draft": "Чернетка",
        "confirmed": "Підтверджено",
        "active": "Активне",
        "returned": "Повернено",
        "completed": "Завершено",
        "cancelled": "Скасовано"
    }
    
    data = []
    for row in rows:
        data.append([
            row[0] or "",  # order_number
            status_map.get(row[1], row[1] or ""),  # status
            row[2] or "",  # customer_name
            row[3] or "",  # customer_phone
            str(row[4]) if row[4] else "0",  # total_rental
            str(row[5]) if row[5] else "0",  # total_deposit
            str(row[6]) if row[6] else "0",  # damage_fee
            row[7] or "",  # created_date
        ])
    
    columns = [
        "Номер ордера", "Статус", "Клієнт", "Телефон", 
        "Оренда (₴)", "Застава (₴)", "Шкода (₴)", "Дата створення"
    ]
    filename = f"orders_finance_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return make_csv_response(data, filename, columns)


# ============================================
# DAMAGE HUB EXPORTS
# ============================================

@router.get("/damage-cases")
async def export_damage_cases(
    status: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Експорт кейсів шкоди"""
    
    where_clause = ""
    params = {}
    
    if status:
        where_clause = "WHERE pdh.processing_status = :status"
        params["status"] = status
    
    query = f"""
        SELECT 
            pdh.order_number,
            pdh.product_name,
            pdh.sku,
            pdh.category,
            pdh.damage_type,
            pdh.severity,
            pdh.fee,
            pdh.processing_type,
            pdh.processing_status,
            pdh.note,
            DATE_FORMAT(pdh.created_at, '%Y-%m-%d') as created_date
        FROM product_damage_history pdh
        {where_clause}
        ORDER BY pdh.created_at DESC
    """
    
    rows = db.execute(text(query), params).fetchall()
    
    processing_type_map = {
        "none": "Не призначено",
        "wash": "Мийка",
        "restoration": "Реставрація",
        "laundry": "Хімчистка"
    }
    
    status_map = {
        "pending": "Очікує",
        "in_progress": "В роботі",
        "completed": "Завершено",
        "failed": "Невдача"
    }
    
    severity_map = {
        "low": "Низька",
        "medium": "Середня",
        "high": "Висока",
        "critical": "Критична"
    }
    
    data = []
    for row in rows:
        data.append([
            row[0] or "",  # order_number
            row[1] or "",  # product_name
            row[2] or "",  # sku
            row[3] or "",  # category
            row[4] or "",  # damage_type
            severity_map.get(row[5], row[5] or ""),  # severity
            str(row[6]) if row[6] else "0",  # fee
            processing_type_map.get(row[7], row[7] or ""),  # processing_type
            status_map.get(row[8], row[8] or ""),  # processing_status
            row[9] or "",  # note
            row[10] or "",  # created_date
        ])
    
    columns = [
        "Номер ордера", "Товар", "SKU", "Категорія", 
        "Тип шкоди", "Серйозність", "Компенсація (₴)",
        "Тип обробки", "Статус", "Примітка", "Дата"
    ]
    filename = f"damage_cases_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return make_csv_response(data, filename, columns)


@router.get("/tasks")
async def export_tasks(
    task_type: Optional[str] = None,  # washing, restoration
    status: Optional[str] = None,
    db: Session = Depends(get_rh_db)
):
    """Експорт задач (мийка, реставрація)"""
    
    where_clauses = []
    params = {}
    
    if task_type:
        where_clauses.append("t.task_type = :task_type")
        params["task_type"] = task_type
    
    if status:
        where_clauses.append("t.status = :status")
        params["status"] = status
    
    where_clause = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""
    
    query = f"""
        SELECT 
            t.id,
            t.task_type,
            t.order_number,
            t.title,
            t.description,
            t.status,
            t.priority,
            t.assigned_to,
            DATE_FORMAT(t.created_at, '%Y-%m-%d') as created_date,
            DATE_FORMAT(t.completed_at, '%Y-%m-%d') as completed_date
        FROM tasks t
        {where_clause}
        ORDER BY t.created_at DESC
    """
    
    rows = db.execute(text(query), params).fetchall()
    
    task_type_map = {
        "washing": "Мийка",
        "restoration": "Реставрація",
        "laundry": "Хімчистка"
    }
    
    status_map = {
        "pending": "Очікує",
        "in_progress": "В роботі",
        "completed": "Завершено",
        "cancelled": "Скасовано"
    }
    
    priority_map = {
        "low": "Низький",
        "normal": "Звичайний",
        "high": "Високий",
        "urgent": "Терміновий"
    }
    
    data = []
    for row in rows:
        data.append([
            str(row[0]) if row[0] else "",  # id
            task_type_map.get(row[1], row[1] or ""),  # task_type
            row[2] or "",  # order_number
            row[3] or "",  # title
            row[4] or "",  # description
            status_map.get(row[5], row[5] or ""),  # status
            priority_map.get(row[6], row[6] or ""),  # priority
            row[7] or "",  # assigned_to
            row[8] or "",  # created_date
            row[9] or "",  # completed_date
        ])
    
    columns = [
        "ID", "Тип", "Ордер", "Назва", "Опис", 
        "Статус", "Пріоритет", "Виконавець", "Створено", "Завершено"
    ]
    
    type_suffix = task_type or "all"
    filename = f"tasks_{type_suffix}_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return make_csv_response(data, filename, columns)


@router.get("/laundry-queue")
async def export_laundry_queue(
    db: Session = Depends(get_rh_db)
):
    """Експорт черги хімчистки з product_damage_history"""
    
    query = """
        SELECT 
            pdh.order_number,
            pdh.product_name,
            pdh.sku,
            pdh.damage_type,
            pdh.processing_status,
            pdh.laundry_batch_id,
            DATE_FORMAT(pdh.created_at, '%Y-%m-%d') as created_date,
            DATE_FORMAT(pdh.sent_to_processing_at, '%Y-%m-%d') as sent_date
        FROM product_damage_history pdh
        WHERE pdh.processing_type = 'laundry'
        ORDER BY pdh.created_at DESC
    """
    
    rows = db.execute(text(query)).fetchall()
    
    status_map = {
        "pending": "В черзі",
        "in_progress": "Відправлено",
        "completed": "Повернуто",
        "failed": "Проблема"
    }
    
    data = []
    for row in rows:
        data.append([
            row[0] or "",  # order_number
            row[1] or "",  # product_name
            row[2] or "",  # sku
            row[3] or "",  # damage_type
            status_map.get(row[4], row[4] or ""),  # processing_status
            row[5] or "",  # laundry_batch_id
            row[6] or "",  # created_date
            row[7] or "",  # sent_date
        ])
    
    columns = [
        "Ордер", "Товар", "SKU", "Тип шкоди", "Статус", "Партія", "Створено", "Відправлено"
    ]
    filename = f"laundry_queue_{datetime.now().strftime('%Y%m%d')}.csv"
    
    return make_csv_response(data, filename, columns)
