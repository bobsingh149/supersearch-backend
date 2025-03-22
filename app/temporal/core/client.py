"""Temporal client utilities."""
import logging
from datetime import timedelta
from typing import Any, Optional, Type, TypeVar, Callable

from temporalio.client import Client, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.service import ConnectConfig, ServiceClient
from temporalio.api.workflowservice.v1 import (
    ListNamespacesRequest,
    RegisterNamespaceRequest
)
from google.protobuf.duration_pb2 import Duration
from app.models.sync_config import SyncInterval

logger = logging.getLogger(__name__)

# Type variable for workflow return type
T = TypeVar("T")

# Default retry policy for activities
DEFAULT_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=3,
)

async def create_namespace_if_not_exists(
    server_url: str,
    namespace: str,
    retention_days: int = 7
) -> None:
    """
    Create a Temporal namespace if it doesn't exist.
    
    Args:
        server_url: Temporal server URL
        namespace: Temporal namespace to create
        retention_days: Workflow execution retention period in days
    """
    logger.info(f"Checking if namespace '{namespace}' exists")
    
    # Connect to Temporal service
    service_client = await ServiceClient.connect(
        ConnectConfig(target_host=server_url)
    )
    
    # List existing namespaces
    list_resp = await service_client.workflow_service.list_namespaces(ListNamespacesRequest())
    
    # Check if namespace already exists
    for existing_namespace in list_resp.namespaces:
        if existing_namespace.namespace_info.name == namespace:
            logger.info(f"Namespace '{namespace}' already exists")
            return
    
    # Create namespace if it doesn't exist
    logger.info(f"Creating namespace '{namespace}'")
    retention_seconds = retention_days * 24 * 60 * 60
    
    await service_client.workflow_service.register_namespace(
        RegisterNamespaceRequest(
            namespace=namespace,
            workflow_execution_retention_period=Duration(seconds=retention_seconds),
        )
    )
    
    logger.info(f"Namespace '{namespace}' created successfully")

async def get_temporal_client(
    server_url: str = "localhost:7233",
    namespace: str = "supersearch",
) -> Client:
    """
    Create and return a Temporal client.
    
    Args:
        server_url: Temporal server URL
        namespace: Temporal namespace
        create_namespace: Whether to create the namespace if it doesn't exist
        retention_days: Workflow execution retention period in days

    Returns:
        Temporal client
    """
    logger.info(f"Connecting to Temporal server at {server_url} with namespace {namespace}")

    await create_namespace_if_not_exists(server_url, namespace, 7)
    
    client = await Client.connect(
        server_url,
        namespace=namespace,
    )
    
    logger.info("Connected to Temporal server")
    return client

async def start_workflow(
    client: Client,
    workflow_type: Type,
    workflow_method: Callable,
    workflow_input: Any,
    workflow_id: str,
    task_queue: str,
    cron_schedule: Optional[str] = None,
    retry_policy: Optional[RetryPolicy] = None,
    execution_timeout: Optional[timedelta] = None,
) -> WorkflowHandle[Any, Any]:
    """
    Start a Temporal workflow.
    
    Args:
        client: Temporal client
        workflow_type: Workflow class
        workflow_method: Workflow method to execute
        workflow_input: Positional arguments for the workflow
        workflow_id: Unique workflow ID
        task_queue: Task queue name
        cron_schedule: Cron schedule for recurring workflows
        retry_policy: Retry policy for the workflow
        execution_timeout: execution timeout for the workflow

    Returns:
        Workflow handle
    """
    logger.info(f"Starting workflow {workflow_type.__name__} with ID {workflow_id} on queue {task_queue}")
    
    # Prepare workflow options
    workflow_options = {
        "id": workflow_id,
        "task_queue": task_queue,
    }
    
    if cron_schedule:
        workflow_options["cron_schedule"] = cron_schedule
        logger.info(f"Workflow scheduled with cron: {cron_schedule}")
    
    if retry_policy:
        workflow_options["retry_policy"] = retry_policy

    if execution_timeout:
        workflow_options["execution_timeout"]  = execution_timeout
    
    # Start the workflow
    handle = await client.start_workflow(
        workflow= workflow_method,
        arg=workflow_input,
        **workflow_options,
    )
    
    logger.info(f"Workflow started with ID: {handle.id}")
    return handle

def get_cron_expression(sync_interval: SyncInterval) -> str:
    """
    Convert a SyncInterval to a cron expression.
    
    Args:
        sync_interval: SyncInterval enum value
        
    Returns:
        Cron expression string
    """
    # Map SyncInterval to cron expressions
    cron_map = {
        SyncInterval.DAILY: "0 0 * * *",      # Run at midnight every day
        SyncInterval.WEEKLY: "0 0 * * 0",     # Run at midnight every Sunday
        SyncInterval.MONTHLY: "0 0 1 * *",    # Run at midnight on the 1st of every month
    }
    
    return cron_map.get(sync_interval, "0 0 * * *")  # Default to daily if not found 