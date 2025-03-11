from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, Text, Boolean, JSON, Uuid
from sqlalchemy.orm import mapped_column, Mapped, relationship
from pydantic import BaseModel, ConfigDict, EmailStr

from app.database.session import Base


class OrganizationDB(Base):
    """SQLAlchemy model for organizations table"""
    __tablename__ = "organizations"
    __table_args__ = {"schema": "common"}
    
    id: Mapped[UUID] = mapped_column(
        Uuid, 
        primary_key=True, 
        default=uuid4
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meta_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.utcnow()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.utcnow()
    )
    
    # Relationships
    tenants = relationship("TenantOrganizationDB", back_populates="organization", cascade="all, delete-orphan")


class Organization(BaseModel):
    """Pydantic model for organization"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str] = None
    meta_data: Optional[dict] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class OrganizationCreate(BaseModel):
    """Pydantic model for creating organization"""
    name: str
    description: Optional[str] = None
    meta_data: Optional[dict] = None
    is_active: bool = True

class OrganizationUpdate(BaseModel):
    """Pydantic model for updating organization"""
    name: Optional[str] = None
    description: Optional[str] = None
    meta_data: Optional[dict] = None
    is_active: Optional[bool] = None

class TenantSummary(BaseModel):
    """Summary of tenant for use in organization responses"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    email: EmailStr

class OrganizationWithTenants(Organization):
    """Organization model with list of associated tenants"""
    tenants: List[TenantSummary] = []





