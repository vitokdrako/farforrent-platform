"""
Calendar API Tests - Unified Calendar Hub
Tests for /api/calendar/* endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCalendarEventTypes:
    """Tests for /api/calendar/event-types endpoint"""
    
    def test_get_event_types_success(self):
        """Test that event-types endpoint returns correct structure"""
        response = requests.get(f"{BASE_URL}/api/calendar/event-types")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "types" in data
        assert "groups" in data
        
        # Verify types contain expected event types
        types = data["types"]
        expected_types = ["issue", "return", "on_rent", "awaiting", "packing", 
                         "ready_issue", "cleaning", "laundry", "repair", 
                         "damage", "overdue", "payment_due", "deposit_return", "task"]
        
        for event_type in expected_types:
            assert event_type in types, f"Missing event type: {event_type}"
            assert "label" in types[event_type]
            assert "color" in types[event_type]
            assert "icon" in types[event_type]
            assert "group" in types[event_type]
        
        # Verify groups
        groups = data["groups"]
        expected_groups = ["orders", "operations", "maintenance", "issues", "finance", "tasks"]
        
        for group in expected_groups:
            assert group in groups, f"Missing group: {group}"
            assert "label" in groups[group]
            assert "icon" in groups[group]


class TestCalendarEvents:
    """Tests for /api/calendar/events endpoint"""
    
    def test_get_events_with_date_range(self):
        """Test getting events with date range"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={"date_from": "2025-01-01", "date_to": "2025-01-31"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "events" in data
        assert "total" in data
        assert "date_from" in data
        assert "date_to" in data
        assert "filters" in data
        
        assert data["date_from"] == "2025-01-01"
        assert data["date_to"] == "2025-01-31"
        assert isinstance(data["events"], list)
        assert isinstance(data["total"], int)
    
    def test_get_events_with_wider_date_range(self):
        """Test getting events with wider date range to get actual data"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={"date_from": "2024-01-01", "date_to": "2026-12-31"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify events have correct structure
        if data["total"] > 0:
            event = data["events"][0]
            assert "id" in event
            assert "type" in event
            assert "date" in event
            assert "title" in event
            assert "_meta" in event
    
    def test_get_events_with_group_filter(self):
        """Test filtering events by group"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={
                "date_from": "2024-01-01", 
                "date_to": "2026-12-31",
                "groups": "tasks"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filters are applied
        assert data["filters"]["groups"] is not None
        assert "tasks" in data["filters"]["groups"]
        
        # Verify all events belong to tasks group
        for event in data["events"]:
            if "_meta" in event:
                assert event["_meta"]["group"] == "tasks", f"Event {event['id']} has wrong group: {event['_meta']['group']}"
    
    def test_get_events_with_type_filter(self):
        """Test filtering events by type"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={
                "date_from": "2024-01-01", 
                "date_to": "2026-12-31",
                "types": "return,issue"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify filters are applied
        assert data["filters"]["types"] is not None
        
        # Verify all events are of correct type
        for event in data["events"]:
            assert event["type"] in ["return", "issue", "ready_issue"], f"Event {event['id']} has wrong type: {event['type']}"
    
    def test_get_events_with_search(self):
        """Test searching events"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={
                "date_from": "2024-01-01", 
                "date_to": "2026-12-31",
                "search": "OC-7222"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify search filter is applied
        assert data["filters"]["search"] == "OC-7222"
        
        # Verify search results contain the search term
        for event in data["events"]:
            title = event.get("title", "").lower()
            subtitle = event.get("subtitle", "").lower()
            order_number = event.get("order_number", "").lower()
            assert "oc-7222" in title or "oc-7222" in subtitle or "oc-7222" in order_number
    
    def test_get_events_missing_date_from(self):
        """Test that missing date_from returns error"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={"date_to": "2025-01-31"}
        )
        
        # Should return 422 for missing required parameter
        assert response.status_code == 422
    
    def test_get_events_missing_date_to(self):
        """Test that missing date_to returns error"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/events",
            params={"date_from": "2025-01-01"}
        )
        
        # Should return 422 for missing required parameter
        assert response.status_code == 422


class TestCalendarStats:
    """Tests for /api/calendar/stats endpoint"""
    
    def test_get_stats_for_date(self):
        """Test getting stats for a specific date"""
        response = requests.get(
            f"{BASE_URL}/api/calendar/stats",
            params={"date": "2026-01-14"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "date" in data
        assert "stats" in data
        assert "total" in data
        
        assert data["date"] == "2026-01-14"
        assert isinstance(data["stats"], dict)
        assert isinstance(data["total"], int)
    
    def test_get_stats_missing_date(self):
        """Test that missing date returns error"""
        response = requests.get(f"{BASE_URL}/api/calendar/stats")
        
        # Should return 422 for missing required parameter
        assert response.status_code == 422


class TestAuthentication:
    """Tests for authentication"""
    
    def test_login_success(self):
        """Test successful login"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "vitokdrako@gmail.com", "password": "test123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "access_token" in data
        assert "token_type" in data
        assert "user" in data
        assert data["token_type"] == "bearer"
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "invalid@example.com", "password": "wrongpassword"}
        )
        
        # Should return 401 for invalid credentials
        assert response.status_code in [401, 400]
