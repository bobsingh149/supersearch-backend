from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from sqlalchemy import Column, String, JSON, DateTime, func
from app.database.session import Base
from datetime import datetime


class SettingDB(Base):
    __tablename__ = "settings"
    __table_args__ = {"schema": "shopify_bulk_seo"}

    key = Column(String(255), primary_key=True)
    value = Column(JSON, nullable=False, default=[])
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SettingOption(BaseModel):
    label: str
    value: str
    isDefault: bool


class Setting(BaseModel):
    key: str
    value: List[SettingOption]
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class SettingCreate(BaseModel):
    key: str
    value: List[SettingOption] = []


class SettingUpdate(BaseModel):
    value: Optional[List[SettingOption]] = None
