"""Task queue definitions for Temporal workflows."""
from enum import StrEnum
from typing import Dict, Type, List, Any

from app.temporal.workflows.product_sync.workflow import ProductSyncWorkflow
from app.temporal.workflows.product_sync.activities import (
    create_sync_history,
    get_products_from_source,
    insert_products,
    update_sync_history,
)

class TaskQueue(StrEnum):
    """Enum for Temporal task queues."""
    PRODUCT_SYNC = "product-sync-task-queue"
    # Add more task queues as needed
    # EXAMPLE_QUEUE = "example-task-queue"

# Mapping from TaskQueue to workflow types
QUEUE_WORKFLOW_MAP: Dict[TaskQueue, List[Type]] = {
    TaskQueue.PRODUCT_SYNC: [ProductSyncWorkflow],
    # Add more mappings as needed
    # TaskQueue.EXAMPLE_QUEUE: [ExampleWorkflow],
}

# Mapping from TaskQueue to activity functions
QUEUE_ACTIVITY_MAP: Dict[TaskQueue, List[Any]] = {
    TaskQueue.PRODUCT_SYNC: [
        create_sync_history,
        get_products_from_source,
        insert_products,
        update_sync_history,
    ],
    # Add more mappings as needed
    # TaskQueue.EXAMPLE_QUEUE: [example_activity1, example_activity2],
}

def get_workflows_for_queue(queue: TaskQueue) -> List[Type]:
    """
    Get workflow types for a task queue.
    
    Args:
        queue: Task queue
        
    Returns:
        List of workflow types
    """
    return QUEUE_WORKFLOW_MAP.get(queue, [])

def get_activities_for_queue(queue: TaskQueue) -> List[Any]:
    """
    Get activity functions for a task queue.
    
    Args:
        queue: Task queue
        
    Returns:
        List of activity functions
    """
    return QUEUE_ACTIVITY_MAP.get(queue, []) 