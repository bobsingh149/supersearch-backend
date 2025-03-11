"""Utility functions for product sync workflow."""
import logging
import uuid
import csv
from typing import List, Dict, Any

import aiohttp
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.product import Product
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

logger = logging.getLogger(__name__)

async def get_search_config() -> Dict[str, Any]:
    """
    Get search configuration from settings
    
    Returns:
        Dictionary containing id_field, title_field, and searchable_attribute_fields
    
    Raises:
        ValueError: If search configuration is not set
    """
    search_config = await get_setting_by_key(SettingKey.SEARCH_CONFIG)
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
    
    Args:
        data: List of product data dictionaries
        
    Returns:
        List of processed Product objects with embeddings
    """
    products = []
    
    if not data:
        logger.warning("No product data provided")
        return products
    
    # Get search configuration from settings
    search_config = await get_search_config()
    id_field = search_config["id_field"]
    title_field = search_config["title_field"]
    searchable_attribute_fields = search_config["searchable_attribute_fields"]
    
    for item in data:
        # Get ID from the specified field or generate a new one
        product_id = str(item.get(id_field)) if item.get(id_field) else str(uuid.uuid4())
        
        # Get title from the specified field
        title = item.get(title_field)
        
        # Combine searchable attributes into a single string
        searchable_content = " ".join(
            str(item.get(field, "")) 
            for field in searchable_attribute_fields 
            if field in item and item.get(field) is not None
        )
        
        # Create embedding for the product
        text_embedding = await get_embedding(searchable_content, TaskType.DOCUMENT)

        # Create a new Product object
        product = Product(
            id=product_id,
            title=title,
            text_embedding=text_embedding,
            searchable_content=searchable_content,
            custom_data=item
        )
        
        products.append(product)
    
    return products

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