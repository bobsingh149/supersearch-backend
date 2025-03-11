from sqlalchemy import Column, String, TIMESTAMP, JSON
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

from app.database.session import Base


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
    role: str  # "user", "model", or "system"
    content: str

    model_config = ConfigDict(from_attributes=True)


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

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """Schema for chat endpoint response"""
    response: str
    conversation_id: str


class ChatRequest(BaseModel):
    """Schema for chat endpoint request"""
    query: str
    conversation_id: str
    product_ids: Optional[List[str]] = None
