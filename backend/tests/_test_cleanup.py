"""
Hard cleanup helper for E2E tests. Registers an atexit handler that
deletes the order + items + test user even if the test crashes.

ВАЖЛИВО: тести Event Tool ЗОБОВ'ЯЗАНІ використовувати цей helper,
бо `convert-to-order` створює реальний рядок у `orders` з реальним
auto_increment ID, що далі конфліктує з OC-cron-синхронізацією.
"""
import atexit
from database_rentalhub import RHSessionLocal
from sqlalchemy import text


def register_order_cleanup(order_id: int, board_id=None, email=None, product_id=None,
                           restore_qty=0):
    """Зареєструвати hard-cleanup що гарантовано виконається при будь-якому виході."""
    def _do_cleanup():
        try:
            db = RHSessionLocal()
            db.execute(text("DELETE FROM order_chat_messages WHERE order_id = :oid"), {"oid": order_id})
            db.execute(text("DELETE FROM order_items WHERE order_id = :oid"), {"oid": order_id})
            db.execute(text("DELETE FROM order_lifecycle WHERE order_id = :oid"), {"oid": order_id})
            db.execute(text("DELETE FROM order_internal_notes WHERE order_id = :oid"), {"oid": order_id})
            db.execute(text("DELETE FROM fin_payments WHERE order_id = :oid"), {"oid": order_id})
            db.execute(text("DELETE FROM fin_transactions WHERE entity_id = :oid AND entity_type='order'"), {"oid": order_id})
            db.execute(text("DELETE FROM product_damage_history WHERE order_id = :oid"), {"oid": order_id})
            # partial_return_versions cascade
            vids = [r[0] for r in db.execute(text(
                "SELECT version_id FROM partial_return_versions WHERE parent_order_id = :oid"
            ), {"oid": order_id}).fetchall()]
            if vids:
                db.execute(text(f"DELETE FROM partial_return_version_items WHERE version_id IN ({','.join(map(str, vids))})"))
                db.execute(text(f"DELETE FROM partial_return_versions WHERE version_id IN ({','.join(map(str, vids))})"))
            db.execute(text("DELETE FROM orders WHERE order_id = :oid"), {"oid": order_id})
            if board_id:
                db.execute(text("DELETE FROM event_board_items WHERE board_id = :bid"), {"bid": board_id})
                db.execute(text("DELETE FROM event_boards WHERE id = :bid"), {"bid": board_id})
            if email:
                db.execute(text("DELETE FROM event_customers WHERE email = :e"), {"e": email})
                db.execute(text("DELETE FROM client_users WHERE email_normalized = :e"), {"e": email.lower()})
            if product_id and restore_qty:
                db.execute(text("UPDATE products SET quantity = quantity + :q WHERE product_id = :pid"),
                           {"q": restore_qty, "pid": product_id})
            db.commit()
            db.close()
            print(f"  [atexit] cleaned up order_id={order_id}")
        except Exception as e:
            print(f"  [atexit] cleanup failed: {e}")
    atexit.register(_do_cleanup)
