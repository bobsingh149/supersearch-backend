"""Utility functions for product sync workflow."""
import logging
import uuid
import csv
from typing import List, Dict, Any
import asyncio

import aiohttp
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.sql import text

from app.models.product import Product, ProductDB
from app.models.sync_product import ProductSyncInput
from app.services.vertex import get_embedding, TaskType
from app.models.sync_config import (
    ManualFileUploadConfig,
    CrawlerConfig,
    SupersearchApiConfig,
    HostedFileConfig,
    SqlDatabaseConfig
)
from app.models.settings import SettingKey
from app.utils.settings import get_setting_by_key
from app.database.session import get_async_session_with_contextmanager

logger = logging.getLogger(__name__)

async def get_search_config() -> Dict[str, Any]:
    """
    Get search configuration from settings
    
    Returns:
        Dictionary containing id_field, title_field, image_url_field, and searchable_attribute_fields
    
    Raises:
        ValueError: If search configuration is not set
    """
    search_config = await get_setting_by_key(SettingKey.SEARCH_CONFIG,"demo_movies")
    if not search_config:
        raise ValueError("Search configuration must be set before syncing products. Please set SEARCH_CONFIG setting.")
    
    # Validate required fields
    required_fields = ["id_field", "title_field", "searchable_attribute_fields"]
    for field in required_fields:
        if field not in search_config:
            raise ValueError(f"Search configuration is missing required field: {field}")
    
    return search_config

async def process_products_from_data(data: List[Dict[str, Any]]) -> List[Product]:
    """
    Convert raw product data to a list of processed Product objects with embeddings
    and insert them into the database.
    
    Args:
        data: List of product data dictionaries
        
    Returns:
        List of processed Product objects with embeddings
    """
    if not data:
        logger.warning("No product data provided")
        return []
    
    # Get search configuration from settings
    search_config = await get_search_config()

    id_field = search_config["id_field"]
    title_field = search_config["title_field"]
    searchable_attribute_fields = search_config["searchable_attribute_fields"]
    image_url_field = search_config.get("image_url_field")
    filter_fields = search_config.get("filter_fields", [])
    sortable_fields = search_config.get("sortable_fields", [])
    
    processed_products = []
    
    async def process_product(item: Dict[str, Any]) -> Product:

        # Get ID from the specified field or generate a new one
        product_id = str(item.get(id_field)) if item.get(id_field) else str(uuid.uuid4())
        
        # Get title from the specified field
        title = item.get(title_field)
        
        # Get image URL if the field is specified
        image_url = None
        if image_url_field:
            image_url = item.get(image_url_field)
        
        # Generate searchable content with field names and values
        searchable_content = generate_searchable_content(item, searchable_attribute_fields)
        
        # Skip products with empty searchable content
        if not searchable_content or not searchable_content.strip():
            logger.error(f"Product {product_id} has empty searchable content. Skipping product.")
            return None
        
        # Check if product already exists in database
        existing_product = None
        text_embedding = None
        
        try:
            async with get_async_session_with_contextmanager() as session:
                existing_product = await session.get(ProductDB, product_id)
                
                # If product exists, compare fields to determine if update is needed
                if existing_product:
                    # Check if content has changed, if not, we can reuse the embedding
                    if existing_product.searchable_content == searchable_content:
                        # Reuse existing embedding if searchable content hasn't changed
                        text_embedding = existing_product.text_embedding
                        logger.info(f"Product {product_id} searchable content unchanged, reusing embedding")
                    else:
                        # Generate new embedding only if searchable content has changed
                        logger.info(f"Product {product_id} content changed, generating new embedding")
                        try:
                            text_embedding = await get_embedding(searchable_content, TaskType.DOCUMENT)
                        except Exception as e:
                            logger.error(f"Error generating embedding for product {product_id}: {str(e)}")
                            # Don't reuse existing embedding as fallback if there's an error
                            logger.error(f"Product {product_id} has null embedding. Skipping product.")
                            return None
                else:
                    # New product, generate embedding
                    logger.info(f"New product {product_id}, generating embedding")
                    try:
                        text_embedding = await get_embedding(searchable_content, TaskType.DOCUMENT)
                    except Exception as e:
                        logger.error(f"Error generating embedding for new product {product_id}: {str(e)}")
                        logger.error(f"Product {product_id} has null embedding. Skipping product.")
                        return None
                
                # Skip products with null embeddings
                if text_embedding is None:
                    logger.error(f"Product {product_id} has null embedding. Skipping product.")
                    return None
                
                # Create product object
                product = Product(
                    id=product_id,
                    title=title,
                    text_embedding=text_embedding,
                    searchable_content=searchable_content,
                    image_url=image_url,
                    custom_data=item
                )
                
                # Insert or update product in database
                product_dict = product.model_dump(exclude={'created_at', 'updated_at'})
                
                if existing_product:
                    # Update existing product
                    for key, value in product_dict.items():
                        setattr(existing_product, key, value)
                    logger.info(f"Updated product {product_id}")
                else:
                    # Insert new product
                    new_product = ProductDB(**product_dict)
                    session.add(new_product)
                    logger.info(f"Inserted new product {product_id}")
                
                await session.commit()
                processed_products.append(product)
                return product
                
        except Exception as e:
            logger.error(f"Database error processing product {product_id}: {str(e)}")

            return None


    # Process all products in parallel using TaskGroup
    async with asyncio.TaskGroup() as tg:
        for item in data:
            tg.create_task(process_product(item))
            await asyncio.sleep(0.6)  # Reduced sleep time for better performance
    
    # Create JSONB indexes for filter and sortable fields
    if filter_fields or sortable_fields:
        await create_jsonb_indexes(filter_fields, sortable_fields)
    
    # Filter out None values (skipped products with empty searchable content or null embeddings)
    return [product for product in processed_products if product is not None]

