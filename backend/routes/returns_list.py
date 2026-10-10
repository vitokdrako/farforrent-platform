"""
Returns List API — глобальний лист повернень по днях.
Повертає замовлення на повернення на вибрану дату:
  - очікувані (status in issued/on_rent, rental_end_date = target_date)
  - в процесі (мають активні return_card або partial_return_version)
  - завершені (status in returned/completed)
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime
from typing import Optional
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/manager/returns-list", tags=["returns-list"])


def _enrich_items_with_zone(items: list, db: Session) -> list:
    """Підтягує zone/image/SKU/components/damage-history для кожного товару."""
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
            "returned_qty": int(it.get("returned_qty") or it.get("quantity_returned") or 0),
            "zone": info.get("zone") or "Без зони",
            "image_url": info.get("image_url"),
            "components": info.get("components") or "",
            "has_damage_history": bool(dmg_count.get(pid, 0)) if pid else False,
        })
    return enriched


def _get_order_items(order_id: int, db: Session) -> list:
    """Повертає позиції замовлення з таблиці order_items."""
    rows = db.execute(text("""
        SELECT product_id, product_name, quantity
        FROM order_items
        WHERE order_id = :oid
          AND (status IS NULL OR status != 'refused')
    """), {"oid": order_id}).fetchall()
    return [
        {
            "id": r[0],
            "product_id": r[0],
            "name": r[1] or "",
            "qty": int(r[2] or 0),
            "returned_qty": 0,
        }
        for r in rows
    ]


@router.get("")
async def get_returns_list(
    date_str: Optional[str] = Query(None, alias="date", description="YYYY-MM-DD. Default: today"),
    db: Session = Depends(get_rh_db)
):
    """
    Лист повернень на конкретну дату.
    Повертає замовлення (expected / in_progress / completed) із items по зонах.
    """
    target_date = None
    if date_str:
        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            target_date = date.today()
    else:
        target_date = date.today()

    target_str = target_date.isoformat()

    # Preload open tasks per order (ті самі, що й у picking-list)
    tasks_by_order = {}
    try:
        task_rows = db.execute(text("""
            SELECT t.order_id, t.id, t.title, t.task_type, t.status, t.priority,
                   t.assigned_to_id, t.assigned_to, t.created_at,
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
                "assignee_name": (tr[9] or "").strip(),
            })
    except Exception:
        tasks_by_order = {}

    result = {
        "date": target_str,
        "expected_returns": [],       # issued / on_rent, повернення сьогодні
        "in_progress_returns": [],    # є активна return_card
        "completed_returns": [],      # returned / completed
    }

    # Знайдемо id карток повернення для замовлень на цю дату (щоб відрізнити in_progress)
    rc_rows = db.execute(text("""
        SELECT rc.order_id, rc.id, rc.status
        FROM return_cards rc
        JOIN orders o ON rc.order_id = o.order_id
        WHERE DATE(o.rental_end_date) = :target_date
    """), {"target_date": target_str}).fetchall()
    return_card_by_order = {int(r[0]): {"id": r[1], "status": r[2]} for r in rc_rows}

    # Головний запит: усі замовлення з rental_end_date = target_date
    orders_query = """
        SELECT o.order_id, o.order_number, o.status, o.customer_name, o.customer_phone,
               o.rental_start_date, o.rental_end_date, o.notes, o.total_price
        FROM orders o
        WHERE DATE(o.rental_end_date) = :target_date
          AND o.is_archived = 0
          AND o.status NOT IN ('cancelled', 'draft', 'awaiting_customer')
        ORDER BY o.rental_end_date ASC, o.order_id DESC
    """
    order_rows = db.execute(text(orders_query), {"target_date": target_str}).fetchall()

    for row in order_rows:
        (order_id, order_number, status, customer_name, customer_phone,
         rental_start_date, rental_end_date, order_notes, total_price) = row

        items = _get_order_items(order_id, db)
        items_enriched = _enrich_items_with_zone(items, db)
        zones = {}
        for it in items_enriched:
            z = it["zone"]
            zones.setdefault(z, []).append(it)

        rc_info = return_card_by_order.get(int(order_id))

        card = {
            "id": rc_info["id"] if rc_info else f"o-{order_id}",
            "order_id": order_id,
            "order_number": order_number or f"#{order_id}",
            "order_status": status,
            "return_card_id": rc_info["id"] if rc_info else None,
            "return_card_status": rc_info["status"] if rc_info else None,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "rental_start_date": rental_start_date.isoformat() if rental_start_date else None,
            "rental_end_date": rental_end_date.isoformat() if rental_end_date else None,
            "order_notes": order_notes or "",
            "total_price": float(total_price or 0),
            "items_count": len(items_enriched),
            "items_total_qty": sum(int(it.get("qty") or 0) for it in items_enriched),
            "items_returned_qty": sum(int(it.get("returned_qty") or 0) for it in items_enriched),
            "zones": [{"zone": z, "items": its} for z, its in sorted(zones.items())],
            "tasks": tasks_by_order.get(int(order_id), []),
        }

        # Класифікація
        if status in ("returned", "completed"):
            result["completed_returns"].append(card)
        elif rc_info and rc_info["status"] in ("received", "checked", "pending"):
            result["in_progress_returns"].append(card)
        else:
            # issued / on_rent / etc.
            result["expected_returns"].append(card)

    # Summary
    total_items_to_return = sum(c["items_total_qty"] for c in result["expected_returns"] + result["in_progress_returns"])
    result["summary"] = {
        "expected_count": len(result["expected_returns"]),
        "in_progress_count": len(result["in_progress_returns"]),
        "completed_count": len(result["completed_returns"]),
        "total_orders": len(result["expected_returns"]) + len(result["in_progress_returns"]) + len(result["completed_returns"]),
        "total_items_to_return": total_items_to_return,
    }
    return result
