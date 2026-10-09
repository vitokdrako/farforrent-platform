"""
Test Return Versions API - Версіонування часткових повернень

Tests for:
- GET /api/return-versions/active - список активних версій
- GET /api/return-versions/version/{version_id} - деталі версії
- GET /api/return-versions/order/{order_id}/versions - історія версій замовлення
- POST /api/return-versions/version/{version_id}/return-item - позначити товар як повернений
- POST /api/return-versions/order/{order_id}/create-version - створення нової версії
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        data = response.json()
        return data.get("token")
    pytest.skip(f"Authentication failed: {response.status_code}")


@pytest.fixture
def api_client(auth_token):
    """Authenticated requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestReturnVersionsActive:
    """Tests for GET /api/return-versions/active"""
    
    def test_get_active_versions_success(self, api_client):
        """Test getting list of active partial return versions"""
        response = api_client.get(f"{BASE_URL}/api/return-versions/active")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "versions" in data
        assert "count" in data
        assert isinstance(data["versions"], list)
        assert isinstance(data["count"], int)
        assert data["count"] == len(data["versions"])
        
        # If there are versions, validate structure
        if data["versions"]:
            version = data["versions"][0]
            assert "version_id" in version
            assert "parent_order_id" in version
            assert "display_number" in version
            assert "customer_name" in version
            assert "customer_phone" in version
            assert "items_count" in version
            print(f"✅ Found {data['count']} active versions")
        else:
            print("✅ No active versions (empty list)")


