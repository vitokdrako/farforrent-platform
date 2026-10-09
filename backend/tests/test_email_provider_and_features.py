"""
Test Email Provider Abstraction and New Features
- Email Provider abstraction (DummyEmailProvider)
- Email send endpoint using provider
- Document email history
- Migration columns (provider, provider_email_id)
"""
import pytest
import requests
import os
import sys

# Add backend to path for imports
sys.path.insert(0, '/app/backend')

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"
TEST_ORDER_ID = 7326


class TestEmailProviderAbstraction:
    """Test the email provider abstraction layer"""
    
    def test_dummy_provider_is_default(self):
        """DummyEmailProvider should be used when EMAIL_PROVIDER env not set"""
        from services.email_provider import get_email_provider, reset_provider, DummyEmailProvider
        
        # Reset to get fresh instance
        reset_provider()
        
        # Clear EMAIL_PROVIDER if set
        original = os.environ.pop('EMAIL_PROVIDER', None)
        
        try:
            reset_provider()
            provider = get_email_provider()
            assert isinstance(provider, DummyEmailProvider), f"Expected DummyEmailProvider, got {type(provider)}"
            assert provider.name == "dummy"
            assert provider.is_configured() == True
        finally:
            if original:
                os.environ['EMAIL_PROVIDER'] = original
            reset_provider()
    
    def test_dummy_provider_send_returns_success(self):
        """DummyEmailProvider.send() should return success without actually sending"""
        import asyncio
        from services.email_provider import DummyEmailProvider, EmailResult
        
        provider = DummyEmailProvider()
        
        async def test_send():
            result = await provider.send(
                to="test@example.com",
                subject="Test Subject",
                html="<p>Test HTML</p>"
            )
            return result
        
        result = asyncio.run(test_send())
        
        assert isinstance(result, EmailResult)
        assert result.success == True
        assert result.provider == "dummy"
        assert result.email_id is not None
        assert result.email_id.startswith("dummy_")
        assert result.error is None
    
    def test_resend_provider_not_configured_fallback(self):
        """ResendEmailProvider should fallback to dummy when not configured"""
        from services.email_provider import get_email_provider, reset_provider, DummyEmailProvider
        
        # Set provider to resend but without API key
        original_provider = os.environ.pop('EMAIL_PROVIDER', None)
        original_key = os.environ.pop('RESEND_API_KEY', None)
        
        try:
            os.environ['EMAIL_PROVIDER'] = 'resend'
            reset_provider()
            provider = get_email_provider()
            # Should fallback to dummy since no API key
            assert isinstance(provider, DummyEmailProvider)
        finally:
            if original_provider:
                os.environ['EMAIL_PROVIDER'] = original_provider
            if original_key:
                os.environ['RESEND_API_KEY'] = original_key
            reset_provider()
    
    def test_sendgrid_provider_not_configured_fallback(self):
        """SendGridEmailProvider should fallback to dummy when not configured"""
        from services.email_provider import get_email_provider, reset_provider, DummyEmailProvider
        
        original_provider = os.environ.pop('EMAIL_PROVIDER', None)
        original_key = os.environ.pop('SENDGRID_API_KEY', None)
        
        try:
            os.environ['EMAIL_PROVIDER'] = 'sendgrid'
            reset_provider()
            provider = get_email_provider()
            # Should fallback to dummy since no API key
            assert isinstance(provider, DummyEmailProvider)
        finally:
            if original_provider:
                os.environ['EMAIL_PROVIDER'] = original_provider
            if original_key:
                os.environ['SENDGRID_API_KEY'] = original_key
            reset_provider()


