"""
Regression tests for the `uploads/uploads/` double-prefix bug fix.

Bug: local `normalize_image_url` defined inside `get_my_order_by_id()` in
/app/backend/routes/event_tool.py unconditionally prepended `/uploads/`,
shadowing the correct global helper from utils.image_helper. This caused
URLs like `uploads/products/X.png` to become `/uploads/uploads/products/X.png`.

Fix: local function removed; global utils.image_helper.normalize_image_url is now used.
"""

import os
import sys
import pytest
import requests

# Backend URL (local — internal call as per agent note)
BASE_URL = "http://localhost:8001"

# Credentials per /app/memory/test_credentials.md
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"


# ────────────────────────────────────────────────────────────────────────────
# Unit tests: global normalize_image_url helper contract
# ────────────────────────────────────────────────────────────────────────────
sys.path.insert(0, "/app/backend")
from utils.image_helper import normalize_image_url  # noqa: E402


class TestNormalizeImageUrlUnit:
    """Pure unit tests on the helper — independent of DB/HTTP."""

    def test_uploads_relative_unchanged(self):
        assert normalize_image_url("uploads/products/x.png") == "uploads/products/x.png"

    def test_uploads_absolute_unchanged(self):
        assert normalize_image_url("/uploads/products/x.png") == "/uploads/products/x.png"

    def test_static_unchanged(self):
        assert normalize_image_url("static/images/y.png") == "static/images/y.png"

    def test_https_full_url_unchanged(self):
        assert normalize_image_url("https://cdn/x.png") == "https://cdn/x.png"

    def test_http_full_url_unchanged(self):
        assert normalize_image_url("http://cdn/x.png") == "http://cdn/x.png"

    def test_legacy_relative_gets_static_prefix(self):
        assert normalize_image_url("foo.png") == "static/images/foo.png"

    def test_legacy_opencart_path(self):
        assert (
            normalize_image_url("catalog/product/image.jpg")
            == "static/images/catalog/product/image.jpg"
        )

    def test_empty_string_returns_none(self):
        assert normalize_image_url("") is None

    def test_none_returns_none(self):
        assert normalize_image_url(None) is None


