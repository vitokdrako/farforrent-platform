"""
Test Master Agreements API - Рамкові договори
Tests for MA CRUD operations, status transitions, and payer integration
"""
import pytest
import requests
import os
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    return response.json().get("access_token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestMasterAgreementsAPI:
    """Test Master Agreements CRUD operations"""
    
    def test_list_agreements(self, auth_headers):
        """Test GET /api/agreements - list all agreements"""
        response = requests.get(f"{BASE_URL}/api/agreements", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "agreements" in data
        assert isinstance(data["agreements"], list)
        
        # Check agreement structure if any exist
        if len(data["agreements"]) > 0:
            agreement = data["agreements"][0]
            assert "id" in agreement
            assert "contract_number" in agreement
            assert "status" in agreement
            assert "payer_profile_id" in agreement
            print(f"Found {len(data['agreements'])} agreements")
    
    def test_get_active_agreement_for_payer(self, auth_headers):
        """Test GET /api/agreements/active/{payer_id} - get active agreement for payer"""
        # Test with payer_id 3 (known to have agreement from previous tests)
        response = requests.get(f"{BASE_URL}/api/agreements/active/3", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "exists" in data
        
        if data["exists"]:
            assert "id" in data
            assert "contract_number" in data
            assert "status" in data
            assert data["status"] in ["draft", "sent", "signed"]
            print(f"Active agreement for payer 3: {data['contract_number']} ({data['status']})")
        else:
            print("No active agreement for payer 3")
    
    def test_get_active_agreement_nonexistent_payer(self, auth_headers):
        """Test GET /api/agreements/active/{payer_id} - nonexistent payer returns exists=false"""
        response = requests.get(f"{BASE_URL}/api/agreements/active/99999", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert data["exists"] == False
        print("Correctly returns exists=false for nonexistent payer")


class TestMasterAgreementCreateSignFlow:
    """Test MA creation and signing workflow"""
    
    @pytest.fixture(scope="class")
    def test_payer(self, auth_headers):
        """Create a test payer for MA testing"""
        payer_data = {
            "type": "fop",
            "display_name": f"TEST_MA_Payer_{datetime.now().strftime('%H%M%S')}",
            "tax_mode": "simplified",
            "legal_name": "ФОП Тестовий",
            "edrpou": "12345678"
        }
        response = requests.post(
            f"{BASE_URL}/api/payer-profiles",
            headers=auth_headers,
            json=payer_data
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        print(f"Created test payer: {data['id']}")
        return data
    
    def test_create_master_agreement(self, auth_headers, test_payer):
        """Test POST /api/agreements/create - create new MA"""
        payer_id = test_payer["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/agreements/create",
            headers=auth_headers,
            json={"payer_profile_id": payer_id}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "agreement_id" in data
        assert "contract_number" in data
        assert data["contract_number"].startswith("MA-")
        assert "valid_from" in data
        assert "valid_until" in data
        
        print(f"Created MA: {data['contract_number']} (ID: {data['agreement_id']})")
        
        # Store for next tests
        self.__class__.created_ma_id = data["agreement_id"]
        self.__class__.created_contract_number = data["contract_number"]
        self.__class__.test_payer_id = payer_id
    
    def test_verify_draft_status(self, auth_headers):
        """Verify newly created MA has draft status"""
        payer_id = self.__class__.test_payer_id
        
        response = requests.get(
            f"{BASE_URL}/api/agreements/active/{payer_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["exists"] == True
        assert data["status"] == "draft"
        assert data["signed_at"] is None
        print(f"Verified MA is in draft status")
    
    def test_sign_master_agreement(self, auth_headers):
        """Test POST /api/agreements/{id}/sign - sign MA"""
        ma_id = self.__class__.created_ma_id
        
        response = requests.post(
            f"{BASE_URL}/api/agreements/{ma_id}/sign",
            headers=auth_headers,
            json={"signed_by": "Test User"}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "message" in data
        assert self.__class__.created_contract_number in data["message"]
        print(f"Signed MA: {data['message']}")
    
    def test_verify_signed_status(self, auth_headers):
        """Verify MA status changed to signed"""
        payer_id = self.__class__.test_payer_id
        
        response = requests.get(
            f"{BASE_URL}/api/agreements/active/{payer_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["exists"] == True
        assert data["status"] == "signed"
        assert data["signed_at"] is not None
        print(f"Verified MA is now signed (signed_at: {data['signed_at']})")
    
    def test_cannot_create_duplicate_active_agreement(self, auth_headers):
        """Test that creating another MA for same payer fails"""
        payer_id = self.__class__.test_payer_id
        
        response = requests.post(
            f"{BASE_URL}/api/agreements/create",
            headers=auth_headers,
            json={"payer_profile_id": payer_id}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower() or "active agreement" in data["detail"].lower()
        print(f"Correctly rejected duplicate MA: {data['detail']}")
    
    def test_cannot_sign_already_signed_agreement(self, auth_headers):
        """Test that signing already signed MA fails"""
        ma_id = self.__class__.created_ma_id
        
        response = requests.post(
            f"{BASE_URL}/api/agreements/{ma_id}/sign",
            headers=auth_headers,
            json={"signed_by": "Another User"}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        print(f"Correctly rejected re-signing: {data['detail']}")


class TestMasterAgreementValidation:
    """Test MA validation and error handling"""
    
    def test_create_agreement_invalid_payer(self, auth_headers):
        """Test creating MA with invalid payer ID"""
        response = requests.post(
            f"{BASE_URL}/api/agreements/create",
            headers=auth_headers,
            json={"payer_profile_id": 99999}
        )
        assert response.status_code == 400
        
        data = response.json()
        assert "detail" in data
        print(f"Correctly rejected invalid payer: {data['detail']}")
    
    def test_sign_nonexistent_agreement(self, auth_headers):
        """Test signing nonexistent MA"""
        response = requests.post(
            f"{BASE_URL}/api/agreements/99999/sign",
            headers=auth_headers,
            json={"signed_by": "Test User"}
        )
        assert response.status_code == 404
        
        data = response.json()
        assert "detail" in data
        print(f"Correctly returned 404 for nonexistent MA")
    
    def test_get_single_agreement(self, auth_headers):
        """Test GET /api/agreements/{id} - get single agreement details"""
        # First get list to find an existing agreement
        list_response = requests.get(f"{BASE_URL}/api/agreements", headers=auth_headers)
        assert list_response.status_code == 200
        
        agreements = list_response.json()["agreements"]
        if len(agreements) == 0:
            pytest.skip("No agreements to test")
        
        agreement_id = agreements[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/agreements/{agreement_id}", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "id" in data
        assert "contract_number" in data
        assert "payer" in data
        assert "annex_count" in data
        print(f"Got agreement details: {data['contract_number']}")


class TestClientsWithPayersAPI:
    """Test Clients API with payer integration"""
    
    def test_list_clients(self, auth_headers):
        """Test GET /api/clients - list clients"""
        response = requests.get(f"{BASE_URL}/api/clients", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        
        if len(data) > 0:
            client = data[0]
            assert "id" in client
            assert "email" in client
            # payers_count should be present
            assert "payers_count" in client
            print(f"Found {len(data)} clients")
    
    def test_get_client_payers(self, auth_headers):
        """Test GET /api/clients/{id}/payers - get payers for client"""
        # First get a client
        clients_response = requests.get(f"{BASE_URL}/api/clients?limit=5", headers=auth_headers)
        assert clients_response.status_code == 200
        
        clients = clients_response.json()
        if len(clients) == 0:
            pytest.skip("No clients to test")
        
        client_id = clients[0]["id"]
        
        response = requests.get(f"{BASE_URL}/api/clients/{client_id}/payers", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"Client {client_id} has {len(data)} payers")


class TestPayerProfilesAPI:
    """Test Payer Profiles API"""
    
    def test_list_payer_profiles(self, auth_headers):
        """Test GET /api/payer-profiles - list all payer profiles"""
        response = requests.get(f"{BASE_URL}/api/payer-profiles", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # API returns {"profiles": [...], "total": N}
        assert "profiles" in data
        assert isinstance(data["profiles"], list)
        print(f"Found {len(data['profiles'])} payer profiles")
    
    def test_create_payer_profile(self, auth_headers):
        """Test POST /api/payer-profiles - create new payer"""
        payer_data = {
            "type": "individual",
            "display_name": f"TEST_Individual_{datetime.now().strftime('%H%M%S')}",
            "tax_mode": "none"
        }
        
        response = requests.post(
            f"{BASE_URL}/api/payer-profiles",
            headers=auth_headers,
            json=payer_data
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] == True
        assert "id" in data
        print(f"Created payer profile: {data['id']}")


# Cleanup fixture
@pytest.fixture(scope="module", autouse=True)
def cleanup_test_data(auth_headers):
    """Cleanup test data after all tests"""
    yield
    # Note: In production, we would delete TEST_ prefixed data here
    # For now, we leave the test data as it doesn't affect functionality
    print("\nTest cleanup: TEST_ prefixed data created during tests")
