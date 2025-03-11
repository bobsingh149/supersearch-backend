from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, Integer, func, Uuid
from sqlalchemy.orm import mapped_column, Mapped
from pydantic import BaseModel, ConfigDict, Field

from app.database.session import Base
from app.models.sync_config import SyncSource, SyncStatus


class SyncHistoryDB(Base):
    """SQLAlchemy model for sync_history table"""
    __tablename__ = "sync_history"
    
    id: Mapped[UUID] = mapped_column(
        Uuid, 
        primary_key=True, 
        default=uuid4
    )
    source: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )
    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    records_processed: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    next_run: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.utcnow()
    )

class SyncHistory(BaseModel):
    """Pydantic model for sync history"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    source: SyncSource
    status: SyncStatus
    start_time: datetime
    end_time: Optional[datetime] = None
    records_processed: Optional[int] = None
    next_run: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class SyncHistoryCreate(BaseModel):
    """Pydantic model for creating sync history"""
    source: SyncSource
    status: SyncStatus = Field(default=SyncStatus.PROCESSING)
    start_time: datetime = Field(default_factory=lambda: datetime.utcnow())
    end_time: Optional[datetime] = None
    records_processed: Optional[int] = None
    next_run: Optional[datetime] = None

class SyncHistoryUpdate(BaseModel):
    """Pydantic model for updating sync history"""
    status: Optional[SyncStatus] = None
    end_time: Optional[datetime] = None
    records_processed: Optional[int] = None
    next_run: Optional[datetime] = None


class PaginatedSyncHistoryResponse(BaseModel):
    """Pydantic model for paginated sync history response"""
    model_config = ConfigDict(from_attributes=True)

    items: List[SyncHistory]
    page: int
    size: int
    has_more: bool
