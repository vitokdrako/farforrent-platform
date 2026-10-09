"""
Test chat new features: Task-Chat integration, Close/Reopen threads, Photo upload
"""
import pytest
import requests
import os
import io
from PIL import Image

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"
TEST_USER_ID = 1


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    assert response.status_code == 200, f"Login failed: {response.text}"
    data = response.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    """Auth headers for requests"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


@pytest.fixture(scope="module")
def general_channel_id(auth_headers):
    """Get the General channel (Загальний) ID - channel #1"""
    response = requests.get(f"{BASE_URL}/api/chat/channels", headers=auth_headers)
    assert response.status_code == 200
    channels = response.json()
    general = next((c for c in channels if c['type'] == 'general'), None)
    assert general is not None, "General channel not found"
    return general['id']


# =============================================
# TASK-CHAT INTEGRATION TESTS
# =============================================

class TestTaskChatIntegration:
    """Test task creation auto-posts notification in General channel"""
    
    def test_create_task_posts_notification(self, auth_headers, general_channel_id):
        """POST /api/tasks creates task AND auto-posts notification in channel #1"""
        # Get current messages before creating task
        before_resp = requests.get(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers
        )
        assert before_resp.status_code == 200
        before_msgs = before_resp.json()
        before_count = len(before_msgs)
        
        # Create a task
        task_data = {
            "title": "TEST_TaskChatIntegration_Task",
            "description": "Testing task-chat notification",
            "task_type": "general",
            "priority": "high",
            "assigned_to_id": TEST_USER_ID
        }
        task_resp = requests.post(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers,
            json=task_data
        )
        assert task_resp.status_code == 200, f"Task creation failed: {task_resp.text}"
        task_result = task_resp.json()
        task_id = task_result.get("id")
        assert task_id, "Task ID not returned"
        
        # Get messages after - should have a new task notification message
        after_resp = requests.get(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers
        )
        assert after_resp.status_code == 200
        after_msgs = after_resp.json()
        
        # Find the task notification message
        task_msgs = [m for m in after_msgs if m.get('task_id') == task_id]
        assert len(task_msgs) > 0, f"Task notification message not found in channel. Task ID: {task_id}"
        
        task_msg = task_msgs[0]
        assert "Нова задача" in task_msg['message'], "Task notification should contain 'Нова задача'"
        assert "TEST_TaskChatIntegration_Task" in task_msg['message'], "Task title should be in message"
        
        # Cleanup - delete the task
        requests.delete(f"{BASE_URL}/api/tasks/{task_id}", headers=auth_headers)
        
        return task_id
    
    def test_task_status_change_creates_thread_reply(self, auth_headers, general_channel_id):
        """PUT /api/tasks/{id} status change creates thread reply to the task notification"""
        # Create a task first
        task_data = {
            "title": "TEST_StatusChange_Task",
            "description": "Testing status change notification",
            "task_type": "general",
            "priority": "medium"
        }
        task_resp = requests.post(
            f"{BASE_URL}/api/tasks",
            headers=auth_headers,
            json=task_data
        )
        assert task_resp.status_code == 200
        task_id = task_resp.json().get("id")
        
        # Get the task notification message
        msgs_resp = requests.get(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers
        )
        assert msgs_resp.status_code == 200
        msgs = msgs_resp.json()
        task_msg = next((m for m in msgs if m.get('task_id') == task_id), None)
        assert task_msg, "Task notification message not found"
        message_id = task_msg['id']
        
        # Change task status
        status_resp = requests.put(
            f"{BASE_URL}/api/tasks/{task_id}",
            headers=auth_headers,
            json={"status": "in_progress"}
        )
        assert status_resp.status_code == 200
        
        # Check thread for status change reply
        thread_resp = requests.get(
            f"{BASE_URL}/api/chat/messages/{message_id}/thread",
            headers=auth_headers
        )
        assert thread_resp.status_code == 200
        thread_msgs = thread_resp.json()
        
        # Should have at least 2 messages - original + status reply
        assert len(thread_msgs) >= 2, f"Expected at least 2 messages in thread, got {len(thread_msgs)}"
        
        # Check if status change message exists
        status_msg = next((m for m in thread_msgs if "Статус змінено" in m.get('message', '')), None)
        assert status_msg, "Status change message not found in thread"
        
        # Cleanup
        requests.delete(f"{BASE_URL}/api/tasks/{task_id}", headers=auth_headers)


# =============================================
# CLOSE/REOPEN THREAD TESTS
# =============================================

