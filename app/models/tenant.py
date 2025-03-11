from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, Boolean, Uuid
from sqlalchemy.orm import mapped_column, Mapped, relationship
from pydantic import BaseModel, ConfigDict, EmailStr

from app.database.session import Base


class TenantDB(Base):
    """SQLAlchemy model for tenants table"""
    __tablename__ = "tenants"
    __table_args__ = {"schema": "common"}
    
    id: Mapped[UUID] = mapped_column(
        Uuid, 
        primary_key=True, 
        default=uuid4
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
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
    organizations = relationship("TenantOrganizationDB", back_populates="tenant", cascade="all, delete-orphan")


class Tenant(BaseModel):
    """Pydantic model for tenant"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    updated_at: datetime

class TenantCreate(BaseModel):
    """Pydantic model for creating tenant"""
    name: str
    email: EmailStr
    is_active: bool = True

class TenantUpdate(BaseModel):
    """Pydantic model for updating tenant"""
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

class OrganizationSummary(BaseModel):
    """Summary of organization for use in tenant responses"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    description: Optional[str] = None

class TenantWithOrganizations(Tenant):
    """Tenant model with list of associated organizations"""
    organizations: List[OrganizationSummary] = [] 