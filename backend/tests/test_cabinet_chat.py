"""
Personal Cabinet & Team Chat API Tests
Tests for /api/cabinet/* and /api/chat/* endpoints (MySQL-based)
Features: Profile, Stats, Tasks, Team, Channels, Messages, Threads, DMs
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
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    assert "access_token" in data
    return data["access_token"]


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Get auth headers for requests"""
    return {"Authorization": f"Bearer {auth_token}"}


class TestCabinetProfile:
    """Tests for /api/cabinet/profile endpoint"""
    
    def test_get_profile_returns_user_data(self, auth_headers):
        """GET /api/cabinet/profile returns current user profile"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/profile",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify profile fields
        assert "user_id" in data
        assert "username" in data
        assert "email" in data
        assert "full_name" in data
        assert "role" in data
        assert "is_active" in data
        
        # Verify correct user
        assert data["email"] == TEST_EMAIL
        assert data["role"] in ["admin", "manager", "requisitor"]
        
    def test_profile_requires_auth(self):
        """GET /api/cabinet/profile requires authentication"""
        response = requests.get(f"{BASE_URL}/api/cabinet/profile")
        assert response.status_code == 401


class TestCabinetStats:
    """Tests for /api/cabinet/stats endpoint"""
    
    def test_get_stats_returns_task_and_activity_stats(self, auth_headers):
        """GET /api/cabinet/stats returns task statistics and today's activity"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/stats",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify task stats structure
        assert "tasks" in data
        tasks = data["tasks"]
        assert "total" in tasks
        assert "todo" in tasks
        assert "in_progress" in tasks
        assert "done" in tasks
        assert "overdue" in tasks
        
        # Verify today stats structure
        assert "today" in data
        today = data["today"]
        assert "tasks_completed" in today
        assert "notes_written" in today
        assert "messages_sent" in today
        
        # Verify values are numeric
        assert isinstance(tasks["total"], int)
        assert isinstance(today["messages_sent"], int)


class TestCabinetMyTasks:
    """Tests for /api/cabinet/my-tasks endpoint"""
    
    def test_get_my_tasks_returns_assigned_tasks(self, auth_headers):
        """GET /api/cabinet/my-tasks returns tasks assigned to current user"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list)
        
        # If tasks exist, verify structure
        if len(data) > 0:
            task = data[0]
            assert "id" in task
            assert "title" in task
            assert "status" in task
            assert "priority" in task
            
    def test_filter_tasks_by_status(self, auth_headers):
        """GET /api/cabinet/my-tasks?status=todo filters by status"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks?status=todo",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # All tasks should have todo status
        for task in data:
            assert task["status"] == "todo"


