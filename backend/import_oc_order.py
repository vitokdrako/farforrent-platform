"""
Manual import: pull orders from OpenCart into RentalHub.
Usage:
  python3 import_oc_order.py 7805 7806   # explicit IDs
  python3 import_oc_order.py --recent 7  # all OC orders from last 7 days
                                          # that are missing in RH
"""
import sys, os, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

import pymysql
from datetime import date, timedelta
from database_rentalhub import RHSessionLocal
from sqlalchemy import text

OC = dict(
    host=os.environ['OC_DB_HOST'], port=int(os.environ['OC_DB_PORT']),
    user=os.environ['OC_DB_USERNAME'], password=os.environ['OC_DB_PASSWORD'],
    db=os.environ['OC_DB_DATABASE'], charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor
)


def _resolve_oc_product_to_rh(oc_db, rh_db, oc_product_id, sku, name) -> int | None:
    """Найкраща стратегія: SKU → product_id → name fallback."""
    if sku:
        pid = rh_db.execute(text("SELECT product_id FROM products WHERE sku = :s LIMIT 1"),
                            {"s": sku}).scalar()
        if pid:
            return pid
    if oc_product_id:
        pid = rh_db.execute(text("SELECT product_id FROM products WHERE product_id = :id LIMIT 1"),
                            {"id": oc_product_id}).scalar()
        if pid:
            return pid
    if name:
        pid = rh_db.execute(text("SELECT product_id FROM products WHERE name = :n LIMIT 1"),
                            {"n": name}).scalar()
        if pid:
            return pid
    return None


def _resolve_product_image_url(rh_db, product_id: int | None) -> str:
    if not product_id:
        return ""
    return rh_db.execute(text("SELECT COALESCE(image_url,'') FROM products WHERE product_id = :id"),
                        {"id": product_id}).scalar() or ""


def import_order(oc_order_id: int, dry_run: bool = False):
    oc = pymysql.connect(**OC)
    rh = RHSessionLocal()
    try:
        cur = oc.cursor()
        cur.execute("SELECT * FROM oc_order WHERE order_id = %s", (oc_order_id,))
        oc_order = cur.fetchone()
        if not oc_order:
            print(f"❌ OC order {oc_order_id} not found")
            return False

        # Check if RH already has it
        exists = rh.execute(text("SELECT 1 FROM orders WHERE order_id = :id"),
                            {"id": oc_order_id}).scalar()
        if exists:
            print(f"⚠️  RH already has order {oc_order_id} — skipping (delete first if reimport needed)")
            return False

        cur.execute("SELECT * FROM oc_order_product WHERE order_id = %s", (oc_order_id,))
        oc_items = cur.fetchall()

        full_name = f"{oc_order['firstname'] or ''} {oc_order['lastname'] or ''}".strip()
        date_added = oc_order['date_added']
        order_number = f"OC-{oc_order_id}"

        # Map OC order_status_id → RH status
        # Spec: status 2 = Processing/New (waiting manager review)
        oc_status = oc_order.get('order_status_id', 0)
        status_map = {
            1: 'awaiting_customer', 2: 'processing', 3: 'shipped',
            5: 'completed', 7: 'cancelled', 8: 'cancelled',
            10: 'awaiting_customer', 11: 'processing', 15: 'completed',
            29: 'awaiting_customer',
        }
        rh_status = status_map.get(oc_status, 'processing')

        comment = (oc_order.get('comment') or '').strip()
        total_price = oc_order['total']

        print(f"\n➜ Importing OC order {oc_order_id}")
        print(f"  customer: {full_name} ({oc_order['email']}, {oc_order['telephone']})")
        print(f"  total: {total_price}, status: oc={oc_status} → rh={rh_status}")
        print(f"  items: {len(oc_items)}")

        if dry_run:
            print("  [DRY-RUN] skipping insert")
            return True

        # Insert order
        rh.execute(text("""
            INSERT INTO orders
              (order_id, order_number, customer_id, customer_name, phone, customer_phone,
               customer_email, email, total_price, status, source,
               customer_comment, created_at, synced_at, updated_at)
            VALUES
              (:oid, :onum, :cid, :name, :ph, :ph, :em, :em, :tp, :st, 'opencart',
               :note, :ca, NOW(), NOW())
        """), {
            "oid": oc_order_id, "onum": order_number, "cid": oc_order.get('customer_id'),
            "name": full_name, "ph": oc_order.get('telephone'),
            "em": oc_order.get('email'),
            "tp": total_price, "st": rh_status, "note": comment, "ca": date_added,
        })

        # Insert items
        inserted_items = 0
        unresolved = []
        for it in oc_items:
            pid = _resolve_oc_product_to_rh(
                oc, rh, it['product_id'], it.get('model') or '', it['name']
            )
            if not pid:
                unresolved.append(it)
                continue
            img = _resolve_product_image_url(rh, pid)
            rh.execute(text("""
                INSERT INTO order_items
                  (order_id, product_id, product_name, quantity, price, total_rental, image_url, status)
                VALUES
                  (:oid, :pid, :name, :qty, :price, :total, :img, 'active')
            """), {
                "oid": oc_order_id, "pid": pid, "name": it['name'],
                "qty": int(it['quantity']), "price": it['price'],
                "total": it['total'], "img": img,
            })
            inserted_items += 1

        if unresolved:
            print(f"  ⚠️  {len(unresolved)} items not matched by SKU/product_id:")
            for u in unresolved[:5]:
                print(f"     - product_id={u['product_id']} sku={u.get('model')} name={u['name']!r}")

        # Lifecycle entry
        try:
            rh.execute(text("""
                INSERT INTO order_lifecycle (order_id, event_type, event_data, created_at)
                VALUES (:oid, 'imported_from_opencart',
                        JSON_OBJECT('oc_order_id', :oid, 'items', :n), NOW())
            """), {"oid": oc_order_id, "n": inserted_items})
        except Exception:
            pass

        rh.commit()
        print(f"  ✅ Imported {inserted_items}/{len(oc_items)} items")
        return True

    except Exception as e:
        rh.rollback()
        print(f"  ❌ FAILED: {e}")
        import traceback; traceback.print_exc()
        return False
    finally:
        oc.close()
        rh.close()


def import_recent(days: int = 7, dry_run: bool = False):
    """Імпортувати всі OC замовлення за останні N днів, яких ще нема в RH."""
    oc = pymysql.connect(**OC)
    rh = RHSessionLocal()
    try:
        cur = oc.cursor()
        cur.execute("""
            SELECT order_id FROM oc_order
            WHERE date_added > NOW() - INTERVAL %s DAY
            ORDER BY order_id ASC
        """, (days,))
        oc_ids = [r['order_id'] for r in cur.fetchall()]
        # Filter out those already in RH
        if not oc_ids:
            print("No OC orders in window")
            return
        existing = {r[0] for r in rh.execute(text(
            f"SELECT order_id FROM orders WHERE order_id IN ({','.join(map(str, oc_ids))})"
        )).fetchall()}
        missing = [o for o in oc_ids if o not in existing]
        print(f"OC orders in last {days}d: {len(oc_ids)}, missing in RH: {len(missing)}")
        for o in missing:
            import_order(o, dry_run=dry_run)
    finally:
        oc.close()
        rh.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ids", nargs='*', type=int, help="OC order IDs to import")
    p.add_argument("--recent", type=int, metavar="DAYS",
                   help="Import all OC orders missing in RH from last N days")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if args.recent:
        import_recent(args.recent, dry_run=args.dry_run)
    elif args.ids:
        for oid in args.ids:
            import_order(oid, dry_run=args.dry_run)
    else:
        p.print_help()
