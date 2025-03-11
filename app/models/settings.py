from datetime import datetime
from typing import Optional
from enum import StrEnum
from sqlalchemy import DateTime, JSON, Text, Enum as SQLEnum
from sqlalchemy.orm import mapped_column, Mapped
from pydantic import BaseModel, ConfigDict

from app.database.session import Base


class SettingKey(StrEnum):
    """Enum for setting key types"""
    ORGANIZATION_DETAILS = "ORGANIZATION_DETAILS"
    DATA_SOURCE = "DATA_SOURCE"
    PREFERENCES = "PREFERENCES"
    SEARCH_CONFIG = "SEARCH_CONFIG"

class SettingsDB(Base):
    """SQLAlchemy model for settings table"""
    __tablename__ = "settings"
    
    key: Mapped[str] = mapped_column(
        Text,
        primary_key=True
    )
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow()
    )

class Settings(BaseModel):
    """Pydantic model for settings"""
    model_config = ConfigDict(from_attributes=True)
    
    key: SettingKey
    title: Optional[str] = None
    description: Optional[str] = None
    value: dict
    created_at: datetime
    updated_at: datetime

class SettingsCreate(BaseModel):
    """Pydantic model for creating settings"""
    key: SettingKey
    title: Optional[str] = None
    description: Optional[str] = None
    value: dict

class SettingsUpdate(BaseModel):
    """Pydantic model for updating settings"""
    title: Optional[str] = None
    description: Optional[str] = None
    value: Optional[dict] = None 