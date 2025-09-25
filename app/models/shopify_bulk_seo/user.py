from pydantic import BaseModel, ConfigDict
from typing import Optional
from sqlalchemy import Column, String, Text, Integer, DateTime, func
from app.database.session import Base
from datetime import datetime


class UserDB(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "shopify_bulk_seo"}

    id = Column(String(255), primary_key=True)
    access_token = Column(String(255), nullable=False)
    product_description_custom_prompt = Column(Text, nullable=True)
    product_description_tone = Column(String(255), nullable=True)
    product_description_word_count = Column(Integer, nullable=True)
    product_description_example = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class User(BaseModel):
    id: str
    access_token: str
    product_description_custom_prompt: Optional[str] = None
    product_description_tone: Optional[str] = None
    product_description_word_count: Optional[int] = None
    product_description_example: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    id: str
    access_token: str
    product_description_custom_prompt: Optional[str] = None
    product_description_tone: Optional[str] = None
    product_description_word_count: Optional[int] = None
    product_description_example: Optional[str] = None


class UserUpdate(BaseModel):
    access_token: Optional[str] = None
    product_description_custom_prompt: Optional[str] = None
    product_description_tone: Optional[str] = None
    product_description_word_count: Optional[int] = None
    product_description_example: Optional[str] = None
