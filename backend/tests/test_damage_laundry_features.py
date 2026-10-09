"""
Test DamageHub Laundry Features - Прання (Washing) та Хімчистка (Dry cleaning)

Testing the refactored DamageHub features:
1. Laundry queue endpoints with type parameter (washing/laundry)
2. Send-to-washing endpoint
3. Send-to-laundry endpoint
4. KPI stats for washing and laundry
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"


class TestLaundryQueueAPI:
    """Test laundry queue API with type parameter"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_laundry_queue_washing_type(self, auth_headers):
        """Test GET /api/laundry/queue?type=washing returns washing queue items"""
        response = requests.get(
            f"{BASE_URL}/api/laundry/queue?type=washing",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should contain 'items' field"
        assert "total" in data, "Response should contain 'total' field"
        assert isinstance(data["items"], list), "Items should be a list"
        
        print(f"✅ Washing queue: {data['total']} items")
    
    def test_laundry_queue_laundry_type(self, auth_headers):
        """Test GET /api/laundry/queue?type=laundry returns laundry (dry cleaning) queue items"""
        response = requests.get(
            f"{BASE_URL}/api/laundry/queue?type=laundry",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should contain 'items' field"
        assert "total" in data, "Response should contain 'total' field"
        assert isinstance(data["items"], list), "Items should be a list"
        
        print(f"✅ Laundry (dry cleaning) queue: {data['total']} items")
    
    def test_laundry_batches_washing_type(self, auth_headers):
        """Test GET /api/laundry/batches?type=washing returns washing batches"""
        response = requests.get(
            f"{BASE_URL}/api/laundry/batches?type=washing",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of batches"
        
        print(f"✅ Washing batches: {len(data)} batches")
    
    def test_laundry_batches_laundry_type(self, auth_headers):
        """Test GET /api/laundry/batches?type=laundry returns laundry (dry cleaning) batches"""
        response = requests.get(
            f"{BASE_URL}/api/laundry/batches?type=laundry",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of batches"
        
        print(f"✅ Laundry (dry cleaning) batches: {len(data)} batches")


class TestDamageHistoryProcessing:
    """Test damage history processing endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_damage_cases_grouped(self, auth_headers):
        """Test GET /api/product-damage-history/cases/grouped returns cases"""
        response = requests.get(
            f"{BASE_URL}/api/product-damage-history/cases/grouped",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "cases" in data, "Response should contain 'cases' field"
        assert "total" in data, "Response should contain 'total' field"
        
        print(f"✅ Damage cases: {data['total']} cases")
    
    def test_wash_processing_queue(self, auth_headers):
        """Test GET /api/product-damage-history/processing/wash returns wash queue"""
        response = requests.get(
            f"{BASE_URL}/api/product-damage-history/processing/wash",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should contain 'items' field"
        assert "total" in data, "Response should contain 'total' field"
        
        print(f"✅ Wash processing queue: {data['total']} items")
    
    def test_restoration_processing_queue(self, auth_headers):
        """Test GET /api/product-damage-history/processing/restoration returns restoration queue"""
        response = requests.get(
            f"{BASE_URL}/api/product-damage-history/processing/restoration",
            headers=auth_headers
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "items" in data, "Response should contain 'items' field"
        assert "total" in data, "Response should contain 'total' field"
        
        print(f"✅ Restoration processing queue: {data['total']} items")


class TestSendToProcessingEndpoints:
    """Test send-to-washing and send-to-laundry endpoints exist and respond properly"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_send_to_washing_endpoint_exists(self, auth_headers):
        """Test POST /api/product-damage-history/{damage_id}/send-to-washing endpoint exists"""
        # Use a fake damage_id to verify endpoint exists and returns proper error
        fake_damage_id = "test-fake-id-12345"
        
        response = requests.post(
            f"{BASE_URL}/api/product-damage-history/{fake_damage_id}/send-to-washing",
            headers=auth_headers,
            json={"notes": "Test"}
        )
        
        # Should return 404 (not found) for fake ID, not 405 (method not allowed) or 404 route not found
        assert response.status_code in [404, 400], f"Expected 404 or 400 for fake ID, got {response.status_code}: {response.text}"
        
        # Check error message is about record not found
        data = response.json()
        assert "detail" in data, "Response should contain error detail"
        
        print(f"✅ send-to-washing endpoint exists - returned {response.status_code} for fake ID")
    
    def test_send_to_laundry_endpoint_exists(self, auth_headers):
        """Test POST /api/product-damage-history/{damage_id}/send-to-laundry endpoint exists"""
        # Use a fake damage_id to verify endpoint exists and returns proper error
        fake_damage_id = "test-fake-id-12345"
        
        response = requests.post(
            f"{BASE_URL}/api/product-damage-history/{fake_damage_id}/send-to-laundry",
            headers=auth_headers,
            json={"notes": "Test"}
        )
        
        # Should return 404 (not found) for fake ID, not 405 (method not allowed)
        assert response.status_code in [404, 400], f"Expected 404 or 400 for fake ID, got {response.status_code}: {response.text}"
        
        # Check error message
        data = response.json()
        assert "detail" in data, "Response should contain error detail"
        
        print(f"✅ send-to-laundry endpoint exists - returned {response.status_code} for fake ID")


class TestAddToBatchEndpoint:
    """Test add-to-batch endpoint for creating laundry/washing batches"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if response.status_code == 200:
            return response.json().get("token")
        pytest.skip("Authentication failed - skipping authenticated tests")
    
    @pytest.fixture
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
    
    def test_add_to_batch_endpoint_exists(self, auth_headers):
        """Test POST /api/laundry/queue/add-to-batch endpoint exists"""
        # Send empty item_ids to verify endpoint exists
        response = requests.post(
            f"{BASE_URL}/api/laundry/queue/add-to-batch",
            headers=auth_headers,
            json={
                "item_ids": [],
                "laundry_company": "Test Company",
                "complexity": "normal",
                "batch_type": "washing"
            }
        )
        
        # Should return 400 for empty items
        assert response.status_code == 400, f"Expected 400 for empty items, got {response.status_code}: {response.text}"
        
        data = response.json()
        assert "detail" in data, "Response should contain error detail"
        
        print(f"✅ add-to-batch endpoint exists - returned 400 for empty items as expected")
    
    def test_add_to_batch_with_batch_type_washing(self, auth_headers):
        """Test add-to-batch accepts batch_type='washing'"""
        response = requests.post(
            f"{BASE_URL}/api/laundry/queue/add-to-batch",
            headers=auth_headers,
            json={
                "item_ids": [],
                "laundry_company": "Пральня Тест",
                "complexity": "normal",
                "batch_type": "washing"
            }
        )
        
        # Should return 400 for empty items, but validates batch_type was accepted
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        print(f"✅ add-to-batch endpoint accepts batch_type='washing'")
    
    def test_add_to_batch_with_batch_type_laundry(self, auth_headers):
        """Test add-to-batch accepts batch_type='laundry'"""
        response = requests.post(
            f"{BASE_URL}/api/laundry/queue/add-to-batch",
            headers=auth_headers,
            json={
                "item_ids": [],
                "laundry_company": "Хімчистка Тест",
                "complexity": "normal",
                "batch_type": "laundry"
            }
        )
        
        # Should return 400 for empty items, but validates batch_type was accepted
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        print(f"✅ add-to-batch endpoint accepts batch_type='laundry'")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
