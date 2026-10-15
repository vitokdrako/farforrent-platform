"""
Phase 1 Multi-Warehouse backend tests.
Covers: warehouses CRUD, _me/accessible, warehouse_id filtering on key endpoints.
"""
import os
import datetime
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://item-photos.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "vitokdrako@gmail.com"
ADMIN_PASS = "test123"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def test_warehouse_id(admin_client):
    """Create test PL warehouse, yield id, delete after module."""
    # Cleanup previous leftover PL (if present) by listing w/ include_inactive and skipping is_default
    payload = {
        "code": f"PLT{datetime.datetime.utcnow().strftime('%H%M%S')}",
        "name": "TEST_Warszawa",
        "country": "PL",
        "city": "Warsaw",
        "currency": "EUR",
        "timezone": "Europe/Warsaw",
        "is_default": False,
        "is_active": True,
    }
    r = admin_client.post(f"{BASE_URL}/api/admin/warehouses", json=payload)
    assert r.status_code == 201, f"create warehouse failed: {r.status_code} {r.text}"
    wid = r.json()["id"]
    yield wid
    # Cleanup — soft delete (archive)
    admin_client.delete(f"{BASE_URL}/api/admin/warehouses/{wid}")


# ---------- Warehouse CRUD / listing ----------
class TestWarehousesCRUD:
    def test_me_accessible_contains_ua(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/warehouses/_me/accessible")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        ua = [w for w in data if w.get("country") == "UA"]
        assert ua, f"Expected UA warehouse in list: {data}"
        # Default UA
        assert any(w.get("is_default") for w in ua)

    def test_list_warehouses_has_stats(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/admin/warehouses")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list) and len(data) >= 1
        ua = next((w for w in data if w.get("country") == "UA"), None)
        assert ua is not None
        assert "stats" in ua
        for key in ("products", "orders", "clients"):
            assert key in ua["stats"]
            assert isinstance(ua["stats"][key], int)

    def test_create_then_get_test_warehouse(self, admin_client, test_warehouse_id):
        r = admin_client.get(f"{BASE_URL}/api/admin/warehouses/{test_warehouse_id}")
        assert r.status_code == 200
        data = r.json()
        assert data["country"] == "PL"
        assert data["currency"] == "EUR"
        assert data["is_default"] is False
        assert data["is_active"] is True

    def test_newly_created_appears_in_me_accessible(self, admin_client, test_warehouse_id):
        r = admin_client.get(f"{BASE_URL}/api/admin/warehouses/_me/accessible")
        assert r.status_code == 200
        ids = [w["id"] for w in r.json()]
        assert test_warehouse_id in ids


# ---------- warehouse_id filtering ----------
class TestWarehouseFiltering:
    def test_dashboard_overview_ua(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/manager/dashboard/overview", params={"warehouse_id": 1})
        assert r.status_code == 200, r.text
        data = r.json()
        # Expected keys
        for key in ("orders_awaiting", "decor_orders", "issue_cards", "finance_summary", "cleaning_stats"):
            assert key in data, f"Missing key {key} in dashboard overview: {list(data.keys())}"

    def test_dashboard_overview_new_wh_is_empty(self, admin_client, test_warehouse_id):
        r = admin_client.get(f"{BASE_URL}/api/manager/dashboard/overview", params={"warehouse_id": test_warehouse_id})
        assert r.status_code == 200, r.text
        data = r.json()
        # New warehouse should have 0 / empty values
        # orders_awaiting could be list or dict with count
        oa = data.get("orders_awaiting")
        if isinstance(oa, list):
            assert len(oa) == 0, f"Expected empty orders_awaiting for new wh, got {len(oa)}"
        elif isinstance(oa, dict):
            # look for any count-ish fields = 0
            for k, v in oa.items():
                if "count" in k.lower() and isinstance(v, int):
                    assert v == 0, f"Expected 0 for {k}, got {v}"

    def test_picking_list_ua(self, admin_client):
        today = datetime.date.today().isoformat()
        r = admin_client.get(
            f"{BASE_URL}/api/manager/picking-list",
            params={"warehouse_id": 1, "date": today, "include_awaiting": "true"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "summary" in data or "items" in data or isinstance(data, dict)

    def test_picking_list_new_wh_empty(self, admin_client, test_warehouse_id):
        today = datetime.date.today().isoformat()
        r = admin_client.get(
            f"{BASE_URL}/api/manager/picking-list",
            params={"warehouse_id": test_warehouse_id, "date": today, "include_awaiting": "true"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") or data.get("orders") or []
        assert len(items) == 0, f"Expected empty picking list for new wh, got {len(items)}"

    def test_returns_list_ua(self, admin_client):
        today = datetime.date.today().isoformat()
        r = admin_client.get(f"{BASE_URL}/api/manager/returns-list", params={"warehouse_id": 1, "date": today})
        assert r.status_code == 200, r.text

    def test_returns_list_new_wh_empty(self, admin_client, test_warehouse_id):
        today = datetime.date.today().isoformat()
        r = admin_client.get(
            f"{BASE_URL}/api/manager/returns-list",
            params={"warehouse_id": test_warehouse_id, "date": today},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        items = data.get("items") or data.get("orders") or []
        assert len(items) == 0

    def test_overdue_list_ua(self, admin_client):
        r = admin_client.get(f"{BASE_URL}/api/manager/overdue-list", params={"warehouse_id": 1})
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data.get("summary") or data
        for key in ("mild_count", "serious_count", "critical_count", "total_count"):
            assert key in summary, f"Missing {key} in overdue summary: {list(summary.keys())}"

    def test_overdue_list_new_wh_empty(self, admin_client, test_warehouse_id):
        r = admin_client.get(f"{BASE_URL}/api/manager/overdue-list", params={"warehouse_id": test_warehouse_id})
        assert r.status_code == 200, r.text
        data = r.json()
        summary = data.get("summary") or data
        assert summary.get("total_count", 0) == 0