def generate_searchable_content(item: Dict[str, Any], searchable_attribute_fields: List[str]) -> str:
    """
    Generate searchable content string with both field names and values.
    
    Args:
        item: Dictionary containing product data
        searchable_attribute_fields: List of fields to include in searchable content
        
    Returns:
        A string containing both field names and their values for searchable attributes
    """
    searchable_parts = []
    
    for field in searchable_attribute_fields:
        if field in item and item.get(field) is not None:
            # Add both field name and value for better semantic search
            field_value = str(item.get(field, ""))
            if field_value.strip():  # Only add non-empty values
                searchable_parts.append(f"{field}: {field_value}")
    
    return " ".join(searchable_parts)

async def get_products_from_supersearch_api(sync_input: ProductSyncInput) -> List[Product]:
    """
    Get products from Supersearch API
    
    Args:
        sync_input: ProductSyncInput containing source configuration and product data
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, SupersearchApiConfig):
        logger.error("Invalid Supersearch API configuration")
        return []
        
    logger.info("Getting products from Supersearch API")
    
    # Process products directly from the input
    return await process_products_from_data(sync_input.products)

async def get_products_from_manual_upload(sync_input: ProductSyncInput) -> List[Product]:
    """
    Get products from manual file upload
    
    Args:
        sync_input: ProductSyncInput containing source configuration and product data
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, ManualFileUploadConfig):
        logger.error("Invalid manual file upload configuration")
        return []
        
    logger.info("Getting products from manual file upload")
    
    # Process the products
    return await process_products_from_data(sync_input.products)

