# import pytest
# from fastapi import status
# from app.models.sync_config import SyncSource
#
# from tests.common import async_client
#
#
# # Sample test data
# class SyncSourceType:
#     pass
#
#
# sample_sync_input = {
#     "source_type": SyncSource.MANUAL_FILE_UPLOAD.value,
#     "id_field": "id",
#     "title_field": "title",
#     "searchable_attribute_fields": ["title", "description", "category"],
#     "data": [
#         {
#             "id": "sync-test-product-1",
#             "title": "Sync Test Product",
#             "description": "This is a test product for sync",
#             "price": 99.99,
#             "category": "Test Category"
#         }
#     ],
#     "organization_id": "test-org",
#     "schedule": None  # No schedule for immediate sync
# }
#
# @pytest.mark.asyncio
# async def test_sync_products(async_client):
#     """Test syncing products endpoint"""
#     response = await async_client.post("/api/v1/sync/products", json=sample_sync_input)
#     assert response.status_code == status.HTTP_202_ACCEPTED
#
#     data = response.json()
#     assert "message" in data
#     assert "sync_id" in data
#     assert data["message"] == "Sync job started"
#
# @pytest.mark.asyncio
# async def test_sync_products_with_schedule(async_client):
#     """Test syncing products with a schedule"""
#     scheduled_sync_input = sample_sync_input.copy()
#     scheduled_sync_input["schedule"] = {
#         "frequency": "daily",
#         "time": "12:00"
#     }
#
#     response = await async_client.post("/api/v1/sync/products", json=scheduled_sync_input)
#     assert response.status_code == status.HTTP_202_ACCEPTED
#
#     data = response.json()
#     assert "message" in data
#     assert "sync_id" in data
#     assert data["message"] == "Scheduled sync job created"
#
# @pytest.mark.asyncio
# async def test_sync_products_with_invalid_source_type(async_client):
#     """Test syncing products with an invalid source type"""
#     invalid_sync_input = sample_sync_input.copy()
#     invalid_sync_input["source_type"] = "INVALID_SOURCE_TYPE"
#
#     response = await async_client.post("/api/v1/sync/products", json=invalid_sync_input)
#     assert response.status_code == status.HTTP_400_BAD_REQUEST