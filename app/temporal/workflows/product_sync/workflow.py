"""Product sync workflow."""
import logging
from datetime import timedelta
from typing import Dict, Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.models.sync_config import SyncStatus
    from app.models.sync_product import ProductSyncWithIdInput
    from app.temporal.workflows.product_sync.models import (
        UpdateSyncHistoryInput,
        ProductSyncInputWithTenant,
    )
    from app.temporal.workflows.product_sync.activities import (
        get_products_from_source,
        insert_products,
        update_sync_history,
    )

logger = logging.getLogger(__name__)

@workflow.defn
class ProductSyncWorkflow:
    """
    Workflow for syncing products from various sources.
    """
    
    @workflow.run
    async def run(
        self,
        sync_input_with_id: ProductSyncWithIdInput,
    ) -> Dict[str, Any]:
        """
        Run the product sync workflow.
        
        Args:
            sync_input_with_id: Product sync input with sync_id
            
        Returns:
            Dictionary with sync result
        """
        # Define retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=5),
            maximum_attempts=3,
        )
        
        # Define timeout for activities
        start_to_close_timeout = timedelta(minutes=30)
        
        # Extract sync_input and sync_id from the combined input
        sync_input = sync_input_with_id.sync_input
        sync_id = sync_input_with_id.sync_id
        tenant = sync_input_with_id.tenant
        source = sync_input.source_config.source

        try:
            # Step 1: Get products from source (products are processed in this step)
            sync_input_with_tenant = ProductSyncInputWithTenant(
                sync_input=sync_input,
                tenant=tenant
            )
            products_output = await workflow.execute_activity(
                get_products_from_source,
                sync_input_with_tenant,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
            )
            
            if not products_output.products:
                # No products found, update sync history and return
                update_history_input = UpdateSyncHistoryInput(
                    sync_id=sync_id,
                    status=SyncStatus.SUCCESS,
                    records_processed=0,
                    tenant=tenant,
                )
                await workflow.execute_activity(
                    update_sync_history,
                    update_history_input,
                    start_to_close_timeout=start_to_close_timeout,
                    retry_policy=retry_policy,
                )
                
                return {
                    "message": "No products found to sync",
                    "sync_id": sync_id,
                }
            
            # Step 2: Insert products into database
            records_processed = await workflow.execute_activity(
                insert_products,
                products_output,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
            )
            
            # Step 3: Update sync history
            update_history_input = UpdateSyncHistoryInput(
                sync_id=sync_id,
                status=SyncStatus.SUCCESS,
                records_processed=records_processed,
                tenant=tenant,
            )
            await workflow.execute_activity(
                update_sync_history,
                update_history_input,
                start_to_close_timeout=start_to_close_timeout,
                retry_policy=retry_policy,
            )
            
            return {
                "message": f"Successfully synced {records_processed} products",
                "sync_id": sync_id,
            }
        
        except Exception as e:
            # Update the sync history with failure status
            try:
                update_history_input = UpdateSyncHistoryInput(
                    sync_id=sync_id,
                    status=SyncStatus.FAILED,
                    tenant=tenant,
                )
                await workflow.execute_activity(
                    update_sync_history,
                    update_history_input,
                    start_to_close_timeout=timedelta(minutes=5),
                    retry_policy=retry_policy,
                )
            except Exception as update_error:
                # Log error but don't raise
                logger.error(f"Error updating sync history: {str(update_error)}")
            
            # Re-raise the original exception
            raise Exception(f"Error syncing products: {str(e)}") 