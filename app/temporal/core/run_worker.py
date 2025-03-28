"""Script to run the product sync worker."""
import asyncio
import logging.handlers
import os
import sys
from pathlib import Path

# Add the project root to the Python path when running as standalone script
if __name__ == "__main__":
    # Get the absolute path of the project root
    project_root = str(Path(__file__).parents[3])
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

from app.temporal.core.client import get_temporal_client
from app.temporal.core.worker import run_worker, create_worker
from app.temporal.core.queues import TaskQueue, get_workflows_for_queue, get_activities_for_queue

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        # Console handler
        logging.StreamHandler(sys.stdout),
        # File handler - rotating file handler to prevent logs from growing too large
        logging.handlers.RotatingFileHandler(
            'logs/temporal_worker.log',
            maxBytes=10485760,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
    ]
)

logger = logging.getLogger(__name__)

async def main():
    """Run the product sync worker."""
    # Get Temporal client
    server_url = os.getenv("TEMPORAL_SERVER_URL", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "supersearch")
    
    logger.info(f"Connecting to Temporal server at {server_url} with namespace {namespace}")
    client = await get_temporal_client(server_url, namespace)
    
    # Define task queue
    queue_name = os.getenv("TEMPORAL_TASK_QUEUE", TaskQueue.PRODUCT_SYNC.value)
    task_queue = TaskQueue(queue_name)
    
    # Get workflows and activities for the task queue
    workflows = get_workflows_for_queue(task_queue)
    activities = get_activities_for_queue(task_queue)
    
    if not workflows or not activities:
        logger.error(f"No workflows or activities found for task queue: {task_queue}")
        return
    
    # Create worker
    worker = await create_worker(
        client= client,
        task_queue= queue_name,
        workflows=workflows,
        activities=activities,
        max_concurrent_activities=10,
    )
    
    # Run worker
    logger.info(f"Starting worker for task queue: {task_queue}")
    await run_worker(worker)

if __name__ == "__main__":
    asyncio.run(main()) 