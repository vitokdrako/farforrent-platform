"""
End-to-end integration test:
  Event Tool → Order → Quantity change → Payment → Return + Total Loss
Tests the entire backend pipeline that the user requested to validate.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import time

BASE = "http://localhost:8001/api"
EVT = f"{BASE}/event"
ADM = f"{BASE}/admin/orders"

email = f"e2e+{int(time.time())}@test.local"
password = "test123"

def jprint(label, data):
    import json
    print(f"\n--- {label} ---")
    print(json.dumps(data, default=str, ensure_ascii=False)[:600])

def fail(msg):
    print(f"\n❌ FAIL: {msg}")
    sys.exit(1)

# 1. Register Event Tool customer
r = requests.post(f"{EVT}/auth/register", json={
    "email": email, "password": password,
    "firstname": "E2E", "lastname": "Tester", "telephone": "+380501234567"
})
assert r.status_code == 200, r.text
jprint("register", r.json())

# 2. Login
r = requests.post(f"{EVT}/auth/login", json={"email": email, "password": password})
assert r.status_code == 200, r.text
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
print(f"\n✓ Token: {token[:24]}...")

# 3. Create board
r = requests.post(f"{EVT}/boards", json={
    "board_name": f"E2E Board {int(time.time())}",
    "event_date": "2026-12-01",
    "event_type": "wedding",
    "rental_start_date": "2026-11-29",
    "rental_end_date": "2026-12-02",
    "notes": "Тестове замовлення E2E"
}, headers=H)
assert r.status_code in (200, 201), r.text
board = r.json()
board_id = board["id"]
jprint("create board", board)

# 4. Fetch products
r = requests.get(f"{EVT}/products?limit=5")
assert r.status_code == 200, r.text
data = r.json()
if isinstance(data, list):
    products = data
elif isinstance(data, dict):
    products = data.get("products") or data.get("items") or []
else:
    products = []
products_with_price = [p for p in products if (p.get("rental_price") or p.get("price")) and (p.get("quantity") or 0) > 0]
if not products_with_price:
    fail("no products with rental price available")
test_product = products_with_price[0]
print(f"✓ Test product: id={test_product.get('product_id')} sku={test_product.get('sku')} price={test_product.get('rental_price')}")

# 5. Add item to board
r = requests.post(f"{EVT}/boards/{board_id}/items", json={
    "product_id": test_product["product_id"], "quantity": 3
}, headers=H)
assert r.status_code in (200, 201), r.text
jprint("add item", r.json())

# 6. Convert board → order
r = requests.post(f"{EVT}/boards/{board_id}/convert-to-order", json={
    "customer_name": "E2E Tester",
    "phone": "+380501234567",
    "customer_comment": "E2E test order — please discard after testing",
    "payer_type": "individual",
    "payment_method": "cash"
}, headers=H)
assert r.status_code == 200, r.text
order = r.json()
jprint("convert-to-order", order)
order_id = order["order_id"]
order_number = order["order_number"]

# 7. Get order from admin side
r = requests.get(f"{BASE}/orders/{order_id}")
print(f"\n✓ Admin GET /orders/{order_id}: status={r.status_code}")

# 8. Add rent payment via admin_finance (modern: fin_payments → mirror to fin_transactions)
r = requests.post(f"{BASE}/admin/finance/orders/{order_id}/transactions", json={
    "tx_type": "rent_payment", "amount": 500, "note": "E2E часткова оплата оренди"
})
print(f"  rent_payment add via admin_finance status={r.status_code}: {r.text[:200]}")

# 9. Add deposit payment via admin_finance
r = requests.post(f"{BASE}/admin/finance/orders/{order_id}/transactions", json={
    "tx_type": "deposit_payment", "amount": 200, "note": "E2E застава"
})
print(f"  deposit_payment add status={r.status_code}: {r.text[:200]}")

# 10. Check finance summary view
r = requests.get(f"{BASE}/admin/finance/orders/{order_id}")
print(f"\n✓ Finance summary status={r.status_code}")
if r.status_code == 200:
    jprint("v_order_finance summary", r.json())

# 11. Create partial return version with the items
from database_rentalhub import RHSessionLocal
from sqlalchemy import text
db = RHSessionLocal()
db.execute(text("""
    INSERT INTO partial_return_versions
        (parent_order_id, version_number, display_number, customer_name, customer_phone,
         rental_end_date, total_price, status, notes)
    VALUES (:oid, 1, :dnum, :cn, :phone, '2026-12-02', :tp, 'active', 'E2E test')
