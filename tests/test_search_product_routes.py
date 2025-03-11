# import pytest
# from fastapi import status
#
# from tests.common import async_client
#
# # Sample test data - same as in test_product_routes.py
# sample_product_input = {
#     "id_field": "id",
#     "title_field": "title",
#     "searchable_attribute_fields": ["title", "description", "category"],
#     "data": [
#         {
#             "id": "test-product-1",
#             "title": "Test Product",
#             "description": "This is a test product",
#             "price": 99.99,
#             "category": "Test Category"
#         },
#         {
#             "id": "test-product-2",
#             "title": "Another Test Product",
#             "description": "This is another test product for searching",
#             "price": 149.99,
#             "category": "Test Category"
#         }
#     ]
# }
#
# @pytest.mark.asyncio
# async def test_hybrid_search(async_client):
#     """Test hybrid search endpoint"""
#     # First create some products
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test hybrid search
#     response = await async_client.get("/api/v1/search/products?q=test+product")
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "items" in data
#     assert "total" in data
#     assert "page" in data
#     assert "size" in data
#     assert isinstance(data["items"], list)
#     assert len(data["items"]) > 0
#
#     # Check if our products are in the results
#     product_ids = [item["id"] for item in data["items"]]
#     assert "test-product-1" in product_ids
#     assert "test-product-2" in product_ids
#
# @pytest.mark.asyncio
# async def test_full_text_search(async_client):
#     """Test full text search endpoint"""
#     # First create some products
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test full text search
#     response = await async_client.get("/api/v1/search/products/full-text?q=test+product")
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "items" in data
#     assert "total" in data
#     assert "page" in data
#     assert "size" in data
#     assert isinstance(data["items"], list)
#     assert len(data["items"]) > 0
#
#     # Check if our products are in the results
#     product_ids = [item["id"] for item in data["items"]]
#     assert "test-product-1" in product_ids
#     assert "test-product-2" in product_ids
#
# @pytest.mark.asyncio
# async def test_autocomplete_search(async_client):
#     """Test autocomplete search endpoint"""
#     # First create some products
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test autocomplete search
#     response = await async_client.get("/api/v1/search/products/autocomplete?q=test")
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "items" in data
#     assert "total" in data
#     assert isinstance(data["items"], list)
#     assert len(data["items"]) > 0
#
#     # Check if our products are in the results
#     product_ids = [item["id"] for item in data["items"]]
#     assert "test-product-1" in product_ids
#     assert "test-product-2" in product_ids
#
# @pytest.mark.asyncio
# async def test_search_with_parameters(async_client):
#     """Test search with parameters"""
#     # First create some products
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test search with parameters
#     response = await async_client.get(
#         "/api/v1/search/products?q=test+product&page=1&size=1&full_text_weight=0.7&semantic_weight=0.3"
#     )
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert data["page"] == 1
#     assert data["size"] == 1
#     assert len(data["items"]) <= 1  # Should respect the size parameter