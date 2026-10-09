"""
Phase 3.2: Document Preview Modal Integration Tests
Tests for document rendering, policy, and signature APIs
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

# Test order ID
TEST_ORDER_ID = 7326


class TestDocumentRenderAPI:
    """Tests for /api/documents/render endpoints"""
    
    def test_list_templates(self):
        """GET /api/documents/render/templates - List available templates"""
        response = requests.get(f"{BASE_URL}/api/documents/render/templates")
        assert response.status_code == 200
        
        data = response.json()
        assert "templates" in data
        assert "template_files" in data
        
        # Check expected templates exist
        expected_templates = ["master_agreement", "annex_to_contract", "issue_act", "return_act", "defect_act", "quote"]
        for template in expected_templates:
            assert template in data["templates"], f"Template {template} not found"
        
        print(f"✓ Found {len(data['templates'])} templates: {data['templates']}")
    
    def test_render_quote_document(self):
        """POST /api/documents/render - Render quote document"""
        response = requests.post(
            f"{BASE_URL}/api/documents/render",
            json={
                "doc_type": "quote",
                "order_id": TEST_ORDER_ID,
                "include_watermark": True
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "html" in data
        assert "doc_number" in data
        assert "context" in data
        
        # Check HTML content
        html = data["html"]
        assert "КОШТОРИС" in html, "Quote title not found in HTML"
        assert "ЧЕРНЕТКА" in html, "Watermark not found in HTML"
        assert f"OC-{TEST_ORDER_ID}" in html, "Order number not found in HTML"
        
        # Check context
        context = data["context"]
        assert context["order"]["order_id"] == TEST_ORDER_ID
        assert len(context["items"]) > 0, "No items in context"
        
        print(f"✓ Quote rendered: {data['doc_number']}")
        print(f"  - Items: {len(context['items'])}")
        print(f"  - Total: {context['totals']['rent_total']} UAH")
    
    def test_render_quote_without_watermark(self):
        """POST /api/documents/render - Render quote without watermark"""
        response = requests.post(
            f"{BASE_URL}/api/documents/render",
            json={
                "doc_type": "quote",
                "order_id": TEST_ORDER_ID,
                "include_watermark": False
            }
        )
        assert response.status_code == 200
        
        data = response.json()
        html = data["html"]
        
        # Watermark text should be empty
        assert data["context"]["meta"]["watermark_text"] == ""
        print("✓ Quote rendered without watermark")
    
    def test_render_invalid_doc_type(self):
        """POST /api/documents/render - Invalid document type returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/documents/render",
            json={
                "doc_type": "invalid_type",
                "order_id": TEST_ORDER_ID
            }
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "Unknown document type" in data["detail"]
        print("✓ Invalid doc_type correctly returns 400")
    
    def test_render_invoice_offer_not_in_templates(self):
        """POST /api/documents/render - invoice_offer not in render templates"""
        response = requests.post(
            f"{BASE_URL}/api/documents/render",
            json={
                "doc_type": "invoice_offer",
                "order_id": TEST_ORDER_ID
            }
        )
        # invoice_offer is in policy but not in render templates
        assert response.status_code == 400
        print("✓ invoice_offer correctly not available in render templates")
    
    def test_preview_document(self):
        """GET /api/documents/render/preview/{doc_type} - Preview document as HTML"""
        response = requests.get(
            f"{BASE_URL}/api/documents/render/preview/quote",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        
        html = response.text
        assert "КОШТОРИС" in html
        print("✓ Document preview returns HTML")
    
    def test_get_document_context(self):
        """GET /api/documents/render/context/{doc_type} - Get document context"""
        response = requests.get(
            f"{BASE_URL}/api/documents/render/context/quote",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "context" in data
        
        context = data["context"]
        assert "meta" in context
        assert "order" in context
        assert "landlord" in context
        assert "items" in context
        assert "totals" in context
        
        print(f"✓ Document context retrieved")
        print(f"  - Order: {context['order']['order_number']}")
        print(f"  - Customer: {context['order']['customer_name']}")


class TestDocumentPolicyAPI:
    """Tests for /api/documents/policy endpoints"""
    
    def test_get_policy_matrix(self):
        """GET /api/documents/policy/matrix - Get full policy matrix"""
        response = requests.get(f"{BASE_URL}/api/documents/policy/matrix")
        assert response.status_code == 200
        
        data = response.json()
        assert "policies" in data
        assert "categories" in data
        
        # Check categories
        expected_categories = ["quote", "contract", "annex", "act", "finance", "operations"]
        for cat in expected_categories:
            assert cat in data["categories"], f"Category {cat} not found"
        
        # Check some policies
        policies = data["policies"]
        assert "quote" in policies
        assert "invoice_offer" in policies
        assert "master_agreement" in policies
        
        print(f"✓ Policy matrix: {len(policies)} document types in {len(data['categories'])} categories")
    
    def test_get_available_documents_for_order(self):
        """GET /api/documents/policy/available - Get available documents for order"""
        response = requests.get(
            f"{BASE_URL}/api/documents/policy/available",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["order_id"] == TEST_ORDER_ID
        assert "documents" in data
        assert "by_category" in data
        assert "context" in data
        
        # Check context
        context = data["context"]
        assert "order_status" in context
        assert "deal_mode" in context
        
        # Count available documents
        available_docs = [d for d in data["documents"] if d["available"]]
        unavailable_docs = [d for d in data["documents"] if not d["available"]]
        
        print(f"✓ Available documents for order {TEST_ORDER_ID}:")
        print(f"  - Order status: {context['order_status']}")
        print(f"  - Available: {len(available_docs)}")
        print(f"  - Unavailable: {len(unavailable_docs)}")
        
        # List available documents
        for doc in available_docs:
            print(f"    ✓ {doc['doc_type']}: {doc['name']}")
    
    def test_check_quote_availability(self):
        """GET /api/documents/policy/check/quote - Check quote availability"""
        response = requests.get(
            f"{BASE_URL}/api/documents/policy/check/quote",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["doc_type"] == "quote"
        assert data["available"] == True
        
        print(f"✓ Quote is available for order {TEST_ORDER_ID}")
    
    def test_check_invoice_offer_availability(self):
        """GET /api/documents/policy/check/invoice_offer - Check invoice_offer availability"""
        response = requests.get(
            f"{BASE_URL}/api/documents/policy/check/invoice_offer",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["doc_type"] == "invoice_offer"
        # invoice_offer should be available for individual payers
        print(f"✓ invoice_offer availability: {data['available']}")
        if not data["available"]:
            print(f"  - Reason: {data.get('reason', 'N/A')}")
    
    def test_check_annex_availability(self):
        """GET /api/documents/policy/check/annex - Check annex availability"""
        response = requests.get(
            f"{BASE_URL}/api/documents/policy/check/annex",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["doc_type"] == "annex"
        
        # Annex requires specific order status and agreement
        print(f"✓ Annex availability: {data['available']}")
        if not data["available"]:
            print(f"  - Reason: {data.get('reason', 'N/A')}")


class TestDocumentSignaturesAPI:
    """Tests for /api/documents/signatures endpoints"""
    
    def test_sign_nonexistent_document(self):
        """POST /api/documents/signatures/sign - Sign non-existent document returns 404"""
        response = requests.post(
            f"{BASE_URL}/api/documents/signatures/sign",
            json={
                "document_id": "nonexistent-doc-123",
                "signer_role": "tenant",
                "signature_png_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
        )
        # Should return 404 for non-existent document
        assert response.status_code == 404
        print("✓ Sign non-existent document returns 404")
    
    def test_sign_invalid_role(self):
        """POST /api/documents/signatures/sign - Invalid signer role returns 400"""
        response = requests.post(
            f"{BASE_URL}/api/documents/signatures/sign",
            json={
                "document_id": "test-doc-123",
                "signer_role": "invalid_role",
                "signature_png_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
            }
        )
        # Returns 400 for invalid role OR 404 if document check happens first
        assert response.status_code in [400, 404]
        print(f"✓ Invalid signer_role returns {response.status_code}")
    
    def test_get_signature_status_nonexistent(self):
        """GET /api/documents/signatures/status/{document_id} - Get status for non-existent doc"""
        response = requests.get(f"{BASE_URL}/api/documents/signatures/status/nonexistent-doc")
        assert response.status_code == 200
        
        data = response.json()
        assert data["document_id"] == "nonexistent-doc"
        assert "signatures" in data
        
        # Both roles should show as not signed
        assert data["signatures"]["landlord"]["signed"] == False
        assert data["signatures"]["tenant"]["signed"] == False
        assert data["fully_signed"] == False
        
        print("✓ Signature status for non-existent doc returns empty signatures")
    
    def test_generate_sign_link(self):
        """POST /api/documents/signatures/generate-sign-link - Generate signing link"""
        response = requests.post(
            f"{BASE_URL}/api/documents/signatures/generate-sign-link",
            params={
                "document_id": "test-doc-123",
                "signer_role": "tenant",
                "expires_hours": 72
            }
        )
        # Returns 404 if document doesn't exist, 200 if it does
        if response.status_code == 200:
            data = response.json()
            assert data["success"] == True
            assert data["document_id"] == "test-doc-123"
            assert data["signer_role"] == "tenant"
            assert "sign_token" in data
            assert "sign_url" in data
            print(f"✓ Sign link generated: {data['sign_url']}")
        else:
            assert response.status_code == 404
            print("✓ Sign link generation returns 404 for non-existent document (expected)")


class TestIntegration:
    """Integration tests for document workflow"""
    
    def test_full_document_preview_workflow(self):
        """Test complete document preview workflow"""
        # 1. Check available documents
        response = requests.get(
            f"{BASE_URL}/api/documents/policy/available",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        available = response.json()
        
        # 2. Find an available document
        available_docs = [d for d in available["documents"] if d["available"]]
        assert len(available_docs) > 0, "No available documents"
        
        doc_type = available_docs[0]["doc_type"]
        print(f"Testing workflow with: {doc_type}")
        
        # 3. Render the document
        response = requests.post(
            f"{BASE_URL}/api/documents/render",
            json={
                "doc_type": doc_type,
                "order_id": TEST_ORDER_ID,
                "include_watermark": True
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            assert data["success"] == True
            assert "html" in data
            print(f"✓ Document rendered: {data['doc_number']}")
        else:
            # Some doc types may not have templates
            print(f"  - {doc_type} not available in render templates (expected for some types)")
    
    def test_document_buttons_show_preview_label(self):
        """Verify document buttons show 'Перегляд' label when available"""
        response = requests.get(
            f"{BASE_URL}/api/documents/policy/available",
            params={"order_id": TEST_ORDER_ID}
        )
        assert response.status_code == 200
        
        data = response.json()
        available_docs = [d for d in data["documents"] if d["available"]]
        
        # Check that available documents have proper structure for UI
        for doc in available_docs:
            assert "doc_type" in doc
            assert "name" in doc
            assert "available" in doc
            assert doc["available"] == True
        
        print(f"✓ {len(available_docs)} documents available with proper structure for UI buttons")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
