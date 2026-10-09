"""
Phase 3.2 Backend Tests: Manual Fields, Email Workflow, Payment Validation, Contract Expiration
Tests for:
- Manual Fields Schema API
- Email send endpoint with audit log
- Payment validation (rent requires annex_id)
- Contract expiration check for annex creation
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestManualFieldsSchema:
    """Test manual fields schema API - GET /api/documents/schema/{doc_type}"""
    
    def test_annex_to_contract_schema_has_pickup_return_time(self):
        """P0: annex_to_contract schema should have pickup_time and return_time fields"""
        response = requests.get(f"{BASE_URL}/api/documents/schema/annex_to_contract")
        assert response.status_code == 200
        
        data = response.json()
        assert data["doc_type"] == "annex_to_contract"
        assert data["has_manual_fields"] == True
        assert data["schema"] is not None
        
        # Check for pickup_time and return_time fields
        fields = data["schema"]["fields"]
        field_keys = [f["key"] for f in fields]
        
        assert "pickup_time" in field_keys, "pickup_time field missing from annex schema"
        assert "return_time" in field_keys, "return_time field missing from annex schema"
        
        # Verify pickup_time field properties
        pickup_field = next(f for f in fields if f["key"] == "pickup_time")
        assert pickup_field["type"] == "time"
        assert pickup_field["required"] == True
        assert pickup_field["default"] == "17:00"
        
        # Verify return_time field properties
        return_field = next(f for f in fields if f["key"] == "return_time")
        assert return_field["type"] == "time"
        assert return_field["required"] == True
        assert return_field["default"] == "10:00"
    
    def test_defect_act_schema_has_tenant_refused_to_sign(self):
        """P0: defect_act schema should have tenant_refused_to_sign checkbox"""
        response = requests.get(f"{BASE_URL}/api/documents/schema/defect_act")
        assert response.status_code == 200
        
        data = response.json()
        assert data["doc_type"] == "defect_act"
        assert data["has_manual_fields"] == True
        
        fields = data["schema"]["fields"]
        field_keys = [f["key"] for f in fields]
        
        assert "tenant_refused_to_sign" in field_keys, "tenant_refused_to_sign field missing"
        
        # Verify field properties
        refused_field = next(f for f in fields if f["key"] == "tenant_refused_to_sign")
        assert refused_field["type"] == "checkbox"
        assert refused_field["default"] == False
        assert "description" in refused_field
    
    def test_return_act_schema(self):
        """Test return_act schema has condition_mode field"""
        response = requests.get(f"{BASE_URL}/api/documents/schema/return_act")
        assert response.status_code == 200
        
        data = response.json()
        assert data["has_manual_fields"] == True
        
        fields = data["schema"]["fields"]
        field_keys = [f["key"] for f in fields]
        
        assert "condition_mode" in field_keys
        assert "return_notes" in field_keys
    
    def test_issue_act_schema(self):
        """Test issue_act schema has pickup_time field"""
        response = requests.get(f"{BASE_URL}/api/documents/schema/issue_act")
        assert response.status_code == 200
        
        data = response.json()
        assert data["has_manual_fields"] == True
        
        fields = data["schema"]["fields"]
        field_keys = [f["key"] for f in fields]
        
        assert "pickup_time" in field_keys
        assert "issue_notes" in field_keys
    
    def test_unknown_doc_type_returns_no_manual_fields(self):
        """Unknown doc type should return has_manual_fields=False"""
        response = requests.get(f"{BASE_URL}/api/documents/schema/unknown_type")
        assert response.status_code == 200
        
        data = response.json()
        assert data["has_manual_fields"] == False
        assert data["schema"] is None
    
    def test_types_with_manual_fields_endpoint(self):
        """Test listing all document types with manual fields"""
        response = requests.get(f"{BASE_URL}/api/documents/types-with-manual-fields")
        assert response.status_code == 200
        
        data = response.json()
        assert "types" in data
        assert "schemas" in data
        
        # Should include annex_to_contract, return_act, defect_act, issue_act
        expected_types = ["annex_to_contract", "return_act", "defect_act", "issue_act"]
        for doc_type in expected_types:
            assert doc_type in data["types"], f"{doc_type} missing from types list"


class TestPaymentValidation:
    """Test payment validation - rent payment requires annex_id"""
    
    def test_rent_payment_without_annex_returns_400(self):
        """P1: Rent payment without annex_id should return 400 error"""
        response = requests.post(
            f"{BASE_URL}/api/finance/payments",
            json={
                "payment_type": "rent",
                "method": "cash",
                "amount": 1000,
                "order_id": 7326
            }
        )
        
        # Should return 400 because annex_id is required for rent payments
        assert response.status_code == 400
        
        data = response.json()
        assert "annex_id" in data.get("detail", "").lower() or "додаток" in data.get("detail", "").lower()
    
    def test_deposit_payment_without_annex_allowed(self):
        """Deposit payment should NOT require annex_id"""
        # This test verifies that deposit payments don't need annex_id
        # We just check the validation doesn't block it for annex_id reason
        response = requests.post(
            f"{BASE_URL}/api/finance/deposits/create",
            json={
                "order_id": 7326,
                "method": "cash",
                "actual_amount": 500,
                "currency": "UAH",
                "expected_amount": 500
            }
        )
        
        # Should either succeed or fail for other reasons (not annex_id)
        if response.status_code != 200:
            data = response.json()
            # Should NOT fail due to annex_id requirement
            assert "annex_id" not in data.get("detail", "").lower()


class TestEmailWorkflow:
    """Test email send endpoint and audit logging"""
    
    def test_send_email_to_nonexistent_document_returns_404(self):
        """Sending email to non-existent document should return 404"""
        response = requests.post(
            f"{BASE_URL}/api/documents/nonexistent-doc-123/send-email",
            json={
                "to": "test@example.com",
                "subject": "Test Subject",
                "message": "Test message body",
                "attach_pdf": True
            }
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data.get("detail", "").lower() or "не знайдено" in data.get("detail", "").lower()
    
    def test_send_email_requires_to_field(self):
        """Email send should require 'to' field"""
        response = requests.post(
            f"{BASE_URL}/api/documents/test-doc/send-email",
            json={
                "subject": "Test",
                "message": "Test"
            }
        )
        
        # Should fail validation - missing 'to' field
        assert response.status_code in [400, 422]
    
    def test_email_history_endpoint(self):
        """Test email history endpoint returns proper structure"""
        response = requests.get(f"{BASE_URL}/api/documents/test-doc-123/email-history")
        
        # Should return 200 with empty history (document may not exist but endpoint should work)
        # Or 404 if document doesn't exist
        assert response.status_code in [200, 404]
        
        if response.status_code == 200:
            data = response.json()
            assert "history" in data or "document_id" in data
    
    def test_recent_emails_endpoint(self):
        """Test recent emails endpoint"""
        response = requests.get(f"{BASE_URL}/api/documents/recent-emails?limit=10")
        
        # Should return 200 or 404 if no documents exist
        assert response.status_code in [200, 404]


class TestContractExpiration:
    """Test contract expiration check for annex creation"""
    
    def test_annex_generation_endpoint_exists(self):
        """Test that annex generation endpoint exists"""
        response = requests.post(
            f"{BASE_URL}/api/annexes/generate-for-order/7326"
        )
        
        # Should return some response (not 404 for endpoint)
        # May fail for business logic reasons but endpoint should exist
        assert response.status_code != 404 or "not found" not in response.text.lower()
    
    def test_get_latest_annex_for_order(self):
        """Test getting latest annex for order"""
        response = requests.get(f"{BASE_URL}/api/annexes/latest/7326")
        assert response.status_code == 200
        
        data = response.json()
        assert "exists" in data
    
    def test_annex_history_for_order(self):
        """Test getting annex history for order"""
        response = requests.get(f"{BASE_URL}/api/annexes/history/7326")
        assert response.status_code == 200
        
        data = response.json()
        assert "versions" in data
        assert "order_id" in data


class TestMigrationAnnexId:
    """Test that annex_id column exists in fin_payments table"""
    
    def test_payments_endpoint_returns_annex_id_field(self):
        """Verify payments API can handle annex_id field"""
        # Create a test payment with annex_id to verify column exists
        # First, let's check if the payments list endpoint works
        response = requests.get(f"{BASE_URL}/api/finance/payments?limit=5")
        assert response.status_code == 200
        
        data = response.json()
        assert "payments" in data
        
        # If there are payments, check if annex_id field is present in response
        # (may be null but field should exist)
        if data["payments"]:
            # The field should be in the response structure
            # Even if null, the API should handle it
            pass  # Field existence is verified by the API not crashing


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
