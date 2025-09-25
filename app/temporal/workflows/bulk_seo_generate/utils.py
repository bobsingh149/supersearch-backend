"""Utility functions for bulk SEO generation workflow."""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.db import Db
from app.models.shopify_bulk_seo.batch_product import BatchProductDB, BatchProductStatus
from app.services.shopify_api import ShopifyAPIService, ShopifyAPIError
from app.services.shopify_bulk_seo.bulk_seo_llm import BulkSEOLLMService
from app.temporal.workflows.bulk_seo_generate.models import (
    ShopifyProduct,
    ShopifyUserData, ProcessedProduct,
)

logger = logging.getLogger(__name__)

async def fetch_shopify_products(
    access_token: str,
    product_ids: Optional[List[str]] = None,
    all_products: bool = False,
    batch_size: int = 250,
    shop_domain: Optional[str] = None
) -> List[ShopifyProduct]:
    """
    Fetch products from Shopify GraphQL API using the ShopifyAPIService.
    
    Args:
        access_token: Shopify access token
        product_ids: Specific product IDs to fetch (optional)
        all_products: Whether to fetch all products
        batch_size: Number of products per request
        shop_domain: Shop domain (optional)
        
    Returns:
        List of Shopify products
    """
    try:
        # Initialize Shopify API service
        shopify_service = ShopifyAPIService(access_token, shop_domain)
        
        # Fetch products based on parameters
        if product_ids:
            # Fetch specific products by IDs
            products_data = await shopify_service.fetch_products_by_ids(product_ids, batch_size)
        elif all_products:
            # Fetch all products with pagination
            products_data = await shopify_service.fetch_all_products_paginated(batch_size)
        else:
            raise ValueError("Either product_ids or all_products=True must be specified")
        
        # Convert to ShopifyProduct models
        products = [_convert_to_shopify_product(product_data) for product_data in products_data]
        
        logger.info(f"Successfully fetched and converted {len(products)} products from Shopify")
        return products
        
    except ShopifyAPIError as e:
        logger.error(f"Shopify API error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error fetching products from Shopify: {str(e)}")
        raise


def _convert_to_shopify_product(data: Dict[str, Any]) -> ShopifyProduct:
    """Convert GraphQL response data to ShopifyProduct model."""
    return ShopifyProduct(
        id=data.get('id', ''),
        title=data.get('title', ''),
        description=data.get('description'),
        descriptionHtml=data.get('descriptionHtml'),
        handle=data.get('handle'),
        productType=data.get('productType'),
        vendor=data.get('vendor'),
        tags=data.get('tags', []),
        status=data.get('status'),
        category=data.get('category'),
        seo=data.get('seo'),
        variants=[{
            'id': variant.get('id'),
            'title': variant.get('title'),
            'price': variant.get('price'),
            'compareAtPrice': variant.get('compareAtPrice'),
            'availableForSale': variant.get('availableForSale'),
            'inventoryQuantity': variant.get('inventoryQuantity'),
        } for variant in data.get('variants', {}).get('nodes', [])],
        media=[{
            'id': media.get('id'),
            'url': media.get('image', {}).get('url'),
            'altText': media.get('image', {}).get('altText'),
        } for media in data.get('media', {}).get('nodes', [])],
        priceRangeV2=data.get('priceRangeV2')
    )


async def generate_ai_description(
    product: ShopifyProduct,
    user_data: ShopifyUserData
) -> str:
    """
    Generate AI description for a product using the BulkSEOLLMService.
    
    Args:
        product: Shopify product data
        user_data: User data with AI settings
        
    Returns:
        Generated AI description
    """
    try:
        # Initialize LLM service
        llm_service = BulkSEOLLMService()
        
        # Convert ShopifyProduct to dict format expected by the service
        product_data = _convert_shopify_product_to_dict(product)
        
        # Generate description using the LLM service
        ai_description = await llm_service.generate_product_description(
            product_data=product_data,
            tone=user_data.product_description_tone or "professional",
            word_count=user_data.product_description_word_count or 150,
            custom_prompt=user_data.product_description_custom_prompt,
            example=user_data.product_description_example
        )
        
        return ai_description
        
    except Exception as e:
        logger.error(f"Error generating AI description for product {product.id}: {str(e)}")
        raise

def _convert_shopify_product_to_dict(product: ShopifyProduct) -> Dict[str, Any]:
    """Convert ShopifyProduct model to dictionary for LLM service."""
    return {
        'id': product.id,
        'title': product.title,
        'description': product.description,
        'descriptionHtml': product.descriptionHtml,
        'handle': product.handle,
        'productType': product.productType,
        'vendor': product.vendor,
        'tags': product.tags,
        'status': product.status,
        'category': product.category,
        'seo': product.seo,
        'variants': {'nodes': product.variants},
        'media': {'nodes': product.media},
        'priceRangeV2': product.priceRangeV2
    }


async def send_email_notification(
    user_id: str,
    batch_name: str,
    total_products: int,
    success_count: int,
    failure_count: int
) -> None:
    """Send email notification about batch completion."""
    # Placeholder for email service integration
    logger.info(f"Sending email notification to user {user_id}: {batch_name} completed")
    
    # You would integrate with your email service here
    pass

async def send_app_notification(
    user_id: str,
    batch_job_id: str,
    message: str
) -> None:
    """Send in-app notification about batch completion."""
    # Placeholder for app notification service
    logger.info(f"Sending app notification to user {user_id}: {message}")

    # You would store this in a notifications table or send via websocket
    pass


async def _process_single_product(
    product: ShopifyProduct,
    user_data: ShopifyUserData,
    batch_job_id: str
) -> ProcessedProduct:
    """Process a single product to generate AI description."""
    try:
        # Generate AI description
        ai_description = await generate_ai_description(
            product=product,
            user_data=user_data
        )

        return ProcessedProduct(
            product_id=product.id,
            status=BatchProductStatus.COMPLETED.value,
            ai_description=ai_description
        )

    except Exception as e:
        logger.error(f"Error processing product {product.id}: {str(e)}")
        raise e



async def _save_batch_results(
    processed_products: List[ProcessedProduct],
    batch_job_id: str,
    tenant: str,
    session: AsyncSession
) -> None:
    """Save batch processing results to database."""
    batch_products_data = []

    for processed_product in processed_products:
        batch_products_data.append({
            "batch_id": batch_job_id,
            "product_id": processed_product.product_id,
            "status": processed_product.status,
            "error": processed_product.error,
            "ai_product_description": processed_product.ai_description,
            "created_at": datetime.now(datetime.UTC),
            "updated_at": datetime.now(datetime.UTC)
        })

    if batch_products_data:
        # Use bulk insert for efficiency
        await Db.bulk_insert(
            session=session,
            tenant=tenant,
            table_name=BatchProductDB.__tablename__,
            columns=[
                BatchProductDB.batch_id.name,
                BatchProductDB.product_id.name,
                BatchProductDB.status.name,
                BatchProductDB.error.name,
                BatchProductDB.ai_product_description.name,
                BatchProductDB.created_at.name,
                BatchProductDB.updated_at.name
            ],
            items=batch_products_data
        )

    await session.commit()
    logger.info(f"Saved {len(processed_products)} batch product results")
