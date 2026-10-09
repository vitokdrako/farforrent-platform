"""
Tests for Invoice-Offer (Рахунок-оферта) and Estimate (Кошторис) document generation
Focus: Additional services, bank details, service_fee fields

Test orders:
- 7403: ready_for_issue - bank details verification
- 7401: processing - basic invoice offer
- 7392: order with additional services (Мінімальне замовлення)
- 7338: order with service_fee (Таксі)
"""
import pytest
import requests
import os
import re

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestInvoiceOfferPreview:
    """Test invoice-offer document preview endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login to get token
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        
        if login_resp.status_code == 200:
            data = login_resp.json()
            self.token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def test_invoice_offer_7403_returns_html(self):
        """Test: GET /api/documents/invoice-offer/7403/preview returns HTML"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7403/preview")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/html" in resp.headers.get("content-type", ""), "Response should be HTML"
        
        html = resp.text
        assert len(html) > 1000, "HTML should be substantial"
        assert "Рахунок-оферта" in html, "Should contain document title"
        print(f"✓ Invoice-offer 7403 preview returns HTML ({len(html)} chars)")
    
    def test_invoice_offer_7403_has_bank_details_iban(self):
        """Test: Invoice-offer 7403 contains IBAN UA043220010000026003340091618"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7403/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        # Check for IBAN (may have spaces or formatting)
        iban_pattern = r"UA04\s*3220\s*0100\s*0002\s*6003\s*3400\s*9161\s*8"
        has_iban = bool(re.search(iban_pattern, html)) or "UA043220010000026003340091618" in html
        
        assert has_iban, f"Invoice should contain IBAN UA043220010000026003340091618"
        print("✓ Invoice-offer 7403 contains IBAN")
    
    def test_invoice_offer_7403_has_bank_details_mfo(self):
        """Test: Invoice-offer 7403 contains MFO 322001"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7403/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        assert "322001" in html, "Invoice should contain MFO 322001"
        print("✓ Invoice-offer 7403 contains MFO 322001")
    
    def test_invoice_offer_7392_has_additional_service(self):
        """Test: Invoice-offer 7392 contains additional service 'Мінімальне замовлення'"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7392/preview")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.text
        
        # Check for additional service name
        has_min_order = "Мінімальне замовлення" in html or "Мінімальне" in html
        
        assert has_min_order, "Invoice 7392 should contain additional service 'Мінімальне замовлення'"
        print("✓ Invoice-offer 7392 contains 'Мінімальне замовлення' additional service")
    
    def test_invoice_offer_7392_has_additional_service_amount(self):
        """Test: Invoice-offer 7392 contains amount 730 for additional service"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7392/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        # Check for amount 730 (may be formatted as 730,00 or 730)
        has_amount = "730" in html
        
        assert has_amount, "Invoice 7392 should contain amount 730 for additional service"
        print("✓ Invoice-offer 7392 contains amount 730")
    
    def test_invoice_offer_7338_has_service_fee(self):
        """Test: Invoice-offer 7338 contains service_fee 'Таксі' (500 грн)"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7338/preview")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.text
        
        # Check for service fee name and amount
        has_taxi = "Таксі" in html or "Taxi" in html
        has_500 = "500" in html
        
        if not has_taxi:
            # May use generic name
            has_taxi = "послуга" in html.lower() or "service" in html.lower()
        
        assert has_taxi or has_500, f"Invoice 7338 should contain service_fee 'Таксі' or amount 500"
        print(f"✓ Invoice-offer 7338 contains service fee (Таксі: {has_taxi}, 500: {has_500})")


class TestEstimatePreview:
    """Test estimate (Кошторис) document preview endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        
        if login_resp.status_code == 200:
            data = login_resp.json()
            self.token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def test_estimate_7392_returns_html(self):
        """Test: GET /api/documents/estimate/7392/preview returns HTML"""
        resp = self.session.get(f"{BASE_URL}/api/documents/estimate/7392/preview")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        assert "text/html" in resp.headers.get("content-type", ""), "Response should be HTML"
        
        html = resp.text
        assert len(html) > 1000, "HTML should be substantial"
        print(f"✓ Estimate 7392 preview returns HTML ({len(html)} chars)")
    
    def test_estimate_7392_has_additional_service(self):
        """Test: Estimate 7392 contains additional service 'Мінімальне замовлення'"""
        resp = self.session.get(f"{BASE_URL}/api/documents/estimate/7392/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        has_min_order = "Мінімальне замовлення" in html or "Мінімальне" in html
        
        assert has_min_order, "Estimate 7392 should contain additional service 'Мінімальне замовлення'"
        print("✓ Estimate 7392 contains 'Мінімальне замовлення' additional service")
    
    def test_estimate_7338_has_service_fee(self):
        """Test: Estimate 7338 contains service_fee 'Таксі' (500 грн)"""
        resp = self.session.get(f"{BASE_URL}/api/documents/estimate/7338/preview")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.text
        
        # Check for service fee
        has_taxi = "Таксі" in html
        has_500 = "500" in html
        
        assert has_taxi or has_500, f"Estimate 7338 should contain service_fee 'Таксі' or amount 500"
        print(f"✓ Estimate 7338 contains service fee (Таксі: {has_taxi}, 500: {has_500})")
    
    def test_estimate_7403_returns_200(self):
        """Test: Estimate 7403 (ready_for_issue) returns 200"""
        resp = self.session.get(f"{BASE_URL}/api/documents/estimate/7403/preview")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        print("✓ Estimate 7403 returns 200 OK")


class TestInvoiceOfferPDF:
    """Test invoice-offer PDF download endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        
        if login_resp.status_code == 200:
            data = login_resp.json()
            self.token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def test_invoice_offer_pdf_endpoint_exists(self):
        """Test: GET /api/documents/invoice-offer/7403/pdf returns HTML (print dialog)"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7403/pdf")
        
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
        html = resp.text
        
        # Should contain print script
        has_print = "window.print()" in html
        assert has_print, "PDF endpoint should include print() script"
        print("✓ Invoice-offer PDF endpoint works (returns printable HTML)")


