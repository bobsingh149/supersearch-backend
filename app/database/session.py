from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import text
from sqlalchemy.exc import SQLAlchemyError
import logging
from typing import AsyncGenerator
from app.core.appsettings import app_settings
from contextlib import asynccontextmanager
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)

# Use settings to construct database URL
SQLALCHEMY_DATABASE_URL = f"postgresql+asyncpg://{app_settings.postgres.user}:{app_settings.postgres.password}@{app_settings.postgres.host}:{app_settings.postgres.port}/{app_settings.postgres.db}"

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




def get_tenant_name(request: Request) -> str:
    tenant = getattr(request.state, 'tenant', None)
    if not tenant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant not found in request.")
    return tenant


def set_tenant_schema(db_class: type, tenant: str) -> type:
    """
    Sets the schema of a SQLAlchemy ORM class to the specified tenant name.
    
    Args:
        db_class: The SQLAlchemy ORM class to modify
        tenant: The tenant name to use as the schema name
        
    Returns:
        The modified SQLAlchemy ORM class with the tenant schema set
    """
    # Create a new table object with the same properties but different schema
    table_args = getattr(db_class, '__table_args__', {})
    
    if isinstance(table_args, dict):
        new_table_args = dict(table_args)
        new_table_args['schema'] = tenant
        db_class.__table_args__ = new_table_args
    elif isinstance(table_args, tuple):
        # Find the dict in the tuple if it exists
        dict_found = False
        new_args = list(table_args)
        
        for i, arg in enumerate(new_args):
            if isinstance(arg, dict):
                dict_found = True
                new_args[i] = {**arg, 'schema': tenant}
                break
        
        # If no dict was found, add one to the tuple
        if not dict_found:
            new_args.append({'schema': tenant})
        
        db_class.__table_args__ = tuple(new_args)
    else:
        # If no table_args exist, create a new one
        db_class.__table_args__ = {'schema': tenant}
    
    # Update table schema in the metadata
    if hasattr(db_class, '__table__') and db_class.__table__ is not None:
        db_class.__table__.schema = tenant
    
    return db_class

async def get_async_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            # Set search path to schema1, public
            await session.execute(text(f"SET search_path TO {get_tenant_name(request)}, public"))
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session_with_contextmanager(tenant: str) -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            # Set search path to schema1, public
            await session.execute(text(f"SET search_path TO {tenant}, public"))
            yield session
        finally:
            await session.close()




