"""Utility functions for product sync workflow."""
import logging
import uuid
import csv
from typing import List, Dict, Any
import asyncio
import math

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

async def get_search_config(tenant: str) -> Dict[str, Any]:
    """
    Get search configuration from settings
    
    Args:
        tenant: Tenant name
    
    Returns:
        Dictionary containing id_field, title_field, image_url_field, and searchable_attribute_fields
    
    Raises:
        ValueError: If search configuration is not set
    """
    search_config = await get_setting_by_key(SettingKey.SEARCH_CONFIG, tenant)
    if not search_config:
        raise ValueError("Search configuration must be set before syncing products. Please set SEARCH_CONFIG setting.")
    
    # Validate required fields
    required_fields = ["id_field", "title_field", "searchable_attribute_fields"]
    for field in required_fields:
        if field not in search_config:
            raise ValueError(f"Search configuration is missing required field: {field}")
    
    return search_config

async def check_database_health(tenant: str) -> bool:
    """
    Check database connectivity and basic health
    
    Args:
        tenant: Tenant name
        
    Returns:
        True if database is healthy, False otherwise
    """
    try:
        async with get_async_session_with_contextmanager(tenant) as session:
            # Simple query to check connectivity
            result = await session.execute(text("SELECT 1"))
            result.scalar()
            logger.info("Database health check passed")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False

async def process_products_from_data(data: List[Dict[str, Any]], tenant: str) -> List[Product]:
    """
    Convert raw product data to a list of processed Product objects with embeddings
    and insert them into the database.
    
    Args:
        data: List of product data dictionaries
        tenant: Tenant name
        
    Returns:
        List of processed Product objects with embeddings
    """
    if not data:
        logger.warning("No product data provided")
        return []
    
    # Check database health before processing
    if not await check_database_health(tenant):
        logger.error("Database health check failed. Aborting product processing.")
        return []
    
    # Get search configuration from settings
    search_config = await get_search_config(tenant)

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
            async with get_async_session_with_contextmanager(tenant) as session:
                existing_product = await session.get(ProductDB, product_id)
                
                # If product exists, compare fields to determine if update is needed
                if existing_product:
                    # Check if content has changed, if not, we can reuse the embedding
                    if existing_product.searchable_content == searchable_content:
                        # Reuse existing embedding if searchable content hasn't changed
                        text_embedding = existing_product.text_embedding
                        # Validate the existing embedding before reusing
                        if text_embedding is not None:
                            logger.info(f"Product {product_id} searchable content unchanged, reusing embedding")
                        else:
                            logger.warning(f"Product {product_id} has invalid existing embedding, generating new one")
                            try:
                                text_embedding = await get_embedding(searchable_content, TaskType.DOCUMENT)
                            except Exception as e:
                                logger.error(f"Error generating embedding for product {product_id}: {str(e)}")
                                logger.error(f"Product {product_id} has null embedding. Skipping product.")
                                return None
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
                
                # Skip products with null embeddings (additional safety check)
                if text_embedding is None:
                    logger.error(f"Product {product_id} has null embedding. Skipping product.")
                    return None
                
                # Convert string values to int/float in custom_data
                processed_custom_data = convert_numeric_strings(item)
                
                # Create product object
                product = Product(
                    id=product_id,
                    title=title,
                    text_embedding=text_embedding,
                    searchable_content=searchable_content,
                    image_url=image_url,
                    custom_data=processed_custom_data
                )
                
                # Insert or update product in database with retry mechanism
                product_dict = product.model_dump(exclude={'created_at', 'updated_at'})
                
                # Additional validation before database insertion
                if 'text_embedding' in product_dict and product_dict['text_embedding'] is not None:
                    # Ensure embedding is properly formatted as list of floats
                    try:
                        product_dict['text_embedding'] = [float(x) for x in product_dict['text_embedding']]
                    except (ValueError, TypeError) as e:
                        logger.error(f"Product {product_id}: Error converting embedding to floats: {e}")
                        return None
                

                max_retries = 3
                for attempt in range(max_retries):
                    try:
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
                        
                    except Exception as db_error:
                        await session.rollback()
                        
                        # Check if this is a vector-related error
                        error_str = str(db_error).lower()
                        if any(keyword in error_str for keyword in ['checkbyteserror', 'archiveerror', 'outofbounds', 'vector']):
                            logger.error(f"Product {product_id}: Vector corruption error detected: {db_error}")
                            logger.error(f"Product {product_id}: Skipping due to vector corruption")
                            return None
                        
                        if attempt < max_retries - 1:
                            logger.warning(f"Database error for product {product_id} (attempt {attempt + 1}/{max_retries}): {str(db_error)}. Retrying...")
                            await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                        else:
                            logger.error(f"Database error for product {product_id} after {max_retries} attempts: {str(db_error)}")
                            return None
                
        except Exception as e:
            logger.error(f"Database error processing product {product_id}: {str(e)}")

            return None


    # Process all products in parallel using TaskGroup
    async with asyncio.TaskGroup() as tg:
        for item in data:
            tg.create_task(process_product(item))
            await asyncio.sleep(0.1)  # Reduced sleep time for better performance
    
    # Create JSONB indexes for filter and sortable fields
    if filter_fields or sortable_fields:
        await create_jsonb_indexes(filter_fields, sortable_fields, tenant)
    
    # Filter out None values (skipped products with empty searchable content or null embeddings)
    valid_products = [product for product in processed_products if product is not None]
    
    # Log processing summary
    total_input = len(data)
    total_processed = len(valid_products)
    total_skipped = total_input - total_processed
    
    logger.info(f"Product processing summary: {total_processed}/{total_input} products processed successfully, {total_skipped} skipped")
    
    if total_skipped > 0:
        skip_rate = (total_skipped / total_input) * 100
        if skip_rate > 50:
            logger.warning(f"High skip rate detected: {skip_rate:.1f}% of products were skipped due to validation errors")
    
    return valid_products

