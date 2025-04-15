from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, Uuid
from sqlalchemy.orm import mapped_column, Mapped
from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.database.session import Base


class LeadDB(Base):
    """SQLAlchemy model for leads table"""
    __tablename__ = "leads"
    __table_args__ = {"schema": "public"}
    
    id: Mapped[UUID] = mapped_column(
        Uuid, 
        primary_key=True, 
        default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
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


class Lead(BaseModel):
    """Pydantic model for lead"""
    model_config = ConfigDict(from_attributes=True)
    
    id: UUID
    name: str
    business_email: EmailStr
    company_name: str
    created_at: datetime
    updated_at: datetime


class LeadCreate(BaseModel):
    """Pydantic model for creating lead"""
    name: str
    business_email: EmailStr
    company_name: str
    
    @model_validator(mode='after')
    def validate_model(self):
        return self


class LeadUpdate(BaseModel):
    """Pydantic model for updating lead"""
    name: Optional[str] = None
    business_email: Optional[EmailStr] = None
    company_name: Optional[str] = None
    
    @model_validator(mode='after')
    def validate_model(self):
        # Check if at least one field is being updated
        if all(value is None for value in [self.name, self.business_email, self.company_name]):
            raise ValueError("At least one field must be provided for update")
        return self 