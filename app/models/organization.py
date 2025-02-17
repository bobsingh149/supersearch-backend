from pydantic import BaseModel
from typing import List, Optional

from sqlalchemy import Column, String, ARRAY
from app.database.session import Base

class OrganizationDB(Base):
    __tablename__ = "organizations"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    members = Column(ARRAY(String), nullable=False)
    plan = Column(String, nullable=False)
    admin_id = Column(String, nullable=False)
    logo = Column(String, nullable=True)

    

class Organization(BaseModel):
    id: str
    name: str
    members: List[str]  # Assuming members are referenced by their UUIDs
    plan: str  # You might want to use an Enum if you have specific plan types
    admin_id: str
    logo: Optional[str] = None  # Optional field for logo URL/path

    class Config:
        from_attributes = True  # Allows ORM model conversion (previously known as orm_mode)





