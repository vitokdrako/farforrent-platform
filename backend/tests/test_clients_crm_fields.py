"""
Test: Client Database Optimization - New CRM Fields
Tests for is_regular, company, rating, rating_labels, internal_notes, instagram fields

Endpoints:
- GET /api/clients - List clients with new fields
- GET /api/clients/{id} - Client detail with new fields
- PATCH /api/clients/{id} - Update new fields
- POST /api/clients - Create client with new fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"

# Client ID 10 is for testing (Катерина Сєдая)
TEST_CLIENT_ID = 10


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token in response: {data}"
    return token


@pytest.fixture(scope="module")
def api_client(auth_token):
    """Session with auth header"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Authorization": f"Bearer {auth_token}"
    })
    return session


class TestClientsList:
    """Test GET /api/clients - list with new CRM fields"""
    
    def test_list_clients_returns_200(self, api_client):
        """List clients endpoint should return 200"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_list_clients_returns_array(self, api_client):
        """List should return array of clients"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        data = response.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) > 0, "Expected at least 1 client"
        
    def test_list_clients_has_new_crm_fields(self, api_client):
        """Each client should have new CRM fields"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        data = response.json()
        
        # Check first client has new fields
        client = data[0]
        new_fields = ['is_regular', 'company', 'rating', 'rating_labels', 'internal_notes', 'instagram', 'total_revenue', 'last_order_date']
        
        for field in new_fields:
            assert field in client, f"Missing field '{field}' in client response. Keys: {list(client.keys())}"
            
    def test_list_clients_search_by_company(self, api_client):
        """Search should work with company field"""
        response = api_client.get(f"{BASE_URL}/api/clients", params={"search": "test"})
        assert response.status_code == 200
        
    def test_list_clients_search_by_instagram(self, api_client):
        """Search should work with instagram field"""
        response = api_client.get(f"{BASE_URL}/api/clients", params={"search": "@test"})
        assert response.status_code == 200


class TestClientDetail:
    """Test GET /api/clients/{id} - detail with new CRM fields"""
    
    def test_get_client_detail_returns_200(self, api_client):
        """Get client by ID should return 200"""
        response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_get_client_detail_has_all_crm_fields(self, api_client):
        """Client detail should include all new CRM fields"""
        response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        client = response.json()
        
        # Required new fields
        new_fields = ['is_regular', 'company', 'rating', 'rating_labels', 'internal_notes', 'instagram', 'total_revenue', 'last_order_date']
        
        for field in new_fields:
            assert field in client, f"Missing field '{field}' in client detail. Keys: {list(client.keys())}"
            
    def test_get_client_detail_has_correct_types(self, api_client):
        """CRM fields should have correct types"""
        response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        client = response.json()
        
        # Type checks
        assert isinstance(client.get('is_regular'), bool) or client.get('is_regular') is False, "is_regular should be boolean"
        assert isinstance(client.get('rating'), (int, float)) or client.get('rating') == 0, "rating should be number"
        assert isinstance(client.get('total_revenue'), (int, float)) or client.get('total_revenue') == 0, "total_revenue should be number"
        
    def test_get_client_detail_has_stats(self, api_client):
        """Client detail should have stats section"""
        response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        client = response.json()
        
        assert 'stats' in client, "Missing 'stats' in client detail"
        
    def test_get_client_not_found(self, api_client):
        """Non-existent client should return 404"""
        response = api_client.get(f"{BASE_URL}/api/clients/999999")
        assert response.status_code == 404


class TestClientUpdate:
    """Test PATCH /api/clients/{id} - update new CRM fields"""
    
    def test_update_is_regular_field(self, api_client):
        """Should update is_regular field"""
        # Get current value
        get_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_response.json()
        original_value = original.get('is_regular', False)
        
        # Update to opposite
        new_value = not original_value
        update_response = api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={
            "is_regular": new_value
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update
        verify_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_response.json()
        assert updated.get('is_regular') == new_value, f"is_regular not updated. Expected {new_value}, got {updated.get('is_regular')}"
        
        # Restore original value
        api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={"is_regular": original_value})
        
    def test_update_rating_field(self, api_client):
        """Should update rating field"""
        # Get current value
        get_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_response.json()
        original_rating = original.get('rating', 0)
        
        # Update rating
        new_rating = 4
        update_response = api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={
            "rating": new_rating
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify update
        verify_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_response.json()
        assert updated.get('rating') == new_rating, f"rating not updated. Expected {new_rating}, got {updated.get('rating')}"
        
        # Restore original value
        api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={"rating": original_rating})
        
    def test_update_company_field(self, api_client):
        """Should update company field"""
        get_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_response.json()
        original_company = original.get('company')
        
        new_company = "TEST_Company_CRM"
        update_response = api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={
            "company": new_company
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        verify_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_response.json()
        assert updated.get('company') == new_company, f"company not updated. Expected {new_company}, got {updated.get('company')}"
        
        # Restore
        api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={"company": original_company})
        
    def test_update_instagram_field(self, api_client):
        """Should update instagram field"""
        get_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_response.json()
        original_instagram = original.get('instagram')
        
        new_instagram = "@test_instagram_crm"
        update_response = api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={
            "instagram": new_instagram
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        verify_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_response.json()
        assert updated.get('instagram') == new_instagram, f"instagram not updated. Expected {new_instagram}, got {updated.get('instagram')}"
        
        # Restore
        api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={"instagram": original_instagram})
        
    def test_update_internal_notes_field(self, api_client):
        """Should update internal_notes field"""
        get_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_response.json()
        original_notes = original.get('internal_notes')
        
        new_notes = "TEST_Internal note for CRM testing"
        update_response = api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={
            "internal_notes": new_notes
        })
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        verify_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_response.json()
        assert updated.get('internal_notes') == new_notes, f"internal_notes not updated. Expected {new_notes}, got {updated.get('internal_notes')}"
        
        # Restore
        api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json={"internal_notes": original_notes})
        
    def test_update_multiple_crm_fields_at_once(self, api_client):
        """Should update multiple CRM fields in single request"""
        get_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_response.json()
        
        # Update multiple fields
        update_payload = {
            "is_regular": True,
            "rating": 5,
            "company": "TEST_MultiUpdate_Company",
            "instagram": "@test_multi",
            "internal_notes": "TEST multi-field update"
        }
        
        update_response = api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json=update_payload)
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        
        # Verify all fields
        verify_response = api_client.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_response.json()
        
        assert updated.get('is_regular') == True
        assert updated.get('rating') == 5
        assert updated.get('company') == "TEST_MultiUpdate_Company"
        assert updated.get('instagram') == "@test_multi"
        assert updated.get('internal_notes') == "TEST multi-field update"
        
        # Restore original values
        restore_payload = {
            "is_regular": original.get('is_regular', False),
            "rating": original.get('rating', 0),
            "company": original.get('company'),
            "instagram": original.get('instagram'),
            "internal_notes": original.get('internal_notes')
        }
        api_client.patch(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}", json=restore_payload)


class TestClientCreate:
    """Test POST /api/clients - create with new CRM fields"""
    
    def test_create_client_with_crm_fields(self, api_client):
        """Should create client with new CRM fields"""
        import time
        unique_email = f"TEST_crm_{int(time.time())}@test.com"
        
        create_payload = {
            "email": unique_email,
            "full_name": "TEST CRM Client",
            "phone": "+380999999999",
            "is_regular": True,
            "rating": 4,
            "company": "TEST_New_Company",
            "instagram": "@test_new_client",
            "internal_notes": "TEST created via API test"
        }
        
        response = api_client.post(f"{BASE_URL}/api/clients", json=create_payload)
        assert response.status_code == 200, f"Create failed: {response.text}"
        
        created = response.json()
        
        # Verify CRM fields are set
        assert created.get('email') == unique_email
        assert created.get('is_regular') == True
        assert created.get('rating') == 4
        assert created.get('company') == "TEST_New_Company"
        assert created.get('instagram') == "@test_new_client"
        assert created.get('internal_notes') == "TEST created via API test"
        
        # Clean up - Note: DELETE endpoint might not exist, so just verify creation worked
        print(f"✅ Created test client ID: {created.get('id')}")


class TestClientFilterRegular:
    """Test filter for regular clients"""
    
    def test_filter_by_regular_clients_in_frontend(self, api_client):
        """List endpoint should return is_regular field for frontend filtering"""
        response = api_client.get(f"{BASE_URL}/api/clients")
        data = response.json()
        
        # Check that at least some clients have is_regular field
        has_is_regular = all('is_regular' in client for client in data[:10])
        assert has_is_regular, "Not all clients have is_regular field"
        
        # Count regular vs non-regular (frontend does this filtering)
        regular_count = sum(1 for c in data if c.get('is_regular'))
        total_count = len(data)
        
        print(f"📊 Total clients: {total_count}, Regular clients: {regular_count}")
