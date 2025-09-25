from pydantic import BaseModel, ConfigDict
from typing import Optional
from sqlalchemy import Column, String, Text, DateTime, func, CheckConstraint, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base
from datetime import datetime
from enum import Enum


class BatchProductStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


BATCH_PRODUCT_STATUS_VALUES = [status.value for status in BatchProductStatus]


class BatchProductDB(Base):
    __tablename__ = "batch_products"
    __table_args__ = (
        CheckConstraint(f"status IN {tuple(BATCH_PRODUCT_STATUS_VALUES)}", name="batch_products_status_check"),
        {"schema": "shopify_bulk_seo"}
    )

    batch_id = Column(String, ForeignKey("shopify_bulk_seo.batch_jobs.id", ondelete="CASCADE"), primary_key=True)
    product_id = Column(String(255), primary_key=True)
    status = Column(String(255), nullable=False, default='pending')
    error = Column(Text, nullable=True)
    ai_product_description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationship to batch job
    batch_job = relationship("BatchJobDB", backref="batch_products")


class BatchProduct(BaseModel):
    batch_id: str
    product_id: str
    status: BatchProductStatus
    error: Optional[str] = None
    ai_product_description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BatchProductCreate(BaseModel):
    batch_id: str
    product_id: str
    status: BatchProductStatus = BatchProductStatus.PENDING
    error: Optional[str] = None
    ai_product_description: Optional[str] = None


class BatchProductUpdate(BaseModel):
    status: Optional[BatchProductStatus] = None
    error: Optional[str] = None
    ai_product_description: Optional[str] = None