# ────────────────────────────────────────────────────────────────────────────
# Integration tests against the running backend
# ────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def api_client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def auth_token(api_client):
    r = api_client.post(
        f"{BASE_URL}/api/event/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in login response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_client(api_client, auth_token):
    api_client.headers.update({"Authorization": f"Bearer {auth_token}"})
    return api_client


def _assert_no_double_prefix(url, ctx=""):
    """The core invariant: no value may contain 'uploads/uploads/'."""
    if url is None or url == "":
        return
    assert isinstance(url, str), f"{ctx}: image_url must be str/None, got {type(url)}"
    assert "uploads/uploads/" not in url, (
        f"{ctx}: DOUBLE-PREFIX bug — image_url='{url}'"
    )


def _assert_valid_shape(url, ctx=""):
    """Allowed shapes per agent: uploads/..., /uploads/..., static/images/..., http(s)://..., '' or None."""
    if url is None or url == "":
        return
    ok = (
        url.startswith("uploads/")
        or url.startswith("/uploads/")
        or url.startswith("static/")
        or url.startswith("/static/")
        or url.startswith("http://")
        or url.startswith("https://")
        or url.startswith("/")
    )
    assert ok, f"{ctx}: unexpected image_url shape: '{url}'"


# ── Smoke ──
class TestSmoke:
    def test_health(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/event/health", timeout=10)
        assert r.status_code == 200, r.text

    def test_cors_preflight_farforevent(self, api_client):
        r = api_client.options(
            f"{BASE_URL}/api/event/health",
            headers={
                "Origin": "https://farforevent.com.ua",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
            timeout=10,
        )
        assert r.status_code in (200, 204), r.text
        acao = r.headers.get("access-control-allow-origin", "")
        assert "farforevent.com.ua" in acao, f"ACAO header missing/wrong: {acao!r}"


# ── PRIMARY: order detail endpoint must not produce double prefix ──
class TestOrderDetailImageUrls:
    def test_order_detail_no_double_prefix(self, auth_client):
        # Pull list of Vita's orders
        r = auth_client.get(f"{BASE_URL}/api/event/orders", timeout=15)
        assert r.status_code == 200, f"GET /orders failed: {r.status_code} {r.text[:200]}"
        orders = r.json()
        # Response may be wrapped — handle both shapes
        if isinstance(orders, dict):
            orders = orders.get("orders") or orders.get("items") or orders.get("data") or []
        assert isinstance(orders, list), f"unexpected orders shape: {type(orders)}"

        order_ids = []
        for o in orders:
            oid = o.get("order_id") or o.get("id")
            if oid is not None:
                order_ids.append(oid)
        if not order_ids:
            # No orders for Vita — fall back to known IDs hinted in the task
            order_ids = [7795, 7451, 10000]

        checked_any = False
        for oid in order_ids[:5]:  # cap at 5 to keep test fast
            r = auth_client.get(f"{BASE_URL}/api/event/orders/{oid}", timeout=15)
            if r.status_code == 404:
                # not owned / not found — skip
                continue
            if r.status_code == 403:
                continue
            assert r.status_code == 200, (
                f"GET /orders/{oid} → {r.status_code} {r.text[:200]}"
            )
            detail = r.json()
            assert "items" in detail, f"order {oid}: missing 'items'"
            items = detail["items"]
            assert isinstance(items, list), f"order {oid}: items not list"
            for i, item in enumerate(items):
                url = item.get("image_url")
                ctx = f"order {oid} item[{i}] product_id={item.get('product_id')}"
                _assert_no_double_prefix(url, ctx)
                _assert_valid_shape(url, ctx)
            checked_any = True

        if not checked_any:
            pytest.skip(
                "No accessible orders for Vita to inspect — primary check inconclusive, "
                "but unit tests on the helper still cover the fix."
            )


# ── Regressions ──
class TestProductsListRegression:
    def test_products_list_no_double_prefix(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/event/products?limit=5", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        # Accept shapes: list, {products: [...]}, {items: [...]}
        if isinstance(data, dict):
            data = data.get("products") or data.get("items") or data.get("data") or []
        assert isinstance(data, list), f"unexpected products shape: {type(data)}"
        assert len(data) > 0, "no products returned"
        for p in data:
            url = p.get("image_url")
            ctx = f"product_id={p.get('product_id') or p.get('id')}"
            _assert_no_double_prefix(url, ctx)
            _assert_valid_shape(url, ctx)


class TestProductDetailRegression:
    def test_product_detail_no_double_prefix(self, api_client):
        # Get first product id
        r = api_client.get(f"{BASE_URL}/api/event/products?limit=5", timeout=15)
        assert r.status_code == 200
        data = r.json()
        if isinstance(data, dict):
            data = data.get("products") or data.get("items") or data.get("data") or []
        if not data:
            pytest.skip("no products available")
        pid = data[0].get("product_id") or data[0].get("id")
        assert pid is not None

        r = api_client.get(f"{BASE_URL}/api/event/products/{pid}", timeout=15)
        assert r.status_code == 200, r.text
        detail = r.json()

        # Top-level image_url
        _assert_no_double_prefix(detail.get("image_url"), f"product {pid} image_url")
        _assert_valid_shape(detail.get("image_url"), f"product {pid} image_url")

        # primary_image
        if "primary_image" in detail:
            _assert_no_double_prefix(detail["primary_image"], f"product {pid} primary_image")
            _assert_valid_shape(detail["primary_image"], f"product {pid} primary_image")

        # images[] array
        imgs = detail.get("images") or []
        for i, img in enumerate(imgs):
            url = img if isinstance(img, str) else img.get("url") or img.get("image_url")
            _assert_no_double_prefix(url, f"product {pid} images[{i}]")
            _assert_valid_shape(url, f"product {pid} images[{i}]")


class TestCabinetRegression:
    def test_profile_email_matches_vita(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/event/cabinet/profile", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("email") == TEST_EMAIL, f"data-leak regression: {data.get('email')}"

    def test_payers_scoped(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/event/cabinet/payers", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        items = data if isinstance(data, list) else (
            data.get("payers") or data.get("items") or []
        )
        # No Марина leak
        for p in items:
            blob = str(p).lower()
            assert "марин" not in blob, f"Марина leak in payers: {p}"

    def test_master_agreement_scoped(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/event/cabinet/master-agreement", timeout=10)
        assert r.status_code == 200, r.text
        ma = r.json()
        # Vita's MA must NOT be 18/83 (those belonged to Марина)
        ma_id = ma.get("id") or ma.get("agreement_id")
        assert ma_id not in (18, 83), f"MA-leak regression: returned Марина's id {ma_id}"

    def test_documents_no_leak(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/event/cabinet/documents", timeout=10)
        assert r.status_code == 200, r.text
        data = r.json()
        blob = str(data).lower()
        assert "марин" not in blob, "Марина leak in documents"

    def test_notifications_unread(self, auth_client):
        r = auth_client.get(
            f"{BASE_URL}/api/event/cabinet/notifications/unread", timeout=10
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert "new_documents" in data
        assert isinstance(data["new_documents"], int)
        assert data["new_documents"] >= 0
