"""Bulk SEO generation activities."""
import logging
import asyncio
import json
import aiohttp
from typing import List, Dict, Any
from datetime import datetime

import tenacity
from temporalio import activity

from app.database.session import get_async_session_with_contextmanager
from app.database.db import Db
from app.models.shopify_bulk_seo.batch_job import BatchJobDB, BatchJobStatus
from app.models.shopify_bulk_seo.batch_product import BatchProductDB, BatchProductStatus
from app.models.shopify_bulk_seo.user import UserDB
from app.temporal.workflows.bulk_seo_generate.models import (
    FetchProductsInput,
    FetchProductsOutput,
    ProcessProductsInput,
    ProcessResult,
    ProcessedProduct,
    NotificationInput,
    ShopifyProduct,
    ShopifyUserData,
)
from app.temporal.workflows.bulk_seo_generate.utils import (
    fetch_shopify_products,
    generate_ai_description,
    send_email_notification,
    send_app_notification,
    _process_single_product,
    _save_batch_results,
)
from app.temporal.workflows.bulk_seo_generate.errors import NonRetryableError
from app.services.redis_service import get_redis_service

logger = logging.getLogger(__name__)

@activity.defn
async def fetch_products_and_user_data(
    input_data: FetchProductsInput,
) -> FetchProductsOutput:
    """
    Fetch products from Shopify and user data with AI settings, and update batch job status.

    Args:
        input_data: Input containing user ID and product filters

    Returns:
        Products and user data
    """
    shopify_user_id = input_data.shopify_user_id
    batch_job_id = input_data.batch_job_id

    if not shopify_user_id:
        raise ValueError("shopify_user_id is required")

    logger.info(f"Fetching products and user data for user: {shopify_user_id}")

    # Use dependency injection for session (assuming it's passed or we need to create it differently)
    # For now, using the context manager approach but with raw SQL
    async with get_async_session_with_contextmanager(input_data.tenant) as session:
        # Update batch job status to running
        if batch_job_id:
            await Db.update(
                session=session,
                tenant=input_data.tenant,
                table_name=BatchJobDB.__tablename__,
                id_field=BatchJobDB.id.name,
                id_value=batch_job_id,
                updates={
                    BatchJobDB.status.name: BatchJobStatus.RUNNING.value,
                }
            )
            logger.info(f"Updated batch job {batch_job_id} status to running")

        # Fetch user data and access token
        user_db = await Db.get_by_id(
            session=session,
            tenant=input_data.tenant,
            table_name=UserDB.__tablename__,
            id_field=UserDB.id.name,
            id_value=shopify_user_id
        )

        if not user_db:
            raise ValueError(f"User not found: {shopify_user_id}")

        # Create user data object
        user_data = ShopifyUserData(
            user_id=user_db.id,
            access_token=user_db.access_token,
            product_description_custom_prompt=user_db.product_description_custom_prompt,
            product_description_tone=user_db.product_description_tone,
            product_description_word_count=user_db.product_description_word_count,
            product_description_example=user_db.product_description_example
        )

        await session.commit()

    # Fetch products from Shopify
    try:
        shopify_products = await fetch_shopify_products(
            access_token=user_data.access_token,
            product_ids=input_data.product_ids,
            all_products=input_data.all_products,
            batch_size=input_data.batch_size
        )

        logger.info(f"Fetched {len(shopify_products)} products")

        return FetchProductsOutput(
            products=shopify_products,
            user_data=user_data
        )

    except Exception as e:
        logger.error(f"Error fetching products from Shopify: {str(e)}")
        raise

