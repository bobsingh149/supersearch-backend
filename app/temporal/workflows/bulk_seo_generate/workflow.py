"""Bulk SEO generation workflow."""
import logging
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

from app.temporal.workflows.bulk_seo_generate.models import (
    BulkSeoGenerateInput,
    FetchProductsInput,
    ProcessProductsInput,
    NotificationInput,
)
from app.temporal.workflows.bulk_seo_generate.errors import NonRetryableError
from app.temporal.workflows.bulk_seo_generate.activities import (
    fetch_products_and_user_data,
    process_products,
    send_notification,
)

logger = logging.getLogger(__name__)

@workflow.defn
class BulkSeoGenerateWorkflow:
    """
    Workflow for bulk SEO generation from Shopify products.
    """
    
    @workflow.run
    async def run(
        self,
        input_data: BulkSeoGenerateInput,
    ) -> Dict[str, Any]:
        """
        Run the bulk SEO generation workflow.
        
        Args:
            input_data: Bulk SEO generation input
            
        Returns:
            Dictionary with generation result
        """
        # Define retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=5),
            maximum_attempts=3,
            non_retryable_error_types=[ValueError, NonRetryableError],
        )
        
        # Define timeout for activities
        start_to_close_timeout = timedelta(minutes=30)
        
        batch_job_id = input_data.batch_job_id
        
        try:
            # Step 1: Fetch products and user data (also updates batch job status to running)
            logger.info(f"Starting bulk SEO generation for batch job: {batch_job_id}")

            fetch_input = FetchProductsInput(
                shopify_user_id=input_data.shopify_user_id,
                batch_job_id=batch_job_id,
                product_ids=input_data.product_ids,
                all_products=input_data.all_products,
                batch_size=250,
                tenant=input_data.tenant
            )
            
            fetch_result = await workflow.execute_activity(
                fetch_products_and_user_data,
                fetch_input,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
            )
            
            if not fetch_result.products:
                # No products found to process
                return {
                    "message": "No products found to process",
                    "batch_job_id": batch_job_id,
                    "total_products": 0,
                    "success_count": 0,
                    "failure_count": 0,
                }
            
            # Step 3: Process all products
            products = fetch_result.products
            total_products = len(products)

            logger.info(f"Processing {total_products} products")

            # Process all products in a single activity
            process_input = ProcessProductsInput(
                products=products,
                user_data=fetch_result.user_data,
                batch_job_id=batch_job_id,
                tenant=input_data.tenant
            )

            process_result = await workflow.execute_activity(
                process_products,
                process_input,
                start_to_close_timeout=timedelta(minutes=45),  # Longer timeout for AI processing
                retry_policy=retry_policy,
            )

            total_success = process_result.success_count
            total_failure = process_result.failure_count

            logger.info(f"Processing completed. Success: {total_success}, Failures: {total_failure}")
            
            # Step 4: Processing completed successfully
            # Batch job status can be monitored through the workflow completion
            
            # Step 5: Send notification
            notification_input = NotificationInput(
                batch_job_id=batch_job_id,
                user_id=input_data.shopify_user_id,
                total_products=total_products,
                success_count=total_success,
                failure_count=total_failure,
                batch_name=f"Bulk SEO Generation - {total_products} products"
            )
            
            await workflow.execute_activity(
                send_notification,
                notification_input,
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=retry_policy,
            )
            
            return {
                "message": f"Successfully processed {total_success} out of {total_products} products",
                "batch_job_id": batch_job_id,
                "total_products": total_products,
                "success_count": total_success,
                "failure_count": total_failure,
            }
        
        except Exception as e:
            # Log the error - batch job status can be updated manually or through monitoring
            logger.error(f"Error in bulk SEO generation for batch {batch_job_id}: {str(e)}")

            # Re-raise the original exception
            raise Exception(f"Error in bulk SEO generation: {str(e)}")
