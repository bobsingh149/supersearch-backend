# import pytest
# from fastapi import status
#
# from tests.common import async_client
#
# # Sample test data - similar to test_product_routes.py but with multiple products
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
#             "title": "Similar Test Product",
#             "description": "This is a similar test product",
#             "price": 89.99,
#             "category": "Test Category"
#         },
#         {
#             "id": "test-product-3",
#             "title": "Different Product",
#             "description": "This is a completely different product",
#             "price": 199.99,
#             "category": "Different Category"
#         }
#     ]
# }
#
# @pytest.mark.asyncio
# async def test_get_similar_products(async_client):
#     """Test getting similar products"""
#     # First create some products
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test getting similar products
#     response = await async_client.get(
#         f"/api/v1/recommend/similar-products/{sample_product_input['data'][0]['id']}"
#     )
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "items" in data
#     assert "total" in data
#     assert isinstance(data["items"], list)
#     assert len(data["items"]) > 0
#
#     # The second product should be in the results since it's similar
#     found_similar = False
#     for item in data["items"]:
#         if item["id"] == sample_product_input["data"][1]["id"]:
#             found_similar = True
#             break
#
#     assert found_similar, "Similar product not found in recommendations"
#
# @pytest.mark.asyncio
# async def test_get_similar_products_with_parameters(async_client):
#     """Test getting similar products with limit and threshold parameters"""
#     # First create some products
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test getting similar products with parameters
#     response = await async_client.get(
#         f"/api/v1/recommend/similar-products/{sample_product_input['data'][0]['id']}?limit=1&threshold=0.5"
#     )
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "items" in data
#     assert len(data["items"]) <= 1  # Should respect the limit parameter
#
# @pytest.mark.asyncio
# async def test_get_similar_products_not_found(async_client):
#     """Test getting similar products for a non-existent product"""
#     response = await async_client.get(
#         "/api/v1/recommend/similar-products/non-existent-product"
#     )
#     assert response.status_code == status.HTTP_404_NOT_FOUND