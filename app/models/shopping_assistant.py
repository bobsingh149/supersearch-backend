from sqlalchemy import Column, String, TIMESTAMP, JSON
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.database.session import Base


# SQLAlchemy Model
class ConversationDB(Base):
    """Database model for conversations"""
    __tablename__ = "conversations"

    conversation_id = Column(String, primary_key=True)
    messages = Column(JSON, nullable=False, default=list)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default='CURRENT_TIMESTAMP')
    metadata = Column(JSON, nullable=True, default=dict)


# Pydantic Models
class Message(BaseModel):
    """Single message in a conversation"""
    role: str  # "user", "model", "system"
    content: str
    timestamp: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode='after')
    def validate_role(self) -> 'Message':
        """Validate that role is one of the allowed values"""
        allowed_roles = ["user", "model", "system", "assistant"]
        if self.role not in allowed_roles:
            raise ValueError(f"Role must be one of {allowed_roles}")
        return self


class ConversationMetadata(BaseModel):
    """Metadata for a conversation"""
    title: Optional[str] = None
    tags: List[str] = []
    user_preferences: Dict[str, Any] = {}
    last_intent: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)


class ConversationCreate(BaseModel):
    """Schema for creating a new conversation"""
    conversation_id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[Message] = []
    metadata: Optional[ConversationMetadata] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationUpdate(BaseModel):
    """Schema for updating an existing conversation"""
    messages: Optional[List[Message]] = None
    metadata: Optional[ConversationMetadata] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    """Schema for conversation response"""
    conversation_id: str
    messages: List[Message]
    created_at: datetime
    updated_at: datetime
    metadata: Optional[ConversationMetadata] = None

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    """Schema for chat endpoint response"""
    response: str
    conversation_id: str
    created_at: Optional[datetime] = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class ChatRequest(BaseModel):
    """Schema for chat endpoint request"""
    query: str
    conversation_id: Optional[str] = None
    product_ids: Optional[List[str]] = None
    context_type: Optional[str] = "general"  # "general", "comparison", "detailed"
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
    
    @model_validator(mode='after')
    def validate_context_type(self) -> 'ChatRequest':
        """Validate that context_type is one of the allowed values"""
        allowed_types = ["general", "comparison", "detailed"]
        if self.context_type not in allowed_types:
            raise ValueError(f"Context type must be one of {allowed_types}")
        return self
