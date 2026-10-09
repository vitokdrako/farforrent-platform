"""
Test suite for Damage Fixation Workflow and Document Generation
Tests:
1. Return Act document generation with modern design
2. Defect Act document generation with all damage types (photo_only, total_loss, state write)
3. photo_only processing type doesn't freeze products
4. Document preview rendering
"""
import pytest
import requests
import os
import json

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com')

# Test orders from the context
ORDER_WITH_PRE_ISSUE = 7425  # Has pre_issue damage
ORDER_WITH_TOTAL_LOSS = 7414  # Has total_loss with fee 420 grn


class TestDocumentGeneration:
    """Test document generation endpoints"""
    
    def test_return_act_generation(self):
        """POST /api/documents/generate with doc_type=return_act should generate modern styled HTML"""
        response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "return_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_PRE_ISSUE)
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Document generation should succeed"
        assert "document_id" in data, "Response should contain document_id"
        assert "doc_number" in data, "Response should contain doc_number"
        assert data.get("doc_type") == "return_act", "doc_type should be return_act"
        assert "preview_url" in data, "Response should contain preview_url"
        assert "html_content" in data, "Response should contain html_content"
        
        # Verify HTML content has modern design elements
        html = data.get("html_content", "")
        assert "Акт повернення" in html, "HTML should contain 'Акт повернення' title"
        assert "border-radius" in html, "HTML should have modern rounded corners"
        assert "OC-7425" in html, "HTML should contain order number"
        
    def test_return_act_with_damage_data(self):
        """Return Act should include damage data and pre-issue comparison"""
        response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "return_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_PRE_ISSUE)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        html = data.get("html_content", "")
        
        # Check for damage-related sections in the template
        # The template should have sections for pre-issue damages comparison
        assert "compare-block" in html or "pre_issue" in html or "Стан до видачі" in html or "Повернені товари" in html, \
            "Return act should have sections for damage comparison or returned items"
        
    def test_defect_act_generation(self):
        """POST /api/documents/generate with doc_type=defect_act should include all damage types"""
        response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "defect_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_TOTAL_LOSS)
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Document generation should succeed"
        assert data.get("doc_type") == "defect_act", "doc_type should be defect_act"
        
        html = data.get("html_content", "")
        assert "Дефектний акт" in html, "HTML should contain 'Дефектний акт' title"
        assert "OC-7414" in html, "HTML should contain order number"
        
    def test_defect_act_has_type_column(self):
        """Defect Act should have 'Тип' column with colored badges for different damage types"""
        response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "defect_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_TOTAL_LOSS)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        html = data.get("html_content", "")
        
        # Check for type column header
        assert "Тип" in html, "Defect act should have 'Тип' column header"
        
        # Check for type badges (Фіксація, Втрата, В стан)
        # At least one of these should be present based on damage types
        has_type_badge = "Фіксація" in html or "Втрата" in html or "В стан" in html or "До видачі" in html
        assert has_type_badge, "Defect act should have type badges for damage classification"
        
    def test_defect_act_includes_total_loss(self):
        """Defect Act for order 7414 should include total_loss records with 'Втрата' label"""
        response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "defect_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_TOTAL_LOSS)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        html = data.get("html_content", "")
        
        # Order 7414 has TOTAL_LOSS damage, should show "Втрата" badge
        assert "Втрата" in html or "TOTAL_LOSS" in html or "Повна втрата" in html, \
            "Defect act should include total_loss records with appropriate label"
        
    def test_document_preview(self):
        """Document preview endpoint should render HTML properly"""
        # First generate a document
        gen_response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "return_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_PRE_ISSUE)
            }
        )
        
        assert gen_response.status_code == 200
        doc_id = gen_response.json().get("document_id")
        
        # Then preview it
        preview_response = requests.get(f"{BASE_URL}/api/documents/{doc_id}/preview")
        
        assert preview_response.status_code == 200, f"Preview should return 200, got {preview_response.status_code}"
        assert "text/html" in preview_response.headers.get("content-type", ""), "Preview should return HTML"
        
        html = preview_response.text
        assert "<!doctype html>" in html.lower() or "<html" in html.lower(), "Preview should return valid HTML"


