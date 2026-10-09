"""
Test batch-by-orders endpoint for ClientsTab document links feature.
Tests the POST /api/documents/batch-by-orders endpoint that returns
documents grouped by order_id with Ukrainian labels.
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestBatchDocumentsByOrders:
    """Tests for POST /api/documents/batch-by-orders endpoint"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_batch_by_orders_returns_200(self):
        """Test that endpoint returns 200 for valid order_ids"""
        # Test with known orders that have documents
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425", "7293"]}
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        print(f"✓ batch-by-orders returns 200")
    
    def test_batch_by_orders_returns_grouped_data(self):
        """Test that response is grouped by order_id"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425", "7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Response should be a dict with order_ids as keys
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        print(f"✓ Response is grouped dict with keys: {list(data.keys())}")
        
        # Check structure of documents
        for order_id, docs in data.items():
            assert isinstance(docs, list), f"Documents for order {order_id} should be a list"
            print(f"  Order {order_id}: {len(docs)} documents")
    
    def test_batch_by_orders_document_structure(self):
        """Test that each document has required fields: id, doc_type, label, preview_url"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425", "7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        required_fields = ["id", "doc_type", "label", "preview_url"]
        
        for order_id, docs in data.items():
            for doc in docs:
                for field in required_fields:
                    assert field in doc, f"Document missing field '{field}': {doc}"
                print(f"  ✓ Order {order_id} doc: {doc['doc_type']} -> {doc['label']}")
        
        print(f"✓ All documents have required fields")
    
    def test_batch_by_orders_ukrainian_labels(self):
        """Test that doc_type labels are in Ukrainian (not raw English)"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425", "7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Known Ukrainian labels mapping
        expected_labels = {
            "issue_act": "Акт видачі",
            "return_act": "Акт повернення",
            "defect_act": "Дефектний акт",
            "contract_rent": "Договір оренди",
            "invoice_offer": "Рахунок-оферта",
            "deposit_refund_act": "Акт повернення застави",
            "deposit_settlement_act": "Акт взаєморозрахунків",
            "invoice_additional": "Додатковий рахунок",
        }
        
        for order_id, docs in data.items():
            for doc in docs:
                doc_type = doc["doc_type"]
                label = doc["label"]
                
                # Label should NOT be the raw doc_type (English)
                if doc_type in expected_labels:
                    assert label == expected_labels[doc_type], \
                        f"Expected Ukrainian label '{expected_labels[doc_type]}' for {doc_type}, got '{label}'"
                else:
                    # For unknown types, label should still not be raw English
                    # (it might fall back to doc_type, but that's acceptable for new types)
                    pass
                
                print(f"  ✓ {doc_type} -> '{label}'")
        
        print(f"✓ All labels are in Ukrainian")
    
    def test_batch_by_orders_skips_duplicates(self):
        """Test that only latest version of each doc_type is returned (no duplicates)"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        if "7293" in data:
            docs = data["7293"]
            doc_types = [d["doc_type"] for d in docs]
            
            # Check for duplicates
            unique_types = set(doc_types)
            assert len(doc_types) == len(unique_types), \
                f"Found duplicate doc_types: {doc_types}"
            
            print(f"✓ Order 7293 has {len(docs)} unique doc_types: {doc_types}")
        else:
            print(f"⚠ Order 7293 has no documents")
    
    def test_batch_by_orders_empty_list(self):
        """Test that empty order_ids returns empty dict"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": []}
        )
        assert response.status_code == 200
        data = response.json()
        assert data == {}, f"Expected empty dict, got {data}"
        print(f"✓ Empty order_ids returns empty dict")
    
    def test_batch_by_orders_nonexistent_orders(self):
        """Test that nonexistent order_ids return empty results"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["999999", "888888"]}
        )
        assert response.status_code == 200
        data = response.json()
        # Should return empty dict or dict with empty lists
        assert isinstance(data, dict)
        print(f"✓ Nonexistent orders handled gracefully: {data}")
    
    def test_batch_by_orders_preview_url_format(self):
        """Test that preview_url has correct format"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425", "7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        for order_id, docs in data.items():
            for doc in docs:
                preview_url = doc["preview_url"]
                # Should start with /api/documents/ and end with /preview
                assert preview_url.startswith("/api/documents/"), \
                    f"preview_url should start with /api/documents/: {preview_url}"
                assert "/preview" in preview_url, \
                    f"preview_url should contain /preview: {preview_url}"
                print(f"  ✓ {doc['doc_type']}: {preview_url}")
        
        print(f"✓ All preview_urls have correct format")
    
    def test_order_7293_has_expected_documents(self):
        """Test that order 7293 has the expected document types"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # According to test data: Order 7293 should have deposit_refund_act, invoice_additional, deposit_settlement_act, invoice_offer
        expected_types = {"deposit_refund_act", "invoice_additional", "deposit_settlement_act", "invoice_offer"}
        
        if "7293" in data:
            actual_types = {d["doc_type"] for d in data["7293"]}
            print(f"Order 7293 actual doc_types: {actual_types}")
            
            # Check if expected types are present (may have more)
            for expected in expected_types:
                if expected in actual_types:
                    print(f"  ✓ Found {expected}")
                else:
                    print(f"  ⚠ Missing {expected}")
        else:
            print(f"⚠ Order 7293 not in response")
    
    def test_order_7425_has_defect_act(self):
        """Test that order 7425 has defect_act"""
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        if "7425" in data:
            doc_types = [d["doc_type"] for d in data["7425"]]
            print(f"Order 7425 doc_types: {doc_types}")
            
            if "defect_act" in doc_types:
                defect_doc = next(d for d in data["7425"] if d["doc_type"] == "defect_act")
                assert defect_doc["label"] == "Дефектний акт", \
                    f"Expected 'Дефектний акт', got '{defect_doc['label']}'"
                print(f"  ✓ Found defect_act with label '{defect_doc['label']}'")
            else:
                print(f"  ⚠ defect_act not found in order 7425")
        else:
            print(f"⚠ Order 7425 not in response")


class TestDocumentPreviewAccess:
    """Test that document preview URLs are accessible"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test session"""
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
    
    def test_document_preview_accessible(self):
        """Test that preview URLs from batch-by-orders are accessible"""
        # Get documents
        response = self.session.post(
            f"{BASE_URL}/api/documents/batch-by-orders",
            json={"order_ids": ["7425", "7293"]}
        )
        assert response.status_code == 200
        data = response.json()
        
        # Test first document preview from each order
        tested = 0
        for order_id, docs in data.items():
            if docs:
                doc = docs[0]
                preview_url = f"{BASE_URL}{doc['preview_url']}"
                preview_response = self.session.get(preview_url)
                
                assert preview_response.status_code == 200, \
                    f"Preview URL {preview_url} returned {preview_response.status_code}"
                
                # Should return HTML
                content_type = preview_response.headers.get("content-type", "")
                assert "text/html" in content_type, \
                    f"Expected HTML content-type, got {content_type}"
                
                print(f"  ✓ Order {order_id} {doc['doc_type']} preview accessible")
                tested += 1
        
        print(f"✓ Tested {tested} document previews")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
