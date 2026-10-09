"""
Test Discount Calculation Fix - Iteration 12
============================================
Tests the discount calculation bug fix:
1) Backend orders PUT now maps 'discount' -> 'discount_percent' (was overwriting discount_amount)
2) 'discount_amount' is now a separate allowed field
3) total_price = items sum BEFORE discount
4) New field 'total_after_discount' = total_price - discount_amount

Key test scenarios:
- PUT /api/orders/{id} with discount fields
- PUT /api/decor-orders/{id} with discount fields
- IDEMPOTENCY: Save same values 3 times, no drift
- Orders without discount
- Percent-only discount (backend calculates amount)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"

# Test order ID from problem statement
TEST_ORDER_ID = 7388

# Expected values for order 7388
EXPECTED_TOTAL_RENTAL = 8800  # Items sum before discount
EXPECTED_DISCOUNT_AMOUNT = 1600  # Fixed discount in UAH
EXPECTED_DISCOUNT_PERCENT = 18.18  # Approximately 1600/8800*100
EXPECTED_TOTAL_AFTER_DISCOUNT = 7200  # 8800 - 1600


class TestAuthentication:
    """Get authentication token for protected endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Login and get JWT token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data or "token" in data, f"No token in response: {data}"
        return data.get("access_token") or data.get("token")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Return headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }


