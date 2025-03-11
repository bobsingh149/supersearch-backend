import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from app.main import app

@pytest_asyncio.fixture
async def async_client():
    """
    Fixture that provides an AsyncClient for testing FastAPI endpoints.
    This can be imported and used across all test files.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client 