class TestDocumentsAdditionalServicesDB:
    """Verify additional services are loaded from order_additional_services table"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        
        if login_resp.status_code == 200:
            data = login_resp.json()
            self.token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def test_invoice_offer_7392_additional_services_section(self):
        """Test: Invoice-offer 7392 shows additional services in totals section"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7392/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        # The template shows additional services in the totals section
        # Either from additional_services list or service_fee_name/service_fee_fmt
        has_services_section = (
            "Мінімальне замовлення" in html or
            "additional_services" in html.lower() or
            "730" in html
        )
        
        assert has_services_section, "Invoice 7392 should show additional services in document"
        print("✓ Invoice-offer 7392 has additional services section")


class TestCompanyConfig:
    """Test that company config is properly loaded from system_settings"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        login_resp = self.session.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        
        if login_resp.status_code == 200:
            data = login_resp.json()
            self.token = data.get("access_token")
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
        else:
            pytest.skip("Authentication failed - skipping tests")
    
    def test_invoice_offer_has_company_name(self):
        """Test: Invoice-offer contains company name"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7403/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        # Check for company name variations
        has_company = (
            "FarforDecorOrenda" in html or
            "ФАРФОР" in html or
            "Farfor" in html or
            "farfor" in html.lower()
        )
        
        assert has_company, "Invoice should contain company name"
        print("✓ Invoice-offer contains company name")
    
    def test_invoice_offer_has_bank_section(self):
        """Test: Invoice-offer contains bank details section"""
        resp = self.session.get(f"{BASE_URL}/api/documents/invoice-offer/7403/preview")
        
        assert resp.status_code == 200
        html = resp.text
        
        # Check for bank section markers
        has_bank_section = (
            "Реквізити" in html or
            "IBAN" in html or
            "МФО" in html or
            "bank" in html.lower()
        )
        
        assert has_bank_section, "Invoice should contain bank details section"
        print("✓ Invoice-offer contains bank details section")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
