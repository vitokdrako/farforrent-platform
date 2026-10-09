"""
Test suite for Admin Template Editor feature
Tests the document template CRUD operations and preview functionality
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "vitokdrako@gmail.com"
ADMIN_PASSWORD = "test123"


class TestTemplateEditorBackend:
    """Tests for Admin Panel Template Editor - Backend APIs"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    # === Templates List API ===
    
    def test_get_templates_list_returns_31_templates(self):
        """GET /api/admin/templates returns list of 31 templates"""
        response = requests.get(f"{BASE_URL}/api/admin/templates", headers=self.headers)
        assert response.status_code == 200
        templates = response.json()
        assert len(templates) == 31, f"Expected 31 templates, got {len(templates)}"
        
        # Verify structure
        for tpl in templates:
            assert "doc_type" in tpl
            assert "has_file" in tpl
            assert "source" in tpl
    
    def test_templates_list_contains_quote_template(self):
        """Templates list contains quote template with correct fields"""
        response = requests.get(f"{BASE_URL}/api/admin/templates", headers=self.headers)
        templates = response.json()
        
        quote = next((t for t in templates if t["doc_type"] == "quote"), None)
        assert quote is not None, "Quote template not found in list"
        assert quote["has_file"] == True, "Quote template should have file"
        assert quote["source"] in ["file", "db"], "Quote source should be file or db"
    
    # === Get Template Content API ===
    
    def test_get_quote_template_content(self):
        """GET /api/admin/templates/quote returns template content (14310+ chars)"""
        response = requests.get(f"{BASE_URL}/api/admin/templates/quote", headers=self.headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "content" in data
        assert "source" in data
        assert "doc_type" in data
        
        assert len(data["content"]) >= 14000, f"Quote template too short: {len(data['content'])} chars"
        assert "<!doctype" in data["content"].lower(), "Template should contain HTML doctype"
    
    def test_get_nonexistent_template_returns_404(self):
        """GET /api/admin/templates/nonexistent returns 404"""
        response = requests.get(f"{BASE_URL}/api/admin/templates/nonexistent_template_xyz", headers=self.headers)
        assert response.status_code == 404
    
    # === Save Template to DB API ===
    
    def test_save_template_to_db(self):
        """PUT /api/admin/templates/quote saves template to DB"""
        # First get original content
        original = requests.get(f"{BASE_URL}/api/admin/templates/quote", headers=self.headers).json()
        original_content = original.get("content", "")
        
        # Save modified content
        test_content = "<!-- TEST_SAVE_TEMPLATE -->\n" + original_content[:1000]
        response = requests.put(
            f"{BASE_URL}/api/admin/templates/quote",
            headers=self.headers,
            json={"content": test_content}
        )
        assert response.status_code == 200
        assert response.json().get("success") == True
        
        # Verify it was saved to DB
        verify = requests.get(f"{BASE_URL}/api/admin/templates/quote", headers=self.headers).json()
        assert verify["source"] == "db", "Template should be from DB after save"
        assert "TEST_SAVE_TEMPLATE" in verify["content"], "Saved content should be retrievable"
        
        # Clean up - reset to file
        requests.post(f"{BASE_URL}/api/admin/templates/quote/reset", headers=self.headers)
    
    def test_save_empty_template_returns_error(self):
        """PUT /api/admin/templates/quote with empty content returns 400"""
        response = requests.put(
            f"{BASE_URL}/api/admin/templates/quote",
            headers=self.headers,
            json={"content": "   "}
        )
        assert response.status_code == 400
    
    # === Reset Template API ===
    
    def test_reset_template_to_file(self):
        """POST /api/admin/templates/quote/reset resets to file version"""
        # First save something to DB
        requests.put(
            f"{BASE_URL}/api/admin/templates/quote",
            headers=self.headers,
            json={"content": "<!-- TEMP_TEST -->\n<html><body>Test</body></html>"}
        )
        
        # Verify it's in DB
        after_save = requests.get(f"{BASE_URL}/api/admin/templates/quote", headers=self.headers).json()
        assert after_save["source"] == "db"
        
        # Reset
        response = requests.post(f"{BASE_URL}/api/admin/templates/quote/reset", headers=self.headers)
        assert response.status_code == 200
        assert response.json().get("success") == True
        assert response.json().get("source") == "file"
        
        # Verify it's back to file
        after_reset = requests.get(f"{BASE_URL}/api/admin/templates/quote", headers=self.headers).json()
        assert after_reset["source"] == "file"
        assert len(after_reset["content"]) >= 14000, "Should have full file content after reset"
    
    # === Preview Template API ===
    
    def test_preview_template_with_order_7403(self):
        """GET /api/admin/templates/quote/preview?order_id=7403 renders preview HTML"""
        response = requests.get(
            f"{BASE_URL}/api/admin/templates/quote/preview?order_id=7403",
            headers=self.headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get("success") == True
        assert "html" in data
        assert len(data["html"]) > 1000, "Preview HTML should be substantial"
    
    def test_preview_contains_company_phone(self):
        """Preview HTML contains company phone from DB: (097) 123 09 93"""
        response = requests.get(
            f"{BASE_URL}/api/admin/templates/quote/preview?order_id=7403",
            headers=self.headers
        )
        data = response.json()
        html = data.get("html", "")
        
        # Check for company phone from system_settings/company_config
        assert "(097) 123 09 93" in html, "Preview should contain company phone from DB"
    
    def test_preview_contains_order_number(self):
        """Preview HTML contains order number OC-7403"""
        response = requests.get(
            f"{BASE_URL}/api/admin/templates/quote/preview?order_id=7403",
            headers=self.headers
        )
        data = response.json()
        html = data.get("html", "")
        
        assert "OC-7403" in html, "Preview should contain order number"


class TestDocumentGenerationWithDBOverride:
    """Tests for document generation using DB override loader"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        self.token = response.json().get("access_token")
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_estimate_preview_uses_company_data_from_db(self):
        """GET /api/documents/estimate/7403/preview returns HTML with company phone from DB"""
        response = requests.get(f"{BASE_URL}/api/documents/estimate/7403/preview")
        assert response.status_code == 200
        
        html = response.text
        # Verify company phone from DB (get_company_config)
        assert "(097) 123 09 93" in html, "Estimate should use company phone from DB"
    
    def test_db_override_is_used_for_rendering(self):
        """When template is saved to DB, document generation uses DB version"""
        # Save a modified template with marker
        marker = "<!-- DB_OVERRIDE_TEST_MARKER_12345 -->"
        
        # Get original content
        original = requests.get(f"{BASE_URL}/api/admin/templates/quote", headers=self.headers).json()
        original_content = original.get("content", "")
        
        # Save with marker at beginning
        modified_content = marker + "\n" + original_content
        requests.put(
            f"{BASE_URL}/api/admin/templates/quote",
            headers=self.headers,
            json={"content": modified_content}
        )
        
        # Preview should show the marker (uses DBOverrideLoader)
        preview = requests.get(
            f"{BASE_URL}/api/admin/templates/quote/preview?order_id=7403",
            headers=self.headers
        ).json()
        
        assert marker in preview.get("html", ""), "Preview should use DB override template"
        
        # Clean up - reset
        requests.post(f"{BASE_URL}/api/admin/templates/quote/reset", headers=self.headers)
        
        # After reset, marker should be gone
        preview_after = requests.get(
            f"{BASE_URL}/api/admin/templates/quote/preview?order_id=7403",
            headers=self.headers
        ).json()
        
        assert marker not in preview_after.get("html", ""), "After reset, should use file template"


class TestTemplateEditorAuthorization:
    """Tests for authorization on template endpoints"""
    
    def test_templates_list_requires_auth(self):
        """GET /api/admin/templates without auth returns 403"""
        response = requests.get(f"{BASE_URL}/api/admin/templates")
        assert response.status_code == 403
    
    def test_templates_list_requires_admin_role(self):
        """GET /api/admin/templates with non-admin token returns 403"""
        # Login as manager (non-admin)
        login = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "max@farforrent.com.ua",
            "password": "test123"
        })
        
        if login.status_code == 200:
            token = login.json().get("access_token")
            response = requests.get(
                f"{BASE_URL}/api/admin/templates",
                headers={"Authorization": f"Bearer {token}"}
            )
            assert response.status_code == 403, "Non-admin should get 403"
        else:
            pytest.skip("Manager user not available for test")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
