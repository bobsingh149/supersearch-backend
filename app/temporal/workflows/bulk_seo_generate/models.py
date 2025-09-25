"""Pydantic models for bulk SEO generation workflow activities."""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class BulkSeoGenerateInput(BaseModel):
    """Input for bulk SEO generation workflow."""
    product_ids: Optional[List[str]] = None
    all_products: bool = False
    shopify_user_id: str
    batch_job_id: str
    tenant: str

class ShopifyProduct(BaseModel):
    """Shopify product model with fields useful for AI generation."""
    id: str
    title: str
    description: Optional[str] = None
    descriptionHtml: Optional[str] = None
    handle: Optional[str] = None
    productType: Optional[str] = None
    vendor: Optional[str] = None
    tags: List[str] = []
    status: Optional[str] = None
    category: Optional[Dict[str, Any]] = None
    seo: Optional[Dict[str, Any]] = None
    variants: List[Dict[str, Any]] = []
    media: List[Dict[str, Any]] = []
    priceRangeV2: Optional[Dict[str, Any]] = None

class ShopifyUserData(BaseModel):
    """Shopify user data with access token and user-specific settings."""
    user_id: str
    access_token: str
    product_description_custom_prompt: Optional[str] = None
    product_description_tone: Optional[str] = None
    product_description_word_count: Optional[int] = None
    product_description_example: Optional[str] = None

class ProcessProductsInput(BaseModel):
    """Input for process products activity."""
    products: List[ShopifyProduct]
    user_data: ShopifyUserData
    batch_job_id: str
    tenant: str

class ProcessedProduct(BaseModel):
    """Result of processing a single product."""
    product_id: str
    status: str  # 'completed' or 'failed'
    ai_description: Optional[str] = None
    error: Optional[str] = None

class ProcessResult(BaseModel):
    """Result of processing products."""
    processed_products: List[ProcessedProduct]
    success_count: int
    failure_count: int

class NotificationInput(BaseModel):
    """Input for notification activity."""
    batch_job_id: str
    user_id: str
    total_products: int
    success_count: int
    failure_count: int
    batch_name: str

class FetchProductsInput(BaseModel):
    """Input for fetching products from Shopify."""
    shopify_user_id: str
    batch_job_id: Optional[str] = None
    product_ids: Optional[List[str]] = None
    all_products: bool = False
    batch_size: int = 250
    tenant: str

class FetchProductsOutput(BaseModel):
    """Output from fetching products."""
    products: List[ShopifyProduct]
    user_data: ShopifyUserData
