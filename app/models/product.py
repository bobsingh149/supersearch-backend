from pydantic import BaseModel, model_validator, ConfigDict
from typing import Optional, Dict, List, Any
from sqlalchemy import Column, String, JSON, DateTime, func, Text, ARRAY
from pgvector.sqlalchemy import Vector
from app.database.session import Base
from datetime import datetime

class ProductDB(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True)
    title = Column(Text, nullable=True)
    text_embedding = Column(Vector(768), nullable=True)
    image_embedding = Column(Vector(768), nullable=True)
    searchable_content = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    custom_data = Column(JSON, nullable=True)
    ai_generated_contents = Column(ARRAY(Text), nullable=True, default=[])
    ai_summary = Column(JSON, nullable=True)
    suggested_questions = Column(JSON, nullable=True)

class ProductInput(BaseModel):
    id_field: str
    title_field: str
    image_url_field: Optional[str] = None
    searchable_attribute_fields: List[str]
    data: List[Dict[str, Any]] | None = None

    @model_validator(mode='after')
    def validate_fields(self) -> 'ProductInput':
        if not self.data:
            raise ValueError("Data list cannot be empty")

        # Check if all required fields exist in the first data item
        first_item = self.data[0]
        
        if self.id_field not in first_item:
            raise ValueError(f"id_field '{self.id_field}' not found in data")
            
        if self.title_field not in first_item:
            raise ValueError(f"title_field '{self.title_field}' not found in data")
            
        # Only validate image_url_field if it's provided
        if self.image_url_field and self.image_url_field not in first_item:
            raise ValueError(f"image_url_field '{self.image_url_field}' not found in data")
            
        for field in self.searchable_attribute_fields:
            if field not in first_item:
                raise ValueError(f"searchable field '{field}' not found in data")

        return self

class Product(BaseModel):
    id: str
    title: Optional[str] = None
    text_embedding: Optional[list[float]] = None  # Vector will be converted to/from list
    image_embedding: Optional[list[float]] = None  # Vector will be converted to/from list
    searchable_content: Optional[str] = None
    image_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    custom_data: Optional[Dict] = None
    ai_generated_contents: Optional[List[str]] = None
    ai_summary: Optional[Dict] = None
    suggested_questions: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)

class ProductSearchResult(BaseModel):
    """
    Simplified product model for search results
    """
    id: str
    title: str
    custom_data: Dict
    searchable_content: str
    score: Optional[float] = None
    search_type: Optional[str] = None
    image_url: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

class PaginatedProductsResponse(BaseModel):
    """
    Paginated response model for product listings
    """
    products: List[Dict[str, Any]]
    page: int
    size: int
    has_more: bool
    
    @classmethod
    def model_validate(cls, data: Dict[str, Any]) -> 'PaginatedProductsResponse':
        return cls(**data)
