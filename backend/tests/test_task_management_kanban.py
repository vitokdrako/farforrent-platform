"""
Task Management Kanban Tests - Iteration 17
Tests for enhanced task management in Personal Cabinet:
- GET /api/cabinet/focus - Focus of the Day widget data
- GET /api/cabinet/my-tasks?scope=my/all - Scope toggle functionality
- POST /api/tasks - Create task with assigned_to_id
- PUT /api/tasks/{id} - Update task status and assignee
- GET /api/tasks/staff - Staff list for assignee dropdown
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"

# Store created task ID for cleanup
created_task_ids = []


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


@pytest.fixture(scope="module")
def current_user_id(auth_headers):
    """Get current user ID"""
    response = requests.get(
        f"{BASE_URL}/api/cabinet/profile",
        headers=auth_headers
    )
    return response.json()["user_id"]


# =================== FOCUS ENDPOINT TESTS ===================

class TestCabinetFocus:
    """Tests for GET /api/cabinet/focus - Focus of the Day widget"""
    
    def test_focus_returns_structure(self, auth_headers):
        """GET /api/cabinet/focus returns correct structure with overdue, due_today, in_progress, week"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/focus",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "overdue" in data, "Focus should have 'overdue' array"
        assert "due_today" in data, "Focus should have 'due_today' array"
        assert "in_progress" in data, "Focus should have 'in_progress' array"
        assert "week" in data, "Focus should have 'week' calendar data"
        
        # Verify types
        assert isinstance(data["overdue"], list)
        assert isinstance(data["due_today"], list)
        assert isinstance(data["in_progress"], list)
        assert isinstance(data["week"], list)
        
    def test_focus_week_calendar_has_7_days(self, auth_headers):
        """Week calendar should return exactly 7 days starting from today"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/focus",
            headers=auth_headers
        )
        data = response.json()
        
        week = data["week"]
        assert len(week) == 7, "Week should have exactly 7 days"
        
        # Verify each day has required fields
        for day in week:
            assert "date" in day
            assert "day_name" in day
            assert "count" in day
            assert isinstance(day["count"], int)
            
    def test_focus_requires_auth(self):
        """GET /api/cabinet/focus requires authentication"""
        response = requests.get(f"{BASE_URL}/api/cabinet/focus")
        assert response.status_code == 401


# =================== MY-TASKS SCOPE TESTS ===================

class TestMyTasksScope:
    """Tests for GET /api/cabinet/my-tasks with scope parameter"""
    
    def test_scope_my_returns_only_assigned_tasks(self, auth_headers, current_user_id):
        """GET /api/cabinet/my-tasks?scope=my returns only tasks assigned to current user"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks?scope=my",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # All tasks should be assigned to current user
        for task in data:
            if task["assigned_to_id"]:
                assert task["assigned_to_id"] == current_user_id, \
                    f"Task {task['id']} should be assigned to user {current_user_id}, but got {task['assigned_to_id']}"
                    
    def test_scope_all_returns_all_tasks(self, auth_headers):
        """GET /api/cabinet/my-tasks?scope=all returns all tasks with assignee names"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks?scope=all",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        # Should return more tasks when scope=all (13 total in DB)
        assert len(data) >= 1, "Should have at least 1 task in database"
        
        # Verify assignee_name field exists
        if data:
            task = data[0]
            assert "assignee_name" in task, "Tasks should have assignee_name field"
            assert "assigned_to_id" in task, "Tasks should have assigned_to_id field"
            
    def test_scope_all_returns_more_than_my(self, auth_headers):
        """scope=all should return >= tasks than scope=my"""
        response_my = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks?scope=my",
            headers=auth_headers
        )
        response_all = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks?scope=all",
            headers=auth_headers
        )
        
        my_count = len(response_my.json())
        all_count = len(response_all.json())
        
        assert all_count >= my_count, \
            f"scope=all ({all_count}) should return >= tasks than scope=my ({my_count})"
            
    def test_default_scope_is_my(self, auth_headers, current_user_id):
        """Default scope (no param) should behave like scope=my"""
        response_default = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks",
            headers=auth_headers
        )
        response_my = requests.get(
            f"{BASE_URL}/api/cabinet/my-tasks?scope=my",
            headers=auth_headers
        )
        
        # Should return same tasks
        default_ids = set(t["id"] for t in response_default.json())
        my_ids = set(t["id"] for t in response_my.json())
        
        assert default_ids == my_ids, "Default scope should equal scope=my"


# =================== TASK CRUD TESTS ===================

class TestTaskCRUD:
    """Tests for POST /api/tasks and PUT /api/tasks/{id}"""
    
    def test_create_task_with_assigned_to_id(self, auth_headers, current_user_id):
        """POST /api/tasks creates task with assigned_to_id (user binding)"""
        today = datetime.now()
        due_date = (today + timedelta(days=1)).isoformat()
        
        task_data = {
            "title": "TEST_task_from_pytest_iteration17",
            "description": "Test task for kanban iteration 17",
            "task_type": "general",
            "priority": "medium",
            "assigned_to_id": current_user_id,  # Assign to current user
            "due_date": due_date
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers,
            json=task_data
        )
        assert response.status_code == 200, f"Create task failed: {response.text}"
        data = response.json()
        
        assert "id" in data
        assert "message" in data
        assert data["assigned_to_id"] == current_user_id
        
        # Store for cleanup and further tests
        created_task_ids.append(data["id"])
        pytest.test_task_id = data["id"]
        
    def test_create_task_with_different_assignee(self, auth_headers):
        """POST /api/tasks can assign task to another user"""
        task_data = {
            "title": "TEST_task_for_user4",
            "task_type": "washing",
            "priority": "high",
            "assigned_to_id": 4  # Assign to user 4 (Макс Менеджер)
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers,
            json=task_data
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["assigned_to_id"] == 4
        created_task_ids.append(data["id"])
        
    def test_get_created_task(self, auth_headers):
        """GET /api/tasks/{id} returns the created task"""
        task_id = getattr(pytest, 'test_task_id', None)
        if not task_id:
            pytest.skip("No test task created")
            
        response = requests.get(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["id"] == task_id
        assert data["title"] == "TEST_task_from_pytest_iteration17"
        assert data["status"] == "todo"  # Default status
        
    def test_update_task_status(self, auth_headers):
        """PUT /api/tasks/{id} can update task status"""
        task_id = getattr(pytest, 'test_task_id', None)
        if not task_id:
            pytest.skip("No test task to update")
            
        # Update to in_progress
        response = requests.put(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "in_progress"
        
    def test_update_task_status_to_done(self, auth_headers):
        """PUT /api/tasks/{id} status=done sets completed_at"""
        task_id = getattr(pytest, 'test_task_id', None)
        if not task_id:
            pytest.skip("No test task to update")
            
        response = requests.put(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=auth_headers,
            json={"status": "done"}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["status"] == "done"
        assert data["completed_at"] is not None, "completed_at should be set when status=done"
        
    def test_update_task_assignee(self, auth_headers):
        """PUT /api/tasks/{id} can change assignee"""
        task_id = getattr(pytest, 'test_task_id', None)
        if not task_id:
            pytest.skip("No test task to update")
            
        # Change assignee to user 4
        response = requests.put(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=auth_headers,
            json={"assigned_to_id": 4}
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["assigned_to_id"] == 4
        assert data["assignee_name"] is not None, "assignee_name should be populated"


# =================== STAFF ENDPOINT TESTS ===================

class TestTasksStaff:
    """Tests for GET /api/tasks/staff - Staff list for assignment"""
    
    def test_get_staff_returns_list(self, auth_headers):
        """GET /api/tasks/staff returns list of staff members"""
        response = requests.get(
            f"{BASE_URL}/api/tasks/staff",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0, "Should have at least one staff member"
        
    def test_staff_has_required_fields(self, auth_headers):
        """Staff members have id, user_id, full_name, role fields"""
        response = requests.get(
            f"{BASE_URL}/api/tasks/staff",
            headers=auth_headers
        )
        data = response.json()
        
        for staff in data:
            assert "id" in staff or "user_id" in staff
            assert "full_name" in staff
            assert "role" in staff


# =================== TASK CREATION FOR FOCUS WIDGET TEST ===================

class TestFocusWidgetWithTasks:
    """Test Focus widget shows tasks when they exist"""
    
    def test_create_task_due_today(self, auth_headers, current_user_id):
        """Create task due today to test focus widget"""
        today = datetime.now().replace(hour=23, minute=59).isoformat()
        
        task_data = {
            "title": "TEST_focus_today_task",
            "description": "Task due today for focus widget test",
            "task_type": "general",
            "priority": "high",
            "status": "todo",
            "assigned_to_id": current_user_id,
            "due_date": today
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers,
            json=task_data
        )
        assert response.status_code == 200
        data = response.json()
        created_task_ids.append(data["id"])
        pytest.focus_task_id = data["id"]
        
    def test_focus_shows_due_today_task(self, auth_headers):
        """Focus endpoint should show the task due today"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/focus",
            headers=auth_headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should have the task in due_today
        due_today_ids = [t["id"] for t in data["due_today"]]
        focus_task_id = getattr(pytest, 'focus_task_id', None)
        
        if focus_task_id:
            assert focus_task_id in due_today_ids, \
                f"Task {focus_task_id} should appear in due_today list"
                
    def test_create_in_progress_task(self, auth_headers, current_user_id):
        """Create in_progress task to test focus widget"""
        task_data = {
            "title": "TEST_in_progress_task",
            "task_type": "general",
            "priority": "medium",
            "status": "in_progress",
            "assigned_to_id": current_user_id
        }
        
        response = requests.post(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers,
            json=task_data
        )
        assert response.status_code == 200
        data = response.json()
        created_task_ids.append(data["id"])
        pytest.in_progress_task_id = data["id"]
        
        # Update status to in_progress
        requests.put(
            f"{BASE_URL}/api/tasks/{data['id']}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        
    def test_focus_shows_in_progress_task(self, auth_headers):
        """Focus endpoint should show in_progress tasks"""
        response = requests.get(
            f"{BASE_URL}/api/cabinet/focus",
            headers=auth_headers
        )
        data = response.json()
        
        in_progress_ids = [t["id"] for t in data["in_progress"]]
        in_progress_task_id = getattr(pytest, 'in_progress_task_id', None)
        
        if in_progress_task_id:
            assert in_progress_task_id in in_progress_ids, \
                f"Task {in_progress_task_id} should appear in in_progress list"


# =================== CLEANUP ===================

class TestCleanup:
    """Cleanup test data"""
    
    def test_delete_created_tasks(self, auth_headers):
        """Delete all TEST_ prefixed tasks created during tests"""
        for task_id in created_task_ids:
            response = requests.delete(
                f"{BASE_URL}/api/tasks/{task_id}",
                headers=auth_headers
            )
            # Don't assert - just try to delete
            
    def test_cleanup_any_remaining_test_tasks(self, auth_headers):
        """Clean up any TEST_ tasks that might remain"""
        response = requests.get(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers
        )
        if response.status_code == 200:
            tasks = response.json()
            for task in tasks:
                if task.get("title", "").startswith("TEST_"):
                    requests.delete(
                        f"{BASE_URL}/api/tasks/{task['id']}",
                        headers=auth_headers
                    )