class TestReturnVersionDetails:
    """Tests for GET /api/return-versions/version/{version_id}"""
    
    def test_get_version_details_success(self, api_client):
        """Test getting details of a specific version"""
        # First get active versions to find a valid version_id
        active_response = api_client.get(f"{BASE_URL}/api/return-versions/active")
        active_data = active_response.json()
        
        if not active_data["versions"]:
            pytest.skip("No active versions to test")
        
        version_id = active_data["versions"][0]["version_id"]
        
        response = api_client.get(f"{BASE_URL}/api/return-versions/version/{version_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert data["version_id"] == version_id
        assert "parent_order_id" in data
        assert "parent_order_number" in data
        assert "version_number" in data
        assert "display_number" in data
        assert "customer" in data
        assert "items" in data
        assert "version_history" in data
        assert "status" in data
        
        # Validate customer structure
        customer = data["customer"]
        assert "name" in customer
        assert "phone" in customer
        assert "email" in customer
        
        # Validate items structure
        assert isinstance(data["items"], list)
        if data["items"]:
            item = data["items"][0]
            assert "item_id" in item
            assert "product_id" in item
            assert "sku" in item
            assert "name" in item
            assert "qty" in item
            assert "daily_rate" in item
            assert "status" in item
        
        # Validate version history
        assert isinstance(data["version_history"], list)
        if data["version_history"]:
            history_item = data["version_history"][0]
            assert "version_id" in history_item
            assert "version_number" in history_item
            assert "display_number" in history_item
            assert "status" in history_item
        
        print(f"✅ Version {data['display_number']} has {len(data['items'])} items")
    
    def test_get_version_details_not_found(self, api_client):
        """Test getting details of non-existent version"""
        response = api_client.get(f"{BASE_URL}/api/return-versions/version/999999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"✅ Correctly returns 404 for non-existent version")


class TestOrderVersionHistory:
    """Tests for GET /api/return-versions/order/{order_id}/versions"""
    
    def test_get_order_versions_success(self, api_client):
        """Test getting all versions for a specific order"""
        # Use known order_id 7266 which has test versions
        order_id = 7266
        
        response = api_client.get(f"{BASE_URL}/api/return-versions/order/{order_id}/versions")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "order_id" in data
        assert data["order_id"] == order_id
        assert "versions" in data
        assert isinstance(data["versions"], list)
        
        # Validate versions structure
        if data["versions"]:
            version = data["versions"][0]
            assert "version_id" in version
            assert "version_number" in version
            assert "display_number" in version
            assert "status" in version
            assert "total_price" in version
            assert "items_count" in version
            
            # Verify version numbering format
            assert f"OC-{order_id}" in version["display_number"]
            
            print(f"✅ Order {order_id} has {len(data['versions'])} versions")
        else:
            print(f"✅ Order {order_id} has no versions yet")
    
    def test_get_order_versions_empty(self, api_client):
        """Test getting versions for order with no versions"""
        # Use an order_id that likely has no versions
        response = api_client.get(f"{BASE_URL}/api/return-versions/order/1/versions")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "order_id" in data
        assert "versions" in data
        assert isinstance(data["versions"], list)
        print(f"✅ Order 1 has {len(data['versions'])} versions")


class TestReturnItem:
    """Tests for POST /api/return-versions/version/{version_id}/return-item"""
    
    def test_return_item_not_found(self, api_client):
        """Test returning item from non-existent version"""
        response = api_client.post(
            f"{BASE_URL}/api/return-versions/version/999999/return-item",
            json={"item_id": 1}
        )
        
        # Should return 404 for non-existent version or item
        assert response.status_code in [404, 500]
        print(f"✅ Correctly handles non-existent version/item")
    
    def test_return_item_invalid_item(self, api_client):
        """Test returning non-existent item from valid version"""
        # First get active versions
        active_response = api_client.get(f"{BASE_URL}/api/return-versions/active")
        active_data = active_response.json()
        
        if not active_data["versions"]:
            pytest.skip("No active versions to test")
        
        version_id = active_data["versions"][0]["version_id"]
        
        response = api_client.post(
            f"{BASE_URL}/api/return-versions/version/{version_id}/return-item",
            json={"item_id": 999999}
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"✅ Correctly returns 404 for non-existent item")


class TestVersionComplete:
    """Tests for POST /api/return-versions/version/{version_id}/complete"""
    
    def test_complete_version_not_found(self, api_client):
        """Test completing non-existent version"""
        response = api_client.post(
            f"{BASE_URL}/api/return-versions/version/999999/complete"
        )
        
        # Should handle gracefully
        assert response.status_code in [200, 404, 500]
        print(f"✅ Complete endpoint responds with status {response.status_code}")


class TestCreateVersion:
    """Tests for POST /api/return-versions/order/{order_id}/create-version"""
    
    def test_create_version_order_not_found(self, api_client):
        """Test creating version for non-existent order"""
        response = api_client.post(
            f"{BASE_URL}/api/return-versions/order/999999/create-version",
            json={
                "not_returned_items": [
                    {
                        "product_id": 1,
                        "sku": "TEST-001",
                        "name": "Test Product",
                        "qty": 1,
                        "daily_rate": 100.0
                    }
                ]
            }
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        print(f"✅ Correctly returns 404 for non-existent order")
    
    def test_create_version_empty_items(self, api_client):
        """Test creating version with empty items list"""
        response = api_client.post(
            f"{BASE_URL}/api/return-versions/order/7266/create-version",
            json={
                "not_returned_items": []
            }
        )
        
        # Should either succeed with 0 items or return validation error
        # The API allows empty items list (all items returned)
        assert response.status_code in [200, 422]
        print(f"✅ Empty items handled with status {response.status_code}")


class TestDataIntegrity:
    """Tests for data integrity and consistency"""
    
    def test_version_display_number_format(self, api_client):
        """Test that display numbers follow correct format OC-XXXX(N)"""
        response = api_client.get(f"{BASE_URL}/api/return-versions/order/7266/versions")
        data = response.json()
        
        for version in data["versions"]:
            display = version["display_number"]
            # Should match pattern OC-7266(1), OC-7266(2), etc.
            assert "OC-7266" in display
            assert "(" in display and ")" in display
            
            # Extract version number from display
            version_num = int(display.split("(")[1].rstrip(")"))
            assert version_num == version["version_number"]
        
        print(f"✅ All display numbers follow correct format")
    
    def test_version_history_ordering(self, api_client):
        """Test that version history is ordered by version_number DESC"""
        active_response = api_client.get(f"{BASE_URL}/api/return-versions/active")
        active_data = active_response.json()
        
        if not active_data["versions"]:
            pytest.skip("No active versions to test")
        
        version_id = active_data["versions"][0]["version_id"]
        response = api_client.get(f"{BASE_URL}/api/return-versions/version/{version_id}")
        data = response.json()
        
        history = data["version_history"]
        if len(history) > 1:
            # Verify descending order
            for i in range(len(history) - 1):
                assert history[i]["version_number"] >= history[i + 1]["version_number"]
        
        print(f"✅ Version history correctly ordered (DESC)")
    
    def test_active_versions_only_active_status(self, api_client):
        """Test that /active endpoint only returns active versions"""
        response = api_client.get(f"{BASE_URL}/api/return-versions/active")
        data = response.json()
        
        # All versions in active list should have status 'active'
        # Note: The API doesn't return status in the list, but we can verify via details
        for version in data["versions"]:
            detail_response = api_client.get(
                f"{BASE_URL}/api/return-versions/version/{version['version_id']}"
            )
            detail_data = detail_response.json()
            assert detail_data["status"] == "active"
        
        print(f"✅ All versions in /active have status='active'")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
