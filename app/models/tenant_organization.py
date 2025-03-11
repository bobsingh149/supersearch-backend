from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import mapped_column, Mapped, relationship
from pydantic import BaseModel, ConfigDict

from app.database.session import Base


class TenantOrganizationDB(Base):
    """SQLAlchemy model for tenant_organizations table"""
    __tablename__ = "tenant_organizations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "organization_id", name="uq_tenant_organization"),
        {"schema": "common"}
    )
    
    id: Mapped[UUID] = mapped_column(
        Uuid, 
        primary_key=True, 
        default=uuid4
    )
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("common.tenants.id", ondelete="CASCADE"),
        nullable=False
    )
    organization_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("common.organizations.id", ondelete="CASCADE"),
        nullable=False
    )
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
    tenant = relationship("TenantDB", back_populates="organizations")
    organization = relationship("OrganizationDB", back_populates="tenants")


class TenantOrganization(BaseModel):
    """Pydantic model for tenant_organization"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    tenant_id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

class TenantOrganizationCreate(BaseModel):
    """Pydantic model for creating tenant_organization"""
    tenant_id: UUID
    organization_id: UUID 