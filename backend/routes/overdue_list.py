"""
Overdue Returns List API — лист прострочених повернень ("Борги").
Повертає замовлення, у яких rental_end_date < сьогодні, і які ще не повернуті
(status NOT IN returned/completed/cancelled).

Групує за кількістю днів прострочки: 1-3 дні / 4-7 днів / 8+ днів.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/manager/overdue-list", tags=["overdue-list"])


def _enrich_items_with_zone(items: list, db: Session) -> list:
    if not items:
        return []
    product_ids = set()
    for it in items:
        pid = it.get("id") or it.get("product_id") or it.get("inventory_id")
        if pid:
            try:
                product_ids.add(int(pid))
            except (ValueError, TypeError):
                pass
    if not product_ids:
        return items

    placeholders = ",".join(str(p) for p in product_ids)
    p_rows = db.execute(text(f"""
        SELECT product_id, zone, image_url, sku, name, components
        FROM products WHERE product_id IN ({placeholders})
    """)).fetchall()
    by_pid = {r[0]: {"zone": r[1], "image_url": r[2], "sku": r[3], "name": r[4], "components": r[5]} for r in p_rows}

    dmg_rows = db.execute(text(f"""
        SELECT product_id, COUNT(*) FROM product_damage_history
        WHERE product_id IN ({placeholders})
        GROUP BY product_id
    """)).fetchall()
    dmg_count = {r[0]: r[1] for r in dmg_rows}

    enriched = []
    for it in items:
        pid_raw = it.get("id") or it.get("product_id") or it.get("inventory_id")
        try:
            pid = int(pid_raw) if pid_raw is not None else None
        except (ValueError, TypeError):
            pid = None
        info = by_pid.get(pid, {}) if pid else {}
        enriched.append({
            "product_id": pid,
            "sku": it.get("sku") or info.get("sku") or "",
            "name": it.get("name") or info.get("name") or "",
            "qty": it.get("qty") or it.get("quantity") or 1,
            "zone": info.get("zone") or "Без зони",
            "image_url": info.get("image_url"),
            "components": info.get("components") or "",
            "has_damage_history": bool(dmg_count.get(pid, 0)) if pid else False,
        })
    return enriched


def _get_order_items(order_id: int, db: Session) -> list:
    rows = db.execute(text("""
        SELECT product_id, product_name, quantity
        FROM order_items
        WHERE order_id = :oid
          AND (status IS NULL OR status != 'refused')
    """), {"oid": order_id}).fetchall()
    return [
        {"id": r[0], "product_id": r[0], "name": r[1] or "", "qty": int(r[2] or 0)}
        for r in rows
    ]


@router.get("")
async def get_overdue_list(db: Session = Depends(get_rh_db)):
    """
    Лист прострочених повернень.
    Повертає замовлення rental_end_date < today, status NOT IN (returned/completed/cancelled).
    Групує за ступенем прострочки.
    """
    today = date.today()
    today_str = today.isoformat()

    # Preload open tasks per order
    tasks_by_order = {}
    try:
        task_rows = db.execute(text("""
            SELECT t.order_id, t.id, t.title, t.task_type, t.status, t.priority,
                   COALESCE(CONCAT(u.firstname, ' ', u.lastname), u.username, t.assigned_to) as assignee_name
            FROM tasks t
            LEFT JOIN users u ON u.user_id = t.assigned_to_id
            WHERE t.status IN ('todo', 'in_progress')
            ORDER BY
              CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
              t.created_at DESC
        """)).fetchall()
        for tr in task_rows:
            if tr[0] is None:
                continue
            tasks_by_order.setdefault(int(tr[0]), []).append({
                "id": tr[1],
                "title": tr[2] or "",
                "task_type": tr[3] or "general",
                "status": tr[4] or "todo",
                "priority": tr[5] or "medium",
                "assignee_name": (tr[6] or "").strip(),
            })
    except Exception:
        tasks_by_order = {}

    orders_query = """
        SELECT o.order_id, o.order_number, o.status, o.customer_name, o.customer_phone,
               o.rental_start_date, o.rental_end_date, o.notes, o.total_price,
               DATEDIFF(:today, o.rental_end_date) AS days_overdue
        FROM orders o
        WHERE o.rental_end_date < :today
          AND o.is_archived = 0
          AND o.status NOT IN ('cancelled', 'draft', 'awaiting_customer', 'returned', 'completed')
        ORDER BY o.rental_end_date ASC, o.order_id DESC
    """
    order_rows = db.execute(text(orders_query), {"today": today_str}).fetchall()

    buckets = {
        "mild": [],    # 1-3 днів
        "serious": [], # 4-7 днів
        "critical": [] # 8+ днів
    }

    for row in order_rows:
        (order_id, order_number, status, customer_name, customer_phone,
         rental_start_date, rental_end_date, order_notes, total_price, days_overdue) = row

        items = _get_order_items(order_id, db)
        items_enriched = _enrich_items_with_zone(items, db)
        zones = {}
        for it in items_enriched:
            z = it["zone"]
            zones.setdefault(z, []).append(it)

        days_od = int(days_overdue or 0)
        card = {
            "id": f"overdue-{order_id}",
            "order_id": order_id,
            "order_number": order_number or f"#{order_id}",
            "order_status": status,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "rental_start_date": rental_start_date.isoformat() if rental_start_date else None,
            "rental_end_date": rental_end_date.isoformat() if rental_end_date else None,
            "days_overdue": days_od,
            "order_notes": order_notes or "",
            "total_price": float(total_price or 0),
            "items_count": len(items_enriched),
            "items_total_qty": sum(int(it.get("qty") or 0) for it in items_enriched),
            "zones": [{"zone": z, "items": its} for z, its in sorted(zones.items())],
            "tasks": tasks_by_order.get(int(order_id), []),
        }

        if days_od >= 8:
            buckets["critical"].append(card)
        elif days_od >= 4:
            buckets["serious"].append(card)
        else:
            buckets["mild"].append(card)

    total_count = len(buckets["mild"]) + len(buckets["serious"]) + len(buckets["critical"])
    total_items = sum(c["items_total_qty"] for b in buckets.values() for c in b)
    total_amount = sum(c["total_price"] for b in buckets.values() for c in b)

    return {
        "date": today_str,
        "mild_overdue": buckets["mild"],
        "serious_overdue": buckets["serious"],
        "critical_overdue": buckets["critical"],
        "summary": {
            "mild_count": len(buckets["mild"]),
            "serious_count": len(buckets["serious"]),
            "critical_count": len(buckets["critical"]),
            "total_count": total_count,
            "total_items": total_items,
            "total_amount": total_amount,
        }
    }
