from enum import StrEnum

# Temporal Workflow Implementation for SuperSearch

This directory contains the Temporal workflow implementation for SuperSearch, which is used to handle product synchronization from various sources.

## Directory Structure

- `core/`: Core utilities for Temporal workflow implementation
  - `client.py`: Utilities for connecting to Temporal and starting workflows
  - `worker.py`: Utilities for creating and running Temporal workers
  - `queues.py`: Task queue definitions and workflow mappings
  - `run_worker.py`: Script to run the product sync worker

- `workflows/`: Temporal workflows for SuperSearch
  - `product_sync/`: Product synchronization workflow
    - `workflow.py`: Product sync workflow definition
    - `activities.py`: Product sync activities
    - `utils.py`: Helper functions for product sync activities
    - `start_workflow.py`: Utilities for starting product sync workflows

## Task Queues

Task queues are defined in the `app/temporal/core/queues.py` file as an enum:

```python
from enum import StrEnum
class TaskQueue(StrEnum):
    PRODUCT_SYNC = "product-sync-task-queue"
    # Add more task queues as needed
```

Each task queue is mapped to its corresponding workflows and activities:

```python
# Mapping from TaskQueue to workflow types
QUEUE_WORKFLOW_MAP: Dict[TaskQueue, List[Type]] = {
    TaskQueue.PRODUCT_SYNC: [ProductSyncWorkflow],
    # Add more mappings as needed
}

# Mapping from TaskQueue to activity functions
QUEUE_ACTIVITY_MAP: Dict[TaskQueue, List[Any]] = {
    TaskQueue.PRODUCT_SYNC: [
        create_sync_history,
        get_products_from_source,
        process_products,
        insert_products,
        update_sync_history,
    ],
    # Add more mappings as needed
}
```

## Workflow Types

### Product Sync Workflow

The product sync workflow handles the synchronization of products from various sources:

1. **MANUAL_FILE_UPLOAD**: Products are provided in the request
2. **CRAWLER**: Products are fetched from web pages
3. **SUPERSEARCH_API**: Products are provided in the request
4. **HOSTED_FILE**: Products are fetched from a hosted CSV or JSON file
5. **SQL_DATABASE**: Products are fetched from a SQL database

The workflow accepts a `ProductSyncInput` object directly, which contains both the source configuration and product data (if applicable). This simplifies the workflow interface and ensures type safety.

The workflow process:
1. Creates a sync history record
2. Fetches products from the source
3. Processes products (generates embeddings)
4. Inserts products into the database
5. Updates the sync history record

## Activity Input/Output Models

Activities use Pydantic models for input and output parameters, providing structured data handling with validation:

```python
# Example input model
class GetProductsInput(BaseModel):
    source: SyncSource
    source_config: SyncConfig
    product_input: Optional[Dict[str, Any]] = None
    
# Example output model
class ProductList(BaseModel):
    products: List[ProductData]
```

## Code Organization

The product sync workflow code is organized as follows:

1. **workflow.py**: Contains the main workflow definition and orchestration logic
2. **activities.py**: Contains the activity definitions that are registered with Temporal
3. **utils.py**: Contains helper functions used by the activities, such as:
   - `process_product_data`: Processes product data and generates embeddings
   - `generate_searchable_content`: Generates searchable content from product data
   - `get_products_from_manual_upload`: Retrieves products from manual file uploads
   - `get_products_from_crawler`: Retrieves products using a web crawler
   - `get_products_from_supersearch_api`: Retrieves products from the Supersearch API
   - `get_products_from_hosted_file`: Retrieves products from hosted files (CSV or JSON)
   - `get_products_from_sql_database`: Retrieves products from an SQL database

This separation of concerns improves code maintainability by:
- Keeping activity definitions focused on Temporal-specific logic
- Moving implementation details to utility functions
- Making the code more testable and reusable

## Trigger Types

Product sync workflows can be triggered in two ways:

1. **IMMEDIATE**: The workflow is executed immediately
   - Used for MANUAL_FILE_UPLOAD and SUPERSEARCH_API sources

2. **SCHEDULED**: The workflow is scheduled to run at regular intervals
   - Used for CRAWLER, HOSTED_FILE, and SQL_DATABASE sources
   - Scheduling is based on the SyncInterval enum (DAILY, WEEKLY, MONTHLY)

## Running the Worker

To run the product sync worker:

```bash
python -m app.temporal.core.run_worker
```

Environment variables:
- `TEMPORAL_SERVER_URL`: Temporal server URL (default: localhost:7233)
- `TEMPORAL_NAMESPACE`: Temporal namespace (default: development)
- `TEMPORAL_TASK_QUEUE`: Task queue name (default: "product-sync-task-queue") 