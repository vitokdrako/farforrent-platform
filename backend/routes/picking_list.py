"""
Picking List API — глобальний лист комплектації по днях.
Повертає замовлення в статусах awaiting/preparation/ready_for_issue з товарами,
згрупованими по зоні складу.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date, datetime
from typing import Optional
import json

from database_rentalhub import get_rh_db

router = APIRouter(prefix="/api/manager/picking-list", tags=["picking-list"])


def _enrich_items_with_zone(items: list, db: Session) -> list:
    """Підтягує zone і має поля шкоди для кожного товару одним batch-запитом."""
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
    # zones + image + components
    p_rows = db.execute(text(f"""
        SELECT product_id, zone, image_url, sku, name, components
        FROM products WHERE product_id IN ({placeholders})
    """)).fetchall()
    by_pid = {r[0]: {"zone": r[1], "image_url": r[2], "sku": r[3], "name": r[4], "components": r[5]} for r in p_rows}

    # damage history flag (any damage = warning)
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


@router.get("")
async def get_picking_list(
    date_str: Optional[str] = Query(None, alias="date", description="YYYY-MM-DD. Default: today"),
    include_awaiting: bool = Query(True, description="Include awaiting_customer orders"),
    db: Session = Depends(get_rh_db)
):
    """
    Лист комплектації на конкретну дату.
    Повертає замовлення з items згрупованими по зоні.
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

    # Preload OPEN tasks per order to show in cards
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
        "preparation_cards": [],
        "ready_cards": [],
        "awaiting_orders": [],
    }

    # === ISSUE CARDS (preparation + ready) для дати видачі ===
    cards_query = """
        SELECT ic.id, ic.order_id, ic.order_number, ic.status,
               ic.prepared_by, ic.issued_by, ic.items,
               ic.preparation_notes, ic.issue_notes,
               ic.prepared_at, ic.issued_at, ic.created_at,
               o.customer_name, o.customer_phone,
               o.rental_start_date, o.rental_end_date, o.notes as order_notes
        FROM issue_cards ic
        JOIN orders o ON ic.order_id = o.order_id
        WHERE ic.status IN ('preparation', 'ready', 'ready_for_issue')
          AND o.status != 'cancelled' AND o.is_archived = 0
          AND DATE(o.rental_start_date) = :target_date
        ORDER BY o.rental_start_date ASC, ic.created_at ASC
    """
    cards_rows = db.execute(text(cards_query), {"target_date": target_str}).fetchall()

    for row in cards_rows:
        items_raw = row[6]
        try:
            items = json.loads(items_raw) if isinstance(items_raw, str) else (items_raw or [])
        except Exception:
            items = []

        # FALLBACK: if issue_cards.items is empty (card not yet picked) — pull from order_items
        if not items:
            oi_rows = db.execute(text("""
                SELECT product_id, product_name, quantity FROM order_items
                WHERE order_id = :oid
            """), {"oid": row[1]}).fetchall()
            items = [
                {"id": ir[0], "product_id": ir[0], "name": ir[1] or "", "qty": int(ir[2] or 0)}
                for ir in oi_rows
            ]

        items_enriched = _enrich_items_with_zone(items, db)
        # Group by zone
        zones = {}
        for it in items_enriched:
            z = it["zone"]
            zones.setdefault(z, []).append(it)

        card = {
            "id": row[0],
            "order_id": row[1],
            "order_number": row[2],
            "status": row[3],
            "customer_name": row[12],
            "customer_phone": row[13],
            "rental_start_date": row[14].isoformat() if row[14] else None,
            "rental_end_date": row[15].isoformat() if row[15] else None,
            "order_notes": row[16] or "",
            "preparation_notes": row[7] or "",
            "issue_notes": row[8] or "",
            "items_count": len(items_enriched),
            "items_total_qty": sum(int(it.get("qty") or 0) for it in items_enriched),
            "zones": [{"zone": z, "items": its} for z, its in sorted(zones.items())],
            "tasks": tasks_by_order.get(int(row[1]), []),
        }
        if row[3] == "preparation":
            result["preparation_cards"].append(card)
        else:
            result["ready_cards"].append(card)

    # === AWAITING_CUSTOMER orders ===
    if include_awaiting:
        aw_query = """
            SELECT order_id, order_number, customer_name, customer_phone,
                   rental_start_date, rental_end_date, notes, total_price, created_at
            FROM orders
            WHERE status = 'awaiting_customer' AND is_archived = 0
              AND (DATE(rental_start_date) = :target_date OR rental_start_date IS NULL)
            ORDER BY created_at DESC
        """
        aw_rows = db.execute(text(aw_query), {"target_date": target_str}).fetchall()
        # also fetch order_items per order
        for ar in aw_rows:
            oid = ar[0]
            items_rows = db.execute(text("""
                SELECT oi.product_id, oi.product_name, oi.quantity, p.zone, p.image_url, p.sku, p.components
                FROM order_items oi
                LEFT JOIN products p ON p.product_id = oi.product_id
                WHERE oi.order_id = :oid
            """), {"oid": oid}).fetchall()
            zones = {}
            total_qty = 0
            for ir in items_rows:
                z = ir[3] or "Без зони"
                qty = int(ir[2] or 0)
                total_qty += qty
                zones.setdefault(z, []).append({
                    "product_id": ir[0],
                    "name": ir[1] or "",
                    "qty": qty,
                    "zone": z,
                    "image_url": ir[4],
                    "sku": ir[5] or "",
                    "components": ir[6] or "",
                    "has_damage_history": False,
                })
            result["awaiting_orders"].append({
                "order_id": oid,
                "order_number": ar[1],
                "customer_name": ar[2],
                "customer_phone": ar[3],
                "rental_start_date": ar[4].isoformat() if ar[4] else None,
                "rental_end_date": ar[5].isoformat() if ar[5] else None,
                "order_notes": ar[6] or "",
                "total_price": float(ar[7] or 0),
                "items_count": len(items_rows),
                "items_total_qty": total_qty,
                "zones": [{"zone": z, "items": its} for z, its in sorted(zones.items())],
                "tasks": tasks_by_order.get(int(oid), []),
            })

    # Summary
    total_items = sum(c["items_total_qty"] for c in result["preparation_cards"] + result["ready_cards"])
    result["summary"] = {
        "preparation_count": len(result["preparation_cards"]),
        "ready_count": len(result["ready_cards"]),
        "awaiting_count": len(result["awaiting_orders"]),
        "total_orders": len(result["preparation_cards"]) + len(result["ready_cards"]) + len(result["awaiting_orders"]),
        "total_items_to_pick": total_items,
    }
    return result
