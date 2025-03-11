import pytest
from fastapi import status

from tests.common import async_client

@pytest.mark.asyncio
async def test_health_check(async_client):
    """Test the health check endpoint"""
    response = await async_client.get("/health")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "message" in data
    assert data["message"] == "server is healthy!" 