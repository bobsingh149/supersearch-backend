# import pytest
# from fastapi import status
# import uuid
#
# from tests.common import async_client
#
# # Sample test data
# sample_organization = {
#     "id": str(uuid.uuid4()),
#     "name": "Test Organization",
#     "description": "This is a test organization",
#     "metadata": {
#         "industry": "Technology",
#         "size": "Small",
#         "location": "Test City"
#     }
# }
#
# @pytest.mark.asyncio
# async def test_create_organization(async_client):
#     """Test creating an organization"""
#     response = await async_client.post(
#         "/api/v1/organizations",
#         json=sample_organization
#     )
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert data["id"] == sample_organization["id"]
#     assert data["name"] == sample_organization["name"]
#
# @pytest.mark.asyncio
# async def test_create_organization_without_id(async_client):
#     """Test creating an organization without providing an ID"""
#     org_without_id = {
#         "name": "Auto ID Organization",
#         "description": "This organization will get an auto-generated ID",
#         "metadata": {
#             "industry": "Healthcare",
#             "size": "Medium",
#             "location": "Test City"
#         }
#     }
#
#     response = await async_client.post(
#         "/api/v1/organizations",
#         json=org_without_id
#     )
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert "id" in data
#     assert data["id"] is not None
#     assert data["name"] == org_without_id["name"]
#
# @pytest.mark.asyncio
# async def test_get_organization(async_client):
#     """Test getting a single organization by ID"""
#     # First create an organization
#     create_response = await async_client.post(
#         "/api/v1/organizations",
#         json=sample_organization
#     )
#     assert create_response.status_code == status.HTTP_200_OK
#
#     # Then get the organization
#     response = await async_client.get(f"/api/v1/organizations/{sample_organization['id']}")
#     assert response.status_code == status.HTTP_200_OK
#
#     data = response.json()
#     assert data["id"] == sample_organization["id"]
#     assert data["name"] == sample_organization["name"]
#
# @pytest.mark.asyncio
# async def test_get_organization_not_found(async_client):
#     """Test getting a non-existent organization"""
#     response = await async_client.get(f"/api/v1/organizations/non-existent-id")
#     assert response.status_code == status.HTTP_404_NOT_FOUND
#
# @pytest.mark.asyncio
# async def test_list_organizations(async_client):
#     """Test listing all organizations with pagination"""
#     # Create an organization first if not exists
#     await async_client.post(
#         "/api/v1/organizations",
#         json=sample_organization
#     )
#
#     # Test listing organizations
#     response = await async_client.get("/api/v1/organizations?page=1&size=10")
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
# async def test_update_organization(async_client):
#     """Test updating an organization"""
#     # First create an organization
#     await async_client.post(
#         "/api/v1/organizations",
#         json=sample_organization
#     )
#
#     # Update data
#     updated_org = sample_organization.copy()
#     updated_org["name"] = "Updated Organization Name"
#     updated_org["metadata"]["size"] = "Large"
#
#     # Update the organization
#     response = await async_client.put(
#         f"/api/v1/organizations/{sample_organization['id']}",
#         json=updated_org
#     )
#     assert response.status_code == status.HTTP_200_OK
#
#     # Verify the update
#     data = response.json()
#     assert data["name"] == "Updated Organization Name"
#     assert data["metadata"]["size"] == "Large"
#
# @pytest.mark.asyncio
# async def test_delete_organization(async_client):
#     """Test deleting an organization"""
#     # First create an organization
#     await async_client.post(
#         "/api/v1/organizations",
#         json=sample_organization
#     )
#
#     # Delete the organization
#     response = await async_client.delete(f"/api/v1/organizations/{sample_organization['id']}")
#     assert response.status_code == status.HTTP_200_OK
#
#     # Verify it's deleted
#     get_response = await async_client.get(f"/api/v1/organizations/{sample_organization['id']}")
#     assert get_response.status_code == status.HTTP_404_NOT_FOUND