def convert_numeric_strings(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert string values to int or float if they represent numeric values.
    
    Args:
        data: Dictionary containing product data
        
    Returns:
        Dictionary with numeric strings converted to int or float
    """
    def convert_value(value):
        """Convert a single value if it's a numeric string."""
        if not isinstance(value, str):
            return value
        
        # Skip empty strings
        if not value.strip():
            return value
        
        # Try to convert to int first
        try:
            # Check if it's a whole number (no decimal point)
            if '.' not in value and 'e' not in value.lower():
                return int(value)
        except (ValueError, OverflowError):
            pass
        
        # Try to convert to float
        try:
            float_val = float(value)
            # Only convert if it's a valid number (not NaN or infinite)
            if not (math.isnan(float_val) or math.isinf(float_val)):
                return float_val
        except (ValueError, OverflowError):
            pass
        
        # Return original value if conversion fails
        return value
    
    def convert_recursive(obj):
        """Recursively convert values in nested structures."""
        if isinstance(obj, dict):
            return {key: convert_recursive(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [convert_recursive(item) for item in obj]
        else:
            return convert_value(obj)
    
    return convert_recursive(data)

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

async def get_products_from_supersearch_api(sync_input: ProductSyncInput, tenant: str) -> List[Product]:
    """
    Get products from Supersearch API
    
    Args:
        sync_input: ProductSyncInput containing source configuration and product data
        tenant: Tenant name
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, SupersearchApiConfig):
        logger.error("Invalid Supersearch API configuration")
        return []
        
    logger.info("Getting products from Supersearch API")
    
    # Process products directly from the input
    return await process_products_from_data(sync_input.products, tenant)

async def get_products_from_manual_upload(sync_input: ProductSyncInput, tenant: str) -> List[Product]:
    """
    Get products from manual file upload
    
    Args:
        sync_input: ProductSyncInput containing source configuration and product data
        tenant: Tenant name
        
    Returns:
        List of processed Product objects
    """
    if not isinstance(sync_input.source_config, ManualFileUploadConfig):
        logger.error("Invalid manual file upload configuration")
        return []
        
    logger.info("Getting products from manual file upload")
    
    # Process the products
    return await process_products_from_data(sync_input.products, tenant)

async def get_products_from_crawler(sync_input: ProductSyncInput, tenant: str) -> List[Product]:
    """
    Get products from web crawler
    
    Args:
        sync_input: ProductSyncInput containing source configuration
        tenant: Tenant name
        
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
    return await process_products_from_data(crawled_data, tenant)

async def get_products_from_hosted_file(sync_input: ProductSyncInput, tenant: str) -> List[Product]:
    """
    Get products from a hosted CSV/JSON file
    
    Args:
        sync_input: ProductSyncInput containing source configuration
        tenant: Tenant name
        
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
                return await process_products_from_data(data, tenant)
                
        except Exception as e:
            logger.error(f"Error downloading or processing file: {str(e)}")
            return []

async def get_products_from_sql_database(sync_input: ProductSyncInput, tenant: str) -> List[Product]:
    """
    Get products from SQL database
    
    Args:
        sync_input: ProductSyncInput containing source configuration
        tenant: Tenant name
        
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
            return await process_products_from_data(data, tenant)
            
    except Exception as e:
        logger.error(f"Error connecting to database or executing query: {str(e)}")
        return []

async def create_jsonb_indexes(filter_fields: List[str], sortable_fields: List[str], tenant: str) -> None:
    """
    Create JSONB B-tree expression indexes for filter_fields and sortable_fields
    
    Args:
        filter_fields: List of fields in custom_data to create indexes for filtering
        sortable_fields: List of fields in custom_data to create indexes for sorting
        tenant: Tenant name
    """
    if not filter_fields and not sortable_fields:
        return
    
    logger.info("Creating JSONB indexes for filter and sortable fields")
    
    # Get all fields that need indexes (combine filter and sortable fields)
    index_fields = list(set(filter_fields + sortable_fields))
    
    try:
        async with get_async_session_with_contextmanager(tenant) as session:
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

def print_complete_sql_with_values(product_dict: Dict[str, Any], product_id: str, tenant: str) -> None:
    """
    Print the complete SQL statement with actual parameter values substituted.
    
    Args:
        product_dict: Dictionary containing product data
        product_id: Product ID for identification
        tenant: Tenant schema name
    """
    import json
    
    print(f"=== COMPLETE SQL WITH VALUES FOR PRODUCT {product_id} ===")
    
    # Helper function to safely format SQL values
    def format_sql_value(value, data_type=""):
        if value is None:
            return "NULL"
        elif isinstance(value, str):
            # Escape single quotes and wrap in quotes
            escaped = value.replace("'", "''")
            if data_type:
                return f"'{escaped}'::{data_type}"
            return f"'{escaped}'"
        elif isinstance(value, list):
            if data_type == "vector":
                # Format as vector
                vector_str = '[' + ','.join(str(x) for x in value) + ']'
                return f"'{vector_str}'::vector"
            elif data_type == "text[]":
                # Format as text array
                if not value:
                    return "ARRAY[]::text[]"
                escaped_items = [f"'{str(item).replace(chr(39), chr(39)+chr(39))}'" for item in value]
                return f"ARRAY[{','.join(escaped_items)}]::text[]"
            else:
                return str(value)
        elif isinstance(value, (dict, list)) and data_type in ["json", "jsonb"]:
            # Format as JSON
            json_str = json.dumps(value, ensure_ascii=False).replace("'", "''")
            return f"'{json_str}'::{data_type}"
        else:
            return str(value)
    
    # Build the complete SQL statement
    sql_parts = []
    sql_parts.append(f"INSERT INTO {tenant}.products (")
    sql_parts.append("    id,")
    sql_parts.append("    title,")
    sql_parts.append("    text_embedding,")
    sql_parts.append("    image_embedding,")
    sql_parts.append("    searchable_content,")
    sql_parts.append("    image_url,")
    sql_parts.append("    custom_data,")
    sql_parts.append("    ai_generated_contents,")
    sql_parts.append("    ai_summary,")
    sql_parts.append("    suggested_questions,")
    sql_parts.append("    reviews")
    sql_parts.append(") VALUES (")
    
    # Add the actual values
    values = []
    
    # ID
    values.append(f"    {format_sql_value(product_dict.get('id'))}")
    
    # Title
    values.append(f"    {format_sql_value(product_dict.get('title'))}")
    
    # Text embedding
    text_embedding = product_dict.get('text_embedding')
    values.append(f"    {format_sql_value(text_embedding, 'vector')}")
    
    # Image embedding
    image_embedding = product_dict.get('image_embedding')
    values.append(f"    {format_sql_value(image_embedding, 'vector')}")
    
    # Searchable content
    values.append(f"    {format_sql_value(product_dict.get('searchable_content'))}")
    
    # Image URL
    values.append(f"    {format_sql_value(product_dict.get('image_url'))}")
    
    # Custom data
    values.append(f"    {format_sql_value(product_dict.get('custom_data'), 'jsonb')}")
    
    # AI generated contents
    ai_contents = product_dict.get('ai_generated_contents', [])
    values.append(f"    {format_sql_value(ai_contents, 'text[]')}")
    
    # AI summary
    values.append(f"    {format_sql_value(product_dict.get('ai_summary'), 'jsonb')}")
    
    # Suggested questions
    values.append(f"    {format_sql_value(product_dict.get('suggested_questions'), 'jsonb')}")
    
    # Reviews
    values.append(f"    {format_sql_value(product_dict.get('reviews'), 'jsonb')}")
    
    # Create the complete SQL
    complete_sql = f"""INSERT INTO {tenant}.products (
    id,
    title,
    text_embedding,
    image_embedding,
    searchable_content,
    image_url,
    custom_data,
    ai_generated_contents,
    ai_summary,
    suggested_questions,
    reviews
) VALUES (
{','.join(values)}
) RETURNING created_at, updated_at;"""
    
    print("=== COMPLETE SQL STATEMENT WITH VALUES ===")
    print(complete_sql)
    
    # Also print detailed embedding information if present
    if text_embedding:
        print("=== EMBEDDING DETAILS ===")
        print(f"Embedding length: {len(text_embedding)}")
        print(f"First 10 values: {text_embedding[:10]}")
        print(f"Last 10 values: {text_embedding[-10:]}")
        
        # Check for problematic values
        problematic_indices = []
        for i, val in enumerate(text_embedding):
            if not isinstance(val, (int, float)):
                problematic_indices.append((i, val, type(val).__name__))
            elif math.isnan(val) or math.isinf(val):
                problematic_indices.append((i, val, "NaN/Inf"))
        
        if problematic_indices:
            print(f"Found {len(problematic_indices)} problematic values:")
            for idx, val, issue in problematic_indices[:20]:  # Show first 20 issues
                print(f"  Index {idx}: {val} ({issue})")
            if len(problematic_indices) > 20:
                print(f"  ... and {len(problematic_indices) - 20} more")
        else:
            print("All embedding values appear valid")
            
        # Statistics
        if all(isinstance(x, (int, float)) and not (math.isnan(x) or math.isinf(x)) for x in text_embedding):
            min_val = min(text_embedding)
            max_val = max(text_embedding)
            avg_val = sum(text_embedding) / len(text_embedding)
            print(f"Value statistics: min={min_val:.6f}, max={max_val:.6f}, avg={avg_val:.6f}")
    
    print("=== END COMPLETE SQL DEBUG ===")