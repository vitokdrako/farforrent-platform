"""
Test Close Month Feature (Закриття місяця)
- POST /api/finance/close-month - Creates monthly report
- GET /api/finance/monthly-reports - Lists all closed months
- GET /api/finance/monthly-reports/{id} - Report detail
- DELETE /api/finance/monthly-reports/{id} - Removes report (reopens month)
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com')

# Test credentials
TEST_EMAIL = "vitokdrako@gmail.com"
TEST_PASSWORD = "test123"


class TestCloseMonthFeature:
    """Tests for Close Month functionality"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login and get token
        login_res = self.session.post(f"{BASE_URL}/api/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_res.status_code == 200:
            data = login_res.json()
            token = data.get("access_token") or data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
        
    def test_01_get_monthly_reports_list(self):
        """GET /api/finance/monthly-reports - Should return list of closed months"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert isinstance(data, list), "Response should be a list"
        
        # Verify existing reports structure (Dec 2025, Nov 2025, Jan 2026 should exist per context)
        if len(data) > 0:
            report = data[0]
            assert "id" in report, "Report should have id"
            assert "year" in report, "Report should have year"
            assert "month" in report, "Report should have month"
            assert "report" in report, "Report should have report data"
            assert "closed_by" in report, "Report should have closed_by"
            assert "closed_at" in report, "Report should have closed_at"
            
            # Check report data structure
            report_data = report.get("report", {})
            assert "income" in report_data, "Report should have income section"
            assert "deposits" in report_data, "Report should have deposits section"
            assert "expenses" in report_data, "Report should have expenses section"
            assert "refunds" in report_data, "Report should have refunds section"
            assert "summary" in report_data, "Report should have summary section"
            
            # Verify summary structure
            summary = report_data.get("summary", {})
            assert "net_cash" in summary, "Summary should have net_cash"
            assert "net_bank" in summary, "Summary should have net_bank"
            assert "net_total" in summary, "Summary should have net_total"
        
        print(f"✓ Monthly reports list returned {len(data)} reports")
    
    def test_02_close_month_feb_2026(self):
        """POST /api/finance/close-month - Should create report for Feb 2026"""
        payload = {
            "year": 2026,
            "month": 2,
            "note": "Test close month",
            "closed_by": "Test User",
            "closed_by_id": 1
        }
        
        res = self.session.post(f"{BASE_URL}/api/finance/close-month", json=payload)
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        assert data.get("success") == True, "Should return success=true"
        assert "report" in data, "Should return report data"
        
        report = data["report"]
        assert "income" in report, "Report should have income"
        assert "deposits" in report, "Report should have deposits"
        assert "expenses" in report, "Report should have expenses"
        assert "refunds" in report, "Report should have refunds"
        assert "summary" in report, "Report should have summary"
        
        # Save report ID for later tests
        self.__class__.created_report_year = 2026
        self.__class__.created_report_month = 2
        
        print(f"✓ Close month successful. Income: {report.get('income', {}).get('total', 0)}, "
              f"Net total: {report.get('summary', {}).get('net_total', 0)}")
    
    def test_03_close_month_duplicate_returns_409(self):
        """POST /api/finance/close-month duplicate - Should return 409 Conflict"""
        payload = {
            "year": 2026,
            "month": 2,  # Same as previous test
            "note": "Duplicate attempt"
        }
        
        res = self.session.post(f"{BASE_URL}/api/finance/close-month", json=payload)
        
        assert res.status_code == 409, f"Expected 409 for duplicate, got {res.status_code}: {res.text}"
        data = res.json()
        assert "detail" in data, "Should return detail message"
        
        print(f"✓ Duplicate close returns 409: {data.get('detail')}")
    
    def test_04_get_reports_list_contains_new_report(self):
        """GET /api/finance/monthly-reports - Should contain Feb 2026 report"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        
        assert res.status_code == 200
        data = res.json()
        
        # Find Feb 2026 report
        feb_report = None
        for r in data:
            if r.get("year") == 2026 and r.get("month") == 2:
                feb_report = r
                break
        
        assert feb_report is not None, "Feb 2026 report should be in list"
        self.__class__.created_report_id = feb_report.get("id")
        
        print(f"✓ Feb 2026 report found in list with ID {feb_report.get('id')}")
    
    def test_05_get_report_detail(self):
        """GET /api/finance/monthly-reports/{id} - Should return report detail"""
        report_id = getattr(self.__class__, 'created_report_id', None)
        
        if not report_id:
            # Get from list
            res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
            data = res.json()
            for r in data:
                if r.get("year") == 2026 and r.get("month") == 2:
                    report_id = r.get("id")
                    break
        
        assert report_id, "Report ID should be available"
        
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports/{report_id}")
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        
        assert data.get("id") == report_id
        assert data.get("year") == 2026
        assert data.get("month") == 2
        assert "report" in data
        
        report = data["report"]
        # Verify full structure
        assert "income" in report
        assert "deposits" in report
        assert "expenses" in report
        assert "refunds" in report
        assert "summary" in report
        
        # Verify income breakdown has by_type
        income = report["income"]
        assert "total" in income
        assert "cash" in income
        assert "bank" in income
        assert "by_type" in income
        
        print(f"✓ Report detail fetched. Period: {data.get('year')}/{data.get('month')}")
    
    def test_06_delete_report(self):
        """DELETE /api/finance/monthly-reports/{id} - Should remove the report"""
        report_id = getattr(self.__class__, 'created_report_id', None)
        
        if not report_id:
            # Get from list
            res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
            data = res.json()
            for r in data:
                if r.get("year") == 2026 and r.get("month") == 2:
                    report_id = r.get("id")
                    break
        
        if not report_id:
            pytest.skip("No Feb 2026 report to delete")
        
        res = self.session.delete(f"{BASE_URL}/api/finance/monthly-reports/{report_id}")
        
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("success") == True
        
        print(f"✓ Report {report_id} deleted successfully")
    
    def test_07_verify_report_deleted(self):
        """GET /api/finance/monthly-reports - Feb 2026 should be gone"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        
        assert res.status_code == 200
        data = res.json()
        
        # Feb 2026 should not exist
        feb_report = None
        for r in data:
            if r.get("year") == 2026 and r.get("month") == 2:
                feb_report = r
                break
        
        assert feb_report is None, "Feb 2026 report should be deleted"
        
        print("✓ Feb 2026 report confirmed deleted")
    
    def test_08_close_month_missing_params(self):
        """POST /api/finance/close-month without params - Should return 400"""
        res = self.session.post(f"{BASE_URL}/api/finance/close-month", json={})
        
        # Should return 400 for missing year/month
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        
        print("✓ Missing params returns 400")


class TestReportDataStructure:
    """Tests for validating report data structure"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session with auth"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        
        # Login
        login_res = self.session.post(f"{BASE_URL}/api/login", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD
        })
        if login_res.status_code == 200:
            data = login_res.json()
            token = data.get("access_token") or data.get("token")
            if token:
                self.session.headers.update({"Authorization": f"Bearer {token}"})
        
        yield
    
    def test_income_section_structure(self):
        """Verify income section has all required fields"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        assert res.status_code == 200
        
        data = res.json()
        if len(data) == 0:
            pytest.skip("No reports to verify")
        
        report = data[0]["report"]
        income = report.get("income", {})
        
        assert "total" in income, "Income should have total"
        assert "cash" in income, "Income should have cash"
        assert "bank" in income, "Income should have bank"
        assert "count" in income, "Income should have count"
        assert "by_type" in income, "Income should have by_type breakdown"
        
        by_type = income["by_type"]
        for ptype in ["rent", "damage", "late", "additional"]:
            assert ptype in by_type, f"by_type should have {ptype}"
            type_data = by_type[ptype]
            assert "total" in type_data
            assert "cash" in type_data
            assert "bank" in type_data
        
        print(f"✓ Income structure valid. Total: {income.get('total')}")
    
    def test_deposits_section_structure(self):
        """Verify deposits section has all required fields"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        data = res.json()
        
        if len(data) == 0:
            pytest.skip("No reports")
        
        deposits = data[0]["report"].get("deposits", {})
        
        required_fields = ["opened_count", "total_held", "total_used", "total_refunded", "closed_count"]
        for field in required_fields:
            assert field in deposits, f"Deposits should have {field}"
        
        print(f"✓ Deposits structure valid. Held: {deposits.get('total_held')}")
    
    def test_expenses_section_structure(self):
        """Verify expenses section has all required fields"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        data = res.json()
        
        if len(data) == 0:
            pytest.skip("No reports")
        
        expenses = data[0]["report"].get("expenses", {})
        
        assert "total" in expenses
        assert "cash" in expenses
        assert "bank" in expenses
        assert "count" in expenses
        assert "by_category" in expenses
        
        print(f"✓ Expenses structure valid. Total: {expenses.get('total')}")
    
    def test_summary_section_structure(self):
        """Verify summary section has all required fields"""
        res = self.session.get(f"{BASE_URL}/api/finance/monthly-reports")
        data = res.json()
        
        if len(data) == 0:
            pytest.skip("No reports")
        
        summary = data[0]["report"].get("summary", {})
        
        assert "net_cash" in summary
        assert "net_bank" in summary
        assert "net_total" in summary
        
        # Verify net_total calculation is reasonable
        income_total = data[0]["report"].get("income", {}).get("total", 0)
        expenses_total = data[0]["report"].get("expenses", {}).get("total", 0)
        refunds_total = data[0]["report"].get("refunds", {}).get("total", 0)
        expected_net = income_total - expenses_total - refunds_total
        
        assert summary["net_total"] == expected_net, f"net_total mismatch: {summary['net_total']} vs expected {expected_net}"
        
        print(f"✓ Summary structure valid. Net: {summary.get('net_total')}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