class TestCloseReopenThread:
    """Test thread close/reopen functionality"""
    
    def test_close_thread(self, auth_headers, general_channel_id):
        """PUT /api/chat/messages/{id}/close - closes a thread"""
        # Create a message to close
        msg_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers,
            json={"message": "TEST_CloseThread_Message"}
        )
        assert msg_resp.status_code == 200
        msg_id = msg_resp.json().get("id")
        
        # Close the thread
        close_resp = requests.put(
            f"{BASE_URL}/api/chat/messages/{msg_id}/close",
            headers=auth_headers
        )
        assert close_resp.status_code == 200
        close_data = close_resp.json()
        assert close_data.get("is_closed") == True, "Thread should be closed"
        
        # Verify via messages endpoint
        msgs_resp = requests.get(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers
        )
        assert msgs_resp.status_code == 200
        msgs = msgs_resp.json()
        closed_msg = next((m for m in msgs if m['id'] == msg_id), None)
        assert closed_msg, "Closed message not found"
        assert closed_msg.get('is_closed') == True, "Message should show is_closed=True"
        
        return msg_id
    
    def test_reopen_thread(self, auth_headers, general_channel_id):
        """PUT /api/chat/messages/{id}/reopen - reopens a closed thread"""
        # Create and close a message
        msg_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers,
            json={"message": "TEST_ReopenThread_Message"}
        )
        assert msg_resp.status_code == 200
        msg_id = msg_resp.json().get("id")
        
        # Close it first
        requests.put(f"{BASE_URL}/api/chat/messages/{msg_id}/close", headers=auth_headers)
        
        # Reopen
        reopen_resp = requests.put(
            f"{BASE_URL}/api/chat/messages/{msg_id}/reopen",
            headers=auth_headers
        )
        assert reopen_resp.status_code == 200
        reopen_data = reopen_resp.json()
        assert reopen_data.get("is_closed") == False, "Thread should be reopened"
    
    def test_post_to_closed_thread_returns_400(self, auth_headers, general_channel_id):
        """POST to closed thread returns 400 error"""
        # Create and close a message
        msg_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers,
            json={"message": "TEST_ClosedThreadBlock_Message"}
        )
        assert msg_resp.status_code == 200
        msg_id = msg_resp.json().get("id")
        
        # Close it
        requests.put(f"{BASE_URL}/api/chat/messages/{msg_id}/close", headers=auth_headers)
        
        # Try to reply to closed thread
        reply_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers,
            json={"message": "This should fail", "reply_to": msg_id}
        )
        assert reply_resp.status_code == 400, f"Expected 400 for reply to closed thread, got {reply_resp.status_code}"
    
    def test_thread_endpoint_returns_is_closed(self, auth_headers, general_channel_id):
        """GET /api/chat/messages/{id}/thread - returns is_closed field"""
        # Create a message
        msg_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers,
            json={"message": "TEST_ThreadIsClosed_Message"}
        )
        assert msg_resp.status_code == 200
        msg_id = msg_resp.json().get("id")
        
        # Get thread
        thread_resp = requests.get(
            f"{BASE_URL}/api/chat/messages/{msg_id}/thread",
            headers=auth_headers
        )
        assert thread_resp.status_code == 200
        thread_msgs = thread_resp.json()
        
        # Check is_closed field exists
        for msg in thread_msgs:
            assert 'is_closed' in msg, "Thread messages should have is_closed field"


# =============================================
# PHOTO UPLOAD TESTS
# =============================================

