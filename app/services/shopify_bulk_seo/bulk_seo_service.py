"""Service for managing bulk SEO operations."""
import logging

from app.services.shopify_bulk_seo.bulk_seo_llm import BulkSEOLLMService

logger = logging.getLogger(__name__)


class BulkSEOServiceError(Exception):
    """Custom exception for bulk SEO service errors."""
    pass


class BulkSEOService:
    """
    Service for managing bulk SEO operations including user management,
    batch processing, and integration with Shopify and LLM services.
    """
    
    def __init__(self):
        """Initialize the bulk SEO service."""
        self.llm_service = BulkSEOLLMService()
