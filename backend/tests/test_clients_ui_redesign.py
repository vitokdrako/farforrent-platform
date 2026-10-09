"""
Test: Client UI Redesign - Backend API tests
Focus: PATCH /api/clients/{id} for updating CRM fields
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com')

# Test client ID 10 (Катерина Сєдая)
TEST_CLIENT_ID = 10

class TestClientPatchEndpoint:
    """Test PATCH /api/clients/{id} endpoint for updating client fields"""
    
    def test_patch_client_is_regular_field(self):
        """Test updating is_regular field"""
        # First get current state
        get_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        assert get_resp.status_code == 200, f"GET failed: {get_resp.text}"
        original = get_resp.json()
        
        # Update is_regular to True
        patch_resp = requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"is_regular": True}
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        # Verify update persisted
        verify_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        assert verify_resp.status_code == 200
        updated = verify_resp.json()
        assert updated["is_regular"] == True, "is_regular should be True after update"
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"is_regular": original.get("is_regular", False)}
        )
        print("✓ PATCH is_regular field works correctly")
    
    def test_patch_client_rating_field(self):
        """Test updating rating field (1-5 stars)"""
        get_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_resp.json()
        
        # Update rating to 4
        patch_resp = requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"rating": 4}
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        # Verify update persisted
        verify_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_resp.json()
        assert updated["rating"] == 4, f"Rating should be 4, got {updated['rating']}"
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"rating": original.get("rating", 0)}
        )
        print("✓ PATCH rating field works correctly")
    
    def test_patch_client_company_field(self):
        """Test updating company field"""
        get_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_resp.json()
        
        # Update company
        test_company = "TEST_UI_Redesign_Company"
        patch_resp = requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"company": test_company}
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        # Verify update persisted
        verify_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_resp.json()
        assert updated["company"] == test_company, f"Company should be '{test_company}'"
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"company": original.get("company")}
        )
        print("✓ PATCH company field works correctly")
    
    def test_patch_client_instagram_field(self):
        """Test updating instagram field"""
        get_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_resp.json()
        
        # Update instagram
        test_instagram = "@test_ui_redesign"
        patch_resp = requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"instagram": test_instagram}
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        # Verify update persisted
        verify_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_resp.json()
        assert updated["instagram"] == test_instagram, f"Instagram should be '{test_instagram}'"
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"instagram": original.get("instagram")}
        )
        print("✓ PATCH instagram field works correctly")
    
    def test_patch_client_internal_notes_field(self):
        """Test updating internal_notes field"""
        get_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_resp.json()
        
        # Update internal_notes
        test_notes = "TEST Internal Notes - UI Redesign Testing"
        patch_resp = requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"internal_notes": test_notes}
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        # Verify update persisted
        verify_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_resp.json()
        assert updated["internal_notes"] == test_notes, f"Internal notes should be '{test_notes}'"
        
        # Restore original value
        requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={"internal_notes": original.get("internal_notes")}
        )
        print("✓ PATCH internal_notes field works correctly")
    
    def test_patch_multiple_crm_fields_at_once(self):
        """Test updating multiple CRM fields in single request"""
        get_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        original = get_resp.json()
        
        # Update multiple fields
        update_data = {
            "is_regular": True,
            "rating": 5,
            "company": "Multi-Field Test Corp",
            "instagram": "@multi_field_test",
            "internal_notes": "Multi-field update test"
        }
        patch_resp = requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json=update_data
        )
        assert patch_resp.status_code == 200, f"PATCH failed: {patch_resp.text}"
        
        # Verify all fields updated
        verify_resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        updated = verify_resp.json()
        
        assert updated["is_regular"] == True, "is_regular not updated"
        assert updated["rating"] == 5, "rating not updated"
        assert updated["company"] == "Multi-Field Test Corp", "company not updated"
        assert updated["instagram"] == "@multi_field_test", "instagram not updated"
        assert updated["internal_notes"] == "Multi-field update test", "internal_notes not updated"
        
        # Restore original values
        requests.patch(
            f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}",
            json={
                "is_regular": original.get("is_regular", False),
                "rating": original.get("rating", 0),
                "company": original.get("company"),
                "instagram": original.get("instagram"),
                "internal_notes": original.get("internal_notes")
            }
        )
        print("✓ PATCH multiple CRM fields works correctly")


class TestClientListEndpoint:
    """Test GET /api/clients for list view"""
    
    def test_clients_list_returns_200(self):
        """Test that clients list endpoint returns 200"""
        resp = requests.get(f"{BASE_URL}/api/clients")
        assert resp.status_code == 200, f"GET /api/clients failed: {resp.text}"
        data = resp.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ GET /api/clients returns {len(data)} clients")
    
    def test_clients_list_has_table_view_fields(self):
        """Test that clients list has required fields for table view"""
        resp = requests.get(f"{BASE_URL}/api/clients")
        assert resp.status_code == 200
        data = resp.json()
        
        if len(data) > 0:
            client = data[0]
            # Table view requires: name, email, phone, orders_count, payers_count, is_regular, rating
            required_fields = ["full_name", "email", "phone", "orders_count", "payers_count", "is_regular", "rating"]
            for field in required_fields:
                assert field in client, f"Missing field '{field}' in client list response"
            print(f"✓ Client list has all required table view fields: {required_fields}")
        else:
            pytest.skip("No clients in list to verify fields")
    
    def test_clients_list_filter_by_regular(self):
        """Test that 'Постійні клієнти' filter concept works"""
        # Get all clients
        all_resp = requests.get(f"{BASE_URL}/api/clients")
        assert all_resp.status_code == 200
        all_clients = all_resp.json()
        
        # Filter regular clients manually (frontend filter)
        regular_clients = [c for c in all_clients if c.get("is_regular")]
        print(f"✓ Regular clients filter: {len(regular_clients)} out of {len(all_clients)}")


class TestClientDetailEndpoint:
    """Test GET /api/clients/{id} for drawer view"""
    
    def test_client_detail_has_drawer_fields(self):
        """Test that client detail has all fields for drawer view"""
        resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        
        # Drawer view requires: Contact info + Payers section + Orders section
        required_fields = [
            "id", "full_name", "email", "phone",
            "is_regular", "rating", "company", "instagram", "internal_notes",
            "total_revenue", "last_order_date",
            "payers", "recent_orders", "stats"
        ]
        for field in required_fields:
            assert field in data, f"Missing field '{field}' in client detail response"
        
        # Verify payers and orders are arrays
        assert isinstance(data["payers"], list), "payers should be a list"
        assert isinstance(data["recent_orders"], list), "recent_orders should be a list"
        
        print(f"✓ Client detail has all drawer view fields")
        print(f"  - Payers: {len(data['payers'])}")
        print(f"  - Orders: {len(data['recent_orders'])}")
    
    def test_client_detail_rating_is_integer(self):
        """Test that rating is an integer for star display"""
        resp = requests.get(f"{BASE_URL}/api/clients/{TEST_CLIENT_ID}")
        assert resp.status_code == 200
        data = resp.json()
        
        assert isinstance(data["rating"], int), f"Rating should be int, got {type(data['rating'])}"
        assert 0 <= data["rating"] <= 5, f"Rating should be 0-5, got {data['rating']}"
        print(f"✓ Rating is integer (0-5): {data['rating']}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
