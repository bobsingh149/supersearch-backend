from app.models.product import Product, ProductInput
from app.services.vertex import get_embedding, TaskType
from app.models.sync_config import (
    SyncSource, 
    ManualFileUploadConfig,
    CrawlerConfig,
    SupersearchApiConfig,
    HostedFileConfig,
    SqlDatabaseConfig
)
from app.services.jina_api import JinaAPI
import aiohttp
import csv
import json
import uuid
from typing import List, Dict, Any
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
import datetime


async def process_product_data(product: Product) -> Product:
    """
    Process product data and generate embeddings
    """
    
    # Generate embeddings
    if product.searchable_content:  # Assuming text description is in custom_data
        product.text_embedding = await get_embedding(product.searchable_content, TaskType.DOCUMENT)
    
    return product


async def get_products_from_source(
    source: SyncSource, 
    source_config: Any, 
    product_input=None
) -> List[Product]:
    """
    Generic method to get products from different sources
    
    Args:
        source: The source type
        source_config: Configuration for the source
        product_input: Optional product input data for MANUAL_FILE_UPLOAD and SUPERSEARCH_API
        
    Returns:
        List of Product objects
    """
    if source == SyncSource.MANUAL_FILE_UPLOAD:
        return await get_products_from_manual_upload(product_input)
    elif source == SyncSource.CRAWLER:
        return await get_products_from_crawler(source_config)
    elif source == SyncSource.SUPERSEARCH_API:
        return await get_products_from_supersearch_api(product_input)
    elif source == SyncSource.HOSTED_FILE:
        return await get_products_from_hosted_file(source_config)
    elif source == SyncSource.SQL_DATABASE:
        return await get_products_from_sql_database(source_config)
    else:
        raise ValueError(f"Unsupported source: {source}")

async def get_products_from_manual_upload(product_input : ProductInput) -> List[Product]:
    """
    Get products from manual file upload
    """
    products = []
    for item in product_input.data:
        product_id = str(item.get(product_input.id_field)) if item.get(product_input.id_field) else str(uuid.uuid4())
        
        # Combine searchable attributes into a single string
        searchable_content = " ".join(
            str(item.get(field, "")) 
            for field in product_input.searchable_attribute_fields 
            if item.get(field)
        )
        
        products.append(
            Product(
                id=product_id,
                custom_data=item,
                title=item.get(product_input.title_field),
                searchable_content=searchable_content
            )
        )
    
    return products

async def get_products_from_crawler(config: CrawlerConfig) -> List[Product]:
    """
    Get products from web crawler using Jina API
    """
    jina_api = JinaAPI()
    products = []
    
    for url in config.urls:
        try:
            # Get content from URL
            content = await jina_api.reader(url)
            
            # Segment content into chunks
            segments = await jina_api.segment(
                content=content,
                max_chunk_length=1000,
                return_chunks=True,
                return_tokens=False
            )
            
            # Process each chunk as a product
            for i, chunk in enumerate(segments['chunks']):
                product_id = f"{url.replace('://', '_').replace('/', '_')}_{i}"
                
                products.append(
                    Product(
                        id=product_id,
                        custom_data={
                            "url": url,
                            "content": chunk,
                            "index": i
                        },
                        title=f"Content from {url} - Part {i+1}",
                        searchable_content=chunk
                    )
                )
        except Exception as e:
            # Log error and continue with next URL
            print(f"Error processing URL {url}: {str(e)}")
    
    return products

async def get_products_from_supersearch_api(product_input : ProductInput) -> List[Product]:
    """
    Get products from Supersearch API
    """
    # This is the same as manual upload since the data is already provided
    return await get_products_from_manual_upload(product_input)

async def get_products_from_hosted_file(config: HostedFileConfig) -> List[Product]:
    """
    Get products from hosted file (CSV or JSON)
    """
    products = []
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(config.file_url) as response:
                response.raise_for_status()
                
                if config.file_format.lower() == "csv":
                    # Parse CSV
                    text = await response.text()
                    reader = csv.DictReader(text.splitlines())
                    data = list(reader)
                elif config.file_format.lower() == "json":
                    # Parse JSON
                    data = await response.json()
                else:
                    raise ValueError(f"Unsupported file format: {config.file_format}")
                
                # Convert data to products
                for i, item in enumerate(data):
                    product_id = str(item.get("id", uuid.uuid4()))
                    
                    products.append(
                        Product(
                            id=product_id,
                            custom_data=item,
                            title=item.get("title", f"Product {i+1}"),
                            searchable_content=" ".join(str(v) for v in item.values() if v)
                        )
                    )
    except Exception as e:
        # Log error
        print(f"Error fetching hosted file: {str(e)}")
    
    return products

