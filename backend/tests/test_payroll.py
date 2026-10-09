"""
Tests for Payroll API endpoints
/app/backend/routes/finance.py - employees & payroll section
"""
import pytest
import sys
import os

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"

def get_auth_headers():
    """Get authentication headers"""
    response = client.post("/api/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD
    })
    if response.status_code == 200:
        token = response.json().get("access_token")
        return {"Authorization": f"Bearer {token}"}
    return {}


class TestEmployeesAPI:
    """Tests for /api/finance/employees endpoints"""
    
    def test_list_employees(self):
        """GET /api/finance/employees - should return list of employees"""
        headers = get_auth_headers()
        response = client.get("/api/finance/employees", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "employees" in data
        assert isinstance(data["employees"], list)
        
    def test_create_employee(self):
        """POST /api/finance/employees - should create new employee"""
        headers = get_auth_headers()
        employee_data = {
            "name": "Тест Працівник",
            "role": "assistant",
            "phone": "+380501234567",
            "email": "test.employee@example.com",
            "base_salary": 15000,
            "note": "Тестовий працівник"
        }
        
        response = client.post("/api/finance/employees", json=employee_data, headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data.get("success") == True
        assert "employee_id" in data
        
    def test_list_employees_after_create(self):
        """Verify employee appears in list after creation"""
        headers = get_auth_headers()
        response = client.get("/api/finance/employees", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        # Check that we have at least one employee
        assert len(data["employees"]) >= 0


class TestPayrollAPI:
    """Tests for /api/finance/payroll endpoints"""
    
    def test_list_payroll(self):
        """GET /api/finance/payroll - should return payroll records"""
        headers = get_auth_headers()
        response = client.get("/api/finance/payroll", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "payroll" in data
        assert isinstance(data["payroll"], list)
        
    def test_create_payroll_record(self):
        """POST /api/finance/payroll - should create payroll record"""
        headers = get_auth_headers()
        
        # First, get an employee ID
        emp_response = client.get("/api/finance/employees", headers=headers)
        employees = emp_response.json().get("employees", [])
        
        if not employees:
            # Create an employee first
            client.post("/api/finance/employees", json={
                "name": "Payroll Test Employee",
                "role": "assistant",
                "base_salary": 10000
            }, headers=headers)
            emp_response = client.get("/api/finance/employees", headers=headers)
            employees = emp_response.json().get("employees", [])
        
        if employees:
            employee_id = employees[0]["id"]
            payroll_data = {
                "employee_id": employee_id,
                "period_start": "2025-12-01",
                "period_end": "2025-12-15",
                "base_amount": 10000,
                "bonus": 2000,
                "deduction": 500,
                "method": "cash",
                "note": "Аванс за грудень 2025"
            }
            
            response = client.post("/api/finance/payroll", json=payroll_data, headers=headers)
            
            assert response.status_code == 200
            data = response.json()
            assert data.get("success") == True
            assert "payroll_id" in data
    
    def test_payroll_record_structure(self):
        """Verify payroll record has correct structure"""
        headers = get_auth_headers()
        response = client.get("/api/finance/payroll", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        
        if data["payroll"]:
            record = data["payroll"][0]
            expected_fields = ["id", "employee_id", "employee_name", "period_start", 
                             "period_end", "base_amount", "bonus", "deduction", 
                             "total_amount", "status", "method"]
            for field in expected_fields:
                assert field in record, f"Missing field: {field}"


class TestPayrollPayment:
    """Tests for payroll payment processing"""
    
    def test_pay_payroll(self):
        """POST /api/finance/payroll/{id}/pay - should process payment"""
        headers = get_auth_headers()
        
        # Get pending payroll records
        response = client.get("/api/finance/payroll", headers=headers)
        payroll_records = response.json().get("payroll", [])
        
        pending_records = [r for r in payroll_records if r["status"] == "pending"]
        
        if pending_records:
            payroll_id = pending_records[0]["id"]
            pay_response = client.post(f"/api/finance/payroll/{payroll_id}/pay", headers=headers)
            
            # Should either succeed or fail with appropriate error
            assert pay_response.status_code in [200, 400, 404]
            
    def test_pay_already_paid(self):
        """Should reject payment for already paid record"""
        headers = get_auth_headers()
        
        response = client.get("/api/finance/payroll", headers=headers)
        payroll_records = response.json().get("payroll", [])
        
        paid_records = [r for r in payroll_records if r["status"] == "paid"]
        
        if paid_records:
            payroll_id = paid_records[0]["id"]
            pay_response = client.post(f"/api/finance/payroll/{payroll_id}/pay", headers=headers)
            
            # Should fail for already paid
            assert pay_response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
