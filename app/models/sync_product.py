from typing import List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field, model_validator

from app.models.sync_config import (
    SourceConfigType,
    SyncSource,
)

class ProductSyncInput(BaseModel):
    """
    Input model for syncing products from various sources
    """
    products: List[Dict[str, Any]] | None = None
    source_config: SourceConfigType = Field(discriminator='source')
    
    @model_validator(mode='after')
    def validate_products_field(self) -> 'ProductSyncInput':
        """
        Validate that products is provided for MANUAL_FILE_UPLOAD and SUPERSEARCH_API
        """
        source = self.source_config.source
        
        # Validate products is provided for MANUAL_FILE_UPLOAD and SUPERSEARCH_API
        if source in [SyncSource.MANUAL_FILE_UPLOAD, SyncSource.SUPERSEARCH_API]:
            if not self.products:
                raise ValueError(f"Products must be provided for source {source}")
        else:
            if self.products:
                raise ValueError(f"Products should not be provided for source {source}")
        
        # Validate source_config data
        self.source_config.validate_data()

        return self

class ProductSyncWithIdInput(BaseModel):
    """
    Input model that combines ProductSyncInput with a sync_id
    Used to pass both the product sync input and the sync_id to the workflow
    """
    sync_input: ProductSyncInput
    sync_id: UUID 