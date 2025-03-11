"""Utilities for starting product sync workflows."""
import logging
import uuid
from typing import Dict, Any

from asyncpg.pgproto.pgproto import timedelta
from temporalio.client import Client

from app.models.sync_config import SYNC_SOURCE_TRIGGER_MAP, TriggerType
from app.models.sync_product import ProductSyncWithIdInput
from app.temporal.core.client import start_workflow, get_cron_expression
from app.temporal.core.queues import TaskQueue
from app.temporal.workflows.product_sync.workflow import ProductSyncWorkflow

logger = logging.getLogger(__name__)

async def start_product_sync_workflow(
    client: Client,
    sync_input_with_id: ProductSyncWithIdInput,
    task_queue: TaskQueue = TaskQueue.PRODUCT_SYNC,
) -> Dict[str, Any]:
    """
    Start a product sync workflow based on the sync input.
    
    Args:
        client: Temporal client
        sync_input_with_id: Product sync input with sync_id
        task_queue: Task queue enum
        
    Returns:
        Dictionary with workflow ID and run ID
    """
    # Extract the sync_input from the combined input
    sync_input = sync_input_with_id.sync_input
    source = sync_input.source_config.source
    trigger_type = SYNC_SOURCE_TRIGGER_MAP.get(source, TriggerType.IMMEDIATE)
    
    # Generate a unique workflow ID
    workflow_id = f"product-sync-{source.value.lower()}-{uuid.uuid4()}"
    
    # Determine if this is a scheduled workflow
    cron_schedule = None
    if (
        trigger_type == TriggerType.SCHEDULED 
        and sync_input.source_config.auto_sync 
        and sync_input.source_config.sync_interval
    ):
        cron_schedule = get_cron_expression(sync_input.source_config.sync_interval)
        logger.info(f"Setting up scheduled workflow with cron: {cron_schedule}")
    
    # Start the workflow - pass sync_input_with_id as a positional argument before keyword arguments
    handle = await start_workflow(
        client= client,
        workflow_type= ProductSyncWorkflow,
        workflow_method=  ProductSyncWorkflow.run,
        workflow_input=  sync_input_with_id,
        workflow_id=workflow_id,
        task_queue=task_queue.value,
        cron_schedule=cron_schedule,
        execution_timeout=timedelta(minutes=3)
    )

    return {
        "workflow_id": handle.id,
        "run_id": handle.first_execution_run_id,
        "is_scheduled": cron_schedule is not None,
    } 