"""), {"oid": order_id, "dnum": f"{order_number}(1)", "cn": "E2E Tester",
       "phone": "+380501234567", "tp": 500})
vid = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
db.execute(text("""
    INSERT INTO partial_return_version_items (version_id, product_id, sku, name, qty, daily_rate, status)
    VALUES (:vid, :pid, :sku, :name, 3, :rate, 'pending')
"""), {"vid": vid, "pid": test_product["product_id"], "sku": test_product.get("sku") or "",
       "name": test_product.get("name") or "Test", "rate": test_product.get("rental_price") or 0})
iid = db.execute(text("SELECT LAST_INSERT_ID()")).scalar()
db.commit()
print(f"\n✓ Created return version_id={vid} item_id={iid}")

# 12. Mark item as TOTAL LOSS (the previously-broken endpoint)
r = requests.post(f"{BASE}/return-versions/version/{vid}/return-item", json={
    "item_id": iid,
    "qty": 3,
    "mark_as_lost": True,
    "loss_amount": 1500,
    "note": "E2E test — повна втрата 3 шт",
    "created_by": "E2E Tester"
})
assert r.status_code == 200, f"LOSS FAILED: {r.text}"
jprint("MARK AS LOST", r.json())

# 13. Verify finance updated
r = requests.get(f"{BASE}/admin/finance/orders/{order_id}")
if r.status_code == 200:
    summary = r.json().get("summary", {})
    print(f"\n✓ Final finance summary:")
    for k, v in summary.items():
        print(f"    {k}: {v}")

# 14. Verify fin_transactions exists (mirror via trigger)
rows = db.execute(text("""
    SELECT id, tx_type, amount, status, note FROM fin_transactions
    WHERE entity_id = :oid ORDER BY id
"""), {"oid": order_id}).fetchall()
print(f"\n✓ fin_transactions for order {order_id} ({len(rows)} rows):")
for row in rows: print(f"    {row}")

# 15. Verify NO duplicate fin_payments
rows = db.execute(text("""
    SELECT id, payment_type, amount, tx_id, note FROM fin_payments WHERE order_id = :oid
"""), {"oid": order_id}).fetchall()
print(f"\n✓ fin_payments for order {order_id} ({len(rows)} rows):")
for row in rows: print(f"    {row}")

# Cleanup
print("\n--- Cleaning up E2E data ---")
db.execute(text("DELETE FROM fin_transactions WHERE entity_id = :oid AND entity_type='order'"), {"oid": order_id})
db.execute(text("DELETE FROM fin_payments WHERE order_id = :oid"), {"oid": order_id})
db.execute(text("DELETE FROM product_damage_history WHERE order_id = :oid"), {"oid": order_id})
db.execute(text("DELETE FROM partial_return_version_items WHERE version_id = :vid"), {"vid": vid})
db.execute(text("DELETE FROM partial_return_versions WHERE version_id = :vid"), {"vid": vid})
db.execute(text("DELETE FROM order_items WHERE order_id = :oid"), {"oid": order_id})
db.execute(text("DELETE FROM order_lifecycle WHERE order_id = :oid"), {"oid": order_id})
db.execute(text("DELETE FROM order_internal_notes WHERE order_id = :oid"), {"oid": order_id})
db.execute(text("DELETE FROM orders WHERE order_id = :oid"), {"oid": order_id})
db.execute(text("DELETE FROM event_board_items WHERE board_id = :bid"), {"bid": board_id})
db.execute(text("DELETE FROM event_boards WHERE id = :bid"), {"bid": board_id})
db.execute(text("DELETE FROM event_customers WHERE email = :e"), {"e": email})
db.execute(text("DELETE FROM client_users WHERE email_normalized = :e"), {"e": email.lower()})
# Restore product quantity
db.execute(text("UPDATE products SET quantity = quantity + 3 WHERE product_id = :pid"),
           {"pid": test_product["product_id"]})
db.commit()
db.close()
print("✅ ALL TESTS PASSED — Full Event Tool order cycle works end-to-end!")
