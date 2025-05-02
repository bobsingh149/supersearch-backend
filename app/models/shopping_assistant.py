from sqlalchemy import Column, String, TIMESTAMP, JSON
from pydantic import BaseModel
from typing import List, Optional, Union, Any
from datetime import datetime
from enum import Enum, StrEnum

from app.database.session import Base
from app.models.product import ProductSearchResult


# SQLAlchemy Model
class ConversationDB(Base):
    """Database model for conversations"""
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True)
    messages = Column(JSON, nullable=False, default=list)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')


# Pydantic Models
class Message(BaseModel):
    """Single message in a conversation"""
    role: str  # "user", "model"
    content: str


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation"""
    conversation_id: str
    messages: Optional[List[Message]] = []


class ConversationUpdate(BaseModel):
    """Schema for updating an existing conversation"""
    messages: List[Message]


class ConversationResponse(BaseModel):
    """Schema for conversation response"""
    conversation_id: str
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    name: Optional[str] = None


class ChatRequest(BaseModel):
    """Schema for chat endpoint request"""
    query: str
    conversation_id: str
    product_ids: Optional[List[str]] = None
    stream: Optional[bool] = False


class ChatResponse(BaseModel):
    """Schema for chat endpoint response"""
    response: str | None
    conversation_id: str
    products: Optional[List[ProductSearchResult]] = None
    follow_up_questions: Optional[List[str]] = None


class StreamingResponseType(StrEnum):
    """Enum for streaming response types"""
    PRODUCTS = "products"
    CONTENT = "content"
    QUESTIONS = "questions"


class StreamingResponse(BaseModel):
    """Schema for streaming response items"""
    type: StreamingResponseType
    conversation_id: str
    content: Union[str, List[Any]]


class ConversationSummary(BaseModel):
    """Schema for conversation summary"""
    conversation_id: str
    name: str
    updated_at: datetime


class PaginatedConversationSummary(BaseModel):
    """Schema for paginated conversation summaries"""
    items: List[ConversationSummary]
    total: int
    page: int
    page_size: int

