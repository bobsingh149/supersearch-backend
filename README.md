# SuperSearch

SuperSearch is a powerful search platform that enables efficient product synchronization, indexing, and searching with advanced embedding-based semantic search capabilities.

## Features

- **Multi-source Product Synchronization**: Import products from various sources:
  - Manual file uploads (CSV, JSON)
  - Web crawlers
  - SuperSearch API
  - Hosted files (CSV, JSON)
  - SQL databases

- **Durable Workflow Processing**: Leverages Temporal for reliable, scalable workflow execution:
  - Automatic retries for failed activities
  - Scheduled synchronization with configurable intervals
  - Graceful error handling and recovery

- **Advanced Search Capabilities**:
  - Semantic search using vector embeddings
  - Hybrid search combining vector and keyword search
  - Customizable search parameters

## Architecture

SuperSearch is built with a modern, scalable architecture:

- **FastAPI Backend**: High-performance, async API framework
- **PostgreSQL with pgvector**: For efficient vector storage and search
- **Temporal**: For durable, reliable workflow execution
- **Embedding Models**: For generating semantic embeddings

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL with pgvector extension
- Temporal server

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/supersearch.git
   cd supersearch
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up environment variables (create a `.env` file):
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/supersearch
   TEMPORAL_SERVER_URL=localhost:7233
   TEMPORAL_NAMESPACE=development
   ```

4. Run database migrations:
   ```bash
   alembic upgrade head
   ```

### Logging

SuperSearch uses a comprehensive logging system that:
- Outputs logs to both console and files
- Uses rotating file handlers to manage log size
- Stores logs in the `logs/` directory:
  - `supersearch.log`: Main application logs
  - `temporal_worker.log`: Temporal worker logs

Log files are automatically rotated when they reach 10MB, with a maximum of 5 backup files maintained.

### Running the Application

1. Start the API server:
   ```bash
   uvicorn app.main:app --reload
   ```

2. Start the Temporal worker:
   ```bash
   python -m app.temporal.core.run_worker
   ```

## Usage

### Syncing Products

To sync products, send a POST request to `/sync-products` with a `ProductSyncInput` object:

```json
{
  "source_config": {
    "source": "MANUAL_FILE_UPLOAD",
    "file_format": "json"
  },
  "products": {
    "id_field": "id",
    "title_field": "name",
    "searchable_attribute_fields": ["name", "description", "category"],
    "data": [
      {
        "id": "1",
        "name": "Product 1",
        "description": "Description of product 1",
        "category": "Category A"
      }
    ]
  }
}
```

### Searching Products

To search for products, send a GET request to `/search-products` with query parameters:

```
/search-products?query=your search query&limit=10
```

## Project Structure

- `app/`: Main application code
  - `core/`: Core utilities and configurations
  - `database/`: Database models and session management
  - `models/`: Pydantic models for API requests/responses
  - `routes/`: API route handlers
  - `services/`: Business logic services
  - `temporal/`: Temporal workflow implementation
    - `core/`: Core utilities for Temporal
    - `workflows/`: Workflow definitions
  - `utils/`: Utility functions

## Development

### Adding a New Sync Source

1. Add a new source type to `SyncSource` enum in `app/models/sync_config.py`
2. Create a new source config class in `app/models/sync_config.py`
3. Implement the product retrieval logic in `app/temporal/workflows/product_sync/activities.py`
4. Update the `SYNC_SOURCE_TRIGGER_MAP` in `app/models/sync_config.py`

### Adding a New Workflow

1. Create a new workflow directory in `app/temporal/workflows/`
2. Implement the workflow and activities
3. Add the workflow to the `TaskQueue` enum and mappings in `app/temporal/core/queues.py`

### Activity Input/Output Models

Temporal activities use Pydantic models for input and output parameters:

1. Define input/output models in `app/temporal/workflows/your_workflow/models.py`
2. Use these models in your activities instead of primitive types
3. This provides type safety, validation, and better documentation

Example:
```python
# In models.py
class CreateSyncHistoryInput(BaseModel):
    source: SyncSource

# In activities.py
@activity.defn
async def create_sync_history(input_data: CreateSyncHistoryInput) -> CreateSyncHistoryOutput:
    # Activity implementation
```

### Best Practices for Pydantic Models

SuperSearch follows these best practices for Pydantic models:

1. **Avoid primitive collections**: Instead of using `List[Dict]` or `Dict[str, Any]`, create proper Pydantic models
   ```python
   # Instead of this:
   class BadModel(BaseModel):
       items: List[Dict[str, Any]]
   
   # Do this:
   class Item(BaseModel):
       name: str
       value: int
   
   class GoodModel(BaseModel):
       items: List[Item]
   ```

2. **Nested models**: Use nested Pydantic models to represent complex data structures
   ```python
   class ProductData(BaseModel):
       product: Product
   
   class ProductList(BaseModel):
       products: List[ProductData]
   ```

3. **Type safety**: Leverage Pydantic's type validation to ensure data integrity throughout the workflow

## License

[MIT License](LICENSE)

## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/)
- [Temporal](https://temporal.io/)
- [pgvector](https://github.com/pgvector/pgvector) 