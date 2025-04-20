from pydantic import BaseModel, model_validate, Field, ConfigDict
from typing import List, Optional, Dict, Any, Union, Literal
from enum import Enum


class ContentTopic(str, Enum):
    PRODUCT_DESCRIPTION = "product_description"
    STYLE_GUIDES = "style_guides"
    FEATURES = "features"
    BENEFITS = "benefits"
    USAGE_INSTRUCTIONS = "usage_instructions"
    CARE_INSTRUCTIONS = "care_instructions"
    SPECIFICATIONS = "specifications"
    REVIEWS_SUMMARY = "reviews_summary"
    COMPARISONS = "comparisons"


class GenerateContentRequest(BaseModel):
    """
    Request model for generating AI content for products
    """
    product_ids: Optional[List[str]] = None
    all_products: bool = False
    topics: List[ContentTopic]

    model_config = ConfigDict(extra="forbid")

    @model_validate(mode='after')
    def validate_input(self) -> 'GenerateContentRequest':
        if not self.product_ids and not self.all_products:
            raise ValueError("Either product_ids or all_products must be provided")
        if self.product_ids and self.all_products:
            raise ValueError("Cannot provide both product_ids and all_products")
        if not self.topics:
            raise ValueError("At least one topic must be provided")
        return self


class ContentGenerationStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ContentGenerationResult(BaseModel):
    """
    Response model for content generation
    """
    product_id: str
    topic: ContentTopic
    content: str
    status: ContentGenerationStatus = ContentGenerationStatus.COMPLETED
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ContentGenerationResponse(BaseModel):
    """
    Overall response for content generation request
    """
    results: List[ContentGenerationResult]
    failed_product_ids: List[str] = []
    total_processed: int
    total_failed: int

    model_config = ConfigDict(from_attributes=True) 