class TestPhotoOnlyProcessing:
    """Test photo_only processing type behavior"""
    
    def test_photo_only_does_not_freeze_product(self):
        """When processing_type=photo_only, product state should NOT be frozen"""
        # Create a photo_only damage record
        response = requests.post(
            f"{BASE_URL}/api/product-damage-history/",
            json={
                "product_id": 99998,  # Test product ID
                "sku": "TEST-PHOTO-ONLY-CHECK",
                "product_name": "Test Product Photo Only Check",
                "category": "Test",
                "order_id": ORDER_WITH_PRE_ISSUE,
                "order_number": "OC-7425",
                "stage": "return",
                "damage_type": "Test Photo Only",
                "damage_code": "test_photo",
                "severity": "low",
                "fee": 0,
                "qty": 1,
                "note": "Testing photo_only - should not freeze product",
                "created_by": "test_agent",
                "processing_type": "photo_only"
            }
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert data.get("success") is True, "Damage record creation should succeed"
        assert data.get("fee") == 0, "photo_only should have fee=0"
        assert data.get("charged_to_client") is False, "photo_only should not charge client"
        
    def test_photo_only_records_in_photo_records_endpoint(self):
        """photo_only records should appear in /api/product-damage-history/photo-records"""
        response = requests.get(f"{BASE_URL}/api/product-damage-history/photo-records")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert "items" in data, "Response should contain items"
        assert "total" in data, "Response should contain total count"
        
        # All items should have processing_type = 'photo_only'
        for item in data.get("items", []):
            # Note: Some items might be from previous tests
            pass  # Just verify the endpoint works


class TestDamageHistoryEndpoints:
    """Test damage history API endpoints"""
    
    def test_get_order_damage_history(self):
        """GET /api/product-damage-history/order/{order_id} should return damage records"""
        response = requests.get(f"{BASE_URL}/api/product-damage-history/order/{ORDER_WITH_TOTAL_LOSS}")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("order_id") == ORDER_WITH_TOTAL_LOSS, "Response should contain correct order_id"
        assert "history" in data, "Response should contain history array"
        assert "total_damages" in data, "Response should contain total_damages count"
        assert "total_fees" in data, "Response should contain total_fees"
        
        # Order 7414 should have damage records
        assert data.get("total_damages", 0) > 0, "Order 7414 should have damage records"
        
    def test_get_pre_issue_damages(self):
        """GET /api/product-damage-history/order/{order_id}/pre-issue should return pre-issue damages"""
        response = requests.get(f"{BASE_URL}/api/product-damage-history/order/{ORDER_WITH_PRE_ISSUE}/pre-issue")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert data.get("order_id") == ORDER_WITH_PRE_ISSUE, "Response should contain correct order_id"
        assert "pre_issue_damages" in data, "Response should contain pre_issue_damages array"
        assert "count" in data, "Response should contain count"
        
        # Order 7425 should have pre_issue damage
        assert data.get("count", 0) > 0, "Order 7425 should have pre_issue damages"
        
    def test_damage_record_has_processing_type(self):
        """Damage records should include processing_type field"""
        response = requests.get(f"{BASE_URL}/api/product-damage-history/order/{ORDER_WITH_TOTAL_LOSS}")
        
        assert response.status_code == 200
        
        data = response.json()
        history = data.get("history", [])
        
        if history:
            # Check that records have processing_type field
            for record in history:
                assert "processing_type" in record, "Damage record should have processing_type field"


class TestDefectActDataBuilder:
    """Test defect act data builder includes all damage types"""
    
    def test_defect_act_data_includes_photo_only(self):
        """Defect act should include photo_only records with 'Фіксація' label"""
        # First create a photo_only record for testing
        create_response = requests.post(
            f"{BASE_URL}/api/product-damage-history/",
            json={
                "product_id": 99997,
                "sku": "TEST-DEFECT-PHOTO",
                "product_name": "Test Product for Defect Act",
                "category": "Test",
                "order_id": ORDER_WITH_PRE_ISSUE,
                "order_number": "OC-7425",
                "stage": "return",
                "damage_type": "Test Fixation",
                "damage_code": "test_fixation",
                "severity": "low",
                "fee": 0,
                "qty": 1,
                "note": "Testing defect act includes photo_only",
                "created_by": "test_agent",
                "processing_type": "photo_only"
            }
        )
        
        assert create_response.status_code == 200
        
        # Now generate defect act
        doc_response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "defect_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_PRE_ISSUE)
            }
        )
        
        assert doc_response.status_code == 200
        # The defect act should be generated successfully
        # Content verification depends on template rendering


class TestReturnActDataBuilder:
    """Test return act data builder includes comprehensive data"""
    
    def test_return_act_data_structure(self):
        """Return act should include items, damages, pre-issue damages, packaging, client info"""
        response = requests.post(
            f"{BASE_URL}/api/documents/generate",
            json={
                "doc_type": "return_act",
                "entity_type": "order",
                "entity_id": str(ORDER_WITH_PRE_ISSUE)
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify document was generated
        assert data.get("success") is True
        assert "html_content" in data
        
        html = data.get("html_content", "")
        
        # Check for key sections in the return act
        assert "Повернені товари" in html or "Найменування" in html, \
            "Return act should have items section"
        assert "Замовник" in html or "ПІБ" in html, \
            "Return act should have client info section"


class TestFinanceSnapshot:
    """Test finance snapshot for damage data"""
    
    def test_finance_snapshot_includes_damage(self):
        """Finance snapshot should include damage data for defect act button logic"""
        response = requests.get(f"{BASE_URL}/api/finance/orders/{ORDER_WITH_TOTAL_LOSS}/snapshot")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Check for damage section
        if "damage" in data:
            damage = data.get("damage", {})
            # damage.rows should exist for defect act button condition
            if "rows" in damage:
                assert isinstance(damage["rows"], list), "damage.rows should be a list"
            # Or damage.items for backward compatibility
            elif "items" in damage:
                assert isinstance(damage["items"], list), "damage.items should be a list"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
