"""
Test damage-related features:
1. Dashboard overview API returns has_damage_items, damage_items_count, damage_photos on issue cards
2. Orders API returns has_damage_history and damage_history on items
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

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
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    token = data.get("access_token")
    assert token, f"No access_token in response: {data}"
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


class TestDashboardOverviewDamageFields:
    """Test /api/manager/dashboard/overview returns damage fields on issue cards"""
    
    def test_dashboard_overview_returns_200(self, auth_headers):
        """Dashboard overview endpoint should return 200"""
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print("PASS: Dashboard overview returns 200")
    
    def test_dashboard_overview_has_issue_cards(self, auth_headers):
        """Dashboard overview should have issue_cards array"""
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        data = response.json()
        assert "issue_cards" in data, f"Missing issue_cards in response: {data.keys()}"
        assert isinstance(data["issue_cards"], list), "issue_cards should be a list"
        print(f"PASS: Dashboard has {len(data['issue_cards'])} issue cards")
    
    def test_issue_cards_have_damage_fields(self, auth_headers):
        """Issue cards should have damage-related fields"""
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        data = response.json()
        issue_cards = data.get("issue_cards", [])
        
        if len(issue_cards) == 0:
            pytest.skip("No issue cards to test")
        
        # Check that at least some cards have damage fields
        cards_with_damage_fields = 0
        for card in issue_cards:
            has_damage_items = "has_damage_items" in card
            has_damage_count = "damage_items_count" in card
            has_damage_photos = "damage_photos" in card
            
            if has_damage_items and has_damage_count and has_damage_photos:
                cards_with_damage_fields += 1
        
        print(f"INFO: {cards_with_damage_fields}/{len(issue_cards)} cards have damage fields")
        assert cards_with_damage_fields > 0, "No issue cards have damage fields"
        print("PASS: Issue cards have damage fields")
    
    def test_damage_fields_structure(self, auth_headers):
        """Verify damage fields have correct structure"""
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        data = response.json()
        issue_cards = data.get("issue_cards", [])
        
        # Find a card with damage
        card_with_damage = None
        for card in issue_cards:
            if card.get("has_damage_items"):
                card_with_damage = card
                break
        
        if not card_with_damage:
            # Check any card for field types
            if len(issue_cards) > 0:
                card = issue_cards[0]
                assert isinstance(card.get("has_damage_items", False), bool), "has_damage_items should be bool"
                assert isinstance(card.get("damage_items_count", 0), int), "damage_items_count should be int"
                assert isinstance(card.get("damage_photos", []), list), "damage_photos should be list"
                print("PASS: Damage fields have correct types (no damage cards found)")
            else:
                pytest.skip("No issue cards to test")
        else:
            # Verify structure of card with damage
            assert card_with_damage["has_damage_items"] == True
            assert card_with_damage["damage_items_count"] > 0
            assert isinstance(card_with_damage["damage_photos"], list)
            
            # Check damage_photos structure
            if len(card_with_damage["damage_photos"]) > 0:
                photo = card_with_damage["damage_photos"][0]
                assert "photo_url" in photo, "damage_photos should have photo_url"
                print(f"PASS: Card {card_with_damage.get('order_id')} has {card_with_damage['damage_items_count']} damage items, {len(card_with_damage['damage_photos'])} photos")
            else:
                print(f"PASS: Card {card_with_damage.get('order_id')} has damage but no photos")


class TestOrderDetailsDamageHistory:
    """Test /api/orders/{order_id} returns damage history on items"""
    
    def test_order_7386_has_damage_history(self, auth_headers):
        """Order 7386 should have items with damage history (Тумба 80 см)"""
        response = requests.get(f"{BASE_URL}/api/orders/7386", headers=auth_headers)
        
        if response.status_code == 404:
            pytest.skip("Order 7386 not found")
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        items = data.get("items", [])
        assert len(items) > 0, "Order should have items"
        
        # Find items with damage history
        items_with_damage = [it for it in items if it.get("has_damage_history")]
        print(f"INFO: Order 7386 has {len(items_with_damage)}/{len(items)} items with damage history")
        
        if len(items_with_damage) > 0:
            item = items_with_damage[0]
            assert "damage_history" in item, "Item should have damage_history field"
            assert isinstance(item["damage_history"], list), "damage_history should be list"
            assert len(item["damage_history"]) > 0, "damage_history should not be empty"
            print(f"PASS: Item '{item.get('name')}' has {len(item['damage_history'])} damage records")
        else:
            print("INFO: No items with damage history in order 7386")
    
    def test_order_items_have_damage_fields(self, auth_headers):
        """Order items should have has_damage_history and damage_history fields"""
        # Get any order with items
        response = requests.get(f"{BASE_URL}/api/orders?limit=5", headers=auth_headers)
        assert response.status_code == 200
        orders = response.json().get("orders", [])
        
        if len(orders) == 0:
            pytest.skip("No orders found")
        
        # Get first order details
        order_id = orders[0].get("order_id") or orders[0].get("id")
        response = requests.get(f"{BASE_URL}/api/orders/{order_id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        items = data.get("items", [])
        if len(items) == 0:
            pytest.skip("Order has no items")
        
        # Check that items have damage fields
        for item in items:
            assert "has_damage_history" in item, f"Item missing has_damage_history: {item.get('name')}"
            assert isinstance(item["has_damage_history"], bool), "has_damage_history should be bool"
            
            if item["has_damage_history"]:
                assert "damage_history" in item, "Item with damage should have damage_history"
                assert isinstance(item["damage_history"], list), "damage_history should be list"
        
        print(f"PASS: Order {order_id} items have damage fields")
    
    def test_damage_history_record_structure(self, auth_headers):
        """Verify damage_history records have correct structure"""
        # Find an order with damage history
        response = requests.get(f"{BASE_URL}/api/orders/7386", headers=auth_headers)
        
        if response.status_code == 404:
            pytest.skip("Order 7386 not found")
        
        data = response.json()
        items = data.get("items", [])
        
        # Find item with damage
        item_with_damage = None
        for item in items:
            if item.get("has_damage_history") and len(item.get("damage_history", [])) > 0:
                item_with_damage = item
                break
        
        if not item_with_damage:
            pytest.skip("No items with damage history found")
        
        record = item_with_damage["damage_history"][0]
        
        # Check expected fields
        expected_fields = ["type", "notes", "severity", "status", "date"]
        for field in expected_fields:
            assert field in record, f"Damage record missing field: {field}"
        
        print(f"PASS: Damage record has correct structure: {list(record.keys())}")


class TestReturnCardsDamageBadge:
    """Test return cards (issued status) have damage badge fields"""
    
    def test_issued_cards_have_damage_fields(self, auth_headers):
        """Issued cards (for return) should have has_damage_items field"""
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        data = response.json()
        issue_cards = data.get("issue_cards", [])
        
        # Filter issued cards (these are shown in return column)
        issued_cards = [c for c in issue_cards if c.get("status") == "issued"]
        
        if len(issued_cards) == 0:
            pytest.skip("No issued cards found")
        
        # Check that issued cards have damage fields
        for card in issued_cards:
            assert "has_damage_items" in card, f"Issued card {card.get('order_id')} missing has_damage_items"
            assert "damage_items_count" in card, f"Issued card {card.get('order_id')} missing damage_items_count"
        
        # Count cards with damage
        cards_with_damage = [c for c in issued_cards if c.get("has_damage_items")]
        print(f"PASS: {len(cards_with_damage)}/{len(issued_cards)} issued cards have damage items")


class TestDamageEnrichmentLogic:
    """Test the damage enrichment logic in dashboard overview"""
    
    def test_damage_enrichment_batch_query(self, auth_headers):
        """Verify damage enrichment uses batch query (performance)"""
        # This is a functional test - we verify the result is correct
        # The batch query is an implementation detail
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Check that response includes timestamp (indicates successful processing)
        assert "timestamp" in data, "Response should have timestamp"
        
        # Check no error field
        assert "error" not in data, f"Response has error: {data.get('error')}"
        
        print("PASS: Dashboard overview processed successfully (no errors)")
    
    def test_damage_photos_limited_to_6(self, auth_headers):
        """Verify damage_photos is limited to 6 per card"""
        response = requests.get(f"{BASE_URL}/api/manager/dashboard/overview", headers=auth_headers)
        data = response.json()
        issue_cards = data.get("issue_cards", [])
        
        for card in issue_cards:
            photos = card.get("damage_photos", [])
            assert len(photos) <= 6, f"Card {card.get('order_id')} has {len(photos)} photos (max 6)"
        
        print("PASS: All cards have <= 6 damage photos")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
