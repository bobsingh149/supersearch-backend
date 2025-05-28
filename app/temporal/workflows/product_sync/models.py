"""Pydantic models for product sync workflow activities."""
from datetime import datetime
from typing import Optional, List
from uuid import UUID

from pydantic import BaseModel

from app.models.product import Product
from app.models.sync_config import SyncSource, SyncStatus
from app.models.sync_product import ProductSyncInput

class CreateSyncHistoryInput(BaseModel):
    """Input for create_sync_history activity."""
    source: SyncSource

class CreateSyncHistoryOutput(BaseModel):
    """Output for create_sync_history activity."""
    sync_id: UUID
    source: SyncSource

class ProductSyncInputWithTenant(BaseModel):
    """ProductSyncInput with tenant information for activities."""
    sync_input: ProductSyncInput
    tenant: str

class ProductsOutput(BaseModel):
    """List of products for activities."""
    products: List[Product]

class UpdateSyncHistoryInput(BaseModel):
    """Input for update_sync_history activity."""
    sync_id: UUID
    status: SyncStatus
    records_processed: Optional[int] = None
    next_run: Optional[datetime] = None
    tenant: str

class UpdateSyncHistoryOutput(BaseModel):
    """Output for update_sync_history activity."""
    sync_id: UUID
    status: SyncStatus
