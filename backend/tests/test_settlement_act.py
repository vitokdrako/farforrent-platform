"""
Test Suite for Settlement Act (Акт взаєморозрахунків) Feature

Tests:
1. Backend API: GET /api/documents/settlement-act/{order_id}/preview
2. Backend API: GET /api/documents/settlement-act/{order_id}/pdf
3. Manager override with final_amount query param
4. Refund scenario (negative final_amount)
5. Non-existent order returns 404
6. Admin template list includes settlement_act
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

# Test credentials from review request
TEST_CREDENTIALS = {
    "email": "vitokdrako@gmail.com",
    "password": "test123"
}

# Test order IDs with status 'returned'
TEST_ORDER_IDS = [7396, 7394, 7392]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for testing"""
    try:
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json=TEST_CREDENTIALS,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        print(f"Auth response status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")  # Note: endpoint returns 'access_token' not 'token'
            if token:
                print(f"Auth token obtained: {token[:30]}...")
                return token
        print(f"Auth failed: {response.status_code} - {response.text[:200]}")
    except Exception as e:
        print(f"Auth exception: {e}")
    pytest.skip(f"Authentication failed")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Headers with authentication token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestSettlementActPreview:
    """Tests for GET /api/documents/settlement-act/{order_id}/preview"""

    def test_settlement_act_preview_returns_200(self, auth_headers):
        """Test that settlement act preview returns 200 for valid order"""
        order_id = TEST_ORDER_IDS[0]  # 7396
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/preview",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text[:500]}"
        assert response.headers.get("content-type", "").startswith("text/html"), "Response should be HTML"
        print(f"SUCCESS: Settlement act preview for order {order_id} returns 200 OK")

    def test_settlement_act_preview_contains_key_sections(self, auth_headers):
        """Test that HTML contains all financial sections"""
        order_id = TEST_ORDER_IDS[0]
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/preview",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Check for key Ukrainian text sections
        assert "Акт взаєморозрахунків" in html, "Missing title 'Акт взаєморозрахунків'"
        assert "Нарахування" in html, "Missing section '1. Нарахування'"
        assert "Оплати клієнта" in html, "Missing section '2. Оплати клієнта'"
        assert "Застава" in html, "Missing section '3. Застава'"
        assert "Підсумок розрахунків" in html, "Missing section '4. Підсумок розрахунків'"
        
        # Check for customer/order info card
        assert "Замовник" in html, "Missing 'Замовник' card"
        assert "Деталі оренди" in html, "Missing 'Деталі оренди' card"
        
        print(f"SUCCESS: Settlement act contains all required financial sections")

    def test_settlement_act_nonexistent_order_returns_404(self, auth_headers):
        """Test that non-existent order returns 404"""
        fake_order_id = 999999
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{fake_order_id}/preview",
            headers=auth_headers
        )
        
        assert response.status_code == 404, f"Expected 404 for non-existent order, got {response.status_code}"
        print(f"SUCCESS: Non-existent order {fake_order_id} returns 404")

    def test_settlement_act_with_manager_override(self, auth_headers):
        """Test that manager override with final_amount=1500 works"""
        order_id = TEST_ORDER_IDS[0]
        final_amount = 1500
        manager_note = "Test override note"
        
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/preview",
            params={"final_amount": final_amount, "manager_note": manager_note},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        html = response.text
        
        # Check that manager override is reflected
        assert "Примітка менеджера" in html or "is_manager_override" in html or "1 500" in html or "1,500" in html, \
            "Manager override should appear in document"
        print(f"SUCCESS: Manager override with final_amount={final_amount} works correctly")

    def test_settlement_act_refund_scenario(self, auth_headers):
        """Test refund scenario with negative final_amount=-500"""
        order_id = TEST_ORDER_IDS[0]
        final_amount = -500  # Negative means refund to client
        
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/preview",
            params={"final_amount": final_amount},
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        html = response.text
        
        # Check for refund indication in the document
        # Either shows "до повернення клієнту" or the amount in refund format
        assert "500" in html, "Refund amount should appear in document"
        print(f"SUCCESS: Refund scenario with final_amount={final_amount} works correctly")


class TestSettlementActPDF:
    """Tests for GET /api/documents/settlement-act/{order_id}/pdf"""

    def test_settlement_act_pdf_returns_200(self, auth_headers):
        """Test that settlement act PDF endpoint returns 200"""
        order_id = TEST_ORDER_IDS[0]
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/pdf",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        # PDF endpoint returns HTML with print script
        assert response.headers.get("content-type", "").startswith("text/html"), "PDF endpoint returns HTML"
        print(f"SUCCESS: Settlement act PDF for order {order_id} returns 200 OK")

    def test_settlement_act_pdf_has_print_script(self, auth_headers):
        """Test that PDF endpoint includes auto-print JavaScript"""
        order_id = TEST_ORDER_IDS[0]
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/pdf",
            headers=auth_headers
        )
        
        assert response.status_code == 200
        html = response.text
        
        # Check for print script
        assert "window.print()" in html, "PDF endpoint should include window.print() script"
        print(f"SUCCESS: Settlement act PDF includes auto-print script")


class TestAdminTemplateList:
    """Tests for settlement_act in admin template list"""

    def test_admin_templates_includes_settlement_act(self, auth_headers):
        """Test that /api/admin/templates includes settlement_act"""
        response = requests.get(
            f"{BASE_URL}/api/admin/templates",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        templates = response.json()
        
        # Check if settlement_act is in the list
        template_types = [t.get("doc_type") for t in templates]
        assert "settlement_act" in template_types, \
            f"settlement_act should be in template list. Found: {template_types}"
        
        # Find settlement_act template
        settlement_template = next((t for t in templates if t.get("doc_type") == "settlement_act"), None)
        assert settlement_template is not None, "settlement_act template not found"
        assert settlement_template.get("has_file") == True, "settlement_act should have a template file"
        
        print(f"SUCCESS: settlement_act template found in admin template list")


class TestMultipleOrders:
    """Test settlement act across multiple returned orders"""

    @pytest.mark.parametrize("order_id", TEST_ORDER_IDS)
    def test_settlement_act_for_each_order(self, auth_headers, order_id):
        """Test settlement act works for each test order"""
        response = requests.get(
            f"{BASE_URL}/api/documents/settlement-act/{order_id}/preview",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Settlement act for order {order_id} failed: {response.status_code}"
        assert "Акт взаєморозрахунків" in response.text, f"Order {order_id} missing settlement act title"
        print(f"SUCCESS: Settlement act for order {order_id} works correctly")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
