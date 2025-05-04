from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Optional, Dict, List, Any, Literal
from sqlalchemy import Column, String, Numeric, JSON, DateTime, func, Text, UUID
from datetime import datetime
import uuid
from app.database.session import Base


class OrderOrm(Base):
    __tablename__ = "orders"

    id = Column(UUID, primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    status = Column(String, nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    items = Column(JSON, nullable=False)
    shipping_address = Column(JSON, nullable=True)
    billing_address = Column(JSON, nullable=True)
    payment_info = Column(JSON, nullable=True)
    tracking_number = Column(Text, nullable=True)
    expected_shipping_date = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class OrderItem(BaseModel):
    product_id: str
    quantity: int
    price: float
    title: str
    custom_data: Optional[Dict[str, Any]] = None


class AddressInfo(BaseModel):
    full_name: str
    address_line1: str
    address_line2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    phone: Optional[str] = None


class PaymentInfo(BaseModel):
    payment_method: str
    transaction_id: Optional[str] = None
    payment_status: str
    amount_paid: float
    currency: str = "USD"


class OrderBase(BaseModel):
    user_id: str
    status: Literal["pending", "processing", "shipped", "delivered", "cancelled", "refunded"]
    total_amount: float = Field(ge=0)
    items: List[OrderItem]
    shipping_address: Optional[AddressInfo] = None
    billing_address: Optional[AddressInfo] = None
    payment_info: Optional[PaymentInfo] = None
    tracking_number: Optional[str] = None
    expected_shipping_date: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode='after')
    def validate_total_amount(self) -> 'OrderBase':
        """Validate that total_amount matches the sum of item prices * quantities"""
        calculated_total = sum(item.price * item.quantity for item in self.items)
        if abs(calculated_total - self.total_amount) > 0.01:  # Allow small floating point difference
            raise ValueError(f"Total amount {self.total_amount} doesn't match calculated total {calculated_total}")
        return self


class OrderCreate(BaseModel):
    status: Literal["pending", "processing", "shipped", "delivered", "cancelled", "refunded"] = "pending"
    total_amount: float = Field(ge=0)
    items: List[OrderItem]
    shipping_address: Optional[AddressInfo] = None
    billing_address: Optional[AddressInfo] = None
    payment_info: Optional[PaymentInfo] = None
    tracking_number: Optional[str] = None
    expected_shipping_date: Optional[datetime] = None
    notes: Optional[str] = None

    @model_validator(mode='after')
    def validate_total_amount(self) -> 'OrderCreate':
        """Validate that total_amount matches the sum of item prices * quantities"""
        calculated_total = sum(item.price * item.quantity for item in self.items)
        if abs(calculated_total - self.total_amount) > 0.01:  # Allow small floating point difference
            raise ValueError(f"Total amount {self.total_amount} doesn't match calculated total {calculated_total}")
        return self


class OrderUpdate(BaseModel):
    status: Optional[Literal["pending", "processing", "shipped", "delivered", "cancelled", "refunded"]] = None
    items: Optional[List[OrderItem]] = None
    shipping_address: Optional[AddressInfo] = None
    billing_address: Optional[AddressInfo] = None
    payment_info: Optional[PaymentInfo] = None
    tracking_number: Optional[str] = None
    expected_shipping_date: Optional[datetime] = None
    notes: Optional[str] = None
    total_amount: Optional[float] = Field(default=None, ge=0)

    @model_validator(mode='after')
    def validate_total_amount(self) -> 'OrderUpdate':
        """Validate that total_amount matches the sum of item prices * quantities if both are provided"""
        if self.items is not None and self.total_amount is not None:
            calculated_total = sum(item.price * item.quantity for item in self.items)
            if abs(calculated_total - self.total_amount) > 0.01:  # Allow small floating point difference
                raise ValueError(f"Total amount {self.total_amount} doesn't match calculated total {calculated_total}")
        return self


class Order(OrderBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedOrdersResponse(BaseModel):
    """
    Paginated response model for order listings
    """
    orders: List[Order]
    page: int
    size: int
    has_more: bool
    total_count: int
    
    @classmethod
    def model_validate(cls, data: Dict[str, Any]) -> 'PaginatedOrdersResponse':
        return cls(**data) 