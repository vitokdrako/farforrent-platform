"""
Invoice Document Generation API Tests
Tests for /api/documents/available-invoices, /api/documents/invoice-payment, /api/documents/service-act endpoints
"""
import pytest
import requests
import os

# Use public URL from environment
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
LOGIN_EMAIL = "vitokdrako@gmail.com"
LOGIN_PASSWORD = "test123"

# Test order IDs (from agent_to_agent_context_note)
ORDER_WITH_PAYER = 7370  # Христина Мулярчук - has ФОП Мельник as payer
ORDER_WITHOUT_PAYER = 7300  # No payer scenario


class TestAvailableInvoicesEndpoint:
    """Tests for GET /api/documents/available-invoices/{order_id}"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": LOGIN_EMAIL,
            "password": LOGIN_PASSWORD
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_available_invoices_with_payer_returns_200(self):
        """Test that order 7370 returns 200 status"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITH_PAYER}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_available_invoices_with_payer_has_payer_true(self):
        """Test that order 7370 returns has_payer=true"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITH_PAYER}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("has_payer") == True, f"Expected has_payer=True, got {data.get('has_payer')}"
    
    def test_available_invoices_payer_has_display_name_fop_melnyk(self):
        """Test that payer display_name contains 'ФОП Мельник'"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITH_PAYER}")
        assert response.status_code == 200
        data = response.json()
        payer = data.get("payer")
        assert payer is not None, "Expected payer to be present"
        display_name = payer.get("display_name", "")
        assert "ФОП" in display_name and "Мельник" in display_name, \
            f"Expected payer display_name to contain 'ФОП Мельник', got: {display_name}"
    
    def test_available_invoices_has_two_types(self):
        """Test that order 7370 returns 2 available_types (invoice-payment and service-act)"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITH_PAYER}")
        assert response.status_code == 200
        data = response.json()
        available_types = data.get("available_types", [])
        assert len(available_types) == 2, f"Expected 2 available_types, got {len(available_types)}: {available_types}"
        
        # Check endpoints are invoice-payment and service-act
        endpoints = [t.get("endpoint") for t in available_types]
        assert "invoice-payment" in endpoints, f"Expected 'invoice-payment' in endpoints, got: {endpoints}"
        assert "service-act" in endpoints, f"Expected 'service-act' in endpoints, got: {endpoints}"
    
    def test_available_invoices_without_payer_returns_200(self):
        """Test that order 7300 returns 200 status"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITHOUT_PAYER}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_available_invoices_without_payer_has_payer_false(self):
        """Test that order 7300 returns has_payer=false"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITHOUT_PAYER}")
        assert response.status_code == 200
        data = response.json()
        assert data.get("has_payer") == False, f"Expected has_payer=False, got {data.get('has_payer')}"
    
    def test_available_invoices_without_payer_empty_types(self):
        """Test that order 7300 returns empty available_types"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITHOUT_PAYER}")
        assert response.status_code == 200
        data = response.json()
        available_types = data.get("available_types", [])
        assert len(available_types) == 0, f"Expected empty available_types for order without payer, got {len(available_types)}"


class TestInvoicePaymentEndpoint:
    """Tests for GET /api/documents/invoice-payment/{order_id}/preview"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": LOGIN_EMAIL,
            "password": LOGIN_PASSWORD
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_invoice_payment_preview_returns_200(self):
        """Test that invoice-payment preview for order 7370 returns 200"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_invoice_payment_preview_returns_html(self):
        """Test that invoice-payment preview returns valid HTML"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        assert "<!DOCTYPE html>" in content or "<html" in content, "Expected HTML response"
        assert "Рахунок на оплату" in content, "Expected 'Рахунок на оплату' in HTML"
    
    def test_invoice_payment_contains_nikolenko_supplier(self):
        """Test that invoice-payment contains Николенко (supplier)"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        # Check for Николенко (Николенко Валерій) in executor section
        assert "Николенко" in content, f"Expected 'Николенко' (supplier name) in HTML, content length: {len(content)}"
    
    def test_invoice_payment_contains_melnyk_buyer(self):
        """Test that invoice-payment contains Мельник (buyer)"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        # Check for Мельник in payer/buyer section
        assert "Мельник" in content, f"Expected 'Мельник' (buyer name) in HTML, content length: {len(content)}"
    
    def test_invoice_payment_contains_prokat_dekoru(self):
        """Test that invoice-payment contains 'Прокат декору' service name"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        assert "Прокат декору" in content, f"Expected 'Прокат декору' in HTML"
    
    def test_invoice_payment_contains_amount(self):
        """Test that invoice-payment contains formatted amount with comma separator"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        # Amount should be formatted with comma (Ukrainian format): "1 100,00" or similar
        # Looking for any amount pattern like X,00 (at least the decimal format)
        import re
        amount_pattern = r'\d[\d\s]*,\d{2}'  # Matches amounts like "1 100,00" or "100,00"
        assert re.search(amount_pattern, content), f"Expected formatted amount (X,XX) in HTML"
    
    def test_invoice_payment_without_payer_returns_400(self):
        """Test that invoice-payment for order without payer returns 400 error"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITHOUT_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        # Should return 400 with error about missing payer
        assert response.status_code == 400, f"Expected 400 for order without payer, got {response.status_code}"


