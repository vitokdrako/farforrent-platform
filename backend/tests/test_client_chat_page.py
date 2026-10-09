"""
Backend regression suite for the new CLIENT-side standalone chat page (/chat in
the Event Tool frontend at /app/event-tool-source).

Covers:
  - POST /api/event/auth/login (returns access_token)
  - GET  /api/event/orders                            (sidebar source; own orders only)
  - GET  /api/event/orders/{id}/chat/messages         (load conversation)
  - POST /api/event/orders/{id}/chat/messages         (client sends message)
  - GET  /api/event/orders/{id}/chat/unread_count     (badge)
  - Read-marker advances after GET /messages
  - Regression: data-leak fix on /api/event/cabinet/profile
  - Cross-side: client JWT against /api/admin/orders/{id}/chat/* should NOT crash
    (current admin endpoints are unauthenticated — documented tech debt).
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
LOCAL_URL = "http://localhost:8001"

CLIENT_EMAIL = "vitokdrako@gmail.com"
CLIENT_PASSWORD = "test123"

# Order known to belong to Vita (re-used from iteration_7/8 manager-chat suite)
KNOWN_ORDER_ID = 7795


# ---------- fixtures ----------------------------------------------------------

@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def client_token(api):
    r = api.post(
        f"{BASE_URL}/api/event/auth/login",
        json={"email": CLIENT_EMAIL, "password": CLIENT_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"event/auth/login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("access_token")
    assert token, f"missing access_token in event login response: {data}"
    return token


@pytest.fixture(scope="session")
def client_headers(client_token):
    return {"Authorization": f"Bearer {client_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def my_order_id(api, client_headers):
    """Pick first order that belongs to the logged-in client. Falls back to KNOWN_ORDER_ID."""
    r = api.get(f"{BASE_URL}/api/event/orders", headers=client_headers, timeout=20)
    assert r.status_code == 200, f"/api/event/orders failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    orders = body if isinstance(body, list) else (body.get("orders") or body.get("items") or [])
    if not orders:
        pytest.skip("No orders for this client — cannot test chat endpoints")
    # Prefer KNOWN_ORDER_ID if it's present, else first one
    ids = [o.get("order_id") or o.get("id") for o in orders]
    return KNOWN_ORDER_ID if KNOWN_ORDER_ID in ids else ids[0]


# ---------- smoke / regression -----------------------------------------------

class TestSmoke:
    def test_event_health(self, api):
        r = api.get(f"{BASE_URL}/api/event/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_cabinet_profile_data_leak_fix(self, api, client_headers):
        """Regression: cabinet profile must return the *caller's* email."""
        r = api.get(f"{BASE_URL}/api/event/cabinet/profile", headers=client_headers, timeout=15)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        email = body.get("email") or (body.get("user") or {}).get("email")
        assert email and email.lower() == CLIENT_EMAIL.lower(), (
            f"data-leak regression: expected {CLIENT_EMAIL}, got {email}"
        )


# ---------- /api/event/orders (sidebar source) -------------------------------

