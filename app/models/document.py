from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import Column, String, Text, DateTime, func
from pgvector.sqlalchemy import Vector
from app.database.session import Base
from datetime import datetime

class DocumentDB(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    content = Column(Text, nullable=True)
    text_embedding = Column(Vector(768), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class Document(BaseModel):
    id: str
    content: Optional[str] = None
    text_embedding: Optional[list[float]] = None  # Vector will be converted to/from list
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class DocumentSearchResult(BaseModel):
    """
    Simplified document model for search results
    """
    id: str
    content: Optional[str] = None
    score: Optional[float] = None

    class Config:
        from_attributes = True 