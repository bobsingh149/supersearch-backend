"""Temporal worker utilities."""
import asyncio
import logging
from typing import List, Type, Dict, Any, Optional

from temporalio.client import Client
from temporalio.worker import Worker

logger = logging.getLogger(__name__)

async def create_worker(
    client: Client,
    task_queue: str,
    workflows: List[Type],
    activities: List[Any],
    max_concurrent_activities: Optional[int] = None,
) -> Worker:
    """
    Create a Temporal worker.
    
    Args:
        client: Temporal client
        task_queue: Task queue name
        workflows: List of workflow classes
        activities: List of activity functions
        max_concurrent_activities: Maximum number of concurrent activities
        
    Returns:
        Temporal worker
    """
    logger.info(f"Creating worker for task queue: {task_queue}")
    
    worker_options = {}
    if max_concurrent_activities:
        worker_options["max_concurrent_activities"] = max_concurrent_activities
    
    worker = Worker(
        client=client,
        task_queue=task_queue,
        workflows=workflows,
        activities=activities,
    )
    
    logger.info(f"Worker created for task queue: {task_queue}")
    return worker

async def run_worker(
    worker: Worker,
    shutdown_event: Optional[asyncio.Event] = None,
) -> None:
    """
    Run a Temporal worker with graceful shutdown handling.
    
    Args:
        worker: Temporal worker
        shutdown_event: Event to signal worker shutdown
    """
    if shutdown_event is None:
        shutdown_event = asyncio.Event()

    logger.info("Started worker with task queue " + worker.task_queue)
    
    # Run the worker until shutdown is requested
    async with worker:
        await shutdown_event.wait()
    
    logger.info("Worker shutdown complete")

async def run_workers(
    client: Client,
    worker_configs: List[Dict[str, Any]],
) -> None:
    """
    Run multiple Temporal workers.
    
    Args:
        client: Temporal client
        worker_configs: List of worker configurations
    """
    shutdown_event = asyncio.Event()

    # Create workers
    workers = []
    for config in worker_configs:
        worker = await create_worker(
            client,
            config["task_queue"],
            config["workflows"],
            config["activities"],
            config.get("max_concurrent_activities"),
        )
        workers.append(worker)
    
    # Start all workers
    logger.info(f"Starting {len(workers)} workers...")
    
    async with asyncio.TaskGroup() as tg:
        for worker in workers:
            async with worker:
                tg.create_task(shutdown_event.wait())
    
    logger.info("All workers shutdown complete") 