class TestCabinetTeam:
    """Tests for /api/cabinet/team endpoint"""
    
    def test_get_team_returns_all_team_members(self, auth_headers):
        """GET /api/cabinet/team returns team members with stats"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/team",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one team member"
        
        # Verify team member structure
        member = data[0]
        assert "user_id" in member
        assert "name" in member
        assert "role" in member
        assert "active_tasks" in member
        assert "done_today" in member


class TestChatChannels:
    """Tests for /api/chat/channels endpoint"""
    
    def test_list_channels_returns_channels(self, auth_headers):
        """GET /api/chat/channels returns list of channels"""
        response = requests.get(
            f"{BASE_URL}/api/chat/channels",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one channel (general)"
        
        # Verify channel structure
        channel = data[0]
        assert "id" in channel
        assert "name" in channel
        assert "type" in channel
        assert "unread" in channel
        
        # Should have general channel
        general = [c for c in data if c["type"] == "general"]
        assert len(general) > 0, "Should have general channel"
        
    def test_create_topic_channel(self, auth_headers):
        """POST /api/chat/channels creates new topic channel"""
        response = requests.post(
            f"{BASE_URL}/api/chat/channels",
            headers=auth_headers,
            json={
                "name": "TEST_PytestChannel",
                "description": "Test channel from pytest",
                "type": "topic"
            }
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify channel created
        assert "id" in data
        assert data["name"] == "TEST_PytestChannel"
        assert data["type"] == "topic"
        
        # Store for cleanup
        pytest.test_channel_id = data["id"]
        
    def test_delete_channel(self, auth_headers):
        """DELETE /api/chat/channels/{id} deletes channel"""
        # Use channel created in previous test
        channel_id = getattr(pytest, 'test_channel_id', None)
        if not channel_id:
            pytest.skip("No test channel to delete")
            
        response = requests.delete(
            f"{BASE_URL}/api/chat/channels/{channel_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        
    def test_cannot_delete_general_channel(self, auth_headers):
        """DELETE /api/chat/channels/1 (general) should fail"""
        # First get the general channel id
        response = requests.get(
            f"{BASE_URL}/api/chat/channels",
            headers=auth_headers
        )
        channels = response.json()
        general = [c for c in channels if c["type"] == "general"]
        
        if general:
            general_id = general[0]["id"]
            response = requests.delete(
                f"{BASE_URL}/api/chat/channels/{general_id}",
                headers=auth_headers
            )
            assert response.status_code == 400  # Should fail


class TestChatMessages:
    """Tests for /api/chat/channels/{id}/messages endpoint"""
    
    def test_get_messages_from_channel(self, auth_headers):
        """GET /api/chat/channels/1/messages returns messages"""
        response = requests.get(
            f"{BASE_URL}/api/chat/channels/1/messages",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should be a list
        assert isinstance(data, list)
        
        # If messages exist, verify structure
        if len(data) > 0:
            msg = data[0]
            assert "id" in msg
            assert "message" in msg
            assert "user_id" in msg
            assert "user_name" in msg
            assert "channel_id" in msg
            
    def test_send_message(self, auth_headers):
        """POST /api/chat/channels/1/messages sends a message"""
        response = requests.post(
            f"{BASE_URL}/api/chat/channels/1/messages",
            headers=auth_headers,
            json={"message": "TEST_pytest_message"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["message"] == "TEST_pytest_message"
        assert data["channel_id"] == 1
        
        # Store for thread test
        pytest.test_message_id = data["id"]
        
    def test_send_empty_message_fails(self, auth_headers):
        """POST with empty message should fail"""
        response = requests.post(
            f"{BASE_URL}/api/chat/channels/1/messages",
            headers=auth_headers,
            json={"message": "   "}
        )
        assert response.status_code == 400


class TestChatThreads:
    """Tests for /api/chat/messages/{id}/thread endpoint"""
    
    def test_send_thread_reply(self, auth_headers):
        """POST message with reply_to creates thread reply"""
        # First, get a message to reply to
        response = requests.get(
            f"{BASE_URL}/api/chat/channels/1/messages",
            headers=auth_headers
        )
        messages = response.json()
        
        if len(messages) == 0:
            pytest.skip("No messages to reply to")
            
        parent_id = messages[0]["id"]
        
        response = requests.post(
            f"{BASE_URL}/api/chat/channels/1/messages",
            headers=auth_headers,
            json={"message": "TEST_thread_reply", "reply_to": parent_id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reply_to"] == parent_id
        
        # Store parent for get thread test
        pytest.test_parent_id = parent_id
        
    def test_get_thread(self, auth_headers):
        """GET /api/chat/messages/{id}/thread returns thread"""
        parent_id = getattr(pytest, 'test_parent_id', 1)
        
        response = requests.get(
            f"{BASE_URL}/api/chat/messages/{parent_id}/thread",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should be a list with parent + replies
        assert isinstance(data, list)
        assert len(data) > 0
        
        # First should be parent
        assert data[0]["is_parent"] == True
        
    def test_thread_not_found(self, auth_headers):
        """GET /api/chat/messages/99999/thread returns 404"""
        response = requests.get(
            f"{BASE_URL}/api/chat/messages/99999/thread",
            headers=auth_headers
        )
        assert response.status_code == 404


class TestChatDM:
    """Tests for /api/chat/dm/{user_id} endpoint"""
    
    def test_create_dm(self, auth_headers):
        """POST /api/chat/dm/{user_id} creates DM channel"""
        # Create DM with user 4 (another user)
        response = requests.post(
            f"{BASE_URL}/api/chat/dm/4",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["type"] == "dm"
        
        pytest.test_dm_id = data["id"]
        
    def test_get_existing_dm(self, auth_headers):
        """POST /api/chat/dm/{user_id} returns existing DM if exists"""
        # Same user should return same DM
        response = requests.post(
            f"{BASE_URL}/api/chat/dm/4",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should be same DM as before
        if hasattr(pytest, 'test_dm_id'):
            assert data["id"] == pytest.test_dm_id
            
    def test_dm_with_self_fails(self, auth_headers):
        """POST /api/chat/dm/{own_id} should fail"""
        # Get current user id from profile
        response = requests.get(
            f"{BASE_URL}/api/cabinet/profile",
            headers=auth_headers
        )
        user_id = response.json()["user_id"]
        
        response = requests.post(
            f"{BASE_URL}/api/chat/dm/{user_id}",
            headers=auth_headers
        )
        assert response.status_code == 400


class TestChatUnread:
    """Tests for /api/chat/unread endpoint"""
    
    def test_get_unread_count(self, auth_headers):
        """GET /api/chat/unread returns unread count"""
        response = requests.get(
            f"{BASE_URL}/api/chat/unread",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "unread" in data
        assert isinstance(data["unread"], int)


class TestChatTeam:
    """Tests for /api/chat/team endpoint"""
    
    def test_get_chat_team(self, auth_headers):
        """GET /api/chat/team returns team members for DM selection"""
        response = requests.get(
            f"{BASE_URL}/api/chat/team",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        member = data[0]
        assert "id" in member
        assert "name" in member
        assert "role" in member


class TestAuthRequired:
    """Tests that all endpoints require authentication"""
    
    def test_cabinet_profile_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/cabinet/profile")
        assert response.status_code == 401
        
    def test_cabinet_stats_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/cabinet/stats")
        assert response.status_code == 401
        
    def test_chat_channels_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/chat/channels")
        assert response.status_code == 401
        
    def test_chat_messages_requires_auth(self):
        response = requests.get(f"{BASE_URL}/api/chat/channels/1/messages")
        assert response.status_code == 401