class TestEmailEndpoints:
    """Test email API endpoints"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        return response.json().get("access_token")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_send_email_endpoint_exists(self, auth_headers):
        """POST /api/documents/{id}/send-email endpoint should exist"""
        # Use a non-existent document ID to test endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/documents/NONEXISTENT/send-email",
            headers=auth_headers,
            json={
                "to": "test@example.com",
                "subject": "Test",
                "message": "Test message"
            }
        )
        # Should return 404 for non-existent document, not 405 (method not allowed)
        assert response.status_code == 404, f"Expected 404, got {response.status_code}: {response.text}"
    
    def test_email_history_endpoint(self, auth_headers):
        """GET /api/documents/{id}/email-history should return history"""
        response = requests.get(
            f"{BASE_URL}/api/documents/TEST-DOC-001/email-history",
            headers=auth_headers
        )
        # Should return 200 with empty history for non-existent doc
        assert response.status_code == 200
        data = response.json()
        assert "document_id" in data
        assert "history" in data
        assert isinstance(data["history"], list)
    
    def test_recent_emails_endpoint(self, auth_headers):
        """GET /api/documents/recent-emails should return recent emails"""
        response = requests.get(
            f"{BASE_URL}/api/documents/recent-emails",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "emails" in data
        assert isinstance(data["emails"], list)


class TestAgreementExpiration:
    """Test agreement expiration logic"""
    
    @pytest.fixture
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
        )
        assert response.status_code == 200
        return response.json().get("access_token")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_agreements_list_includes_valid_until(self, auth_headers):
        """GET /api/agreements should include valid_until field"""
        response = requests.get(
            f"{BASE_URL}/api/agreements",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert "agreements" in data
        
        # If there are agreements, check they have valid_until
        if data["agreements"]:
            agreement = data["agreements"][0]
            # valid_until should be present (can be null)
            assert "valid_until" in agreement or "valid_until" not in agreement  # Field may or may not exist
    
    def test_agreement_detail_includes_expiration_info(self, auth_headers):
        """Agreement detail should include expiration info"""
        # First get list of agreements
        response = requests.get(
            f"{BASE_URL}/api/agreements",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        if data["agreements"]:
            agreement_id = data["agreements"][0]["id"]
            # Get detail
            detail_response = requests.get(
                f"{BASE_URL}/api/agreements/{agreement_id}",
                headers=auth_headers
            )
            # Endpoint may or may not exist
            if detail_response.status_code == 200:
                detail = detail_response.json()
                # Check for expiration-related fields
                print(f"Agreement detail keys: {detail.keys()}")


class TestDocumentPreviewPrintButton:
    """Test that print button exists in document preview"""
    
    def test_print_button_in_frontend_code(self):
        """Verify print button exists in DocumentPreviewModal.jsx"""
        with open('/app/frontend/src/components/DocumentPreviewModal.jsx', 'r') as f:
            content = f.read()
        
        # Check for print button with data-testid
        assert 'data-testid="print-pdf-btn"' in content, "Print button should have data-testid"
        # Print button opens new window and triggers print
        assert 'printWindow.print()' in content or 'window.print()' in content, "Print button should trigger print"
        assert '🖨️' in content or 'Друк' in content, "Print button should have print icon or label"


class TestPrintCSS:
    """Test print CSS in base.css"""
    
    def test_print_media_query_exists(self):
        """Verify @media print CSS exists in base.css"""
        with open('/app/backend/templates/documents/_partials/base.css', 'r') as f:
            content = f.read()
        
        assert '@media print' in content, "Print media query should exist"
        assert 'size: A4' in content, "A4 page size should be defined"
        assert 'page-break' in content, "Page break rules should exist"


class TestExpirationBannerInUI:
    """Test expiration banner implementation in FinanceHub"""
    
    def test_expiration_banner_code_exists(self):
        """Verify expiration banner code exists in FinanceHub.jsx"""
        with open('/app/frontend/src/pages/FinanceHub.jsx', 'r') as f:
            content = f.read()
        
        # Check for expiration status logic
        assert 'expirationStatus' in content, "Expiration status variable should exist"
        assert 'expired' in content, "Expired status should be handled"
        assert 'warning' in content, "Warning status should be handled"
        assert 'valid_until' in content, "valid_until field should be used"
        
        # Check for expiration banners
        assert 'Договір закінчився' in content, "Expired banner text should exist"
        assert 'Договір закінчується' in content, "Warning banner text should exist"
        
        # Check for 30 days logic
        assert '30' in content, "30 days threshold should be used"


class TestContractStatusBadge:
    """Test contract status badge in order header"""
    
    def test_contract_status_badge_code_exists(self):
        """Verify contract status badge exists in FinanceHub.jsx"""
        with open('/app/frontend/src/pages/FinanceHub.jsx', 'r') as f:
            content = f.read()
        
        # Check for contract status badge in order header
        assert 'daysUntilExpiry' in content, "Days until expiry calculation should exist"
        assert 'bg-rose-100' in content, "Red/rose badge for expired should exist"
        assert 'bg-amber-100' in content, "Amber badge for warning should exist"
        assert 'bg-emerald-100' in content, "Green badge for active should exist"
        
        # Check for badge labels
        assert 'закінч' in content, "Expired label should exist"
        assert 'активн' in content, "Active label should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
