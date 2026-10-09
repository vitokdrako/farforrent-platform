"""
Test suite for Clients and Master Agreements API
Verifies the bug fix: MA is now linked to client_users, not payer_profiles
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com')

class TestClientsAPI:
    """Test /api/clients endpoints"""
    
    def test_get_clients_list(self):
        """GET /api/clients - should return list of clients"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"✅ GET /api/clients returned {len(data)} clients")
        
        # Verify client structure
        client = data[0]
        assert "id" in client
        assert "email" in client
        assert "full_name" in client
        print(f"✅ Client structure verified: id={client['id']}, email={client['email']}")
    
    def test_get_client_55_has_agreement(self):
        """GET /api/clients - client 55 should have has_agreement=true"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        data = response.json()
        client_55 = next((c for c in data if c['id'] == 55), None)
        
        assert client_55 is not None, "Client 55 not found"
        assert client_55.get('has_agreement') == True, f"Client 55 should have agreement, got: {client_55.get('has_agreement')}"
        assert client_55.get('agreement_number') == "MA-2026-007", f"Expected MA-2026-007, got: {client_55.get('agreement_number')}"
        assert client_55.get('agreement_status') == "draft", f"Expected draft, got: {client_55.get('agreement_status')}"
        print(f"✅ Client 55 has MA: {client_55.get('agreement_number')} (status: {client_55.get('agreement_status')})")
    
    def test_get_client_53_no_agreement(self):
        """GET /api/clients - client 53 should have has_agreement=false"""
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        data = response.json()
        client_53 = next((c for c in data if c['id'] == 53), None)
        
        assert client_53 is not None, "Client 53 not found"
        assert client_53.get('has_agreement') == False, f"Client 53 should NOT have agreement, got: {client_53.get('has_agreement')}"
        assert client_53.get('agreement_number') is None, f"Expected None, got: {client_53.get('agreement_number')}"
        print(f"✅ Client 53 has no MA (has_agreement={client_53.get('has_agreement')})")
    
    def test_get_client_detail(self):
        """GET /api/clients/{id} - should return client details"""
        response = requests.get(f"{BASE_URL}/api/clients/55")
        assert response.status_code == 200
        
        data = response.json()
        assert data['id'] == 55
        assert 'email' in data
        assert 'payers' in data
        assert 'recent_orders' in data
        print(f"✅ GET /api/clients/55 returned client: {data['email']}")
    
    def test_get_client_payers(self):
        """GET /api/clients/{id}/payers - should return payers list"""
        response = requests.get(f"{BASE_URL}/api/clients/55/payers")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        print(f"✅ GET /api/clients/55/payers returned {len(data)} payers")


class TestMasterAgreementsAPI:
    """Test /api/agreements endpoints"""
    
    def test_get_client_agreement_exists(self):
        """GET /api/agreements/client/{id} - client 55 should have MA"""
        response = requests.get(f"{BASE_URL}/api/agreements/client/55")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('exists') == True, f"Expected exists=True, got: {data}"
        assert data.get('contract_number') == "MA-2026-007"
        assert data.get('status') == "draft"
        print(f"✅ Client 55 MA: {data.get('contract_number')} (status: {data.get('status')})")
    
    def test_get_client_agreement_not_exists(self):
        """GET /api/agreements/client/{id} - client 53 should NOT have MA"""
        response = requests.get(f"{BASE_URL}/api/agreements/client/53")
        assert response.status_code == 200
        
        data = response.json()
        assert data.get('exists') == False, f"Expected exists=False, got: {data}"
        print(f"✅ Client 53 has no MA (exists={data.get('exists')})")
    
    def test_get_agreements_list(self):
        """GET /api/agreements - should return list of agreements"""
        response = requests.get(f"{BASE_URL}/api/agreements")
        assert response.status_code == 200
        
        data = response.json()
        assert 'agreements' in data
        assert isinstance(data['agreements'], list)
        print(f"✅ GET /api/agreements returned {len(data['agreements'])} agreements")
    
    def test_get_agreement_detail(self):
        """GET /api/agreements/{id} - should return agreement details"""
        # First get the agreement ID for client 55
        response = requests.get(f"{BASE_URL}/api/agreements/client/55")
        assert response.status_code == 200
        ma_data = response.json()
        
        if ma_data.get('exists'):
            ma_id = ma_data.get('id')
            response = requests.get(f"{BASE_URL}/api/agreements/{ma_id}")
            assert response.status_code == 200
            
            data = response.json()
            assert data['id'] == ma_id
            assert 'contract_number' in data
            assert 'status' in data
            print(f"✅ GET /api/agreements/{ma_id} returned: {data.get('contract_number')}")
        else:
            pytest.skip("No MA found for client 55")


class TestBugFixVerification:
    """Verify the bug fix: MA is linked to client, not payer"""
    
    def test_ma_linked_to_client_not_payer(self):
        """
        Bug fix verification:
        - MA should be fetched via /api/agreements/client/{client_id}
        - NOT via /api/agreements/active/{payer_id}
        """
        # Get client 55's MA via client endpoint
        response = requests.get(f"{BASE_URL}/api/agreements/client/55")
        assert response.status_code == 200
        client_ma = response.json()
        
        assert client_ma.get('exists') == True
        assert client_ma.get('contract_number') == "MA-2026-007"
        print(f"✅ MA correctly linked to client 55: {client_ma.get('contract_number')}")
    
    def test_client_list_includes_agreement_info(self):
        """
        Verify client list includes agreement info at client level
        """
        response = requests.get(f"{BASE_URL}/api/clients")
        assert response.status_code == 200
        
        clients = response.json()
        
        # Find clients with agreements
        clients_with_ma = [c for c in clients if c.get('has_agreement')]
        clients_without_ma = [c for c in clients if not c.get('has_agreement')]
        
        print(f"✅ Clients with MA: {len(clients_with_ma)}")
        print(f"✅ Clients without MA: {len(clients_without_ma)}")
        
        # Verify structure
        if clients_with_ma:
            client = clients_with_ma[0]
            assert 'agreement_number' in client
            assert 'agreement_status' in client
            print(f"✅ Client {client['id']} has MA: {client['agreement_number']} ({client['agreement_status']})")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
