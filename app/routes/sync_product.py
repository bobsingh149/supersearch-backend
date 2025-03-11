import logging
import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.database.session import get_async_session
from app.models.sync_product import ProductSyncInput, ProductSyncWithIdInput
from app.models.sync_history import SyncHistoryDB, SyncHistoryCreate
from app.models.sync_config import SyncStatus
from app.temporal.core.client import get_temporal_client
from app.temporal.workflows.product_sync.start_workflow import start_product_sync_workflow

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sync-products",
    tags=["sync-products"]
)

@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def sync_products(
    sync_input: ProductSyncInput,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Sync products from various sources:
    - MANUAL_FILE_UPLOAD: Products are provided in the request
    - CRAWLER: Products are fetched from web pages
    - SUPERSEARCH_API: Products are provided in the request
    - HOSTED_FILE: Products are fetched from a hosted CSV or JSON file
    - SQL_DATABASE: Products are fetched from a SQL database
    
    The sync process is handled by a Temporal workflow:
    1. Creates a sync history record
    2. Fetches products from the source
    3. Processes products (generates embeddings)
    4. Inserts products into the database
    5. Updates the sync history record
    
    Returns:
        A response with the sync_id that can be used to poll the sync history API
    """
    try:
        # Create sync history record
        sync_history = SyncHistoryCreate(
            source=sync_input.source_config.source,
            status=SyncStatus.PROCESSING,
            start_time=datetime.datetime.now(datetime.UTC)
        )
        
        # Convert to dict and ensure enums are converted to strings
        sync_history_dict = sync_history.model_dump()
        sync_history_dict['source'] = sync_history_dict['source'].value
        sync_history_dict['status'] = sync_history_dict['status'].value
        
        sync_history_db = SyncHistoryDB(**sync_history_dict)
        session.add(sync_history_db)
        await session.flush()
        
        # Commit the transaction
        await session.commit()
        
        logger.info(f"Created sync history record with ID: {sync_history_db.id}")
        
        # Get Temporal client
        client = await get_temporal_client()
        
        # Create the combined input with sync_id
        product_sync_with_id = ProductSyncWithIdInput(
            sync_input=sync_input,
            sync_id=sync_history_db.id
        )
        
        # Start the product sync workflow
        await start_product_sync_workflow(client, product_sync_with_id)


        return {
            "message": "Product sync workflow started. You can use the sync_id to poll the sync history API to check the status.",
            "sync_id": sync_history_db.id,
        }
    except Exception as e:
        logger.error(f"Error starting product sync workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e)) 