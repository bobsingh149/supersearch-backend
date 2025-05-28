"""Product sync activities."""
import logging
import datetime

from temporalio import activity
from sqlalchemy.dialects.postgresql import insert

from app.database.session import get_async_session_with_contextmanager
from app.models.product import ProductDB
from app.models.sync_history import SyncHistoryDB, SyncHistoryCreate, SyncHistoryUpdate
from app.models.sync_config import (
    SyncSource, 
    SyncStatus,
)
from app.models.sync_product import ProductSyncInput
from app.temporal.workflows.product_sync.models import (
    CreateSyncHistoryInput,
    CreateSyncHistoryOutput,
    ProductsOutput,
    UpdateSyncHistoryInput,
    UpdateSyncHistoryOutput,
    ProductSyncInputWithTenant,
)
from app.temporal.workflows.product_sync.utils import (
    get_products_from_manual_upload,
    get_products_from_crawler,
    get_products_from_supersearch_api,
    get_products_from_hosted_file,
    get_products_from_sql_database,
)

logger = logging.getLogger(__name__)

@activity.defn
async def create_sync_history(
    input_data: CreateSyncHistoryInput,
) -> CreateSyncHistoryOutput | None:
    """
    Create a sync history record.
    
    Args:
        input_data: Input data containing the source
        
    Returns:
        Output with sync history ID and source
    """
    logger.info(f"Creating sync history record for source: {input_data.source}")
    
    async with get_async_session_with_contextmanager("demo_movies") as session:
        # Create sync history record
        sync_history = SyncHistoryCreate(
            source=input_data.source,
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
        
        return CreateSyncHistoryOutput(
            sync_id=sync_history_db.id,
            source=input_data.source
        )
    

@activity.defn
async def get_products_from_source(
    sync_input_with_tenant: ProductSyncInputWithTenant,
) -> ProductsOutput:
    """
    Get products from the specified source.
    
    Args:
        sync_input_with_tenant: ProductSyncInputWithTenant containing source configuration, product data, and tenant
        
    Returns:
        List of products
    """
    sync_input = sync_input_with_tenant.sync_input
    tenant = sync_input_with_tenant.tenant
    source = sync_input.source_config.source
    logger.info(f"Getting products from source: {source} for tenant: {tenant}")
    
    # Get products based on the source type
    if source == SyncSource.MANUAL_FILE_UPLOAD:
        products = await get_products_from_manual_upload(sync_input, tenant)
    elif source == SyncSource.CRAWLER:
        products = await get_products_from_crawler(sync_input, tenant)
    elif source == SyncSource.SUPERSEARCH_API:
        products = await get_products_from_supersearch_api(sync_input, tenant)
    elif source == SyncSource.HOSTED_FILE:
        products = await get_products_from_hosted_file(sync_input, tenant)
    elif source == SyncSource.SQL_DATABASE:
        products = await get_products_from_sql_database(sync_input, tenant)
    else:
        raise ValueError(f"Unsupported source: {source}")
    
    logger.info(f"Retrieved {len(products)} products from source: {source}")
    
    # Return products directly
    return ProductsOutput(products=products)

@activity.defn
async def insert_products(
    products_output: ProductsOutput,
) -> int | None:
    """
    Insert products into the database.
    
    Args:
        products_output: List of products to insert

    Returns:
        Number of products inserted
    """
    products_count = len(products_output.products)
    return products_count
    # logger.info(f"Inserting {products_count} products into database")
    
    # async with get_async_session_with_contextmanager() as session:
    #     # Convert processed products to dictionaries for bulk insert
    #     products_to_insert = []
    #     for product in products_output.products:
    #         # Convert to dict and exclude created_at and updated_at as they are handled by the database
    #         product_dict = product.model_dump(exclude={'created_at', 'updated_at'})
    #         products_to_insert.append(product_dict)
        
    #     # Bulk insert using insert()
    #     stmt = insert(ProductDB).values(products_to_insert)
    #     await session.execute(stmt)
        
    #     # Commit the transaction
    #     await session.commit()
        
    #     logger.info(f"Inserted {products_count} products into database")
        

@activity.defn
async def update_sync_history(
    input_data: UpdateSyncHistoryInput,
) -> UpdateSyncHistoryOutput | None:
    """
    Update a sync history record.
    
    Args:
        input_data: Input data containing sync_id, status, records_processed, next_run, and tenant
        
    Returns:
        Output with sync history ID and status
    """
    logger.info(f"Updating sync history record with ID: {input_data.sync_id} for tenant: {input_data.tenant}")
    
    async with get_async_session_with_contextmanager(input_data.tenant) as session:
        # Get the sync history record
        sync_history_db = await session.get(SyncHistoryDB, input_data.sync_id)
        
        if not sync_history_db:
            raise ValueError(f"Sync history record not found with ID: {input_data.sync_id}")
        
        # Update sync history
        sync_history_update = SyncHistoryUpdate(
            status=input_data.status,
            end_time=datetime.datetime.now(datetime.UTC),
            records_processed=input_data.records_processed,
            next_run=input_data.next_run,
        )
        
        # Convert to dict and ensure enum is converted to string
        update_dict = sync_history_update.model_dump(exclude_none=True)
        if 'status' in update_dict:
            update_dict['status'] = update_dict['status'].value
        
        for key, value in update_dict.items():
            setattr(sync_history_db, key, value)
        
        # Commit the transaction
        await session.commit()
        
        logger.info(f"Updated sync history record with ID: {input_data.sync_id}")
        
        return UpdateSyncHistoryOutput(
            sync_id=input_data.sync_id,
            status=input_data.status,
        )
    
    return None 