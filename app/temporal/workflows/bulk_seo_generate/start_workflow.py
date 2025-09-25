"""Utilities for starting bulk SEO generation workflows."""
import logging
import uuid
from typing import Dict, Any

from temporalio.client import Client
from datetime import timedelta

from app.temporal.core.client import start_workflow
from app.temporal.core.queues import TaskQueue
from app.temporal.workflows.bulk_seo_generate.workflow import BulkSeoGenerateWorkflow
from app.temporal.workflows.bulk_seo_generate.models import BulkSeoGenerateInput

logger = logging.getLogger(__name__)

async def start_bulk_seo_generate_workflow(
    client: Client,
    input_data: BulkSeoGenerateInput,
    task_queue: TaskQueue = TaskQueue.BULK_SEO_GENERATE,
) -> Dict[str, Any]:
    """
    Start a bulk SEO generation workflow.
    
    Args:
        client: Temporal client
        input_data: Bulk SEO generation input
        task_queue: Task queue enum
        
    Returns:
        Dictionary with workflow ID and run ID
    """
    # Generate a unique workflow ID
    workflow_id = f"bulk-seo-generate-{input_data.shopify_user_id}-{uuid.uuid4()}"
    
    logger.info(f"Starting bulk SEO generation workflow for user {input_data.shopify_user_id}")
    
    # Start the workflow
    handle = await start_workflow(
        client=client,
        workflow_type=BulkSeoGenerateWorkflow,
        workflow_method=BulkSeoGenerateWorkflow.run,
        workflow_input=input_data,
        workflow_id=workflow_id,
        task_queue=str(task_queue.value),
        execution_timeout=timedelta(hours=1)  # Allow up to 1 hour for large batches
    )

    return {
        "workflow_id": handle.id,
        "run_id": handle.first_execution_run_id,
        "batch_job_id": input_data.batch_job_id,
    }
