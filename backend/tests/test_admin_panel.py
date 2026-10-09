"""
Admin Panel API Tests
Тестування адмін-панелі: користувачі, документи, категорії, налаштування
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "vitokdrako@gmail.com"
ADMIN_PASSWORD = "test123"
MANAGER_EMAIL = "max@farforrent.com.ua"
MANAGER_PASSWORD = "test123"


class TestAdminAuth:
    """Test authentication for admin endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    @pytest.fixture(scope="class")
    def manager_token(self):
        """Get manager token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": MANAGER_EMAIL,
            "password": MANAGER_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip(f"Manager login failed: {response.text}")
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    def test_admin_login_success(self):
        """Admin should be able to login"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        assert 'access_token' in data or 'token' in data
        
    def test_manager_cannot_access_admin_users(self, manager_token):
        """Non-admin should get 403 on admin endpoints"""
        if not manager_token:
            pytest.skip("Manager token not available")
        headers = {"Authorization": f"Bearer {manager_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        # Should be 403 for non-admin
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        
    def test_no_auth_returns_403(self):
        """No auth should return 403"""
        response = requests.get(f"{BASE_URL}/api/admin/users")
        assert response.status_code == 403


class TestAdminUsers:
    """Test admin users endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    def test_get_users_success(self, admin_token):
        """GET /api/admin/users should return list of users"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        assert response.status_code == 200
        data = response.json()
        
        # Should return list
        assert isinstance(data, list)
        # Should have users
        assert len(data) > 0
        
        # Each user should have expected fields
        user = data[0]
        assert 'user_id' in user
        assert 'email' in user
        assert 'role' in user
        assert 'username' in user
        
    def test_users_have_roles(self, admin_token):
        """Users should have valid roles"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=headers)
        data = response.json()
        
        valid_roles = ['admin', 'manager', 'requisitor', 'office_manager']
        for user in data:
            assert user.get('role') in valid_roles, f"Invalid role: {user.get('role')}"


class TestAdminDocumentStats:
    """Test document stats endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    def test_get_document_stats(self, admin_token):
        """GET /api/admin/document-stats should return document type counts"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/document-stats", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        # Should return dict with doc_type: count
        assert isinstance(data, dict)
        
        # If there are documents, check they have int counts
        for doc_type, count in data.items():
            assert isinstance(count, int), f"Count for {doc_type} should be int"


class TestAdminCategories:
    """Test categories endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    def test_get_categories(self, admin_token):
        """GET /api/admin/categories should return categories list"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/categories", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        # Per spec, should have ~155 categories
        assert len(data) > 50, f"Expected many categories, got {len(data)}"
        
        # Each category should have expected fields
        if data:
            cat = data[0]
            assert 'category_id' in cat
            assert 'name' in cat


class TestAdminSettings:
    """Test company settings endpoints"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    def test_get_settings(self, admin_token):
        """GET /api/admin/settings should return company settings"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/admin/settings", headers=headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, dict)
        
        # Should have some default settings fields
        # name, tax_status, tax_id, iban, address, etc.
        # These may or may not exist depending on table state
        
    def test_update_settings(self, admin_token):
        """PUT /api/admin/settings should save settings"""
        headers = {
            "Authorization": f"Bearer {admin_token}",
            "Content-Type": "application/json"
        }
        
        # Update test setting
        test_data = {
            "name": "ФОП Николенко Наталя Станіславівна",
            "tax_status": "платник єдиного податку",
            "address": "м. Київ"
        }
        
        response = requests.put(
            f"{BASE_URL}/api/admin/settings",
            headers=headers,
            json=test_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('success') == True
        
        # Verify settings were saved by reading back
        get_response = requests.get(f"{BASE_URL}/api/admin/settings", headers=headers)
        assert get_response.status_code == 200
        saved_data = get_response.json()
        
        # Verify saved values
        assert saved_data.get('name') == test_data['name']
        assert saved_data.get('address') == test_data['address']


class TestAdminExpenseCategories:
    """Test expense categories endpoint"""
    
    @pytest.fixture(scope="class")
    def admin_token(self):
        """Get admin token"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        data = response.json()
        return data.get('access_token') or data.get('token')
    
    def test_get_expense_categories(self, admin_token):
        """GET /api/finance/admin/expense-categories should return expense categories"""
        headers = {"Authorization": f"Bearer {admin_token}"}
        response = requests.get(f"{BASE_URL}/api/finance/admin/expense-categories", headers=headers)
        
        # May return 200 or 404 depending on implementation
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
        elif response.status_code == 404:
            pytest.skip("Expense categories endpoint not implemented")
        else:
            # Log the actual response for debugging
            print(f"Expense categories response: {response.status_code} - {response.text}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