class TestClientOrdersList:
    def test_returns_200_and_list(self, api, client_headers):
        r = api.get(f"{BASE_URL}/api/event/orders", headers=client_headers, timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        orders = body if isinstance(body, list) else (body.get("orders") or body.get("items") or [])
        assert isinstance(orders, list)

    def test_only_caller_orders_no_leak(self, api, client_headers):
        """
        Each returned order must belong to the calling client. We can't easily
        verify ownership without inspecting the DB, but we DO require that the
        endpoint never returns someone-else's email in any per-order field, and
        that the count is bounded (i.e. not the full table).
        """
        r = api.get(f"{BASE_URL}/api/event/orders", headers=client_headers, timeout=20)
        assert r.status_code == 200
        body = r.json()
        orders = body if isinstance(body, list) else (body.get("orders") or body.get("items") or [])
        # Soft bound — even prolific clients have <100 orders in test db
        assert len(orders) <= 100, f"suspicious order count {len(orders)} — possible leak"
        # If customer_email is exposed per order, must match the caller
        for o in orders:
            ce = (o.get("customer_email") or "").lower().strip()
            if ce:
                assert ce == CLIENT_EMAIL.lower(), (
                    f"Order {o.get('order_id')} exposed foreign customer_email={ce}"
                )

    def test_requires_auth(self, api):
        r = api.get(f"{BASE_URL}/api/event/orders", timeout=15)
        assert r.status_code in (401, 403), f"expected 401/403 without token, got {r.status_code}"


# ---------- client chat: messages -------------------------------------------

class TestClientChatMessages:
    def test_get_messages_returns_list(self, api, client_headers, my_order_id):
        r = api.get(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/messages",
            headers=client_headers,
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert "messages" in body and isinstance(body["messages"], list)
        if body["messages"]:
            m = body["messages"][0]
            for key in ("id", "sender_type", "sender_name", "message", "created_at"):
                assert key in m, f"message missing {key}: {m}"
            assert m["sender_type"] in ("client", "manager", "system")

    def test_send_message_persists_with_sender_type_client(self, api, client_headers, my_order_id):
        marker = f"TEST_client_chat_{int(time.time())}"
        payload = {"message": f"привіт від клієнта {marker}"}

        # POST
        r = api.post(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/messages",
            headers=client_headers,
            json=payload,
            timeout=20,
        )
        assert r.status_code == 200, f"send failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        assert isinstance(body.get("messages"), list)

        # GET to confirm persistence
        r2 = api.get(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/messages",
            headers=client_headers,
            timeout=15,
        )
        assert r2.status_code == 200
        msgs = r2.json()["messages"]
        match = [m for m in msgs if marker in (m.get("message") or "")]
        assert match, f"sent message with marker {marker} not found in GET result"
        assert match[-1]["sender_type"] == "client"
        assert match[-1]["sender_name"]  # non-empty

    def test_send_empty_message_rejected(self, api, client_headers, my_order_id):
        r = api.post(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/messages",
            headers=client_headers,
            json={"message": "   "},
            timeout=15,
        )
        assert r.status_code == 400

    def test_foreign_order_returns_404(self, api, client_headers):
        """Order that does NOT belong to the client should return 404, not 200."""
        # 999999 is unlikely to exist; either way it cannot belong to this client
        r = api.get(
            f"{BASE_URL}/api/event/orders/999999/chat/messages",
            headers=client_headers,
            timeout=15,
        )
        assert r.status_code == 404, f"expected 404 for foreign order, got {r.status_code}"

    def test_requires_auth(self, api, my_order_id):
        r = api.get(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/messages",
            timeout=15,
        )
        assert r.status_code in (401, 403), f"expected 401/403 without token, got {r.status_code}"


# ---------- client chat: unread_count ----------------------------------------

class TestClientChatUnread:
    def test_unread_count_shape(self, api, client_headers, my_order_id):
        r = api.get(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/unread_count",
            headers=client_headers,
            timeout=15,
        )
        assert r.status_code == 200
        body = r.json()
        assert "unread" in body and isinstance(body["unread"], int) and body["unread"] >= 0

    def test_get_messages_marks_manager_messages_read(self, api, client_headers, my_order_id):
        """
        Per order_chat.py:108-113, GET /messages marks all manager+system messages
        as read by the client. So /unread_count right after must be 0.
        """
        r1 = api.get(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/messages",
            headers=client_headers,
            timeout=15,
        )
        assert r1.status_code == 200

        r2 = api.get(
            f"{BASE_URL}/api/event/orders/{my_order_id}/chat/unread_count",
            headers=client_headers,
            timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json()["unread"] == 0


# ---------- cross-side: client token vs admin endpoints ----------------------

class TestClientTokenAgainstAdminChatEndpoints:
    """
    Admin chat endpoints currently DO NOT require auth (tech debt).
    A client JWT hitting /api/admin/orders/{id}/chat/messages will be ignored
    by the endpoint (no auth dependency) and may return 200. The acceptance
    criterion here is purely: it MUST NOT 500, and we document the current
    behaviour for the main agent.
    """

    def test_admin_messages_no_crash(self, api, client_headers, my_order_id):
        r = api.get(
            f"{LOCAL_URL}/api/admin/orders/{my_order_id}/chat/messages",
            headers=client_headers,
            timeout=15,
        )
        assert r.status_code != 500, f"crashed: {r.text[:200]}"
        # Either currently-open (200) or later locked down (401/403/404) — all OK.
        assert r.status_code in (200, 401, 403, 404), f"unexpected: {r.status_code}"
