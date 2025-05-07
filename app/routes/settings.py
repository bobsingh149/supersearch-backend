from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.settings import Settings, SettingsDB, SettingsCreate, SettingsUpdate, SettingKey, SearchConfigModel
from app.database.session import get_async_session
from pydantic import BaseModel

router = APIRouter(
    prefix="/settings",
    tags=["settings"]
)


@router.post("", response_model=None)
async def create_setting(
    setting: SettingsCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new setting"""
    # Check if setting with same key exists
    query = select(SettingsDB).where(SettingsDB.key == setting.key.value)
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail=f"Setting with key {setting.key} already exists")
    
    # Create new SettingsDB instance with string key
    setting_dict = setting.model_dump()
    setting_dict["key"] = setting.key.value  # Convert enum to string
    db_setting = SettingsDB(**setting_dict)
    
    session.add(db_setting)
    await session.commit()

    return None

@router.get("/{key}", response_model=Settings)
async def get_setting(
    key: SettingKey,
    session: AsyncSession = Depends(get_async_session)
):
    """Get a setting by key"""
    query = select(SettingsDB).where(SettingsDB.key == key.value)
    result = await session.execute(query)
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting with key {key} not found")
    
    # Convert to Settings model
    return Settings.model_validate(setting)

@router.get("", response_model=List[Settings])
async def list_settings(
    session: AsyncSession = Depends(get_async_session)
):
    """List all settings"""
    query = select(SettingsDB)
    result = await session.execute(query)
    settings_db = result.scalars().all()
    
    # Convert to Settings models
    return [Settings.model_validate(setting) for setting in settings_db]

@router.put("/{key}", response_model=None)
async def update_setting(
    key: SettingKey, 
    setting_update: SettingsUpdate, 
    session: AsyncSession = Depends(get_async_session)
):
    """Update a setting by key"""
    query = select(SettingsDB).where(SettingsDB.key == key.value)
    result = await session.execute(query)
    db_setting = result.scalar_one_or_none()
    
    if not db_setting:
        raise HTTPException(status_code=404, detail=f"Setting with key {key} not found")
    
    # Update setting fields
    update_data = setting_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if value is not None:  # Skip None values
            setattr(db_setting, field, value)
    
    await session.commit()
    return None


@router.delete("/{key}")
async def delete_setting(
    key: SettingKey, 
    session: AsyncSession = Depends(get_async_session)
):
    """Delete a setting by key"""
    query = select(SettingsDB).where(SettingsDB.key == key.value)
    result = await session.execute(query)
    db_setting = result.scalar_one_or_none()
    
    if not db_setting:
        raise HTTPException(status_code=404, detail=f"Setting with key {key} not found")
    
    await session.delete(db_setting)
    await session.commit()
    return {"message": f"Setting with key {key} deleted successfully"}

@router.post("/search-config", response_model=None)
async def set_search_config(
    config: SearchConfigModel,
    session: AsyncSession = Depends(get_async_session)
):
    """Set the search configuration for product syncing"""
    # Create settings object
    setting = SettingsCreate(
        key=SettingKey.SEARCH_CONFIG,
        title="Search Configuration",
        description="Configuration for product search fields",
        value=config.model_dump()
    )
    
    # Check if setting already exists
    query = select(SettingsDB).where(SettingsDB.key == setting.key.value)
    result = await session.execute(query)
    existing_setting = result.scalar_one_or_none()
    
    if existing_setting:
        # Update existing setting
        for field, value in setting.model_dump(exclude={'key'}).items():
            if value is not None:
                setattr(existing_setting, field, value)
        await session.commit()
        return None
    else:
        # Create new setting with string key
        setting_dict = setting.model_dump()
        setting_dict["key"] = setting.key.value  # Convert enum to string
        db_setting = SettingsDB(**setting_dict)
        
        session.add(db_setting)
        await session.commit()
        return None