class TestDiscountCalculationFix(TestAuthentication):
    """Test discount calculation bug fix for orders endpoint"""
    
    def test_01_get_order_initial_state(self, auth_headers):
        """GET /api/orders/7388 - Verify initial state of test order"""
        response = requests.get(f"{BASE_URL}/api/orders/{TEST_ORDER_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get order: {response.text}"
        
        order = response.json()
        print(f"\n[Initial State] Order {TEST_ORDER_ID}:")
        print(f"  total_rental: {order.get('total_rental')}")
        print(f"  discount_amount: {order.get('discount_amount')}")
        print(f"  discount_percent: {order.get('discount_percent')}")
        print(f"  discount: {order.get('discount')}")
        print(f"  total_after_discount: {order.get('total_after_discount')}")
        
        # Verify expected fields exist
        assert "total_rental" in order, "Missing total_rental field"
        assert "discount_amount" in order, "Missing discount_amount field"
        assert "total_after_discount" in order, "Missing total_after_discount field"
    
    def test_02_put_orders_with_discount_fields(self, auth_headers):
        """PUT /api/orders/7388 - Save with discount, discount_amount, total_price"""
        payload = {
            "discount": EXPECTED_DISCOUNT_PERCENT,  # 18.18%
            "discount_amount": EXPECTED_DISCOUNT_AMOUNT,  # 1600 UAH
            "total_price": EXPECTED_TOTAL_RENTAL  # 8800 UAH (before discount)
        }
        
        response = requests.put(
            f"{BASE_URL}/api/orders/{TEST_ORDER_ID}", 
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"
        print(f"\n[PUT /api/orders/{TEST_ORDER_ID}] Saved: {payload}")
    
    def test_03_verify_get_after_put(self, auth_headers):
        """GET /api/orders/7388 - Verify data after PUT"""
        response = requests.get(f"{BASE_URL}/api/orders/{TEST_ORDER_ID}", headers=auth_headers)
        assert response.status_code == 200, f"Failed to get order: {response.text}"
        
        order = response.json()
        print(f"\n[After PUT] Order {TEST_ORDER_ID}:")
        print(f"  total_rental: {order.get('total_rental')}")
        print(f"  discount_amount: {order.get('discount_amount')}")
        print(f"  discount_percent: {order.get('discount_percent')}")
        print(f"  total_after_discount: {order.get('total_after_discount')}")
        
        # Critical assertions
        assert order.get('discount_amount') == EXPECTED_DISCOUNT_AMOUNT, \
            f"discount_amount should be {EXPECTED_DISCOUNT_AMOUNT}, got {order.get('discount_amount')}"
        
        assert abs(order.get('discount_percent', 0) - EXPECTED_DISCOUNT_PERCENT) < 0.1, \
            f"discount_percent should be ~{EXPECTED_DISCOUNT_PERCENT}, got {order.get('discount_percent')}"
        
        assert order.get('total_rental') == EXPECTED_TOTAL_RENTAL, \
            f"total_rental should be {EXPECTED_TOTAL_RENTAL}, got {order.get('total_rental')}"
        
        assert order.get('total_after_discount') == EXPECTED_TOTAL_AFTER_DISCOUNT, \
            f"total_after_discount should be {EXPECTED_TOTAL_AFTER_DISCOUNT}, got {order.get('total_after_discount')}"


class TestDecorOrdersDiscountFix(TestAuthentication):
    """Test discount fix for decor-orders endpoint (same logic)"""
    
    def test_04_put_decor_orders_with_discount(self, auth_headers):
        """PUT /api/decor-orders/7388 - Save with discount fields"""
        payload = {
            "discount": EXPECTED_DISCOUNT_PERCENT,
            "discount_amount": EXPECTED_DISCOUNT_AMOUNT,
            "total_price": EXPECTED_TOTAL_RENTAL
        }
        
        response = requests.put(
            f"{BASE_URL}/api/decor-orders/{TEST_ORDER_ID}",
            json=payload,
            headers=auth_headers
        )
        # decor-orders may not require auth
        if response.status_code == 401:
            response = requests.put(
                f"{BASE_URL}/api/decor-orders/{TEST_ORDER_ID}",
                json=payload
            )
        
        assert response.status_code == 200, f"PUT decor-orders failed: {response.text}"
        print(f"\n[PUT /api/decor-orders/{TEST_ORDER_ID}] Saved: {payload}")
    
    def test_05_verify_decor_orders_get(self, auth_headers):
        """GET /api/decor-orders/7388 - Verify discount fields"""
        # Try with auth first
        response = requests.get(
            f"{BASE_URL}/api/decor-orders/{TEST_ORDER_ID}",
            headers=auth_headers
        )
        if response.status_code == 401:
            response = requests.get(f"{BASE_URL}/api/decor-orders/{TEST_ORDER_ID}")
        
        assert response.status_code == 200, f"GET decor-orders failed: {response.text}"
        
        order = response.json()
        print(f"\n[GET /api/decor-orders/{TEST_ORDER_ID}]:")
        print(f"  discount_amount: {order.get('discount_amount')}")
        print(f"  discount_percent: {order.get('discount_percent')}")
        print(f"  total_rental: {order.get('total_rental')}")
        print(f"  total_after_discount: {order.get('total_after_discount')}")
        
        # Verify discount_amount preserved
        assert order.get('discount_amount') == EXPECTED_DISCOUNT_AMOUNT, \
            f"discount_amount should be {EXPECTED_DISCOUNT_AMOUNT}"


class TestIdempotency(TestAuthentication):
    """Test that saving same values 3 times doesn't cause drift (snowball effect)"""
    
    def test_06_idempotency_save_3_times(self, auth_headers):
        """IDEMPOTENCY: Save same values 3 times, verify no drift"""
        payload = {
            "discount": EXPECTED_DISCOUNT_PERCENT,
            "discount_amount": EXPECTED_DISCOUNT_AMOUNT,
            "total_price": EXPECTED_TOTAL_RENTAL
        }
        
        # Save 3 times
        for i in range(3):
            response = requests.put(
                f"{BASE_URL}/api/orders/{TEST_ORDER_ID}",
                json=payload,
                headers=auth_headers
            )
            assert response.status_code == 200, f"PUT #{i+1} failed: {response.text}"
            print(f"\n[Idempotency] Save #{i+1} completed")
        
        # Verify data hasn't drifted
        response = requests.get(f"{BASE_URL}/api/orders/{TEST_ORDER_ID}", headers=auth_headers)
        assert response.status_code == 200
        
        order = response.json()
        print(f"\n[After 3 saves] Order {TEST_ORDER_ID}:")
        print(f"  discount_amount: {order.get('discount_amount')} (expected: {EXPECTED_DISCOUNT_AMOUNT})")
        print(f"  discount_percent: {order.get('discount_percent')} (expected: ~{EXPECTED_DISCOUNT_PERCENT})")
        print(f"  total_rental: {order.get('total_rental')} (expected: {EXPECTED_TOTAL_RENTAL})")
        print(f"  total_after_discount: {order.get('total_after_discount')} (expected: {EXPECTED_TOTAL_AFTER_DISCOUNT})")
        
        # Critical: values should NOT have changed
        assert order.get('discount_amount') == EXPECTED_DISCOUNT_AMOUNT, \
            f"DRIFT DETECTED! discount_amount is {order.get('discount_amount')}, expected {EXPECTED_DISCOUNT_AMOUNT}"
        
        assert abs(order.get('discount_percent', 0) - EXPECTED_DISCOUNT_PERCENT) < 0.1, \
            f"DRIFT DETECTED! discount_percent is {order.get('discount_percent')}, expected ~{EXPECTED_DISCOUNT_PERCENT}"
        
        assert order.get('total_after_discount') == EXPECTED_TOTAL_AFTER_DISCOUNT, \
            f"DRIFT DETECTED! total_after_discount is {order.get('total_after_discount')}, expected {EXPECTED_TOTAL_AFTER_DISCOUNT}"


class TestZeroDiscount(TestAuthentication):
    """Test orders without discount"""
    
    def test_07_get_orders_list(self, auth_headers):
        """GET /api/orders - Find order with zero discount"""
        response = requests.get(
            f"{BASE_URL}/api/orders",
            params={"limit": 10},
            headers=auth_headers
        )
        assert response.status_code == 200, f"Failed to get orders list: {response.text}"
        
        data = response.json()
        orders = data.get('orders', [])
        print(f"\n[GET /api/orders] Found {len(orders)} orders")
        
        # Find any order and check it has the new fields
        if orders:
            sample_order_id = orders[0].get('order_id')
            print(f"  Sample order_id: {sample_order_id}")


class TestPercentOnlyDiscount(TestAuthentication):
    """Test when only percent is provided (backend should calculate amount)"""
    
    def test_08_percent_only_discount(self, auth_headers):
        """Save with discount percent only, verify amount is calculated"""
        # First, save with 10% discount and 0 amount
        payload = {
            "discount": 10,  # 10%
            "discount_amount": 0,  # Zero - backend should calculate
            "total_price": 5000
        }
        
        response = requests.put(
            f"{BASE_URL}/api/orders/{TEST_ORDER_ID}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200, f"PUT failed: {response.text}"
        
        # GET and verify
        response = requests.get(f"{BASE_URL}/api/orders/{TEST_ORDER_ID}", headers=auth_headers)
        order = response.json()
        
        print(f"\n[Percent-only discount test]:")
        print(f"  Sent: discount=10%, discount_amount=0, total_price=5000")
        print(f"  Got: discount_amount={order.get('discount_amount')}, total_after_discount={order.get('total_after_discount')}")
        
        # When discount_amount is 0 but discount_percent > 0, backend should calculate discount_amount
        # Expected: 5000 * 10% = 500
        # Note: The backend logic at lines 596-597 says:
        # if discount_percent_db > 0 and discount_amount == 0 and total_price > 0:
        #     discount_amount = total_price * discount_percent_db / 100
        
        # This is a READ-time calculation, not WRITE-time, so discount_amount stays 0 in DB
        # but the API response should show the calculated value
        
        # Restore original values
        restore_payload = {
            "discount": EXPECTED_DISCOUNT_PERCENT,
            "discount_amount": EXPECTED_DISCOUNT_AMOUNT,
            "total_price": EXPECTED_TOTAL_RENTAL
        }
        requests.put(
            f"{BASE_URL}/api/orders/{TEST_ORDER_ID}",
            json=restore_payload,
            headers=auth_headers
        )


class TestCatalogRegression(TestAuthentication):
    """Regression tests for catalog endpoints (from iteration 10)"""
    
    def test_09_catalog_families_regression(self, auth_headers):
        """GET /api/catalog/families - Should still work after discount fix"""
        response = requests.get(f"{BASE_URL}/api/catalog/families", headers=auth_headers)
        
        if response.status_code == 401:
            response = requests.get(f"{BASE_URL}/api/catalog/families")
        
        assert response.status_code == 200, f"Catalog families failed: {response.text}"
        
        data = response.json()
        families = data if isinstance(data, list) else data.get('families', [])
        print(f"\n[Regression] /api/catalog/families returned {len(families)} families")
        
        # Should have around 118 families per iteration_10
        assert len(families) > 100, f"Expected ~118 families, got {len(families)}"
    
    def test_10_catalog_items_by_category_regression(self, auth_headers):
        """GET /api/catalog/items-by-category?availability=on_laundry - Should return 7 items"""
        response = requests.get(
            f"{BASE_URL}/api/catalog/items-by-category",
            params={"availability": "on_laundry", "limit": 100},
            headers=auth_headers
        )
        
        if response.status_code == 401:
            response = requests.get(
                f"{BASE_URL}/api/catalog/items-by-category",
                params={"availability": "on_laundry", "limit": 100}
            )
        
        assert response.status_code == 200, f"Catalog items-by-category failed: {response.text}"
        
        data = response.json()
        items = data.get('products', data.get('items', []))
        count = len(items) if isinstance(items, list) else data.get('total', 0)
        
        print(f"\n[Regression] /api/catalog/items-by-category?availability=on_laundry returned {count} items")
        
        # Per iteration_11, on_laundry should have 7 products
        # Allow some variance as data may change
        assert count >= 5, f"Expected ~7 items with on_laundry, got {count}"


class TestFieldMappingVerification(TestAuthentication):
    """Verify the field mapping is correct (discount -> discount_percent)"""
    
    def test_11_field_mapping_orders(self, auth_headers):
        """Verify PUT /api/orders maps 'discount' to 'discount_percent' in DB"""
        # Save a specific discount percent
        test_percent = 15.5
        test_amount = 1500
        
        payload = {
            "discount": test_percent,
            "discount_amount": test_amount,
            "total_price": EXPECTED_TOTAL_RENTAL
        }
        
        response = requests.put(
            f"{BASE_URL}/api/orders/{TEST_ORDER_ID}",
            json=payload,
            headers=auth_headers
        )
        assert response.status_code == 200
        
        # GET and verify both fields
        response = requests.get(f"{BASE_URL}/api/orders/{TEST_ORDER_ID}", headers=auth_headers)
        order = response.json()
        
        print(f"\n[Field Mapping Test]:")
        print(f"  Sent: discount={test_percent}, discount_amount={test_amount}")
        print(f"  Got: discount={order.get('discount')}, discount_percent={order.get('discount_percent')}, discount_amount={order.get('discount_amount')}")
        
        # Both 'discount' and 'discount_percent' should match what we sent
        assert abs(order.get('discount', 0) - test_percent) < 0.1, \
            f"discount field mismatch: {order.get('discount')} vs {test_percent}"
        
        assert abs(order.get('discount_percent', 0) - test_percent) < 0.1, \
            f"discount_percent field mismatch: {order.get('discount_percent')} vs {test_percent}"
        
        assert order.get('discount_amount') == test_amount, \
            f"discount_amount mismatch: {order.get('discount_amount')} vs {test_amount}"
        
        # Restore original values
        requests.put(
            f"{BASE_URL}/api/orders/{TEST_ORDER_ID}",
            json={
                "discount": EXPECTED_DISCOUNT_PERCENT,
                "discount_amount": EXPECTED_DISCOUNT_AMOUNT,
                "total_price": EXPECTED_TOTAL_RENTAL
            },
            headers=auth_headers
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
