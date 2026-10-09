"""
Test Settlement Act direct opening and editable charge forms
Tests for iteration_26:
- GET /api/documents/settlement-act/{order_id}/preview - direct opening
- GET /api/documents/settlement-act/{order_id}/pdf 
- GET /api/finance/order/{order_id}/charges - charges data with damage and late sections
- POST /api/finance/order/{order_id}/charges/add - add late/damage charges
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com')
TEST_ORDER_ID = 7396

@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "vitokdrako@gmail.com", "password": "test123"}
    )
    if response.status_code == 200:
        data = response.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code}")

@pytest.fixture
def auth_headers(auth_token):
    """Headers with auth token"""
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestSettlementActDirectOpening:
    """Test settlement act preview/pdf endpoints"""
    
    def test_settlement_act_preview_returns_200(self, auth_headers):
        """GET /api/documents/settlement-act/{order_id}/preview returns 200 with HTML"""
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{TEST_ORDER_ID}/preview",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        # Verify HTML content
        assert "text/html" in response.headers.get("content-type", "").lower() or "<html" in response.text.lower()
        print(f"PASS: Settlement act preview returns HTML (length: {len(response.text)})")
    
    def test_settlement_act_pdf_returns_200(self, auth_headers):
        """GET /api/documents/settlement-act/{order_id}/pdf returns 200"""
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{TEST_ORDER_ID}/pdf",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        print("PASS: Settlement act PDF endpoint returns 200")


class TestOrderChargesAPI:
    """Test charges API for late fees and damage charges"""
    
    def test_get_charges_returns_damage_and_late(self, auth_headers):
        """GET /api/finance/order/{order_id}/charges returns charges with damage and late sections"""
        response = requests.get(
            f"{BASE_URL}/api/finance/order/{TEST_ORDER_ID}/charges",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        # Verify structure has damage section
        assert "damage" in data, "Response should have 'damage' section"
        assert "total" in data["damage"], "Damage section should have 'total'"
        assert "paid" in data["damage"], "Damage section should have 'paid'"
        assert "due" in data["damage"], "Damage section should have 'due'"
        
        # Verify structure has late section
        assert "late" in data, "Response should have 'late' section"
        assert "total" in data["late"], "Late section should have 'total'"
        assert "paid" in data["late"], "Late section should have 'paid'"
        assert "due" in data["late"], "Late section should have 'due'"
        
        print(f"PASS: Charges API returns damage (due: {data['damage']['due']}) and late (due: {data['late']['due']})")
    
    def test_add_late_fee_charge(self, auth_headers):
        """POST /api/finance/order/{order_id}/charges/add with type='late' returns success"""
        response = requests.post(
            f"{BASE_URL}/api/finance/order/{TEST_ORDER_ID}/charges/add",
            headers=auth_headers,
            json={"type": "late", "amount": 100, "note": "Test late fee - auto test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("type") == "late", "Should return type='late'"
        assert data.get("amount") == 100, "Should return amount=100"
        print("PASS: Late fee charge added successfully")
    
    def test_add_damage_charge(self, auth_headers):
        """POST /api/finance/order/{order_id}/charges/add with type='damage' returns success"""
        response = requests.post(
            f"{BASE_URL}/api/finance/order/{TEST_ORDER_ID}/charges/add",
            headers=auth_headers,
            json={"type": "damage", "amount": 50, "note": "Test damage charge - auto test"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") == True, f"Expected success=True, got {data}"
        assert data.get("type") == "damage", "Should return type='damage'"
        assert data.get("amount") == 50, "Should return amount=50"
        print("PASS: Damage charge added successfully")


class TestAlternativeOrderCharges:
    """Test with alternative order 7380"""
    
    def test_get_charges_order_7380(self, auth_headers):
        """GET /api/finance/order/7380/charges returns valid structure"""
        response = requests.get(
            f"{BASE_URL}/api/finance/order/7380/charges",
            headers=auth_headers
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "damage" in data and "late" in data, "Should have damage and late sections"
        print(f"PASS: Order 7380 charges - damage due: {data['damage']['due']}, late due: {data['late']['due']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
