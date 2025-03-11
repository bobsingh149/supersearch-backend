import asyncio
import pytest
import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text

from app.main import app
from app.database.session import get_async_session, Base
from app.core.settings import settings

# Use the same database but with a test schema
TEST_SCHEMA = "test"
TEST_DATABASE_URL = f"postgresql+asyncpg://{settings.postgres.user}:{settings.postgres.password}@{settings.postgres.host}:{settings.postgres.port}/{settings.postgres.db}"

# Create test engine and session
test_engine = create_async_engine(
    TEST_DATABASE_URL, 
    poolclass=NullPool,
    echo=False
)
TestingSessionLocal = sessionmaker(
    test_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

# Override the get_async_session dependency
async def override_get_async_session():
    async with TestingSessionLocal() as session:
        # Set the search path to the test schema for this session
        await session.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        yield session

app.dependency_overrides[get_async_session] = override_get_async_session

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def setup_database():
    # Create test schema if it doesn't exist
    async with test_engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
        await conn.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        
        # Drop all tables in the test schema if they exist
        await conn.run_sync(Base.metadata.drop_all)
        
        # Create all tables in the test schema
        await conn.run_sync(Base.metadata.create_all)
    
    yield
    
    # Drop all tables in the test schema after tests
    async with test_engine.begin() as conn:
        await conn.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        await conn.run_sync(Base.metadata.drop_all)
        
        # Optionally, you can drop the schema entirely if you want a complete cleanup
        # await conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))

@pytest.fixture
def client(setup_database):
    with TestClient(app) as c:
        yield c

@pytest.fixture
async def async_session():
    async with TestingSessionLocal() as session:
        await session.execute(text(f"SET search_path TO {TEST_SCHEMA}"))
        yield session 