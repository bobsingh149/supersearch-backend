from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict
from sqlalchemy import Column, String, JSON, DateTime, func, Text, Computed
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from app.database.session import Base
from datetime import datetime

class ProductDB(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    title = Column(Text, nullable=True)
    text_embedding = Column(Vector(768), nullable=True)
    image_embedding = Column(Vector(768), nullable=True)
    searchable_content = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    custom_data = Column(JSON, nullable=True)

class Product(BaseModel):
    id: str
    title: Optional[str] = None
    text_embedding: Optional[list[float]] = None  # Vector will be converted to/from list
    image_embedding: Optional[list[float]] = None  # Vector will be converted to/from list
    searchable_content: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    custom_data: Optional[Dict] = None

    class Config:
        from_attributes = True

class ProductInput(BaseModel):
    """
    Simplified product model for input with only id and custom_data
    """
    id: str
    custom_data: Optional[Dict] = None


class ProductSearchResult(BaseModel):
    """
    Simplified product model for search results
    """
    id: str
    title: Optional[str] = None
    custom_data: Optional[Dict] = None
    searchable_content: Optional[str] = None
    score: Optional[float] = None

    class Config:
        from_attributes = True
