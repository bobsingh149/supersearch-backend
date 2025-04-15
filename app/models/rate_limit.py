from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.sql import func
from sqlalchemy.ext.declarative import declarative_base
from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Optional

Base = declarative_base()

class RateLimitDB(Base):
    __tablename__ = "rate_limits"
    
    ip_address = Column(String, primary_key=True)
    request_count = Column(Integer, default=0, nullable=False)
    last_request_time = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<RateLimit(ip_address={self.ip_address}, request_count={self.request_count})>"

class RateLimit(BaseModel):
    ip_address: str
    request_count: int
    last_request_time: datetime
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @model_validator(mode='before')
    @classmethod
    def validate_to_json(cls, data):
        if isinstance(data, RateLimitDB):
            return {
                "ip_address": data.ip_address,
                "request_count": data.request_count,
                "last_request_time": data.last_request_time,
                "created_at": data.created_at,
                "updated_at": data.updated_at
            }
        return data 