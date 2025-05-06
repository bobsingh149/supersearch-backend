from typing import Optional, Any, Dict, TypeVar, Type

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.settings import SettingKey
from app.database.session import get_async_session_with_contextmanager
from app.database.sql.sql import render_sql, SQLFilePath

T = TypeVar('T')

async def get_setting_by_key(
    key: SettingKey, 
    tenant: str,
    session: Optional[AsyncSession] = None,
    default_value: Optional[Dict[str, Any]] = None,

) -> Optional[Dict[str, Any]]:
    """
    Retrieve a setting value by its key.
    
    Args:
        key: The SettingKey enum value to look up
        session: Optional database session (will create one if not provided)
        default_value: Optional default value to return if setting is not found

    Returns:
        The setting value as a dictionary or default_value if not found
    """
    # Use provided session or create a new one with context manager
    if session is not None:

        # Use the provided session
        query = render_sql(
            SQLFilePath.GENERIC_GET_BY_ID, 
            tenant=tenant,
            table_name="settings",
            id_field="key",
            id=key.value
        )
        result = await session.execute(text(query))
        setting = result.mappings().one_or_none()
        
        if setting:
            return setting["value"]
        return default_value
    else:
        # Create a new session using the context manager
        async with get_async_session_with_contextmanager() as new_session:
            query = render_sql(
                SQLFilePath.GENERIC_GET_BY_ID, 
                tenant=tenant,
                table_name="settings",
                id_field="key",
                id=key.value
            )
            result = await new_session.execute(query)
            setting = result.mappings().one_or_none()
            
            if setting:
                return setting["value"]
            return default_value

async def get_typed_setting_by_key(
    key: SettingKey,
    tenant: str,
    model_class: Type[T],
    session: Optional[AsyncSession] = None,
    default_value: Optional[T] = None,
) -> Optional[T]:
    """
    Retrieve a setting value by its key and convert it to a specific type.
    
    Args:
        key: The SettingKey enum value to look up
        model_class: The Pydantic model class to convert the value to
        session: Optional database session (will create one if not provided)
        default_value: Optional default value to return if setting is not found

    Returns:
        The setting value converted to the specified type or default_value if not found
    """
    value = await get_setting_by_key(key=key, tenant=tenant, session=session)
    
    if value is None:
        return default_value
        
    return model_class.model_validate(value) 