async def get_products_from_sql_database(config: SqlDatabaseConfig) -> List[Product]:
    """
    Get products from SQL database
    """
    products = []
    
    try:
        # Create engine
        engine = create_async_engine(config.connection_string)
        
        async with engine.connect() as conn:
            # Execute query
            result = await conn.execute(sa.text(config.query))
            rows = result.mappings().all()
            
            # Convert rows to products
            for row in rows:
                row_dict = dict(row)
                product_id = str(row_dict.get(config.id_column, uuid.uuid4()))
                
                # Extract title
                title = row_dict.get(config.title_column, "")
                
                # Combine searchable attributes
                searchable_content = " ".join(
                    str(row_dict.get(col, "")) 
                    for col in config.searchable_columns 
                    if row_dict.get(col)
                )
                
                products.append(
                    Product(
                        id=product_id,
                        custom_data=row_dict,
                        title=title,
                        searchable_content=searchable_content
                    )
                )
    except Exception as e:
        # Log error
        print(f"Error querying SQL database: {str(e)}")
    
    return products

async def sync_products_service(
    sync_input,
    session
):
    """
    Service method to handle product synchronization from various sources.
    
    The sync process:
    1. Creates a sync history record
    2. Fetches products from the source
    3. Processes products (generates embeddings)
    4. Inserts products into the database
    5. Updates the sync history record
    
    Args:
        sync_input: ProductSyncInput object containing source configuration and products
        session: AsyncSession for database operations
        
    Returns:
        Dictionary with message and sync_id
    """
    from app.models.sync_history import SyncHistoryDB, SyncHistoryCreate, SyncHistoryUpdate
    from app.models.sync_config import SyncStatus
    from app.models.product import ProductDB
    from asyncio import TaskGroup
    from sqlalchemy.dialects.postgresql import insert
    import logging
    
    logger = logging.getLogger(__name__)
    
    try:
        # Create sync history record
        sync_history = SyncHistoryCreate(
            source=sync_input.source_config.source,
            status=SyncStatus.PROCESSING,
            start_time=datetime.datetime.now(datetime.UTC)
        )
        
        sync_history_db = SyncHistoryDB(**sync_history.model_dump())
        session.add(sync_history_db)
        await session.flush()
        
        # Get products from source
        source = sync_input.source_config.source
        logger.info(f"Fetching products from source: {source}")
        products = await get_products_from_source(
            source=source,
            source_config=sync_input.source_config,
            product_input=sync_input.products
        )
        
        if not products:
            logger.warning(f"No products found from source: {source}")
            
            # Update sync history
            sync_history_update = SyncHistoryUpdate(
                status=SyncStatus.SUCCESS,
                end_time=datetime.datetime.now(datetime.UTC),
                records_processed=0
            )
            
            for key, value in sync_history_update.model_dump(exclude_none=True).items():
                setattr(sync_history_db, key, value)
            
            await session.commit()
            
            return {"message": "No products found to sync", "sync_id": str(sync_history_db.id)}
        
        logger.info(f"Processing {len(products)} products")
        
        # Process products concurrently using TaskGroup
        processed_products = []
        async with TaskGroup() as tg:
            tasks = []
            for product in products:
                tasks.append(tg.create_task(process_product_data(product)))
        
        # Collect results from all tasks
        processed_products = [task.result() for task in tasks]
        
        # Convert processed products to dictionaries for bulk insert
        products_to_insert = [
            product.model_dump(exclude={'created_at', 'updated_at'}) 
            for product in processed_products
        ]
        
        # Bulk insert using insert()
        stmt = insert(ProductDB).values(products_to_insert)
        await session.execute(stmt)
        
        # Update sync history
        sync_history_update = SyncHistoryUpdate(
            status=SyncStatus.SUCCESS,
            end_time=datetime.datetime.now(datetime.UTC),
            records_processed=len(processed_products)
        )
        
        for key, value in sync_history_update.model_dump(exclude_none=True).items():
            setattr(sync_history_db, key, value)
        
        await session.commit()
        
        logger.info(f"Successfully synced {len(processed_products)} products")
        
        return {
            "message": f"Successfully synced {len(processed_products)} products",
            "sync_id": str(sync_history_db.id)
        }
    
    except Exception as e:
        logger.error(f"Error syncing products: {str(e)}")
        
        # Update sync history if it was created
        if 'sync_history_db' in locals():
            sync_history_update = SyncHistoryUpdate(
                status=SyncStatus.FAILED,
                end_time=datetime.datetime.now(datetime.UTC)
            )
            
            for key, value in sync_history_update.model_dump(exclude_none=True).items():
                setattr(sync_history_db, key, value)
            
            await session.commit()
        
        await session.rollback()
        raise Exception(f"Error syncing products: {str(e)}")

