# import pytest
# from fastapi import status
#
# from tests.common import async_client
#
# # Sample test data
# sample_product = {
#     "id": "test-product-1",
#     "title": "Test Product",
#     "custom_data": {
#         "id": "test-product-1",
#         "title": "Test Product",
#         "description": "This is a test product",
#         "price": 99.99,
#         "category": "Test Category"
#     },
#     "searchable_content": "Test Product This is a test product Test Category"
# }
#
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
#         }
#     ]
# }
#
# @pytest.mark.asyncio
# async def test_create_products(async_client):
#     """Test creating products endpoint"""
#     response = await async_client.post("/api/v1/products", json=sample_product_input)
#     assert response.status_code == status.HTTP_201_CREATED
#     data = response.json()
#     assert data["message"] == "Products created successfully"
#     assert data["count"] == 1
#
# @pytest.mark.asyncio
# async def test_get_product(async_client):
#     """Test getting a single product by ID"""
#     # First create a product
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Then get the product
#     response = await async_client.get(f"/api/v1/products/{sample_product['id']}")
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert data["id"] == sample_product["id"]
#     assert data["title"] == sample_product["title"]
#     assert data["custom_data"] == sample_product["custom_data"]
#
# @pytest.mark.asyncio
# async def test_list_products(async_client):
#     """Test listing all products with pagination"""
#     # Create a product first if not exists
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Test listing products
#     response = await async_client.get("/api/v1/products?page=1&size=10")
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "items" in data
#     assert "total" in data
#     assert "page" in data
#     assert "size" in data
#     assert data["page"] == 1
#     assert data["size"] == 10
#     assert len(data["items"]) > 0
#
# @pytest.mark.asyncio
# async def test_update_product(async_client):
#     """Test updating a product"""
#     updated_product = sample_product.copy()
#     updated_product["title"] = "Updated Test Product"
#     updated_product["custom_data"]["title"] = "Updated Test Product"
#     updated_product["custom_data"]["price"] = 129.99
#
#     # Create the product first
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Update the product
#     response = await async_client.put(f"/api/v1/products/{sample_product['id']}", json=updated_product)
#     assert response.status_code == status.HTTP_200_OK
#
#     # Verify the update
#     data = response.json()
#     assert data["title"] == "Updated Test Product"
#     assert data["custom_data"]["price"] == 129.99
#
# @pytest.mark.asyncio
# async def test_delete_product(async_client):
#     """Test deleting a product"""
#     # Create the product first
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Delete the product
#     response = await async_client.delete(f"/api/v1/products/{sample_product['id']}")
#     assert response.status_code == status.HTTP_200_OK
#
#     # Verify it's deleted
#     get_response = await async_client.get(f"/api/v1/products/{sample_product['id']}")
#     assert get_response.status_code == status.HTTP_404_NOT_FOUND
#
# @pytest.mark.asyncio
# async def test_delete_all_products(async_client):
#     """Test deleting all products"""
#     # Create a product first
#     await async_client.post("/api/v1/products", json=sample_product_input)
#
#     # Delete all products
#     response = await async_client.delete("/api/v1/products")
#     assert response.status_code == status.HTTP_200_OK
#
#     # Verify all are deleted by checking the list
#     list_response = await async_client.get("/api/v1/products")
#     list_data = list_response.json()
#     assert list_data["total"] == 0
#     assert len(list_data["items"]) == 0