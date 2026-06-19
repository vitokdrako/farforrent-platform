"""
Data migration: return_cards → partial_return_versions

ВАЖЛИВО:
  - Запускається ОДИН раз перед видаленням return_cards.py
  - Створює нові записи у partial_return_versions + partial_return_version_items
  - Не видаляє return_cards (на випадок необхідності rollback). Видалення
    робиться окремим кроком після перевірки.

Mapping:
  return_cards.order_id          → partial_return_versions.parent_order_id
  return_cards.created_at        → partial_return_versions.created_at
  return_cards.received_by       → partial_return_versions.created_by_name
  return_cards.status            → partial_return_versions.status (map нижче)
  return_cards.notes/return_notes → partial_return_versions.notes
  return_cards.items[] / items_returned[] → partial_return_version_items[]

Use: python3 migrate_return_cards.py [--dry-run]
"""
import sys, os, json, argparse, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database_rentalhub import RHSessionLocal
from sqlalchemy import text


STATUS_MAP = {
    "pending": "active",
    "in_progress": "active",
    "completed": "completed",
    "closed": "completed",
    "cancelled": "cancelled",
}


def parse_items(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw) if isinstance(raw, str) else []
    except Exception:
        return []


def migrate(dry_run: bool = False):
    db = RHSessionLocal()
    try:
        rc_rows = db.execute(text("""
            SELECT id, order_id, order_number, status, received_by, received_by_id,
                   notes, return_notes, items, items_returned,
                   created_at, returned_at, checked_at,
                   cleaning_fee, late_fee, items_ok, items_dirty,
                   items_damaged, items_missing
            FROM return_cards
            WHERE NOT EXISTS (
                SELECT 1 FROM partial_return_versions prv
                WHERE prv.parent_order_id = return_cards.order_id
                  AND prv.notes LIKE CONCAT('[migrated from return_cards #', return_cards.id, ']%')
            )
        """)).fetchall()
        print(f"Found {len(rc_rows)} return_cards rows to migrate")

        for rc in rc_rows:
            (rc_id, order_id, order_number, status, recv_by, recv_by_id,
             notes, return_notes, items_raw, items_returned_raw,
             created_at, returned_at, checked_at,
             cleaning_fee, late_fee, items_ok, items_dirty,
             items_damaged, items_missing) = rc

            # Pick the most-detailed items source
            items = parse_items(items_returned_raw) or parse_items(items_raw)
            new_status = STATUS_MAP.get(status, "active")

            # Get next version_number for this order
            next_num = db.execute(text("""
                SELECT COALESCE(MAX(version_number), 0) + 1
                FROM partial_return_versions WHERE parent_order_id = :oid
            """), {"oid": order_id}).scalar()

            display_num = order_number or f"O-{order_id}"
            display_num = f"{display_num}({next_num})-legacy"

            notes_combined = (
                f"[migrated from return_cards #{rc_id}] "
                + ((return_notes or "") + " " + (notes or "")).strip()
            ).strip()

            print(f"\n→ return_cards id={rc_id} order={order_id} status={status} → {new_status} (items: {len(items)})")

            if dry_run:
                continue

            # Insert version
            db.execute(text("""
                INSERT INTO partial_return_versions
                  (parent_order_id, version_number, display_number, status, notes,
                   created_at, customer_name)
                VALUES (:oid, :vn, :dn, :st, :nt, :ca, :cn)
            """), {
                "oid": order_id, "vn": next_num, "dn": display_num,
                "st": new_status, "nt": notes_combined,
                "ca": created_at, "cn": recv_by or "Legacy",
            })
            vid = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
            print(f"   → version_id={vid}")

            # Insert items
            for it in items:
                product_id = it.get("product_id") or it.get("id")
                try:
                    product_id = int(product_id) if product_id else None
                except (ValueError, TypeError):
                    product_id = None
                qty_returned = int(it.get("returned_qty") or it.get("qty") or 0)
                qty_expected = int(it.get("rented_qty") or it.get("expected") or qty_returned)
                sku = it.get("sku") or ""
                name = it.get("name") or ""
                findings = it.get("findings") or []
                item_status = "returned"
                if findings:
                    bad = [f for f in findings if str(f.get("kind","")).lower() in ("damaged","lost","missing")]
                    if bad and any(f.get("kind") == "lost" for f in bad):
                        item_status = "lost"
                    elif bad:
                        item_status = "damaged"
                if qty_returned == 0 and qty_expected > 0:
                    item_status = "lost"

                db.execute(text("""
                    INSERT INTO partial_return_version_items
                      (version_id, product_id, sku, name, qty, status, returned_at)
                    VALUES (:vid, :pid, :sku, :name, :qty, :st, :rt)
                """), {
                    "vid": vid, "pid": product_id, "sku": sku, "name": name,
                    "qty": qty_expected or qty_returned or 1,
                    "st": item_status,
                    "rt": returned_at or checked_at or created_at,
                })

        if not dry_run:
            db.commit()
            print(f"\n✅ Migration committed. {len(rc_rows)} cards migrated.")
        else:
            db.rollback()
            print(f"\n🔍 DRY-RUN — nothing changed. Would migrate {len(rc_rows)} cards.")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Migration FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    migrate(dry_run=args.dry_run)
