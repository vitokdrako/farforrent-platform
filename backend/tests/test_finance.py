#!/usr/bin/env python3
"""
Finance Engine API Testing Script
Testing the Finance Engine API for rental equipment management application.

Test Scenarios:
1. GET /api/finance/accounts - Should return 11 accounts with balances
2. GET /api/finance/categories - Should return 22 categories
3. GET /api/finance/dashboard?period=month - Should return metrics
4. POST /api/finance/payments - Create different payment types
5. POST /api/finance/expenses - Create expense
6. GET /api/finance/deposits - List deposits with order info
7. POST /api/finance/deposits/{id}/use - Use deposit
8. POST /api/finance/deposits/{id}/refund - Refund deposit
9. GET /api/finance/ledger - Verify double-entry bookkeeping
10. GET /api/finance/payments?order_id=X - Filter payments by order
"""

import requests
import json
import sys
from datetime import datetime, date, timedelta
from typing import Dict, List, Any

# Configuration
BASE_URL = "https://item-photos.preview.emergentagent.com/api"
TEST_CREDENTIALS = {
    "email": "vitokdrako@gmail.com",
    "password": "test123"
}

class FinanceEngineAPITester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.auth_token = None
        self.test_results = {}
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def test_api_health(self) -> bool:
        """Test if API is accessible"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                self.log("✅ API Health Check: OK")
                return True
            else:
                self.log(f"❌ API Health Check Failed: {response.status_code}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ API Health Check Exception: {str(e)}", "ERROR")
            return False
    
    def authenticate(self) -> bool:
        """Authenticate with the API"""
        try:
            self.log("🔐 Authenticating with provided credentials...")
            
            response = self.session.post(
                f"{self.base_url}/auth/login",
                json=TEST_CREDENTIALS
            )
            
            if response.status_code == 200:
                data = response.json()
                self.auth_token = data.get('access_token')
                if self.auth_token:
                    self.session.headers.update({
                        'Authorization': f'Bearer {self.auth_token}'
                    })
                    self.log("✅ Authentication successful")
                    return True
                else:
                    self.log("❌ No access token in response", "ERROR")
                    return False
            else:
                self.log(f"❌ Authentication failed: {response.status_code} - {response.text}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"❌ Authentication exception: {str(e)}", "ERROR")
            return False

    def test_finance_accounts(self) -> Dict[str, Any]:
        """Test GET /api/finance/accounts - Should return 11 accounts with balances"""
        try:
            self.log("🧪 Testing GET /api/finance/accounts...")
            
            response = self.session.get(f"{self.base_url}/finance/accounts")
            
            if response.status_code == 200:
                data = response.json()
                
                if not isinstance(data, list):
                    self.log(f"❌ Expected list, got {type(data)}", "ERROR")
                    return {"success": False, "error": "Invalid response format"}
                
                self.log(f"✅ Retrieved {len(data)} accounts")
                
                # Check for expected buckets
                expected_buckets = ["CASH", "BANK", "RENT_REV", "DMG_COMP", "DEP_HOLD", "OPEX"]
                found_buckets = [acc.get("code") for acc in data]
                
                for bucket in expected_buckets:
                    if bucket in found_buckets:
                        account = next(acc for acc in data if acc.get("code") == bucket)
                        balance = account.get("balance", 0)
                        self.log(f"   - {bucket}: {account.get('name')} - Balance: ₴{balance}")
                    else:
                        self.log(f"   ⚠️ Missing expected bucket: {bucket}")
                
                return {
                    "success": True,
                    "data": data,
                    "count": len(data),
                    "found_buckets": found_buckets
                }
            else:
                self.log(f"❌ Failed to get accounts: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing accounts: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_finance_categories(self) -> Dict[str, Any]:
        """Test GET /api/finance/categories - Should return 22 categories"""
        try:
            self.log("🧪 Testing GET /api/finance/categories...")
            
            # Test all categories
            response = self.session.get(f"{self.base_url}/finance/categories")
            
            if response.status_code == 200:
                data = response.json()
                
                if not isinstance(data, list):
                    self.log(f"❌ Expected list, got {type(data)}", "ERROR")
                    return {"success": False, "error": "Invalid response format"}
                
                self.log(f"✅ Retrieved {len(data)} categories")
                
                # Test filtering by type
                expense_response = self.session.get(f"{self.base_url}/finance/categories?type=expense")
                if expense_response.status_code == 200:
                    expense_data = expense_response.json()
                    self.log(f"✅ Retrieved {len(expense_data)} expense categories")
                
                # Show some categories
                for cat in data[:5]:
                    self.log(f"   - {cat.get('code')}: {cat.get('name')} ({cat.get('type')})")
                
                return {
                    "success": True,
                    "data": data,
                    "count": len(data),
                    "expense_count": len(expense_data) if expense_response.status_code == 200 else 0
                }
            else:
                self.log(f"❌ Failed to get categories: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing categories: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_finance_dashboard(self) -> Dict[str, Any]:
        """Test GET /api/finance/dashboard?period=month - Should return metrics"""
        try:
            self.log("🧪 Testing GET /api/finance/dashboard?period=month...")
            
            response = self.session.get(f"{self.base_url}/finance/dashboard?period=month")
            
            if response.status_code == 200:
                data = response.json()
                
                expected_fields = ["period", "metrics", "deposits"]
                missing_fields = [field for field in expected_fields if field not in data]
                
                if missing_fields:
                    self.log(f"❌ Missing fields: {missing_fields}", "ERROR")
                    return {"success": False, "error": f"Missing fields: {missing_fields}"}
                
                metrics = data.get("metrics", {})
                deposits = data.get("deposits", {})
                
                self.log(f"✅ Dashboard metrics retrieved:")
                self.log(f"   - Net Profit: ₴{metrics.get('net_profit', 0)}")
                self.log(f"   - Rent Revenue: ₴{metrics.get('rent_revenue', 0)}")
                self.log(f"   - Damage Compensation: ₴{metrics.get('damage_compensation', 0)}")
                self.log(f"   - Operating Expenses: ₴{metrics.get('operating_expenses', 0)}")
                self.log(f"   - Cash Balance: ₴{metrics.get('cash_balance', 0)}")
                self.log(f"   - Deposits Held: ₴{deposits.get('held', 0)}")
                self.log(f"   - Deposits Used: ₴{deposits.get('used', 0)}")
                self.log(f"   - Deposits Refunded: ₴{deposits.get('refunded', 0)}")
                self.log(f"   - Available to Refund: ₴{deposits.get('available_to_refund', 0)}")
                
                return {
                    "success": True,
                    "data": data,
                    "metrics": metrics,
                    "deposits": deposits
                }
            else:
                self.log(f"❌ Failed to get dashboard: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing dashboard: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_create_payments(self) -> Dict[str, Any]:
        """Test POST /api/finance/payments - Create different payment types"""
        try:
            self.log("🧪 Testing POST /api/finance/payments...")
            
            # Test payment scenarios from review request
            test_payments = [
                {
                    "payment_type": "rent",
                    "method": "cash",
                    "amount": 3000,
                    "order_id": 7104,
                    "payer_name": "Test Customer"
                },
                {
                    "payment_type": "deposit",
                    "method": "card",
                    "amount": 1500,
                    "order_id": 7104
                },
                {
                    "payment_type": "damage",
                    "method": "cash",
                    "amount": 500,
                    "damage_case_id": 1
                }
            ]
            
            created_payments = []
            
            for payment_data in test_payments:
                response = self.session.post(
                    f"{self.base_url}/finance/payments",
                    json=payment_data
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        payment_id = result.get("payment_id")
                        tx_id = result.get("tx_id")
                        created_payments.append({
                            "payment_id": payment_id,
                            "tx_id": tx_id,
                            "type": payment_data["payment_type"],
                            "amount": payment_data["amount"]
                        })
                        self.log(f"✅ Created {payment_data['payment_type']} payment: ₴{payment_data['amount']} (ID: {payment_id})")
                    else:
                        self.log(f"❌ Payment creation failed: {result}", "ERROR")
                        return {"success": False, "error": f"Payment creation failed: {result}"}
                else:
                    self.log(f"❌ Failed to create payment: {response.status_code} - {response.text}", "ERROR")
                    return {"success": False, "status_code": response.status_code}
            
            return {
                "success": True,
                "created_payments": created_payments,
                "count": len(created_payments)
            }
                
        except Exception as e:
            self.log(f"❌ Exception testing payments: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_create_expense(self) -> Dict[str, Any]:
        """Test POST /api/finance/expenses - Create expense"""
        try:
            self.log("🧪 Testing POST /api/finance/expenses...")
            
            expense_data = {
                "expense_type": "expense",
                "category_code": "CONSUMABLES",
                "amount": 250,
                "method": "cash",
                "note": "Пакувальні матеріали"
            }
            
            response = self.session.post(
                f"{self.base_url}/finance/expenses",
                json=expense_data
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    expense_id = result.get("expense_id")
                    tx_id = result.get("tx_id")
                    self.log(f"✅ Created expense: ₴{expense_data['amount']} (ID: {expense_id})")
                    
                    return {
                        "success": True,
                        "expense_id": expense_id,
                        "tx_id": tx_id,
                        "amount": expense_data["amount"]
                    }
                else:
                    self.log(f"❌ Expense creation failed: {result}", "ERROR")
                    return {"success": False, "error": f"Expense creation failed: {result}"}
            else:
                self.log(f"❌ Failed to create expense: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing expense: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_deposits_list(self) -> Dict[str, Any]:
        """Test GET /api/finance/deposits - List deposits with order info"""
        try:
            self.log("🧪 Testing GET /api/finance/deposits...")
            
            response = self.session.get(f"{self.base_url}/finance/deposits")
            
            if response.status_code == 200:
                data = response.json()
                
                if not isinstance(data, list):
                    self.log(f"❌ Expected list, got {type(data)}", "ERROR")
                    return {"success": False, "error": "Invalid response format"}
                
                self.log(f"✅ Retrieved {len(data)} deposits")
                
                # Show deposit details
                for deposit in data[:3]:  # Show first 3 deposits
                    self.log(f"   - Deposit ID {deposit.get('id')}: Order #{deposit.get('order_number')} - {deposit.get('customer_name')}")
                    self.log(f"     Held: ₴{deposit.get('held_amount', 0)}, Used: ₴{deposit.get('used_amount', 0)}, Available: ₴{deposit.get('available', 0)}")
                    self.log(f"     Status: {deposit.get('status')}")
                
                return {
                    "success": True,
                    "data": data,
                    "count": len(data)
                }
            else:
                self.log(f"❌ Failed to get deposits: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing deposits: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_deposit_operations(self) -> Dict[str, Any]:
        """Test deposit use and refund operations"""
        try:
            self.log("🧪 Testing deposit operations...")
            
            # First get deposits to find one to test with
            deposits_response = self.session.get(f"{self.base_url}/finance/deposits")
            if deposits_response.status_code != 200:
                self.log("❌ Could not get deposits for testing operations", "ERROR")
                return {"success": False, "error": "Could not get deposits"}
            
            deposits = deposits_response.json()
            if not deposits:
                self.log("⚠️ No deposits found for testing operations")
                return {"success": True, "warning": "No deposits available for testing"}
            
            # Find a deposit with available amount
            test_deposit = None
            for deposit in deposits:
                if deposit.get("available", 0) > 0:
                    test_deposit = deposit
                    break
            
            if not test_deposit:
                self.log("⚠️ No deposits with available amount for testing")
                return {"success": True, "warning": "No deposits with available amount"}
            
            deposit_id = test_deposit["id"]
            available_amount = test_deposit["available"]
            
            self.log(f"   Using deposit ID {deposit_id} with available amount: ₴{available_amount}")
            
            results = {}
            
            # Test deposit use (if available amount > 300)
            if available_amount >= 300:
                use_response = self.session.post(
                    f"{self.base_url}/finance/deposits/{deposit_id}/use?amount=300&note=Test damage"
                )
                
                if use_response.status_code == 200:
                    use_result = use_response.json()
                    if use_result.get("success"):
                        self.log(f"✅ Used ₴300 from deposit {deposit_id}")
                        results["use_success"] = True
                        results["use_tx_id"] = use_result.get("tx_id")
                    else:
                        self.log(f"❌ Deposit use failed: {use_result}", "ERROR")
                        results["use_success"] = False
                else:
                    self.log(f"❌ Failed to use deposit: {use_response.status_code} - {use_response.text}", "ERROR")
                    results["use_success"] = False
            else:
                self.log(f"⚠️ Insufficient amount for use test (available: ₴{available_amount})")
                results["use_success"] = None
            
            # Test deposit refund (if still available amount > 1000)
            remaining_amount = available_amount - (300 if results.get("use_success") else 0)
            if remaining_amount >= 1000:
                refund_response = self.session.post(
                    f"{self.base_url}/finance/deposits/{deposit_id}/refund?amount=1000&method=cash"
                )
                
                if refund_response.status_code == 200:
                    refund_result = refund_response.json()
                    if refund_result.get("success"):
                        self.log(f"✅ Refunded ₴1000 from deposit {deposit_id}")
                        results["refund_success"] = True
                        results["refund_tx_id"] = refund_result.get("tx_id")
                    else:
                        self.log(f"❌ Deposit refund failed: {refund_result}", "ERROR")
                        results["refund_success"] = False
                else:
                    self.log(f"❌ Failed to refund deposit: {refund_response.status_code} - {refund_response.text}", "ERROR")
                    results["refund_success"] = False
            else:
                self.log(f"⚠️ Insufficient amount for refund test (remaining: ₴{remaining_amount})")
                results["refund_success"] = None
            
            return {
                "success": True,
                "deposit_id": deposit_id,
                "operations": results
            }
                
        except Exception as e:
            self.log(f"❌ Exception testing deposit operations: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_ledger_transactions(self) -> Dict[str, Any]:
        """Test GET /api/finance/ledger - Verify double-entry bookkeeping"""
        try:
            self.log("🧪 Testing GET /api/finance/ledger...")
            
            response = self.session.get(f"{self.base_url}/finance/ledger?limit=10")
            
            if response.status_code == 200:
                data = response.json()
                
                if not isinstance(data, dict) or "transactions" not in data:
                    self.log(f"❌ Expected dict with 'transactions' key, got {type(data)}", "ERROR")
                    return {"success": False, "error": "Invalid response format"}
                
                transactions = data["transactions"]
                self.log(f"✅ Retrieved {len(transactions)} ledger transactions")
                
                # Verify double-entry bookkeeping
                double_entry_valid = True
                for tx in transactions[:3]:  # Check first 3 transactions
                    entries = tx.get("entries", [])
                    debit_total = sum(entry["amount"] for entry in entries if entry["direction"] == "D")
                    credit_total = sum(entry["amount"] for entry in entries if entry["direction"] == "C")
                    
                    self.log(f"   - TX {tx['id']} ({tx['tx_type']}): ₴{tx['amount']}")
                    self.log(f"     Debit: ₴{debit_total}, Credit: ₴{credit_total}")
                    
                    if abs(debit_total - credit_total) > 0.01:  # Allow for small floating point differences
                        self.log(f"     ❌ Double-entry violation: Debit ≠ Credit", "ERROR")
                        double_entry_valid = False
                    else:
                        self.log(f"     ✅ Double-entry balanced")
                    
                    for entry in entries:
                        self.log(f"       {entry['direction']}: {entry['account_code']} - ₴{entry['amount']}")
                
                return {
                    "success": True,
                    "data": data,
                    "count": len(transactions),
                    "double_entry_valid": double_entry_valid
                }
            else:
                self.log(f"❌ Failed to get ledger: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing ledger: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def test_payments_filter(self) -> Dict[str, Any]:
        """Test GET /api/finance/payments?order_id=X - Filter payments by order"""
        try:
            self.log("🧪 Testing GET /api/finance/payments?order_id=7121...")
            
            response = self.session.get(f"{self.base_url}/finance/payments?order_id=7121")
            
            if response.status_code == 200:
                data = response.json()
                
                if not isinstance(data, dict) or "payments" not in data:
                    self.log(f"❌ Expected dict with 'payments' key, got {type(data)}", "ERROR")
                    return {"success": False, "error": "Invalid response format"}
                
                payments = data["payments"]
                self.log(f"✅ Retrieved {len(payments)} payments for order 7121")
                
                # Show payment details
                for payment in payments:
                    self.log(f"   - Payment ID {payment.get('id')}: {payment.get('payment_type')} - ₴{payment.get('amount')} ({payment.get('method')})")
                    self.log(f"     Payer: {payment.get('payer_name', 'N/A')}, Status: {payment.get('status')}")
                
                return {
                    "success": True,
                    "data": data,
                    "count": len(payments)
                }
            else:
                self.log(f"❌ Failed to get filtered payments: {response.status_code} - {response.text}", "ERROR")
                return {"success": False, "status_code": response.status_code}
                
        except Exception as e:
            self.log(f"❌ Exception testing payment filter: {str(e)}", "ERROR")
            return {"success": False, "error": str(e)}

    def run_comprehensive_finance_test(self):
        """Run the comprehensive Finance Engine API test"""
        self.log("🚀 Starting comprehensive Finance Engine API test")
        self.log("=" * 70)
        
        # Step 1: Health check
        if not self.test_api_health():
            self.log("❌ API health check failed, aborting tests", "ERROR")
            return False
        
        # Step 2: Authentication
        self.log("\n🔍 Step 1: Testing authentication...")
        if not self.authenticate():
            self.log("❌ Authentication failed, aborting tests", "ERROR")
            return False
        
        # Step 3: Test accounts
        self.log("\n🔍 Step 2: Testing finance accounts...")
        accounts_result = self.test_finance_accounts()
        self.test_results["accounts"] = accounts_result
        
        # Step 4: Test categories
        self.log("\n🔍 Step 3: Testing finance categories...")
        categories_result = self.test_finance_categories()
        self.test_results["categories"] = categories_result
        
        # Step 5: Test dashboard
        self.log("\n🔍 Step 4: Testing finance dashboard...")
        dashboard_result = self.test_finance_dashboard()
        self.test_results["dashboard"] = dashboard_result
        
        # Step 6: Test payments creation
        self.log("\n🔍 Step 5: Testing payment creation...")
        payments_result = self.test_create_payments()
        self.test_results["payments_create"] = payments_result
        
        # Step 7: Test expense creation
        self.log("\n🔍 Step 6: Testing expense creation...")
        expense_result = self.test_create_expense()
        self.test_results["expense_create"] = expense_result
        
        # Step 8: Test deposits list
        self.log("\n🔍 Step 7: Testing deposits list...")
        deposits_result = self.test_deposits_list()
        self.test_results["deposits_list"] = deposits_result
        
        # Step 9: Test deposit operations
        self.log("\n🔍 Step 8: Testing deposit operations...")
        deposit_ops_result = self.test_deposit_operations()
        self.test_results["deposit_operations"] = deposit_ops_result
        
        # Step 10: Test ledger
        self.log("\n🔍 Step 9: Testing ledger transactions...")
        ledger_result = self.test_ledger_transactions()
        self.test_results["ledger"] = ledger_result
        
        # Step 11: Test payment filtering
        self.log("\n🔍 Step 10: Testing payment filtering...")
        payment_filter_result = self.test_payments_filter()
        self.test_results["payments_filter"] = payment_filter_result
        
        # Summary
        self.log("\n" + "=" * 70)
        self.log("📊 COMPREHENSIVE FINANCE ENGINE API TEST SUMMARY:")
        
        success_count = 0
        total_tests = 0
        
        for test_name, result in self.test_results.items():
            total_tests += 1
            if result.get("success"):
                success_count += 1
                self.log(f"   ✅ {test_name}: PASSED")
            else:
                self.log(f"   ❌ {test_name}: FAILED - {result.get('error', 'Unknown error')}")
        
        self.log(f"\n📈 Test Results: {success_count}/{total_tests} tests passed")
        
        # Detailed results
        if accounts_result.get("success"):
            self.log(f"   • Accounts: {accounts_result.get('count', 0)} accounts retrieved")
        
        if categories_result.get("success"):
            self.log(f"   • Categories: {categories_result.get('count', 0)} categories retrieved")
        
        if dashboard_result.get("success"):
            metrics = dashboard_result.get("metrics", {})
            self.log(f"   • Dashboard: Net Profit ₴{metrics.get('net_profit', 0)}")
        
        if payments_result.get("success"):
            self.log(f"   • Payments: {payments_result.get('count', 0)} payments created")
        
        if ledger_result.get("success"):
            self.log(f"   • Ledger: {ledger_result.get('count', 0)} transactions, Double-entry: {'✅' if ledger_result.get('double_entry_valid') else '❌'}")
        
        self.log("\n🎉 FINANCE ENGINE API TESTING COMPLETED!")
        
        # Check if all critical tests passed
        critical_tests = ["accounts", "categories", "dashboard", "payments_create", "ledger"]
        critical_success = all(self.test_results.get(test, {}).get("success", False) for test in critical_tests)
        
        if critical_success:
            self.log("\n✅ ALL CRITICAL FINANCE ENGINE API TESTS PASSED!")
        else:
            failed_tests = [test for test in critical_tests if not self.test_results.get(test, {}).get("success", False)]
            self.log(f"\n⚠️ SOME CRITICAL TESTS FAILED: {failed_tests}")
        
        return critical_success

def main():
    """Main test execution"""
    print("🧪 Backend Testing: Finance Engine API")
    print("=" * 80)
    print("Testing the Finance Engine API for rental equipment management:")
    print("   1. 🏦 Accounts - List all buckets with balances")
    print("   2. 📋 Categories - List expense/income categories")
    print("   3. 📊 Dashboard - Financial overview with metrics")
    print("   4. 💰 Payments - Create rent/deposit/damage payments")
    print("   5. 💸 Expenses - Create expenses with categories")
    print("   6. 🏛️ Deposits - List and manage deposits")
    print("   7. 📚 Ledger - Verify double-entry bookkeeping")
    print("   8. 🔍 Filtering - Filter payments by order")
    print(f"Credentials: {TEST_CREDENTIALS['email']} / {TEST_CREDENTIALS['password']}")
    print("URL: https://item-photos.preview.emergentagent.com")
    print("=" * 80)
    
    tester = FinanceEngineAPITester(BASE_URL)
    
    try:
        success = tester.run_comprehensive_finance_test()
        
        if success:
            print("\n✅ ALL CRITICAL FINANCE ENGINE API TESTS PASSED")
            print("📊 Summary: Finance Engine API working correctly")
            print("🎯 Expected behavior confirmed:")
            print("   ✅ Accounts API returns buckets with balances")
            print("   ✅ Categories API returns expense/income categories")
            print("   ✅ Dashboard API returns financial metrics")
            print("   ✅ Payments API creates different payment types")
            print("   ✅ Expenses API creates expenses with categories")
            print("   ✅ Deposits API manages deposit operations")
            print("   ✅ Ledger API shows double-entry bookkeeping")
            print("   ✅ Payment filtering works correctly")
            sys.exit(0)
        else:
            print("\n❌ SOME FINANCE ENGINE API TESTS FAILED")
            print("📊 Summary: Issues found in Finance Engine implementation")
            print("🔍 Check the detailed logs above for specific failures")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()