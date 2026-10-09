"""
Test Order Chats Integration into Personal Cabinet
Tests for:
- GET /api/cabinet/order-chats with different modes (active, with_notes, all)
- GET /api/cabinet/order-chats with search parameter
- GET /api/orders/{order_id}/internal-notes
- POST /api/orders/{order_id}/internal-notes
- Existing cabinet endpoints (profile, stats, tasks, team)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com')

class TestAuth:
    """Authentication tests"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with authentication"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_login_returns_token(self):
        """Test login endpoint returns access token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "user" in data
        assert data["user"]["email"] == "vitokdrako@gmail.com"


class TestOrderChatsAPI:
    """Order Chats API tests - main feature under test"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_order_chats_mode_active(self, auth_headers):
        """GET /api/cabinet/order-chats?mode=active returns active orders"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/order-chats?mode=active",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Check that at least some orders are returned
        assert len(data) > 0, "No active orders returned"
        
        # Verify response structure
        order = data[0]
        assert "order_id" in order
        assert "order_number" in order
        assert "customer_name" in order
        assert "status" in order
        assert "notes_count" in order
    
    def test_order_chats_mode_with_notes(self, auth_headers):
        """GET /api/cabinet/order-chats?mode=with_notes returns orders with notes"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/order-chats?mode=with_notes",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # All returned orders should have notes_count > 0
        for order in data:
            assert order.get("notes_count", 0) > 0, f"Order {order.get('order_number')} has no notes"
    
    def test_order_chats_mode_all(self, auth_headers):
        """GET /api/cabinet/order-chats?mode=all returns all orders"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/order-chats?mode=all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0, "No orders returned for mode=all"
    
    def test_order_chats_search_by_order_number(self, auth_headers):
        """Search for specific order by number"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/order-chats?mode=active&search=OC-7400",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        
        # Should find the specific order
        found = any(o.get("order_number") == "OC-7400" for o in data)
        assert found, "OC-7400 not found in search results"
    
    def test_order_chats_search_empty_results(self, auth_headers):
        """Search with no matches returns empty list"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/order-chats?mode=active&search=NONEXISTENT-99999",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0, "Expected empty results for non-existent order"


class TestOrderInternalNotes:
    """Internal notes API tests"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_get_internal_notes(self, auth_headers):
        """GET /api/orders/{order_id}/internal-notes returns notes"""
        response = requests.get(
            f"{BASE_URL}/api/orders/7400/internal-notes",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") is True
        assert "notes" in data
        assert isinstance(data["notes"], list)
        assert data.get("count", 0) >= 2, "OC-7400 should have at least 2 notes"
        
        # Verify note structure
        note = data["notes"][0]
        assert "id" in note
        assert "order_id" in note
        assert "message" in note
        assert "created_at" in note
    
    def test_post_internal_note(self, auth_headers):
        """POST /api/orders/{order_id}/internal-notes creates new note"""
        # First, get current count
        get_response = requests.get(
            f"{BASE_URL}/api/orders/7400/internal-notes",
            headers=auth_headers
        )
        initial_count = get_response.json().get("count", 0)
        
        # Post new note
        response = requests.post(
            f"{BASE_URL}/api/orders/7400/internal-notes",
            headers=auth_headers,
            json={"message": "TEST_pytest_order_chats: Test message for verification"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data.get("success") is True
        assert "note" in data
        assert data["note"]["message"] == "TEST_pytest_order_chats: Test message for verification"
        assert data["note"]["user_name"] is not None
        
        # Verify note was created (count increased)
        verify_response = requests.get(
            f"{BASE_URL}/api/orders/7400/internal-notes",
            headers=auth_headers
        )
        new_count = verify_response.json().get("count", 0)
        assert new_count > initial_count, "Note count should have increased"
    
    def test_post_internal_note_empty_message_fails(self, auth_headers):
        """POST with empty message should fail"""
        response = requests.post(
            f"{BASE_URL}/api/orders/7400/internal-notes",
            headers=auth_headers,
            json={"message": "   "}
        )
        assert response.status_code == 400
    
    def test_post_internal_note_requires_auth(self):
        """POST without auth should fail"""
        response = requests.post(
            f"{BASE_URL}/api/orders/7400/internal-notes",
            headers={"Content-Type": "application/json"},
            json={"message": "Should fail without auth"}
        )
        assert response.status_code == 401


class TestExistingCabinetTabs:
    """Test existing cabinet tabs still work"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "vitokdrako@gmail.com",
            "password": "test123"
        })
        token = response.json()["access_token"]
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def test_profile_endpoint(self, auth_headers):
        """GET /api/cabinet/profile returns user profile"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/profile",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "user_id" in data
        assert "email" in data
        assert "role" in data
    
    def test_stats_endpoint(self, auth_headers):
        """GET /api/cabinet/stats returns user stats"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "tasks" in data
        assert "today" in data
    
    def test_team_endpoint(self, auth_headers):
        """GET /api/cabinet/team returns team overview"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/team",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        if len(data) > 0:
            member = data[0]
            assert "user_id" in member
            assert "name" in member
            assert "role" in member
    
    def test_my_tasks_endpoint(self, auth_headers):
        """GET /api/cabinet/my-tasks returns tasks"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_focus_endpoint(self, auth_headers):
        """GET /api/cabinet/focus returns focus data"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/focus",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "overdue" in data
        assert "due_today" in data
        assert "in_progress" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
