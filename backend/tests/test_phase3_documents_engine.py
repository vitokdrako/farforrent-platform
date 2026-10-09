#!/usr/bin/env python3
"""
Phase 3: Documents Engine API Tests
Testing Master Agreements, Order Annexes, and Document Policy APIs

Test Data:
- Payer Profile ID: 1 (Хук Тетяна, fop_simple)
- Order ID: 7325 (status: issued, has payer_profile_id: 1)
- Order ID: 7326 (status: processing, no payer)
- Master Agreement: MA-2026-001 (signed, for payer 1)
- Annex: MA-2026-001-A001 (generated for order 7325)
"""

import pytest
import requests
import os
from datetime import datetime, date, timedelta

# Configuration
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://item-photos.preview.emergentagent.com').rstrip('/')

# Test data
TEST_PAYER_PROFILE_ID = 1
TEST_ORDER_WITH_PAYER = 7325  # status: issued, has payer_profile_id: 1
TEST_ORDER_WITHOUT_PAYER = 7326  # status: processing, no payer
EXISTING_AGREEMENT_ID = 1
EXISTING_ANNEX_ID = 1


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json"
    })
    return session


# ============================================================
# MASTER AGREEMENTS API TESTS
# ============================================================

class TestMasterAgreementsAPI:
    """Master Agreements CRUD API tests"""
    
    def test_list_agreements(self, api_client):
        """Test GET /api/agreements - List all agreements"""
        response = api_client.get(f"{BASE_URL}/api/agreements")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response structure
        assert "agreements" in data
        assert isinstance(data["agreements"], list)
        
        # Should have at least one agreement (MA-2026-001)
        assert len(data["agreements"]) >= 1
        
        # Validate agreement structure
        agreement = data["agreements"][0]
        assert "id" in agreement
        assert "payer_profile_id" in agreement
        assert "contract_number" in agreement
        assert "status" in agreement
        assert "payer" in agreement
        
        print(f"✅ Found {len(data['agreements'])} agreements")
    
    def test_list_agreements_filter_by_payer(self, api_client):
        """Test GET /api/agreements?payer_profile_id=1 - Filter by payer"""
        response = api_client.get(f"{BASE_URL}/api/agreements?payer_profile_id={TEST_PAYER_PROFILE_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # All agreements should belong to payer 1
        for agreement in data["agreements"]:
            assert agreement["payer_profile_id"] == TEST_PAYER_PROFILE_ID
        
        print(f"✅ Found {len(data['agreements'])} agreements for payer {TEST_PAYER_PROFILE_ID}")
    
    def test_list_agreements_filter_by_status(self, api_client):
        """Test GET /api/agreements?status=signed - Filter by status"""
        response = api_client.get(f"{BASE_URL}/api/agreements?status=signed")
        
        assert response.status_code == 200
        data = response.json()
        
        # All agreements should have status 'signed'
        for agreement in data["agreements"]:
            assert agreement["status"] == "signed"
        
        print(f"✅ Found {len(data['agreements'])} signed agreements")
    
    def test_list_agreements_active_only(self, api_client):
        """Test GET /api/agreements?active_only=true - Active agreements only"""
        response = api_client.get(f"{BASE_URL}/api/agreements?active_only=true")
        
        assert response.status_code == 200
        data = response.json()
        
        # All agreements should be signed and not expired
        for agreement in data["agreements"]:
            assert agreement["status"] == "signed"
            # valid_until should be in the future
            if agreement["valid_until"]:
                valid_until = datetime.fromisoformat(agreement["valid_until"]).date()
                assert valid_until >= date.today()
        
        print(f"✅ Found {len(data['agreements'])} active agreements")
    
    def test_get_single_agreement(self, api_client):
        """Test GET /api/agreements/{id} - Get single agreement"""
        response = api_client.get(f"{BASE_URL}/api/agreements/{EXISTING_AGREEMENT_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate full agreement structure
        assert data["id"] == EXISTING_AGREEMENT_ID
        assert data["contract_number"] == "MA-2026-001"
        assert data["status"] == "signed"
        assert data["payer_profile_id"] == TEST_PAYER_PROFILE_ID
        
        # Validate payer data
        assert "payer" in data
        assert data["payer"]["company_name"] == "Хук Тетяна"
        assert data["payer"]["payer_type"] == "fop_simple"
        
        # Validate snapshot
        assert "snapshot_json" in data
        assert data["snapshot_json"] is not None
        
        # Validate annex count
        assert "annex_count" in data
        assert data["annex_count"] >= 1
        
        print(f"✅ Agreement {data['contract_number']} retrieved with {data['annex_count']} annexes")
    
    def test_get_agreement_not_found(self, api_client):
        """Test GET /api/agreements/{id} - Agreement not found"""
        response = api_client.get(f"{BASE_URL}/api/agreements/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
        
        print("✅ Correctly returns 404 for non-existent agreement")
    
    def test_get_active_agreement_for_payer(self, api_client):
        """Test GET /api/agreements/active/{payer_profile_id} - Get active agreement"""
        response = api_client.get(f"{BASE_URL}/api/agreements/active/{TEST_PAYER_PROFILE_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exists"] == True
        assert data["contract_number"] == "MA-2026-001"
        assert data["id"] == EXISTING_AGREEMENT_ID
        assert "valid_from" in data
        assert "valid_until" in data
        assert "signed_at" in data
        
        print(f"✅ Active agreement found: {data['contract_number']}")
    
    def test_get_active_agreement_for_payer_without_agreement(self, api_client):
        """Test GET /api/agreements/active/{payer_profile_id} - No active agreement"""
        # Use a payer ID that doesn't have an agreement
        response = api_client.get(f"{BASE_URL}/api/agreements/active/99999")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exists"] == False
        assert "message" in data
        
        print("✅ Correctly returns exists=false for payer without agreement")
    
    def test_create_agreement_duplicate_check(self, api_client):
        """Test POST /api/agreements/create - Should fail for payer with existing active agreement"""
        payload = {
            "payer_profile_id": TEST_PAYER_PROFILE_ID,
            "template_version": "v1",
            "valid_months": 12
        }
        
        response = api_client.post(f"{BASE_URL}/api/agreements/create", json=payload)
        
        # Should fail because payer 1 already has an active agreement
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "already exists" in data["detail"].lower() or "MA-2026-001" in data["detail"]
        
        print("✅ Correctly prevents duplicate agreement creation")
    
    def test_update_agreement_status(self, api_client):
        """Test PUT /api/agreements/{id} - Update agreement note (non-destructive test)"""
        # Update only the note to avoid changing status
        payload = {
            "note": f"Test note updated at {datetime.now().isoformat()}"
        }
        
        response = api_client.put(f"{BASE_URL}/api/agreements/{EXISTING_AGREEMENT_ID}", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify the update
        verify_response = api_client.get(f"{BASE_URL}/api/agreements/{EXISTING_AGREEMENT_ID}")
        verify_data = verify_response.json()
        assert "Test note updated" in verify_data["note"]
        
        print("✅ Agreement note updated successfully")
    
    def test_update_agreement_invalid_status(self, api_client):
        """Test PUT /api/agreements/{id} - Invalid status should fail"""
        payload = {
            "status": "invalid_status"
        }
        
        response = api_client.put(f"{BASE_URL}/api/agreements/{EXISTING_AGREEMENT_ID}", json=payload)
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "invalid status" in data["detail"].lower()
        
        print("✅ Correctly rejects invalid status")


# ============================================================
# ORDER ANNEXES API TESTS
# ============================================================

class TestOrderAnnexesAPI:
    """Order Annexes API tests"""
    
    def test_list_annexes(self, api_client):
        """Test GET /api/annexes - List all annexes"""
        response = api_client.get(f"{BASE_URL}/api/annexes")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "annexes" in data
        assert isinstance(data["annexes"], list)
        assert len(data["annexes"]) >= 1
        
        # Validate annex structure
        annex = data["annexes"][0]
        assert "id" in annex
        assert "order_id" in annex
        assert "master_agreement_id" in annex
        assert "annex_number" in annex
        assert "version" in annex
        assert "status" in annex
        
        print(f"✅ Found {len(data['annexes'])} annexes")
    
    def test_list_annexes_filter_by_order(self, api_client):
        """Test GET /api/annexes?order_id=7325 - Filter by order"""
        response = api_client.get(f"{BASE_URL}/api/annexes?order_id={TEST_ORDER_WITH_PAYER}")
        
        assert response.status_code == 200
        data = response.json()
        
        # All annexes should belong to order 7325
        for annex in data["annexes"]:
            assert annex["order_id"] == TEST_ORDER_WITH_PAYER
        
        print(f"✅ Found {len(data['annexes'])} annexes for order {TEST_ORDER_WITH_PAYER}")
    
    def test_list_annexes_filter_by_agreement(self, api_client):
        """Test GET /api/annexes?master_agreement_id=1 - Filter by agreement"""
        response = api_client.get(f"{BASE_URL}/api/annexes?master_agreement_id={EXISTING_AGREEMENT_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # All annexes should belong to agreement 1
        for annex in data["annexes"]:
            assert annex["master_agreement_id"] == EXISTING_AGREEMENT_ID
        
        print(f"✅ Found {len(data['annexes'])} annexes for agreement {EXISTING_AGREEMENT_ID}")
    
    def test_get_single_annex(self, api_client):
        """Test GET /api/annexes/{id} - Get single annex with full snapshot"""
        response = api_client.get(f"{BASE_URL}/api/annexes/{EXISTING_ANNEX_ID}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate annex structure
        assert data["id"] == EXISTING_ANNEX_ID
        assert data["annex_number"] == "MA-2026-001-A001"
        assert data["order_id"] == TEST_ORDER_WITH_PAYER
        assert data["master_agreement_id"] == EXISTING_AGREEMENT_ID
        assert data["version"] == 1
        assert data["status"] == "generated"
        
        # Validate snapshot
        assert "snapshot" in data
        snapshot = data["snapshot"]
        assert "items" in snapshot
        assert "order" in snapshot
        assert "payer" in snapshot
        assert "period" in snapshot
        assert "totals" in snapshot
        
        # Validate items in snapshot
        assert len(snapshot["items"]) > 0
        item = snapshot["items"][0]
        assert "name" in item
        assert "quantity" in item
        assert "price_per_day" in item
        
        print(f"✅ Annex {data['annex_number']} retrieved with {len(snapshot['items'])} items")
    
    def test_get_annex_not_found(self, api_client):
        """Test GET /api/annexes/{id} - Annex not found"""
        response = api_client.get(f"{BASE_URL}/api/annexes/99999")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        
        print("✅ Correctly returns 404 for non-existent annex")
    
    def test_get_latest_annex_for_order(self, api_client):
        """Test GET /api/annexes/latest/{order_id} - Get latest annex"""
        response = api_client.get(f"{BASE_URL}/api/annexes/latest/{TEST_ORDER_WITH_PAYER}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exists"] == True
        # Annex number should start with MA-2026-001-A
        assert data["annex_number"].startswith("MA-2026-001-A")
        # Version should be at least 1
        assert data["version"] >= 1
        assert "snapshot" in data
        
        print(f"✅ Latest annex for order {TEST_ORDER_WITH_PAYER}: {data['annex_number']} (v{data['version']})")
    
    def test_get_latest_annex_for_order_without_annex(self, api_client):
        """Test GET /api/annexes/latest/{order_id} - No annex exists"""
        response = api_client.get(f"{BASE_URL}/api/annexes/latest/{TEST_ORDER_WITHOUT_PAYER}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exists"] == False
        
        print("✅ Correctly returns exists=false for order without annex")
    
    def test_get_annex_history_for_order(self, api_client):
        """Test GET /api/annexes/history/{order_id} - Get all versions"""
        response = api_client.get(f"{BASE_URL}/api/annexes/history/{TEST_ORDER_WITH_PAYER}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["order_id"] == TEST_ORDER_WITH_PAYER
        assert "versions" in data
        assert "total" in data
        assert data["total"] >= 1
        
        # Versions should be ordered by version DESC
        versions = data["versions"]
        for i in range(len(versions) - 1):
            assert versions[i]["version"] >= versions[i + 1]["version"]
        
        print(f"✅ Found {data['total']} annex versions for order {TEST_ORDER_WITH_PAYER}")
    
    def test_generate_annex_order_without_payer_fails(self, api_client):
        """Test POST /api/annexes/generate-for-order/{order_id} - Fails when order has no payer"""
        response = api_client.post(f"{BASE_URL}/api/annexes/generate-for-order/{TEST_ORDER_WITHOUT_PAYER}")
        
        # Should fail because order 7326 has no payer and wrong status
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        # Either "no payer" or "status" error
        assert "payer" in data["detail"].lower() or "status" in data["detail"].lower()
        
        print("✅ Correctly fails to generate annex for order without payer/wrong status")
    
    def test_generate_annex_duplicate_check(self, api_client):
        """Test POST /api/annexes/generate-for-order/{order_id} - Creates new version"""
        # This should create a new version (v2) for order 7325
        response = api_client.post(f"{BASE_URL}/api/annexes/generate-for-order/{TEST_ORDER_WITH_PAYER}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] == True
        assert "annex_id" in data
        assert "annex_number" in data
        assert "version" in data
        # Version should be >= 2 since v1 already exists
        assert data["version"] >= 2
        
        print(f"✅ New annex version created: {data['annex_number']} (v{data['version']})")
    
    def test_update_annex_status(self, api_client):
        """Test PUT /api/annexes/{id}/status - Update annex status"""
        response = api_client.put(
            f"{BASE_URL}/api/annexes/{EXISTING_ANNEX_ID}/status?status=signed"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        
        # Verify the update
        verify_response = api_client.get(f"{BASE_URL}/api/annexes/{EXISTING_ANNEX_ID}")
        verify_data = verify_response.json()
        assert verify_data["status"] == "signed"
        
        # Reset back to generated
        api_client.put(f"{BASE_URL}/api/annexes/{EXISTING_ANNEX_ID}/status?status=generated")
        
        print("✅ Annex status updated successfully")
    
    def test_update_annex_invalid_status(self, api_client):
        """Test PUT /api/annexes/{id}/status - Invalid status should fail"""
        response = api_client.put(
            f"{BASE_URL}/api/annexes/{EXISTING_ANNEX_ID}/status?status=invalid"
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        
        print("✅ Correctly rejects invalid annex status")


# ============================================================
# DOCUMENT POLICY API TESTS
# ============================================================

class TestDocumentPolicyAPI:
    """Document Policy Matrix API tests"""
    
    def test_get_policy_matrix(self, api_client):
        """Test GET /api/documents/policy/matrix - Get full policy matrix"""
        response = api_client.get(f"{BASE_URL}/api/documents/policy/matrix")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "policies" in data
        assert "categories" in data
        
        # Validate categories
        expected_categories = ["quote", "contract", "annex", "act", "finance", "operations"]
        assert data["categories"] == expected_categories
        
        # Validate policies structure
        policies = data["policies"]
        assert len(policies) >= 15  # Should have many document types
        
        # Check some key document types exist
        assert "quote" in policies
        assert "master_agreement" in policies
        assert "annex" in policies
        assert "invoice_legal" in policies
        
        # Validate policy structure
        annex_policy = policies["annex"]
        assert annex_policy["name"] == "Додаток до договору"
        assert annex_policy["category"] == "annex"
        assert annex_policy["is_legal"] == True
        assert annex_policy["requires_master_agreement"] == True
        
        print(f"✅ Policy matrix retrieved with {len(policies)} document types")
    
    def test_check_document_availability_annex_with_payer(self, api_client):
        """Test GET /api/documents/policy/check/annex - Annex available for order with payer"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/check/annex?order_id={TEST_ORDER_WITH_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["doc_type"] == "annex"
        assert data["available"] == True
        
        # Validate context
        assert "context" in data
        context = data["context"]
        assert context["order"]["order_id"] == TEST_ORDER_WITH_PAYER
        assert context["order"]["payer_profile_id"] == TEST_PAYER_PROFILE_ID
        assert context["payer"]["payer_type"] == "fop_simple"
        assert context["agreement"]["status"] == "signed"
        
        print("✅ Annex is available for order with payer and signed agreement")
    
    def test_check_document_availability_annex_without_payer(self, api_client):
        """Test GET /api/documents/policy/check/annex - Annex not available for order without payer"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/check/annex?order_id={TEST_ORDER_WITHOUT_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["doc_type"] == "annex"
        assert data["available"] == False
        assert "reason" in data
        # Should fail due to status or missing payer
        
        # Validate context shows no payer
        context = data["context"]
        assert context["order"]["payer_profile_id"] is None
        assert context["payer"] is None
        assert context["agreement"] is None
        
        print(f"✅ Annex correctly unavailable: {data['reason']}")
    
    def test_check_document_availability_invoice_legal(self, api_client):
        """Test GET /api/documents/policy/check/invoice_legal - Legal invoice for FOP"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/check/invoice_legal?order_id={TEST_ORDER_WITH_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["doc_type"] == "invoice_legal"
        # Should be available for fop_simple with signed agreement
        assert data["available"] == True
        
        print("✅ Legal invoice available for FOP with signed agreement")
    
    def test_check_document_availability_contract_rent(self, api_client):
        """Test GET /api/documents/policy/check/contract_rent - Rent contract for individual only"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/check/contract_rent?order_id={TEST_ORDER_WITH_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["doc_type"] == "contract_rent"
        # Should NOT be available for fop_simple (only for individual)
        assert data["available"] == False
        assert "reason" in data
        assert "fop_simple" in data["reason"].lower() or "платника" in data["reason"].lower()
        
        print(f"✅ Rent contract correctly unavailable for FOP: {data['reason']}")
    
    def test_get_available_documents_for_order(self, api_client):
        """Test GET /api/documents/policy/available - Get all available documents for order"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/available?order_id={TEST_ORDER_WITH_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["order_id"] == TEST_ORDER_WITH_PAYER
        assert "documents" in data
        assert "by_category" in data
        assert "context" in data
        
        # Validate context
        context = data["context"]
        assert context["order_status"] == "issued"
        assert context["deal_mode"] == "rent"
        assert context["has_payer"] == True
        assert context["payer_type"] == "fop_simple"
        assert context["has_agreement"] == True
        assert context["has_annex"] == True
        
        # Count available documents
        available_docs = [d for d in data["documents"] if d["available"]]
        unavailable_docs = [d for d in data["documents"] if not d["available"]]
        
        print(f"✅ Found {len(available_docs)} available and {len(unavailable_docs)} unavailable documents")
        
        # Validate by_category structure
        assert "quote" in data["by_category"]
        assert "contract" in data["by_category"]
        assert "annex" in data["by_category"]
        assert "act" in data["by_category"]
        assert "finance" in data["by_category"]
        assert "operations" in data["by_category"]
    
    def test_get_available_documents_order_not_found(self, api_client):
        """Test GET /api/documents/policy/available - Order not found"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/available?order_id=99999"
        )
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        
        print("✅ Correctly returns 404 for non-existent order")
    
    def test_document_availability_based_on_order_status(self, api_client):
        """Test document availability changes based on order status"""
        # Order 7325 is in 'issued' status
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/available?order_id={TEST_ORDER_WITH_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Find specific documents and check their availability
        docs_by_type = {d["doc_type"]: d for d in data["documents"]}
        
        # Quote should NOT be available for 'issued' status
        assert docs_by_type["quote"]["available"] == False
        assert "issued" in docs_by_type["quote"]["reason"]
        
        # Issue act SHOULD be available for 'issued' status
        assert docs_by_type["issue_act"]["available"] == True
        
        # Return act should NOT be available for 'issued' status (needs returning/returned/closed)
        assert docs_by_type["return_act"]["available"] == False
        
        # Annex SHOULD be available for 'issued' status
        assert docs_by_type["annex"]["available"] == True
        
        print("✅ Document availability correctly reflects order status 'issued'")
    
    def test_document_availability_payer_type_restrictions(self, api_client):
        """Test document availability based on payer type"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/available?order_id={TEST_ORDER_WITH_PAYER}"
        )
        
        assert response.status_code == 200
        data = response.json()
        
        docs_by_type = {d["doc_type"]: d for d in data["documents"]}
        
        # Payer is fop_simple
        # invoice_offer is only for 'individual' - should NOT be available
        assert docs_by_type["invoice_offer"]["available"] == False
        
        # contract_rent is only for 'individual' - should NOT be available
        assert docs_by_type["contract_rent"]["available"] == False
        
        # invoice_legal is for fop_simple - SHOULD be available
        assert docs_by_type["invoice_legal"]["available"] == True
        
        # goods_invoice is for fop_general/llc_general - should NOT be available
        assert docs_by_type["goods_invoice"]["available"] == False
        
        print("✅ Document availability correctly reflects payer type 'fop_simple'")


# ============================================================
# INTEGRATION TESTS
# ============================================================

class TestDocumentsEngineIntegration:
    """Integration tests for Documents Engine"""
    
    def test_agreement_annex_relationship(self, api_client):
        """Test that annexes are correctly linked to agreements"""
        # Get agreement
        agreement_response = api_client.get(f"{BASE_URL}/api/agreements/{EXISTING_AGREEMENT_ID}")
        assert agreement_response.status_code == 200
        agreement = agreement_response.json()
        
        # Get annexes for this agreement
        annexes_response = api_client.get(
            f"{BASE_URL}/api/annexes?master_agreement_id={EXISTING_AGREEMENT_ID}"
        )
        assert annexes_response.status_code == 200
        annexes = annexes_response.json()["annexes"]
        
        # Annex count should match
        assert len(annexes) == agreement["annex_count"]
        
        # All annexes should reference the same contract number
        for annex in annexes:
            assert annex["contract_number"] == agreement["contract_number"]
        
        print(f"✅ Agreement {agreement['contract_number']} has {len(annexes)} linked annexes")
    
    def test_annex_snapshot_immutability(self, api_client):
        """Test that annex snapshot contains immutable data"""
        response = api_client.get(f"{BASE_URL}/api/annexes/{EXISTING_ANNEX_ID}")
        assert response.status_code == 200
        annex = response.json()
        
        snapshot = annex["snapshot"]
        
        # Snapshot should contain all required data
        assert "contract_number" in snapshot
        assert "payer" in snapshot
        assert "order" in snapshot
        assert "items" in snapshot
        assert "period" in snapshot
        assert "totals" in snapshot
        assert "generated_at" in snapshot
        
        # Payer snapshot should have full details
        payer = snapshot["payer"]
        assert "company_name" in payer
        assert "payer_type" in payer
        assert "edrpou" in payer
        assert "iban" in payer
        
        # Order snapshot should have key details
        order = snapshot["order"]
        assert "order_id" in order
        assert "order_number" in order
        assert "customer_name" in order
        
        print("✅ Annex snapshot contains all required immutable data")
    
    def test_policy_context_completeness(self, api_client):
        """Test that policy check returns complete context"""
        response = api_client.get(
            f"{BASE_URL}/api/documents/policy/check/annex?order_id={TEST_ORDER_WITH_PAYER}"
        )
        assert response.status_code == 200
        data = response.json()
        
        context = data["context"]
        
        # Order context
        assert context["order"]["order_id"] == TEST_ORDER_WITH_PAYER
        assert context["order"]["status"] == "issued"
        assert context["order"]["deal_mode"] == "rent"
        assert "deposit_held" in context["order"]
        assert "has_damage" in context["order"]
        assert "has_issue_card" in context["order"]
        
        # Payer context
        assert context["payer"]["id"] == TEST_PAYER_PROFILE_ID
        assert context["payer"]["payer_type"] == "fop_simple"
        
        # Agreement context
        assert context["agreement"]["id"] == EXISTING_AGREEMENT_ID
        assert context["agreement"]["status"] == "signed"
        assert context["agreement"]["is_expired"] == False
        
        # Annex context - ID may change as new versions are created
        assert context["annex"]["id"] >= EXISTING_ANNEX_ID  # At least the original or newer
        assert context["annex"]["status"] in ["generated", "signed"]
        assert "annex_number" in context["annex"]
        assert "version" in context["annex"]
        
        print("✅ Policy check returns complete context for all entities")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
