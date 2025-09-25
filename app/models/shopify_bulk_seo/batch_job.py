from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from sqlalchemy import Column, String, JSON, DateTime, func, CheckConstraint
from app.database.session import Base
from datetime import datetime
from enum import Enum


class BatchJobStatus(str, Enum):
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETED = 'completed'
    FAILED = 'failed'


BATCH_JOB_STATUS_VALUES = [status.value for status in BatchJobStatus]


class BatchJobDB(Base):
    __tablename__ = "batch_jobs"
    __table_args__ = (
        CheckConstraint(f"status IN {tuple(BATCH_JOB_STATUS_VALUES)}", name="batch_jobs_status_check"),
        {"schema": "shopify_bulk_seo"}
    )

    id = Column(String, primary_key=True)  # UUID as string
    name = Column(String(255), nullable=False)
    payload = Column(JSON, nullable=True)
    status = Column(String(255), nullable=False, default='pending')
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class BatchJob(BaseModel):
    id: str
    name: str
    payload: Optional[Dict[str, Any]] = None
    status: BatchJobStatus
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class BatchJobCreate(BaseModel):
    name: str
    payload: Optional[Dict[str, Any]] = None
    status: BatchJobStatus = BatchJobStatus.PENDING


class BatchJobUpdate(BaseModel):
    name: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    status: Optional[BatchJobStatus] = None