async def get_products_from_crawler(sync_input: ProductSyncInput) -> List[Product]:
    """
    Get products from web crawler
    
    Args:
        sync_input: ProductSyncInput containing source configuration
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, CrawlerConfig):
        logger.error("Invalid crawler configuration")
        return []
    
    config = sync_input.source_config
    logger.info(f"Crawling website: {config.base_url}")
    
    # Here you would implement the actual crawling logic
    # For now, we'll just return a placeholder product
    
    # Example of crawled data
    crawled_data = [
        {
            "id": str(uuid.uuid4()),
            "title": f"Crawled Product from {config.base_url}",
            "description": "This is a placeholder for crawled product data",
            "url": f"{config.base_url}/product/1",
            "price": "99.99",
            "image_url": "https://example.com/image.jpg"
        }
    ]
    
    # Process the crawled data
    return await process_products_from_data(crawled_data)

async def get_products_from_hosted_file(sync_input: ProductSyncInput) -> List[Product]:
    """
    Get products from a hosted CSV/JSON file
    
    Args:
        sync_input: ProductSyncInput containing source configuration
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, HostedFileConfig):
        logger.error("Invalid hosted file configuration")
        return []
    
    config = sync_input.source_config
    logger.info(f"Downloading file from: {config.file_url}")
    
    # Download the file
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(config.file_url) as response:
                if response.status != 200:
                    logger.error(f"Failed to download file: {response.status}")
                    return []
                
                content = await response.text()
                
                # Parse the file based on format
                if config.file_format.lower() == 'csv':
                    # Parse CSV
                    reader = csv.DictReader(content.splitlines())
                    data = list(reader)
                elif config.file_format.lower() == 'json':
                    # Parse JSON
                    import json
                    data = json.loads(content)
                else:
                    logger.error(f"Unsupported file format: {config.file_format}")
                    return []
                
                # Process the data
                return await process_products_from_data(data)
                
        except Exception as e:
            logger.error(f"Error downloading or processing file: {str(e)}")
            return []

async def get_products_from_sql_database(sync_input: ProductSyncInput) -> List[Product]:
    """
    Get products from SQL database
    
    Args:
        sync_input: ProductSyncInput containing source configuration
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, SqlDatabaseConfig):
        logger.error("Invalid SQL database configuration")
        return []
    
    config = sync_input.source_config
    logger.info(f"Connecting to database: {config.connection_string}")
    
    try:
        # Create engine
        engine = create_async_engine(config.connection_string)
        
        # Execute query
        async with engine.connect() as conn:
            result = await conn.execute(sa.text(config.query))
            rows = result.mappings().all()
            
            # Convert to list of dicts
            data = [dict(row) for row in rows]
            
            # Process the data
            return await process_products_from_data(data)
            
    except Exception as e:
        logger.error(f"Error connecting to database or executing query: {str(e)}")
        return []

async def create_jsonb_indexes(filter_fields: List[str], sortable_fields: List[str]) -> None:
    """
    Create JSONB B-tree expression indexes for filter_fields and sortable_fields
    
    Args:
        filter_fields: List of fields in custom_data to create indexes for filtering
        sortable_fields: List of fields in custom_data to create indexes for sorting
    """
    if not filter_fields and not sortable_fields:
        return
    
    logger.info("Creating JSONB indexes for filter and sortable fields")
    
    # Get all fields that need indexes (combine filter and sortable fields)
    index_fields = list(set(filter_fields + sortable_fields))
    
    try:
        async with get_async_session_with_contextmanager() as session:
            for field in index_fields:
                # Create index name
                index_name = f"idx_product_custom_data_{field.replace('-', '_')}"
                
                # Create index if not exists
                index_statement = text(
                    f"CREATE INDEX IF NOT EXISTS {index_name} ON products ((custom_data->>'{field}'))"
                )
                
                try:
                    await session.execute(index_statement)
                    logger.info(f"Created JSONB index for field: {field}")
                except Exception as e:
                    logger.error(f"Error creating index for field {field}: {str(e)}")
            
            await session.commit()
            logger.info("JSONB index creation completed")
    except Exception as e:
        logger.error(f"Error creating JSONB indexes: {str(e)}") 