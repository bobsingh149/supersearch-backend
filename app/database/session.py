from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Update URL to use async postgres driver
SQLALCHEMY_DATABASE_URL = "postgresql+asyncpg://supersearch:supersearch@localhost:5433/supersearch"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

async def check_db_connection():
    """Check if database connection is healthy using AsyncSessionLocal"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute("SELECT 1")
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to create database session: {str(e)}")
        return False

# Async dependency for FastAPI
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# For backward compatibility during migration (will be removed later)
get_db = get_async_session 