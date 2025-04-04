from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import AsyncGenerator
from app.core.settings import settings
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Use settings to construct database URL
SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{settings.postgres.user}:{settings.postgres.password}@{settings.postgres.host}:{settings.postgres.port}/{settings.postgres.db}"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True
)


AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def check_db_connection():
    """Check if database connection is healthy using AsyncSessionLocal"""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to create database session: {str(e)}")
        return False


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            # Set search path to schema1, public
            await session.execute(text("SET search_path TO demo_movies,public"))
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_with_contextmanager() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            # Set search path to schema1, public
            await session.execute(text("SET search_path TO demo_movies,public"))
            yield session
        finally:
            await session.close()



