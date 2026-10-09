"""
Analytics API - Фінансові звіти та аналітика
Підтримує: звіти по замовленнях, товарах, клієнтах, пошкодженнях
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from database_rentalhub import get_rh_db
from datetime import datetime, timedelta
import json

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

def get_date_range(period: str = "month"):
    """Отримати діапазон дат для періоду"""
    today = datetime.now().date()
    
    if period == "7d":
        start = today - timedelta(days=7)
    elif period == "30d":
        start = today - timedelta(days=30)
    elif period == "prev_month":
        first_this_month = today.replace(day=1)
        last_prev_month = first_this_month - timedelta(days=1)
        start = last_prev_month.replace(day=1)
        today = last_prev_month
    elif period == "month":
        start = today.replace(day=1)
    elif period == "quarter":
        quarter = (today.month - 1) // 3
        start = today.replace(month=quarter * 3 + 1, day=1)
    elif period == "year":
        start = today.replace(month=1, day=1)
    else:
        if ":" in period:
            parts = period.split(":")
            start = datetime.strptime(parts[0], "%Y-%m-%d").date()
            today = datetime.strptime(parts[1], "%Y-%m-%d").date()
        else:
            start = today - timedelta(days=30)
    
    return start, today


# ================== ORDER DAMAGE FEE ==================

@router.get("/order-damage-fee/{order_id}")
async def get_order_damage_fee(
    order_id: int,
    db: Session = Depends(get_rh_db)
):
    """
    Отримати суму шкод для замовлення з product_damage_history.
    Використовується в фінансовому кабінеті для показу "Потребує доплати"
    """
    try:
        result = db.execute(text("""
            SELECT 
                COALESCE(SUM(fee), 0) as total_damage_fee,
                COUNT(*) as damage_count
            FROM product_damage_history
            WHERE order_id = :order_id
        """), {"order_id": order_id})
        
        row = result.fetchone()
        total_damage_fee = float(row[0]) if row else 0
        damage_count = row[1] if row else 0
        
        paid_result = db.execute(text("""
            SELECT COALESCE(SUM(amount), 0) as paid
            FROM fin_payments
            WHERE order_id = :order_id AND payment_type = 'damage'
        """), {"order_id": order_id})
        paid_row = paid_result.fetchone()
        paid_damage = float(paid_row[0]) if paid_row else 0
        
        due_amount = max(0, total_damage_fee - paid_damage)
        
        details_result = db.execute(text("""
            SELECT product_name, damage_type, fee, qty, created_at
            FROM product_damage_history
            WHERE order_id = :order_id
            ORDER BY created_at DESC
        """), {"order_id": order_id})
        
        damage_items = []
        for r in details_result:
            damage_items.append({
                "product_name": r[0],
                "damage_type": r[1],
                "fee": float(r[2]) if r[2] else 0,
                "qty": r[3] or 1,
                "created_at": r[4].isoformat() if r[4] else None
            })
        
        return {
            "order_id": order_id,
            "total_damage_fee": total_damage_fee,
            "paid_damage": paid_damage,
            "due_amount": due_amount,
            "damage_count": damage_count,
            "needs_payment": due_amount > 0,
            "damage_items": damage_items
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ================== OVERVIEW DASHBOARD ==================

@router.get("/overview")
async def get_overview(
    period: str = Query("month"),
    db: Session = Depends(get_rh_db)
):
    """Головний дашборд - огляд всіх ключових метрик"""
    start_date, end_date = get_date_range(period)
    
    try:
        revenue_result = db.execute(text("""
            SELECT 
                COALESCE(SUM(CASE WHEN status IN ('issued', 'on_rent', 'returned', 'closed') 
                    THEN total_price ELSE 0 END), 0) as rent_revenue,
                COUNT(CASE WHEN status IN ('issued', 'on_rent', 'returned', 'closed') THEN 1 END) as completed_orders,
                COUNT(*) as total_orders
            FROM orders 
            WHERE DATE(created_at) BETWEEN :start AND :end
        """), {"start": start_date, "end": end_date})
        revenue = revenue_result.fetchone()
        
        damage_result = db.execute(text("""
            SELECT COALESCE(SUM(fee), 0) as damage_revenue
            FROM product_damage_history
            WHERE DATE(created_at) BETWEEN :start AND :end
        """), {"start": start_date, "end": end_date})
        damage_rev = damage_result.fetchone()
        
        status_result = db.execute(text("""
            SELECT status, COUNT(*) as cnt
            FROM orders
            WHERE DATE(created_at) BETWEEN :start AND :end
            GROUP BY status
        """), {"start": start_date, "end": end_date})
        status_counts = {row[0]: row[1] for row in status_result}
        
        avg_result = db.execute(text("""
            SELECT COALESCE(AVG(total_price), 0) as avg_rent
            FROM orders 
            WHERE status IN ('issued', 'on_rent', 'returned', 'closed')
            AND DATE(created_at) BETWEEN :start AND :end
        """), {"start": start_date, "end": end_date})
        avg_data = avg_result.fetchone()
        
        avg_damage_result = db.execute(text("""
            SELECT COALESCE(AVG(fee), 0) as avg_damage, COUNT(DISTINCT order_id) as damaged_orders
            FROM product_damage_history
            WHERE DATE(created_at) BETWEEN :start AND :end AND fee > 0
        """), {"start": start_date, "end": end_date})
        avg_damage = avg_damage_result.fetchone()
        
        daily_result = db.execute(text("""
            SELECT DATE(created_at) as day, COALESCE(SUM(total_price), 0) as rent
            FROM orders
            WHERE DATE(created_at) BETWEEN :start AND :end
            AND status IN ('issued', 'on_rent', 'returned', 'closed')
            GROUP BY DATE(created_at)
            ORDER BY day
        """), {"start": start_date, "end": end_date})
        daily_rent = [{"day": str(row[0]), "rent": float(row[1])} for row in daily_result]
        
        daily_damage_result = db.execute(text("""
            SELECT DATE(created_at) as day, COALESCE(SUM(fee), 0) as damage
            FROM product_damage_history
            WHERE DATE(created_at) BETWEEN :start AND :end
            GROUP BY DATE(created_at)
            ORDER BY day
        """), {"start": start_date, "end": end_date})
        daily_damage = {str(row[0]): float(row[1]) for row in daily_damage_result}
        
        for item in daily_rent:
            item["damage"] = daily_damage.get(item["day"], 0)
        
        rent_revenue = float(revenue[0]) if revenue else 0
        damage_revenue = float(damage_rev[0]) if damage_rev else 0
        
        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "kpi": {
                "total_revenue": rent_revenue + damage_revenue,
                "rent_revenue": rent_revenue,
                "damage_revenue": damage_revenue,
                "total_orders": revenue[2] if revenue else 0,
                "completed_orders": revenue[1] if revenue else 0,
                "avg_rent_check": float(avg_data[0]) if avg_data else 0,
                "avg_damage_check": float(avg_damage[0]) if avg_damage else 0,
                "damaged_orders": avg_damage[1] if avg_damage else 0,
                "damage_percent": round(damage_revenue / rent_revenue * 100, 1) if rent_revenue > 0 else 0
            },
            "orders_by_status": status_counts,
            "daily_chart": daily_rent
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ================== ORDERS REPORT ==================

@router.get("/orders")
async def get_orders_report(
    period: str = Query("month"),
    group_by: str = Query("day"),
    db: Session = Depends(get_rh_db)
):
    """Звіт по замовленнях: виручка, кількість, середній чек"""
    start_date, end_date = get_date_range(period)
    
    date_format = {"day": "%Y-%m-%d", "week": "%Y-%u", "month": "%Y-%m"}.get(group_by, "%Y-%m-%d")
    
    try:
        result = db.execute(text("""
            SELECT 
                DATE_FORMAT(created_at, :fmt) as period,
                COUNT(*) as orders_count,
                COALESCE(SUM(CASE WHEN status IN ('issued','on_rent','returned','closed') 
                    THEN total_price ELSE 0 END), 0) as rent_revenue,
                COALESCE(AVG(CASE WHEN status IN ('issued','on_rent','returned','closed') 
                    THEN total_price END), 0) as avg_check
            FROM orders
            WHERE DATE(created_at) BETWEEN :start AND :end
            GROUP BY DATE_FORMAT(created_at, :fmt)
            ORDER BY period
        """), {"start": start_date, "end": end_date, "fmt": date_format})
        
        data = [{"period": row[0], "orders_count": row[1], "rent_revenue": float(row[2]), "avg_check": float(row[3])} for row in result]
        
        totals_result = db.execute(text("""
            SELECT COUNT(*) as total_orders,
                COALESCE(SUM(CASE WHEN status IN ('issued','on_rent','returned','closed') THEN total_price ELSE 0 END), 0) as total_rent,
                COALESCE(AVG(CASE WHEN status IN ('issued','on_rent','returned','closed') THEN total_price END), 0) as avg_check,
                COUNT(CASE WHEN status = 'closed' THEN 1 END) as closed
            FROM orders WHERE DATE(created_at) BETWEEN :start AND :end
        """), {"start": start_date, "end": end_date})
        totals = totals_result.fetchone()
        
        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "group_by": group_by,
            "data": data,
            "totals": {
                "orders": totals[0],
                "rent_revenue": float(totals[1]),
                "avg_check": float(totals[2]),
                "by_status": {"closed": totals[3]}
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ================== PRODUCTS REPORT ==================

@router.get("/products")
async def get_products_report(
    period: str = Query("month"),
    sort_by: str = Query("revenue"),
    limit: int = Query(20),
    db: Session = Depends(get_rh_db)
):
    """Звіт по товарах: ROI, найприбутковіші, простоюючі"""
    start_date, end_date = get_date_range(period)
    
    try:
        result = db.execute(text("""
            SELECT 
                oi.product_id,
                p.name as product_name,
                p.sku,
                p.price as buy_price,
                COUNT(DISTINCT oi.order_id) as rental_count,
                COALESCE(SUM(oi.price * oi.quantity), 0) as rent_revenue,
                COALESCE((SELECT SUM(fee) FROM product_damage_history WHERE product_id = oi.product_id AND DATE(created_at) BETWEEN :start AND :end), 0) as damage_cost
            FROM order_items oi
            JOIN orders o ON oi.order_id = o.order_id
            LEFT JOIN products p ON oi.product_id = p.product_id
            WHERE DATE(o.created_at) BETWEEN :start AND :end AND o.status IN ('issued', 'on_rent', 'returned', 'closed')
            GROUP BY oi.product_id, p.name, p.sku, p.price
            ORDER BY rent_revenue DESC
            LIMIT :limit
        """), {"start": start_date, "end": end_date, "limit": limit})
        
        top_products = []
        for row in result:
            buy_price = float(row[3]) if row[3] else 1
            rent_revenue = float(row[5])
            damage_cost = float(row[6])
            profit = rent_revenue - damage_cost
            roi = round((profit / buy_price) * 100, 1) if buy_price > 0 else 0
            
            top_products.append({
                "product_id": row[0], "name": row[1] or f"Товар #{row[0]}", "sku": row[2],
                "rental_count": row[4], "rent_revenue": rent_revenue, "damage_cost": damage_cost,
                "profit": profit, "roi": roi
            })
        
        if sort_by == "roi":
            top_products.sort(key=lambda x: x["roi"], reverse=True)
        elif sort_by == "rentals":
            top_products.sort(key=lambda x: x["rental_count"], reverse=True)
        
        idle_result = db.execute(text("""
            SELECT p.product_id, p.name, p.sku, p.price, p.last_rented_date,
                DATEDIFF(NOW(), COALESCE(p.last_rented_date, p.created_at)) as days_idle
            FROM products p
            WHERE p.product_id NOT IN (
                SELECT DISTINCT oi.product_id FROM order_items oi
                JOIN orders o ON oi.order_id = o.order_id
                WHERE DATE(o.created_at) BETWEEN :start AND :end
            ) AND p.status = 'active'
            ORDER BY days_idle DESC LIMIT 20
        """), {"start": start_date, "end": end_date})
        
        idle_products = [{"product_id": row[0], "name": row[1] or f"Товар #{row[0]}", "sku": row[2], 
                         "price": float(row[3]) if row[3] else 0, "last_rented": str(row[4]) if row[4] else "Ніколи",
                         "days_idle": row[5] or 0} for row in idle_result]
        
        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "top_products": top_products[:limit],
            "idle_products": idle_products,
            "summary": {
                "total_rent_revenue": sum(p["rent_revenue"] for p in top_products),
                "total_damage_cost": sum(p["damage_cost"] for p in top_products),
                "avg_roi": round(sum(p["roi"] for p in top_products) / len(top_products), 1) if top_products else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ================== CLIENTS REPORT ==================

@router.get("/clients")
async def get_clients_report(
    period: str = Query("month"),
    limit: int = Query(20),
    db: Session = Depends(get_rh_db)
):
    """Звіт по клієнтах: топ по витратах, нові vs повторні"""
    start_date, end_date = get_date_range(period)
    
    try:
        result = db.execute(text("""
            SELECT c.client_id, c.name as client_name, c.phone, COUNT(o.order_id) as orders_count,
                COALESCE(SUM(o.total_price), 0) as rent_spent,
                COALESCE((SELECT SUM(fee) FROM product_damage_history pdh JOIN orders o2 ON pdh.order_id = o2.order_id 
                    WHERE o2.customer_id = c.client_id AND DATE(pdh.created_at) BETWEEN :start AND :end), 0) as damage_spent,
                MIN(o.created_at) as first_order
            FROM clients c
            JOIN orders o ON o.customer_id = c.client_id
            WHERE DATE(o.created_at) BETWEEN :start AND :end
            GROUP BY c.client_id, c.name, c.phone
            ORDER BY rent_spent DESC LIMIT :limit
        """), {"start": start_date, "end": end_date, "limit": limit})
        
        top_clients = [{"client_id": row[0], "name": row[1], "phone": row[2], "orders_count": row[3],
                       "rent_spent": float(row[4]), "damage_spent": float(row[5]), 
                       "total_spent": float(row[4]) + float(row[5]), "first_order": str(row[6]) if row[6] else None} for row in result]
        
        new_vs_returning = db.execute(text("""
            SELECT CASE WHEN (SELECT COUNT(*) FROM orders o2 WHERE o2.customer_id = o.customer_id AND o2.created_at < :start) = 0 
                THEN 'new' ELSE 'returning' END as client_type,
                COUNT(DISTINCT o.customer_id) as client_count, COALESCE(AVG(o.total_price), 0) as avg_check
            FROM orders o WHERE DATE(o.created_at) BETWEEN :start AND :end GROUP BY client_type
        """), {"start": start_date, "end": end_date})
        
        client_types = {"new": {"count": 0, "avg_check": 0}, "returning": {"count": 0, "avg_check": 0}}
        for row in new_vs_returning:
            client_types[row[0]] = {"count": row[1], "avg_check": float(row[2])}
        
        total_clients = client_types["new"]["count"] + client_types["returning"]["count"]
        
        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "top_clients": top_clients,
            "client_analysis": {
                "new_clients": client_types["new"]["count"],
                "returning_clients": client_types["returning"]["count"],
                "returning_percent": round(client_types["returning"]["count"] / total_clients * 100, 1) if total_clients > 0 else 0,
                "new_avg_check": client_types["new"]["avg_check"],
                "returning_avg_check": client_types["returning"]["avg_check"]
            },
            "summary": {"total_clients": total_clients, "total_spent": sum(c["total_spent"] for c in top_clients)}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ================== DAMAGE REPORT ==================

@router.get("/damage")
async def get_damage_report(
    period: str = Query("month"),
    limit: int = Query(20),
    db: Session = Depends(get_rh_db)
):
    """Звіт по пошкодженнях: загальна сума, топ товарів"""
    start_date, end_date = get_date_range(period)
    
    try:
        totals_result = db.execute(text("""
            SELECT COUNT(*) as damage_count, COALESCE(SUM(fee), 0) as total_damage,
                COALESCE(AVG(fee), 0) as avg_damage, COUNT(DISTINCT product_id) as products_damaged,
                COUNT(DISTINCT order_id) as orders_affected
            FROM product_damage_history WHERE DATE(created_at) BETWEEN :start AND :end
        """), {"start": start_date, "end": end_date})
        totals = totals_result.fetchone()
        
        rent_result = db.execute(text("""
            SELECT COALESCE(SUM(total_price), 0) as rent_revenue FROM orders
            WHERE DATE(created_at) BETWEEN :start AND :end AND status IN ('issued', 'on_rent', 'returned', 'closed')
        """), {"start": start_date, "end": end_date})
        rent_revenue = float(rent_result.fetchone()[0])
        
        total_damage = float(totals[1])
        damage_percent = round(total_damage / rent_revenue * 100, 1) if rent_revenue > 0 else 0
        
        products_result = db.execute(text("""
            SELECT pdh.product_id, pdh.product_name, pdh.sku, COUNT(*) as damage_count, SUM(pdh.fee) as total_fee,
                COALESCE((SELECT SUM(oi.price * oi.quantity) FROM order_items oi JOIN orders o ON oi.order_id = o.order_id
                    WHERE oi.product_id = pdh.product_id AND DATE(o.created_at) BETWEEN :start AND :end), 0) as product_revenue
            FROM product_damage_history pdh WHERE DATE(pdh.created_at) BETWEEN :start AND :end
            GROUP BY pdh.product_id, pdh.product_name, pdh.sku ORDER BY total_fee DESC LIMIT :limit
        """), {"start": start_date, "end": end_date, "limit": limit})
        
        damaged_products = []
        for row in products_result:
            product_revenue = float(row[5])
            product_damage = float(row[4])
            damaged_products.append({
                "product_id": row[0], "name": row[1] or f"Товар #{row[0]}", "sku": row[2],
                "damage_count": row[3], "total_fee": product_damage, "revenue": product_revenue,
                "damage_ratio": round(product_damage / product_revenue * 100, 1) if product_revenue > 0 else 100
            })
        
        by_type_result = db.execute(text("""
            SELECT damage_type, COUNT(*) as cnt, SUM(fee) as total FROM product_damage_history
            WHERE DATE(created_at) BETWEEN :start AND :end GROUP BY damage_type ORDER BY total DESC
        """), {"start": start_date, "end": end_date})
        by_type = [{"type": row[0], "count": row[1], "total": float(row[2])} for row in by_type_result]
        
        daily_result = db.execute(text("""
            SELECT DATE(created_at) as day, COUNT(*) as cnt, SUM(fee) as total FROM product_damage_history
            WHERE DATE(created_at) BETWEEN :start AND :end GROUP BY DATE(created_at) ORDER BY day
        """), {"start": start_date, "end": end_date})
        daily_trend = [{"day": str(row[0]), "count": row[1], "total": float(row[2])} for row in daily_result]
        
        return {
            "period": {"start": str(start_date), "end": str(end_date)},
            "kpi": {
                "total_damage": total_damage, "damage_count": totals[0], "avg_damage": float(totals[2]),
                "products_damaged": totals[3], "orders_affected": totals[4], "rent_revenue": rent_revenue,
                "damage_percent": damage_percent, "is_critical": damage_percent > 10
            },
            "damaged_products": damaged_products,
            "by_type": by_type,
            "daily_trend": daily_trend
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


# ================== EXPORT ==================

@router.get("/export/{report_type}")
async def export_report(
    report_type: str,
    period: str = Query("month"),
    format: str = Query("csv"),
    db: Session = Depends(get_rh_db)
):
    """Експорт звіту у CSV або JSON"""
    from fastapi.responses import Response
    import csv
    import io
    
    start_date, end_date = get_date_range(period)
    
    try:
        if report_type == "orders":
            result = db.execute(text("""
                SELECT o.order_number, o.customer_name, o.status, o.total_price, o.created_at
                FROM orders o WHERE DATE(o.created_at) BETWEEN :start AND :end ORDER BY o.created_at DESC
            """), {"start": start_date, "end": end_date})
            headers = ["Номер", "Клієнт", "Статус", "Сума оренди", "Дата"]
            rows = [[row[0], row[1], row[2], row[3], str(row[4])] for row in result]
            
        elif report_type == "products":
            result = db.execute(text("""
                SELECT p.sku, p.name, COUNT(DISTINCT oi.order_id) as rentals, SUM(oi.price * oi.quantity) as revenue
                FROM products p LEFT JOIN order_items oi ON p.product_id = oi.product_id
                LEFT JOIN orders o ON oi.order_id = o.order_id AND DATE(o.created_at) BETWEEN :start AND :end
                GROUP BY p.product_id, p.sku, p.name ORDER BY revenue DESC
            """), {"start": start_date, "end": end_date})
            headers = ["Артикул", "Назва", "Кількість оренд", "Виручка"]
            rows = [[row[0], row[1], row[2], float(row[3]) if row[3] else 0] for row in result]
            
        elif report_type == "damage":
            result = db.execute(text("""
                SELECT pdh.product_name, pdh.sku, pdh.damage_type, pdh.severity, pdh.fee, pdh.order_number, pdh.created_at
                FROM product_damage_history pdh WHERE DATE(pdh.created_at) BETWEEN :start AND :end ORDER BY pdh.created_at DESC
            """), {"start": start_date, "end": end_date})
            headers = ["Товар", "Артикул", "Тип", "Рівень", "Сума", "Замовлення", "Дата"]
            rows = [[row[0], row[1], row[2], row[3], float(row[4]), row[5], str(row[6])] for row in result]
        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")
        
        if format == "json":
            data = [dict(zip(headers, row)) for row in rows]
            return {"data": data, "period": {"start": str(start_date), "end": str(end_date)}}
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        writer.writerows(rows)
        
        return Response(
            content=output.getvalue().encode('utf-8-sig'),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_type}_{start_date}_{end_date}.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")