class TestServiceActEndpoint:
    """Tests for GET /api/documents/service-act/{order_id}/preview"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": LOGIN_EMAIL,
            "password": LOGIN_PASSWORD
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_service_act_preview_returns_200(self):
        """Test that service-act preview for order 7370 returns 200"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    def test_service_act_preview_returns_html(self):
        """Test that service-act preview returns valid HTML"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        assert "<!DOCTYPE html>" in content or "<html" in content, "Expected HTML response"
    
    def test_service_act_contains_zatverdzhuju(self):
        """Test that service-act contains ЗАТВЕРДЖУЮ header"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        assert "ЗАТВЕРДЖУЮ" in content, f"Expected 'ЗАТВЕРДЖУЮ' in service-act HTML"
    
    def test_service_act_contains_nikolenko(self):
        """Test that service-act contains Николенко (executor)"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        assert "Николенко" in content, f"Expected 'Николенко' (executor name) in HTML"
    
    def test_service_act_contains_melnyk(self):
        """Test that service-act contains Мельник (payer)"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        assert "Мельник" in content, f"Expected 'Мельник' (payer name) in HTML"
    
    def test_service_act_contains_signatures_section(self):
        """Test that service-act contains signatures section (Від Виконавця, Від Замовника)"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        # Check for both party signature blocks
        assert "Від Виконавця" in content, f"Expected 'Від Виконавця' (From Executor) in signatures"
        assert "Від Замовника" in content, f"Expected 'Від Замовника' (From Customer) in signatures"
    
    def test_service_act_contains_amount(self):
        """Test that service-act contains formatted amount"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 200
        content = response.text
        import re
        amount_pattern = r'\d[\d\s]*,\d{2}'  # Matches amounts like "1 100,00"
        assert re.search(amount_pattern, content), f"Expected formatted amount in service-act HTML"
    
    def test_service_act_without_payer_returns_400(self):
        """Test that service-act for order without payer returns 400 error"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/service-act/{ORDER_WITHOUT_PAYER}/preview",
            params={"executor_type": "fop"}
        )
        assert response.status_code == 400, f"Expected 400 for order without payer, got {response.status_code}"


class TestPayerAutoDetection:
    """Tests for payer auto-detection via fallback mechanism"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get auth token before each test"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_response = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": LOGIN_EMAIL,
            "password": LOGIN_PASSWORD
        })
        if login_response.status_code == 200:
            data = login_response.json()
            token = data.get("access_token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_payer_auto_detected_without_payer_id_param(self):
        """Test that payer is auto-detected without explicit payer_id parameter"""
        response = self.session.get(
            f"{BASE_URL}/api/documents/invoice-payment/{ORDER_WITH_PAYER}/preview",
            params={"executor_type": "fop"}
            # Note: NOT passing payer_id parameter - should auto-detect
        )
        assert response.status_code == 200, \
            f"Payer should be auto-detected. Got {response.status_code}: {response.text}"
        
        # Verify the payer is in the response
        content = response.text
        assert "Мельник" in content, "Auto-detected payer should be Мельник"
    
    def test_available_invoices_payer_has_type_field(self):
        """Test that payer object includes 'type' field (fop, tov, individual)"""
        response = self.session.get(f"{BASE_URL}/api/documents/available-invoices/{ORDER_WITH_PAYER}")
        assert response.status_code == 200
        data = response.json()
        payer = data.get("payer")
        assert payer is not None
        assert "type" in payer, f"Expected 'type' field in payer, got keys: {payer.keys()}"
        assert payer["type"] in ("fop", "fop_simple", "tov", "individual"), \
            f"Expected valid payer type, got: {payer['type']}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