class TestPhotoUpload:
    """Test photo upload functionality"""
    
    def test_upload_image_creates_message(self, auth_token, general_channel_id):
        """POST /api/chat/upload - uploads image and creates message with attachment_url"""
        # Create a test image in memory
        img = Image.new('RGB', (100, 100), color='blue')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        # Upload via multipart form
        files = {'file': ('test_image.jpg', img_bytes, 'image/jpeg')}
        data = {
            'channel_id': str(general_channel_id),
            'message': 'TEST_PhotoUpload_Message'
        }
        
        response = requests.post(
            f"{BASE_URL}/api/chat/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files,
            data=data
        )
        assert response.status_code == 200, f"Upload failed: {response.text}"
        result = response.json()
        
        # Verify response has attachment fields
        assert result.get('attachment_url'), "attachment_url should be returned"
        assert result.get('attachment_type') == 'image', "attachment_type should be 'image'"
        assert result.get('attachment_url').startswith('/api/uploads/chat/'), "URL should start with /api/uploads/chat/"
        
        return result
    
    def test_uploaded_image_accessible(self, auth_token, general_channel_id):
        """Uploaded image is accessible via /api/uploads/chat/{filename}"""
        # Create and upload an image
        img = Image.new('RGB', (50, 50), color='green')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        files = {'file': ('test_access.png', img_bytes, 'image/png')}
        data = {'channel_id': str(general_channel_id), 'message': ''}
        
        upload_resp = requests.post(
            f"{BASE_URL}/api/chat/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files,
            data=data
        )
        assert upload_resp.status_code == 200
        attachment_url = upload_resp.json().get('attachment_url')
        
        # Access the uploaded file
        file_resp = requests.get(f"{BASE_URL}{attachment_url}")
        assert file_resp.status_code == 200, f"File not accessible at {attachment_url}"
        assert 'image' in file_resp.headers.get('Content-Type', ''), "Should return image content type"
    
    def test_non_image_rejected(self, auth_token, general_channel_id):
        """Non-image files should be rejected"""
        # Try to upload a text file
        files = {'file': ('test.txt', b'This is text content', 'text/plain')}
        data = {'channel_id': str(general_channel_id), 'message': ''}
        
        response = requests.post(
            f"{BASE_URL}/api/chat/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files,
            data=data
        )
        assert response.status_code == 400, f"Expected 400 for non-image, got {response.status_code}"
    
    def test_messages_return_attachment_fields(self, auth_headers, general_channel_id):
        """GET /api/chat/channels/{id}/messages - returns attachment_url, attachment_type fields"""
        response = requests.get(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers
        )
        assert response.status_code == 200
        messages = response.json()
        
        # Check that all messages have the attachment fields
        for msg in messages:
            assert 'attachment_url' in msg, "Message should have attachment_url field"
            assert 'attachment_type' in msg, "Message should have attachment_type field"
            assert 'is_closed' in msg, "Message should have is_closed field"
            assert 'task_id' in msg, "Message should have task_id field"
    
    def test_upload_to_closed_thread_rejected(self, auth_token, general_channel_id):
        """Photo upload to closed thread should be rejected"""
        # Create a message and close it
        headers = {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}
        msg_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=headers,
            json={"message": "TEST_UploadClosedThread"}
        )
        assert msg_resp.status_code == 200
        msg_id = msg_resp.json().get("id")
        
        # Close the thread
        requests.put(f"{BASE_URL}/api/chat/messages/{msg_id}/close", headers=headers)
        
        # Try to upload to closed thread
        img = Image.new('RGB', (30, 30), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        files = {'file': ('test_closed.jpg', img_bytes, 'image/jpeg')}
        data = {'channel_id': str(general_channel_id), 'message': '', 'reply_to': str(msg_id)}
        
        response = requests.post(
            f"{BASE_URL}/api/chat/upload",
            headers={"Authorization": f"Bearer {auth_token}"},
            files=files,
            data=data
        )
        assert response.status_code == 400, f"Expected 400 for upload to closed thread, got {response.status_code}"


# =============================================
# API FIELD VERIFICATION TESTS
# =============================================

class TestApiFields:
    """Verify API returns all required fields"""
    
    def test_messages_endpoint_fields(self, auth_headers, general_channel_id):
        """Verify GET /api/chat/channels/{id}/messages returns all new fields"""
        response = requests.get(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers
        )
        assert response.status_code == 200
        messages = response.json()
        
        if len(messages) > 0:
            msg = messages[0]
            required_fields = ['id', 'channel_id', 'user_id', 'user_name', 'user_role',
                             'message', 'reply_to', 'thread_count', 'created_at',
                             'attachment_url', 'attachment_type', 'is_closed', 'task_id']
            for field in required_fields:
                assert field in msg, f"Message missing required field: {field}"
    
    def test_thread_endpoint_fields(self, auth_headers, general_channel_id):
        """Verify GET /api/chat/messages/{id}/thread returns attachment and closed state"""
        # Create a message
        msg_resp = requests.post(
            f"{BASE_URL}/api/chat/channels/{general_channel_id}/messages",
            headers=auth_headers,
            json={"message": "TEST_ThreadFieldsCheck"}
        )
        assert msg_resp.status_code == 200
        msg_id = msg_resp.json().get("id")
        
        # Get thread
        thread_resp = requests.get(
            f"{BASE_URL}/api/chat/messages/{msg_id}/thread",
            headers=auth_headers
        )
        assert thread_resp.status_code == 200
        thread_msgs = thread_resp.json()
        
        if len(thread_msgs) > 0:
            msg = thread_msgs[0]
            required_fields = ['id', 'channel_id', 'user_id', 'user_name', 'user_role',
                             'message', 'reply_to', 'is_parent', 'created_at',
                             'attachment_url', 'attachment_type', 'is_closed', 'task_id']
            for field in required_fields:
                assert field in msg, f"Thread message missing required field: {field}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
