"""
Backend regression suite for the new manager-side standalone chat page
(/manager/chat in frontend).

Covers:
  - GET /api/decor-orders  (sidebar source: list of active orders for managers)
  - GET  /api/admin/orders/{id}/chat/messages   (load conversation; also marks
    client->manager messages as read)
  - POST /api/admin/orders/{id}/chat/messages   (manager replies)
  - GET  /api/admin/orders/{id}/chat/unread_count   (badge in sidebar)
  - Behaviour without auth (must NOT 500)
  - Smoke: backend health, data-leak regression on /api/event/cabinet/profile

Notes:
  Admin chat endpoints in routes/order_chat.py admin_router are mounted with
  prefix /api at server.py:156, so final paths are /api/admin/orders/{id}/chat/*.
  The endpoints currently do NOT require auth (Depends only on DB session). We
  still pass a manager token because the frontend always sends one — and we
  verify the no-auth case separately to confirm they don't crash.
"""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001").rstrip("/")
LOCAL_URL = "http://localhost:8001"  # used for the no-auth smoke to bypass any edge auth

MANAGER_EMAIL = "vitokdrako@gmail.com"
MANAGER_PASSWORD = "test123"

# Vita's known test order — referenced in the review request
TEST_ORDER_ID = 7795


# ---------- fixtures ----------------------------------------------------------

@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def manager_token(api):
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": MANAGER_EMAIL, "password": MANAGER_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    assert "access_token" in data and isinstance(data["access_token"], str)
    return data["access_token"]


@pytest.fixture(scope="session")
def auth_headers(manager_token):
    return {"Authorization": f"Bearer {manager_token}", "Content-Type": "application/json"}


# ---------- smoke -------------------------------------------------------------

class TestSmoke:
    def test_event_health(self, api):
        r = api.get(f"{BASE_URL}/api/event/health", timeout=10)
        assert r.status_code == 200
        assert r.json().get("status") == "ok"

    def test_cabinet_profile_returns_own_email(self, api, auth_headers):
        # Previous data-leak regression: profile must return the caller's email
        r = api.get(f"{BASE_URL}/api/event/cabinet/profile", headers=auth_headers, timeout=10)
        # If endpoint doesn't exist for admin role, accept 404/403; only fail on 500 or wrong email
        assert r.status_code != 500, f"cabinet/profile 500: {r.text[:200]}"
        if r.status_code == 200:
            body = r.json()
            email = body.get("email") or (body.get("user") or {}).get("email")
            assert email == MANAGER_EMAIL, f"expected {MANAGER_EMAIL}, got {email}"


# ---------- decor-orders sidebar ---------------------------------------------

class TestDecorOrdersSidebar:
    """Sidebar of /manager/chat fetches active orders via /api/decor-orders."""

    def test_list_active_orders_returns_200(self, api, auth_headers):
        params = {
            "status": "on_rent,issued,processing,ready_for_issue,awaiting_customer",
            "limit": 10,
        }
        r = api.get(f"{BASE_URL}/api/decor-orders", params=params, headers=auth_headers, timeout=15)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
        body = r.json()
        # Accept either a bare list OR {orders: [...]} wrapper
        if isinstance(body, dict):
            orders = body.get("orders") or body.get("items") or body.get("data") or []
        else:
            orders = body
        assert isinstance(orders, list), f"expected list, got {type(orders).__name__}"

    def test_list_no_auth_does_not_500(self, api):
        # Even without Authorization header the endpoint must not crash
        r = requests.get(
            f"{LOCAL_URL}/api/decor-orders",
            params={"status": "on_rent", "limit": 5},
            timeout=15,
        )
        assert r.status_code != 500, f"server crashed without auth: {r.text[:200]}"


# ---------- admin chat endpoints ---------------------------------------------

class TestAdminChatEndpoints:
    """The three endpoints powering the manager chat page main pane."""

    def test_get_messages_returns_list(self, api, auth_headers):
        r = api.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert "messages" in body, f"missing 'messages' key: {body}"
        assert isinstance(body["messages"], list)

        # If any messages exist, validate shape of the first one
        if body["messages"]:
            m = body["messages"][0]
            for key in ("id", "sender_type", "sender_name", "message", "created_at"):
                assert key in m, f"message missing {key}: {m}"
            assert m["sender_type"] in ("client", "manager", "system"), m["sender_type"]

    def test_unread_count_returns_int(self, api, auth_headers):
        r = api.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/unread_count",
            headers=auth_headers,
            timeout=15,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert "unread" in body
        assert isinstance(body["unread"], int)
        assert body["unread"] >= 0

    def test_send_message_and_persistence(self, api, auth_headers):
        marker = f"TEST_chat_iter7_{int(time.time())}"
        payload = {"message": f"Тест від менеджера {marker}"}

        # POST
        r = api.post(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            headers=auth_headers,
            json=payload,
            timeout=20,
        )
        assert r.status_code == 200, f"send failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        assert "messages" in body and isinstance(body["messages"], list)

        # GET to confirm persistence
        r2 = api.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            headers=auth_headers,
            timeout=15,
        )
        assert r2.status_code == 200
        msgs = r2.json()["messages"]
        match = [m for m in msgs if marker in (m.get("message") or "")]
        assert match, f"sent message with marker {marker} not found in GET result"
        assert match[-1]["sender_type"] == "manager"
        assert match[-1]["sender_name"]  # non-empty

    def test_get_messages_marks_client_messages_read(self, api, auth_headers):
        """
        After GET /messages, all client→manager messages should be marked read,
        so the next /unread_count is 0.
        """
        # First GET — this performs the UPDATE inside the handler
        r1 = api.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            headers=auth_headers,
            timeout=15,
        )
        assert r1.status_code == 200

        r2 = api.get(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/unread_count",
            headers=auth_headers,
            timeout=15,
        )
        assert r2.status_code == 200
        assert r2.json()["unread"] == 0, (
            "unread_count should be 0 right after list_messages marks them read"
        )

    def test_send_empty_message_rejected(self, api, auth_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            headers=auth_headers,
            json={"message": "   "},
            timeout=15,
        )
        assert r.status_code == 400, f"expected 400 for empty msg, got {r.status_code}"


# ---------- no-auth smoke (endpoints currently unprotected) ------------------

class TestAdminChatNoAuthSmoke:
    """
    Per code review, admin chat endpoints don't require auth right now.
    These tests just confirm they don't 500 — they may return 200 (current) or
    401/403 if main agent later locks them down. Either is acceptable, but NOT 500.
    """

    def test_messages_no_auth_does_not_500(self):
        r = requests.get(
            f"{LOCAL_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            timeout=15,
        )
        assert r.status_code != 500, f"crashed: {r.text[:200]}"
        assert r.status_code in (200, 401, 403), f"unexpected: {r.status_code}"

    def test_unread_count_no_auth_does_not_500(self):
        r = requests.get(
            f"{LOCAL_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/unread_count",
            timeout=15,
        )
        assert r.status_code != 500, f"crashed: {r.text[:200]}"
        assert r.status_code in (200, 401, 403), f"unexpected: {r.status_code}"

    def test_send_no_auth_does_not_500(self):
        r = requests.post(
            f"{LOCAL_URL}/api/admin/orders/{TEST_ORDER_ID}/chat/messages",
            json={"message": "noauth-smoke"},
            timeout=15,
        )
        # 200 (currently unprotected) or 401/403 (if locked down) — never 500
        assert r.status_code != 500, f"crashed: {r.text[:200]}"
        assert r.status_code in (200, 400, 401, 403), f"unexpected: {r.status_code}"