@activity.defn
async def process_products(
    input_data: ProcessProductsInput,
) -> ProcessResult:
    """
    Process products using AI to generate descriptions.

    Args:
        input_data: Input containing products, user data, and batch job ID

    Returns:
        Result of processing the products
    """
    logger.info(f"Processing {len(input_data.products)} products")

    # Get Redis service instance
    redis_service = get_redis_service()

    # Check already processed products from Redis
    redis_key = f"batch_products:{input_data.batch_job_id}"
    existing_redis_data = redis_service.hgetall(redis_key)

    # Extract product IDs that are already processed from Redis
    processed_product_ids = set()
    if existing_redis_data:
        processed_product_ids = {product_id for product_id in existing_redis_data.keys()}
    logger.info(f"Found {len(processed_product_ids)} already processed products in Redis")

    # Filter out products that have already been processed
    products_to_process = [product for product in input_data.products if product.id not in processed_product_ids]
    logger.info(f"Processing {len(products_to_process)} new products out of {len(input_data.products)} total")

    processed_products: List[ProcessedProduct] = []

    # Process all products in parallel using TaskGroup

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(aiohttp.ClientResponseError),
        wait=tenacity.wait_exponential(multiplier=1, min=1, max=60),
        stop=tenacity.stop_after_attempt(5),
        before_sleep=tenacity.before_sleep_log(logger, logging.WARNING),
        retry_error_callback=lambda retry_state: retry_state.outcome.exception()
    )
    async def process_with_exception_handling(product):
        try:
            processed_product = await _process_single_product(
                product=product,
                user_data=input_data.user_data,
                batch_job_id=input_data.batch_job_id
            )

            # Save successful result to Redis
            redis_key = f"batch_products:{input_data.batch_job_id}"
            payload = {
                "product_id": processed_product.product_id,
                "status": processed_product.status,
                "error": processed_product.error,
                "ai_description": processed_product.ai_description,
                "batch_id": input_data.batch_job_id
            }
            redis_service.hset(redis_key, str(processed_product.product_id), payload)

        except aiohttp.ClientResponseError as e:

            # For other HTTP errors, save failed result to Redis
            redis_key = f"batch_products:{input_data.batch_job_id}"
            payload = {
                "product_id": product.id,
                "status": BatchProductStatus.FAILED.value,
                "error": str(e),
                "ai_description": None,
                "batch_id": input_data.batch_job_id
            }
            redis_service.hset(redis_key, str(product.id), payload)

            # Check if this is a retryable error (too many requests or server error)
            if e.status == 429 or e.status >= 500:
                # Raise as error to trigger retry
                raise NonRetryableError(f"Non-retryable HTTP error: {str(e)}", e)

        except Exception as e:
            # For non-HTTP errors, save failed result to Redis
            redis_key = f"batch_products:{input_data.batch_job_id}"
            payload = {
                "product_id": product.id,
                "status": BatchProductStatus.FAILED.value,
                "error": str(e),
                "ai_description": None,
                "batch_id": input_data.batch_job_id
            }
            redis_service.hset(redis_key, str(product.id), payload)

    async with asyncio.TaskGroup() as tg:
        for product in products_to_process:
            tg.create_task(process_with_exception_handling(product))

    # All tasks completed - results are already saved to Redis

    # Read all processed products from Redis
    redis_key = f"batch_products:{input_data.batch_job_id}"
    redis_data = redis_service.hgetall(redis_key)

    if not redis_data:
        logger.warning(f"No data found in Redis for batch job {input_data.batch_job_id}")
        redis_data = {}

    # Convert Redis data to ProcessedProduct objects
    success_count = 0
    failure_count = 0
    processed_products = []

    for product_id, payload in redis_data.items():
        processed_product = ProcessedProduct(
            product_id=payload["product_id"],
            status=payload["status"],
            error=payload["error"],
            ai_description=payload["ai_description"]
        )
        processed_products.append(processed_product)

        if processed_product.status == BatchProductStatus.COMPLETED.value:
            success_count += 1
        else:
            failure_count += 1

    # Save results to database
    async with get_async_session_with_contextmanager(input_data.tenant) as session:
        await _save_batch_results(processed_products, input_data.batch_job_id, input_data.tenant, session)

    # Clear Redis data after successful save
    redis_service.delete(redis_key)

    logger.info(f"Processing completed. Success: {success_count}, Failures: {failure_count}")

    return ProcessResult(
        processed_products=processed_products,
        success_count=success_count,
        failure_count=failure_count
    )


@activity.defn
async def send_notification(
    input_data: NotificationInput,
) -> bool:
    """
    Send email and app notifications about batch completion.
    
    Args:
        input_data: Notification input data
        
    Returns:
        True if successful
    """
    logger.info(f"Sending notifications for batch job: {input_data.batch_job_id}")
    
    try:
        # Send email notification
        await send_email_notification(
            user_id=input_data.user_id,
            batch_name=input_data.batch_name,
            total_products=input_data.total_products,
            success_count=input_data.success_count,
            failure_count=input_data.failure_count
        )
        
        # Send app notification
        await send_app_notification(
            user_id=input_data.user_id,
            batch_job_id=input_data.batch_job_id,
            message=f"Bulk SEO generation completed: {input_data.success_count}/{input_data.total_products} successful"
        )
        
        logger.info(f"Successfully sent notifications for batch job: {input_data.batch_job_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending notifications: {str(e)}")
        # Don't fail the whole workflow for notification errors
        return False
