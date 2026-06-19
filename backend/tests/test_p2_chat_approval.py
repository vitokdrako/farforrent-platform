"""E2E test for P2 features: chat + inline estimate approval."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests, time

BASE = "http://localhost:8001/api"
EVT = f"{BASE}/event"

email = f"p2+{int(time.time())}@test.local"
requests.post(f"{EVT}/auth/register", json={"email": email, "password": "x",
                                            "firstname": "P2", "lastname": "T", "telephone": "+380"})
tok = requests.post(f"{EVT}/auth/login", json={"email": email, "password": "x"}).json()["access_token"]
H = {"Authorization": f"Bearer {tok}"}

# Create board → order
b = requests.post(f"{EVT}/boards", json={
    "board_name": "P2 Board", "event_date": "2026-12-15",
    "event_type": "wedding", "rental_start_date": "2026-12-13", "rental_end_date": "2026-12-16"
}, headers=H).json()
bid = b["id"]
prod = requests.get(f"{EVT}/products?limit=1").json()
pid = prod[0]["product_id"] if isinstance(prod, list) else prod.get("products", [{}])[0].get("product_id")
requests.post(f"{EVT}/boards/{bid}/items", json={"product_id": pid, "quantity": 1}, headers=H)
order = requests.post(f"{EVT}/boards/{bid}/convert-to-order", json={
    "customer_name": "P2", "phone": "+380", "payer_type": "individual", "payment_method": "cash"
}, headers=H).json()
oid = order["order_id"]
print(f"\n✓ Order created: {order['order_number']} (id={oid})")

# === CHAT ===
print("\n=== CHAT ===")
r = requests.get(f"{EVT}/orders/{oid}/chat/messages", headers=H).json()
print(f"  initial messages: {len(r['messages'])}")
r = requests.post(f"{EVT}/orders/{oid}/chat/messages",
                  json={"message": "Привіт! Питання щодо доставки."}, headers=H)
print(f"  client sent: status={r.status_code}, msgs={len(r.json().get('messages', []))}")
# manager replies
r = requests.post(f"{BASE}/admin/orders/{oid}/chat/messages",
                  json={"message": "Доброго дня! Доставимо до 11:00."},
                  params={"sender_name": "Менеджер Олена"})
print(f"  manager sent: status={r.status_code}, msgs={len(r.json().get('messages', []))}")
# client refresh + check unread
r = requests.get(f"{EVT}/orders/{oid}/chat/unread_count", headers=H).json()
print(f"  client unread before refresh: {r['unread']}")
r = requests.get(f"{EVT}/orders/{oid}/chat/messages", headers=H).json()
for m in r["messages"]:
    print(f"  [{m['sender_type']}] {m['sender_name']}: {m['message']}")
r = requests.get(f"{EVT}/orders/{oid}/chat/unread_count", headers=H).json()
print(f"  client unread after refresh: {r['unread']} (expected 0)")

# === INLINE ESTIMATE APPROVAL ===
print("\n=== INLINE ESTIMATE APPROVAL ===")
from database_rentalhub import RHSessionLocal
from sqlalchemy import text
import uuid
db = RHSessionLocal()
# Create a fake estimate document
doc_id = str(uuid.uuid4())
db.execute(text("""
    INSERT INTO documents (id, doc_type, doc_number, entity_type, entity_id, category, status)
    VALUES (:id, 'estimate', :num, 'order', :oid, 'quote', 'draft')
"""), {"id": doc_id, "num": f"EST-{oid}", "oid": str(oid)})
db.commit()
print(f"  created estimate doc: {doc_id}")

# Client approves
r = requests.post(f"{EVT}/orders/{oid}/documents/{doc_id}/approve", json={}, headers=H)
print(f"  approve: status={r.status_code}, body={r.json()}")

# Try second approve (should fail)
r = requests.post(f"{EVT}/orders/{oid}/documents/{doc_id}/approve", json={}, headers=H)
print(f"  approve again: status={r.status_code} (expected 400)")

# Verify in DB
row = db.execute(text("SELECT status FROM documents WHERE id = :id"), {"id": doc_id}).fetchone()
print(f"  document status in DB: {row[0]}")
sigs = db.execute(text("""
    SELECT signer_role, signer_name, signature_image FROM document_signatures
    WHERE document_id = :id
"""), {"id": doc_id}).fetchall()
print(f"  signatures: {sigs}")

# === Try approving a non-estimate doc (should reject) ===
doc_id2 = str(uuid.uuid4())
db.execute(text("""
    INSERT INTO documents (id, doc_type, doc_number, entity_type, entity_id, category, status)
    VALUES (:id, 'rental_agreement', :num, 'order', :oid, 'contract', 'draft')
"""), {"id": doc_id2, "num": f"CONTRACT-{oid}", "oid": str(oid)})
db.commit()
r = requests.post(f"{EVT}/orders/{oid}/documents/{doc_id2}/approve", json={}, headers=H)
print(f"  approve contract (should fail): status={r.status_code} body={r.text[:200]}")

# === Cleanup ===
print("\n--- Cleanup ---")
db.execute(text("DELETE FROM document_signatures WHERE document_id IN (:a, :b)"),
           {"a": doc_id, "b": doc_id2})
db.execute(text("DELETE FROM documents WHERE id IN (:a, :b)"),
           {"a": doc_id, "b": doc_id2})
db.execute(text("DELETE FROM order_chat_messages WHERE order_id = :oid"), {"oid": oid})
db.execute(text("DELETE FROM order_items WHERE order_id = :oid"), {"oid": oid})
db.execute(text("DELETE FROM order_lifecycle WHERE order_id = :oid"), {"oid": oid})
db.execute(text("DELETE FROM order_internal_notes WHERE order_id = :oid"), {"oid": oid})
db.execute(text("DELETE FROM orders WHERE order_id = :oid"), {"oid": oid})
db.execute(text("DELETE FROM event_board_items WHERE board_id = :bid"), {"bid": bid})
db.execute(text("DELETE FROM event_boards WHERE id = :bid"), {"bid": bid})
db.execute(text("DELETE FROM event_customers WHERE email = :e"), {"e": email})
db.execute(text("DELETE FROM client_users WHERE email_normalized = :e"), {"e": email.lower()})
db.execute(text("UPDATE products SET quantity = quantity + 1 WHERE product_id = :pid"), {"pid": pid})
db.commit(); db.close()

print("\n✅ ALL P2 TESTS PASSED!")
