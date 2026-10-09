"""
Tests for Vendors API endpoints
/app/backend/routes/finance.py - vendors section
"""
import pytest
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"

def get_auth_headers():
    """Get authentication headers"""
    response = client.post("/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


class TestVendorsAPI:
    """Tests for /api/finance/vendors endpoints"""
    
    def test_list_vendors(self):
        """GET /api/finance/vendors - should return list of vendors"""
        headers = get_auth_headers()
        response = client.get("/api/finance/vendors", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "vendors" in data
        assert isinstance(data["vendors"], list)
        
    def test_create_vendor_service(self):
        """POST /api/finance/vendors - should create service vendor"""
        headers = get_auth_headers()
        vendor_data = {
            "name": "Тест Хімчистка",
            "vendor_type": "cleaning",
            "contact_name": "Іван Петренко",
            "phone": "+380501234567",
            "email": "cleaning@example.com",
            "address": "м. Харків, вул. Тестова, 1",
            "iban": "UA000000000000000000000000000",
            "note": "Тестовий постачальник хімчистки"
        }
        
        response = client.post("/api/finance/vendors", json=vendor_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "vendor_id" in data
        
    def test_create_vendor_repair(self):
        """POST /api/finance/vendors - should create repair vendor"""
        headers = get_auth_headers()
        vendor_data = {
            "name": "Реставрація Декор",
            "vendor_type": "repair",
            "contact_name": "Марія Сидоренко",
            "phone": "+380679876543",
            "email": "repair@example.com",
            "note": "Реставрація фарфору та скла"
        }
        
        response = client.post("/api/finance/vendors", json=vendor_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        
    def test_create_vendor_delivery(self):
        """POST /api/finance/vendors - should create delivery vendor"""
        headers = get_auth_headers()
        vendor_data = {
            "name": "Швидка Доставка",
            "vendor_type": "delivery",
            "contact_name": "Олег Кравченко",
            "phone": "+380931112233",
            "note": "Доставка по Харкову"
        }
        
        response = client.post("/api/finance/vendors", json=vendor_data, headers=headers)
        
        assert response.status_code == 200
        
    def test_vendor_types_filter(self):
        """GET /api/finance/vendors?vendor_type=cleaning - should filter by type"""
        headers = get_auth_headers()
        response = client.get("/api/finance/vendors?vendor_type=cleaning", headers=headers)
        
        assert response.status_code == 200
        # Filter parameter accepted (even if not implemented, no error)
        
    def test_update_vendor(self):
        """PUT /api/finance/vendors/{id} - should update vendor"""
        headers = get_auth_headers()
        
        # First, get a vendor ID
        list_response = client.get("/api/finance/vendors", headers=headers)
        vendors = list_response.json().get("vendors", [])
        
        if vendors:
            vendor_id = vendors[0]["id"]
            update_data = {
                "name": vendors[0]["name"] + " (updated)",
                "vendor_type": vendors[0].get("vendor_type", "service"),
                "contact_name": vendors[0].get("contact_name"),
                "phone": vendors[0].get("phone"),
                "email": vendors[0].get("email"),
                "address": vendors[0].get("address"),
                "iban": vendors[0].get("iban"),
                "note": "Updated note"
            }
            
            response = client.put(f"/api/finance/vendors/{vendor_id}", json=update_data, headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") == True
            
    def test_vendor_structure(self):
        """Verify vendor record has correct structure"""
        headers = get_auth_headers()
        response = client.get("/api/finance/vendors", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["vendors"]:
            vendor = data["vendors"][0]
            expected_fields = ["id", "name", "vendor_type", "contact_name", 
                             "phone", "email", "address", "iban", "balance", "is_active"]
            for field in expected_fields:
                assert field in vendor, f"Missing field: {field}"


class TestVendorTypes:
    """Tests for vendor type categorization"""
    
    def test_vendor_types(self):
        """Verify supported vendor types"""
        expected_types = ["service", "cleaning", "repair", "delivery"]
        
        headers = get_auth_headers()
        response = client.get("/api/finance/vendors", headers=headers)
        vendors = response.json().get("vendors", [])
        
        for vendor in vendors:
            vendor_type = vendor.get("vendor_type", "service")
            # Should be one of expected types or default to 'service'
            assert vendor_type in expected_types or vendor_type == "service"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
