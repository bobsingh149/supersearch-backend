from typing import Optional
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Column, String, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import relationship
from app.database.session import Base


class ReviewBase(BaseModel):
    """Base model for review data"""
    content: str


class ReviewCreate(ReviewBase):
    """Model for creating reviews"""
    product_id: str


class ReviewUpdate(ReviewBase):
    """Model for updating reviews"""
    pass


class ReviewInDBBase(ReviewBase):
    """Base model for reviews stored in the database"""
    id: UUID
    product_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Review(ReviewInDBBase):
    """Review model with all fields"""
    pass


class ReviewInDB(ReviewInDBBase):
    """Review model as stored in the database"""
    pass


class ReviewOrm(Base):
    """SQLAlchemy ORM model for reviews"""
    __tablename__ = "reviews"

    id = Column(PostgresUUID, primary_key=True, default=uuid4, index=True)
    content = Column(Text, nullable=False)
    product_id = Column(String, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.now, onupdate=datetime.now)

    # Relationship to products (uncomment if needed)
    # product = relationship("ProductOrm", back_populates="reviews") 