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
from utils.image_helper import (  # noqa: E402
    normalize_image_url,
    serialize_product_image,
    serialize_order_item_image,
)


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
# Unit tests: NEW serializer mapper layer (iteration_6 refactor)
# Contract: never returns None — returns "" instead so the JSON consumer
# can use a single falsy check uniformly.
# ────────────────────────────────────────────────────────────────────────────
class TestSerializeProductImageUnit:
    def test_uploads_relative_unchanged(self):
        assert serialize_product_image("uploads/products/x.png") == "uploads/products/x.png"

    def test_none_returns_empty_string(self):
        assert serialize_product_image(None) == ""

    def test_empty_returns_empty_string(self):
        assert serialize_product_image("") == ""

    def test_legacy_relative_gets_static_prefix(self):
        assert serialize_product_image("foo.png") == "static/images/foo.png"

    def test_uploads_absolute_unchanged(self):
        assert serialize_product_image("/uploads/x.png") == "/uploads/x.png"

    def test_https_full_url_unchanged(self):
        assert serialize_product_image("https://cdn/x.png") == "https://cdn/x.png"

    def test_return_type_always_str(self):
        # Critical contract: result must never be None
        for v in [None, "", "foo.png", "uploads/x.png", "https://cdn/x.png"]:
            r = serialize_product_image(v)
            assert isinstance(r, str), f"serialize_product_image({v!r}) returned {type(r)}"


class TestSerializeOrderItemImageUnit:
    def test_fallback_used_when_item_image_none(self):
        assert (
            serialize_order_item_image(None, "uploads/products/p.png")
            == "uploads/products/p.png"
        )

    def test_per_item_override_preferred(self):
        assert (
            serialize_order_item_image("uploads/products/o.png", "uploads/products/p.png")
            == "uploads/products/o.png"
        )

    def test_both_none_returns_empty_string(self):
        assert serialize_order_item_image(None, None) == ""

    def test_both_empty_returns_empty_string(self):
        assert serialize_order_item_image("", "") == ""

    def test_empty_item_falls_back_to_product(self):
        # "" is falsy, so fallback should kick in
        assert (
            serialize_order_item_image("", "uploads/products/p.png")
            == "uploads/products/p.png"
        )

    def test_legacy_relative_item_gets_static_prefix(self):
        assert serialize_order_item_image("foo.png", None) == "static/images/foo.png"

    def test_return_type_always_str(self):
        for a, b in [(None, None), ("", ""), ("x.png", None), (None, "y.png")]:
            r = serialize_order_item_image(a, b)
            assert isinstance(r, str), (
                f"serialize_order_item_image({a!r},{b!r}) returned {type(r)}"
            )


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


# ────────────────────────────────────────────────────────────────────────────
# NEW: contract checks for mapper-layer refactor.
# After iteration_6, every image_url-emitting endpoint must return a STRING
# (never None) per the serialize_product_image / serialize_order_item_image
# contract.
# ────────────────────────────────────────────────────────────────────────────
class TestImageUrlIsAlwaysString:
    def test_products_list_image_url_is_string(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/event/products?limit=10", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        if isinstance(data, dict):
            data = data.get("products") or data.get("items") or data.get("data") or []
        assert isinstance(data, list) and len(data) > 0
        for p in data:
            url = p.get("image_url")
            pid = p.get("product_id") or p.get("id")
            assert isinstance(url, str), (
                f"product {pid}: image_url must be str per new contract, "
                f"got {type(url).__name__}={url!r}"
            )
            assert "uploads/uploads/" not in url, f"product {pid}: double prefix"

    def test_product_detail_image_url_is_string(self, api_client):
        r = api_client.get(f"{BASE_URL}/api/event/products?limit=5", timeout=15)
        data = r.json()
        if isinstance(data, dict):
            data = data.get("products") or data.get("items") or data.get("data") or []
        if not data:
            pytest.skip("no products available")
        pid = data[0].get("product_id") or data[0].get("id")
        r = api_client.get(f"{BASE_URL}/api/event/products/{pid}", timeout=15)
        assert r.status_code == 200
        detail = r.json()
        # Top-level image_url must be a str now
        assert isinstance(detail.get("image_url"), str), (
            f"product {pid}: detail.image_url must be str, "
            f"got {type(detail.get('image_url')).__name__}"
        )
        # primary_image is allowed to be None per agent note ("possibly None")
        pi = detail.get("primary_image")
        assert pi is None or isinstance(pi, str), (
            f"product {pid}: primary_image must be str or None, got {type(pi).__name__}"
        )
        # images[] urls must all be strings, no None-in-list
        for i, img in enumerate(detail.get("images") or []):
            url = img if isinstance(img, str) else (
                img.get("url") or img.get("image_url")
            )
            assert isinstance(url, str), (
                f"product {pid} images[{i}]: must be str, got {type(url).__name__}"
            )

    def test_order_detail_item_image_url_is_string(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/event/orders", timeout=15)
        assert r.status_code == 200
        orders = r.json()
        if isinstance(orders, dict):
            orders = (
                orders.get("orders") or orders.get("items") or orders.get("data") or []
            )
        order_ids = [
            o.get("order_id") or o.get("id") for o in orders if (o.get("order_id") or o.get("id"))
        ]
        if not order_ids:
            pytest.skip("no orders to inspect")
        checked = False
        for oid in order_ids[:5]:
            r = auth_client.get(f"{BASE_URL}/api/event/orders/{oid}", timeout=15)
            if r.status_code != 200:
                continue
            for i, item in enumerate(r.json().get("items") or []):
                url = item.get("image_url")
                assert isinstance(url, str), (
                    f"order {oid} item[{i}]: image_url must be str, "
                    f"got {type(url).__name__}={url!r}"
                )
                assert "uploads/uploads/" not in url
            checked = True
        if not checked:
            pytest.skip("no accessible orders")

    def test_boards_list_and_detail_image_url_is_string(self, auth_client):
        r = auth_client.get(f"{BASE_URL}/api/event/boards", timeout=15)
        # Boards endpoint may 404 or 200 depending on user state — only assert if 200
        if r.status_code != 200:
            pytest.skip(f"/boards returned {r.status_code}; skipping")
        data = r.json()
        boards = data if isinstance(data, list) else (
            data.get("boards") or data.get("items") or []
        )
        for b in boards:
            # Boards-list level: each board may have products inside
            items = b.get("products") or b.get("items") or []
            for it in items:
                p = it.get("product") or it
                url = p.get("image_url")
                if url is not None:
                    assert isinstance(url, str), (
                        f"boards-list: image_url must be str, got {type(url).__name__}"
                    )
                    assert "uploads/uploads/" not in url
        # Pick first board for detail
        if not boards:
            return
        bid = boards[0].get("board_id") or boards[0].get("id")
        if bid is None:
            return
        r = auth_client.get(f"{BASE_URL}/api/event/boards/{bid}", timeout=15)
        if r.status_code != 200:
            return
        d = r.json()
        for it in (d.get("products") or d.get("items") or []):
            p = it.get("product") or it
            url = p.get("image_url")
            if url is not None:
                assert isinstance(url, str), (
                    f"board {bid} detail: image_url must be str, got {type(url).__name__}"
                )
                assert "uploads/uploads/" not in url
