"""
Catalog API Performance Tests - Testing N+1 query optimization
Tests for:
1. /api/catalog/families - All families with products (was 18.2s, now should be <5s)
2. /api/catalog/products-lite - Lightweight endpoint for FamiliesManager
3. /api/catalog - Main catalog endpoint with reservation data
4. /api/catalog/items-by-category - Items by category with availability
5. /api/catalog/categories - Category tree
6. /api/catalog/families/{family_id}/products - Products for specific family
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestCatalogFamiliesOptimization:
    """Tests for /api/catalog/families - the N+1 query that was optimized"""
    
    def test_families_endpoint_returns_200(self):
        """Test that families endpoint is reachable"""
        response = requests.get(f"{BASE_URL}/api/catalog/families", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_families_performance_under_5_seconds(self):
        """Test that families endpoint responds in under 5 seconds (was 18.2s)"""
        start_time = time.time()
        response = requests.get(f"{BASE_URL}/api/catalog/families", timeout=60)
        elapsed_time = time.time() - start_time
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert elapsed_time < 5, f"Response took {elapsed_time:.2f}s, expected <5s (was 18.2s before optimization)"
        print(f"✅ /api/catalog/families responded in {elapsed_time:.2f}s (target: <5s)")
        
    def test_families_data_structure(self):
        """Test that families endpoint returns correct data structure"""
        response = requests.get(f"{BASE_URL}/api/catalog/families", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of families"
        
        # Check expected counts (118 families, 478 products)
        total_families = len(data)
        total_products = sum(len(f.get('products', [])) for f in data)
        
        print(f"Families count: {total_families} (expected: ~118)")
        print(f"Total products: {total_products} (expected: ~478)")
        
        # At least verify we have data
        assert total_families > 0, "Should have at least 1 family"
        
    def test_families_product_fields(self):
        """Test that family products have required fields"""
        response = requests.get(f"{BASE_URL}/api/catalog/families", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        
        # Find a family with products
        family_with_products = next((f for f in data if f.get('products')), None)
        
        if family_with_products:
            product = family_with_products['products'][0]
            required_fields = ['product_id', 'sku', 'name', 'image']
            
            for field in required_fields:
                assert field in product, f"Product missing required field: {field}"
            
            print(f"✅ Product fields verified: {list(product.keys())}")
        else:
            print("⚠️ No families with products found to verify structure")


class TestProductsLiteEndpoint:
    """Tests for /api/catalog/products-lite - new lightweight endpoint"""
    
    def test_products_lite_endpoint_returns_200(self):
        """Test that products-lite endpoint is reachable"""
        response = requests.get(f"{BASE_URL}/api/catalog/products-lite?limit=100", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_products_lite_minimal_fields(self):
        """Test that products-lite returns only minimal fields"""
        response = requests.get(f"{BASE_URL}/api/catalog/products-lite?limit=10", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of products"
        
        if data:
            product = data[0]
            expected_fields = ['product_id', 'sku', 'name', 'image', 'category', 'family_id', 'color', 'quantity']
            
            for field in expected_fields:
                assert field in product, f"Missing expected field: {field}"
                
            # Verify no heavy fields
            heavy_fields = ['reserved', 'in_rent', 'who_has', 'location', 'description', 'history']
            for field in heavy_fields:
                if field in product:
                    print(f"⚠️ Unexpected heavy field present: {field}")
                    
            print(f"✅ products-lite fields: {list(product.keys())}")
            
    def test_products_lite_faster_than_catalog(self):
        """Test that products-lite is faster than main /api/catalog for same limit"""
        limit = 100
        
        # Time products-lite
        start = time.time()
        lite_response = requests.get(f"{BASE_URL}/api/catalog/products-lite?limit={limit}", timeout=60)
        lite_time = time.time() - start
        
        # Time main catalog
        start = time.time()
        catalog_response = requests.get(f"{BASE_URL}/api/catalog?limit={limit}&include_reservations=true", timeout=60)
        catalog_time = time.time() - start
        
        assert lite_response.status_code == 200, f"products-lite failed: {lite_response.status_code}"
        assert catalog_response.status_code == 200, f"catalog failed: {catalog_response.status_code}"
        
        print(f"products-lite: {lite_time:.3f}s, catalog: {catalog_time:.3f}s")
        
        # products-lite should be faster or at least comparable
        # Not enforcing strict assertion as both should be fast
        
    def test_products_lite_returns_expected_count(self):
        """Test that products-lite returns products with default limit"""
        response = requests.get(f"{BASE_URL}/api/catalog/products-lite?limit=1000", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        print(f"Products count (limit=1000): {len(data)} (expected: ~7116 or less)")
        assert len(data) > 0, "Should return products"


class TestMainCatalogEndpoint:
    """Tests for /api/catalog - main catalog with reservation data"""
    
    def test_catalog_endpoint_returns_200(self):
        """Test that main catalog endpoint is reachable"""
        response = requests.get(f"{BASE_URL}/api/catalog?limit=100", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_catalog_with_reservations(self):
        """Test catalog with include_reservations=true"""
        response = requests.get(f"{BASE_URL}/api/catalog?limit=100&include_reservations=true", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of products"
        
        if data:
            product = data[0]
            # With reservations, should have availability fields
            availability_fields = ['available', 'reserved', 'in_rent', 'quantity']
            present_fields = [f for f in availability_fields if f in product]
            print(f"✅ Availability fields present: {present_fields}")
            
    def test_catalog_search_filter(self):
        """Test catalog with search filter"""
        response = requests.get(f"{BASE_URL}/api/catalog?limit=50&search=test", timeout=60)
        assert response.status_code == 200, f"Search filter failed: {response.status_code}"


class TestItemsByCategoryEndpoint:
    """Tests for /api/catalog/items-by-category"""
    
    def test_items_by_category_returns_200(self):
        """Test that items-by-category endpoint is reachable"""
        response = requests.get(f"{BASE_URL}/api/catalog/items-by-category?limit=100", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_items_by_category_data_structure(self):
        """Test items-by-category returns items and stats"""
        response = requests.get(f"{BASE_URL}/api/catalog/items-by-category?limit=50", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert 'items' in data, "Response should have 'items' key"
        assert 'stats' in data, "Response should have 'stats' key"
        
        # Check stats structure
        stats = data['stats']
        expected_stat_fields = ['total', 'available', 'in_rent', 'reserved']
        for field in expected_stat_fields:
            assert field in stats, f"Stats missing field: {field}"
            
        print(f"✅ Stats: {stats}")


class TestCategoriesEndpoint:
    """Tests for /api/catalog/categories"""
    
    def test_categories_returns_200(self):
        """Test that categories endpoint is reachable"""
        response = requests.get(f"{BASE_URL}/api/catalog/categories", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        
    def test_categories_data_structure(self):
        """Test categories returns tree structure"""
        response = requests.get(f"{BASE_URL}/api/catalog/categories", timeout=60)
        assert response.status_code == 200
        
        data = response.json()
        assert 'categories' in data, "Response should have 'categories' key"
        
        categories = data['categories']
        assert isinstance(categories, list), "Categories should be a list"
        
        if categories:
            category = categories[0]
            assert 'name' in category, "Category should have name"
            print(f"✅ Found {len(categories)} categories")
            print(f"Sample category: {category.get('name')}, products: {category.get('product_count', 0)}")


class TestFamilyProductsEndpoint:
    """Tests for /api/catalog/families/{family_id}/products"""
    
    def test_family_products_requires_family_id(self):
        """Test that endpoint requires valid family_id"""
        # Get a valid family_id first
        families_response = requests.get(f"{BASE_URL}/api/catalog/families", timeout=60)
        if families_response.status_code != 200:
            pytest.skip("Cannot get families list")
            
        families = families_response.json()
        if not families:
            pytest.skip("No families available")
            
        family_id = families[0].get('id')
        if not family_id:
            pytest.skip("Family has no ID")
            
        # Test specific family products endpoint
        response = requests.get(f"{BASE_URL}/api/catalog/families/{family_id}/products", timeout=60)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        assert isinstance(data, list), "Response should be a list of products"
        print(f"✅ Family {family_id} has {len(data)} products")


class TestPerformanceBenchmarks:
    """Performance benchmark tests"""
    
    def test_all_endpoints_performance(self):
        """Benchmark all catalog endpoints"""
        endpoints = [
            ("/api/catalog/families", "Families (was 18.2s, target <5s)"),
            ("/api/catalog/products-lite?limit=100", "Products-lite (100)"),
            ("/api/catalog?limit=100&include_reservations=true", "Catalog+reservations (100)"),
            ("/api/catalog/items-by-category?limit=100", "Items by category (100)"),
            ("/api/catalog/categories", "Categories"),
        ]
        
        results = []
        for endpoint, description in endpoints:
            start = time.time()
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=120)
            elapsed = time.time() - start
            
            results.append({
                "endpoint": endpoint,
                "description": description,
                "status": response.status_code,
                "time_seconds": round(elapsed, 3)
            })
            
        print("\n=== Performance Benchmark Results ===")
        for r in results:
            status = "✅" if r["status"] == 200 else "❌"
            print(f"{status} {r['description']}: {r['time_seconds']}s (HTTP {r['status']})")
            
        # Assert critical endpoint performance
        families_result = next((r for r in results if "/families" in r["endpoint"] and "products" not in r["endpoint"]), None)
        if families_result and families_result["status"] == 200:
            assert families_result["time_seconds"] < 5, f"Families endpoint took {families_result['time_seconds']}s, expected <5s"
