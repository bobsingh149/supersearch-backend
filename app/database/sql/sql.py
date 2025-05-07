from jinja2 import Environment, FileSystemLoader
import os
from enum import Enum, auto
import re
from typing import Any, Dict, Union
import logging

logger = logging.getLogger(__name__)

# Set up Jinja2 environment
TEMPLATE_DIR = os.path.dirname(__file__)
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=True  # Enable autoescaping for security
)

class SQLFilePath(Enum):
    """Enum representing SQL file paths for use with render_sql."""
    # Product related queries
    PRODUCT_FULL_TEXT_SEARCH = "product/full_text_search"
    PRODUCT_SEMANTIC_SEARCH = "product/semantic_search"
    PRODUCT_SEMANTIC_SEARCH_WITH_REVIEWS = "product/semantic_search_with_reviews"
    PRODUCT_HYBRID_SEARCH = "product/hybrid_search"
    PRODUCT_HYBRID_SEARCH_WITHOUT_RANKING = "product/hybrid_search_without_ranking"
    PRODUCT_AUTOCOMPLETE_SEARCH = "product/autocomplete_search"
    PRODUCT_SIMILAR_PRODUCTS_HYBRID = "product/similar_products_hybrid"
    PRODUCT_SIMILAR_PRODUCTS_SEMANTIC = "product/similar_products_semantic"
    PRODUCT_GET_BY_IDS = "product/get_products_by_ids"
    PRODUCT_EMPTY_QUERY = "product/empty_query"
    
    # Generic CRUD operations
    GENERIC_GET_BY_ID = "generic/get_by_id"
    GENERIC_GET_ALL = "generic/get_all"
    GENERIC_INSERT = "generic/insert"
    GENERIC_BULK_INSERT = "generic/bulk_insert"
    GENERIC_UPDATE = "generic/update"
    GENERIC_DELETE = "generic/delete"
    GENERIC_COUNT = "generic/count"
    GENERIC_ADVANCED_FILTER = "generic/advanced_filter"
    
    # Add more SQL file paths as needed
    
    def __str__(self) -> str:
        """Convert enum to string representation."""
        return self.value

def pg_escape_value(value: Any) -> Any:
    """
    Escape values to prevent SQL injection in PostgreSQL.
    
    Args:
        value: The value to escape
        
    Returns:
        Escaped value safe for PostgreSQL
    """
    if value is None:
        return None
    
    if isinstance(value, (int, float, bool,)):
        return value
    
    if isinstance(value, str):
        # Escape single quotes by doubling them (PostgreSQL style)
        return value.replace("'", "''")
    
    logger.warning(f"Unexpected value type: {type(value)}")
    # For other types, convert to string and escape
    return str(value).replace("'", "''")

def sanitize_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize all string values in kwargs to prevent SQL injection.
    
    Args:
        kwargs: Dictionary of parameters
        
    Returns:
        Sanitized dictionary
    """
    sanitized = {}
    for key, value in kwargs.items():
        if isinstance(value, dict):
            sanitized[key] = sanitize_kwargs(value)
        elif isinstance(value, list):
            sanitized[key] = [pg_escape_value(item) for item in value]
        else:
            sanitized[key] = pg_escape_value(value)
    return sanitized

def render_sql(filename: SQLFilePath, tenant: str, **kwargs) -> str:
    """
    Loads and renders an SQL template with the given parameters.
    
    Args:
        filename: Name of the SQL file (with or without .sql extension)
                 Can be a string path or SQLFilePath enum
                 Can include subfolder path like 'product/full_text_search'
        tenant: The tenant/schema name (required)
        kwargs: Dictionary of parameters to pass to the template
    
    Returns:
        Rendered SQL query as a string
    
    Example:
        render_sql(SQLFilePath.PRODUCT_FULL_TEXT_SEARCH, tenant='demo_movies', query_text='search term', limit=10)
        render_sql('product/full_text_search', tenant='demo_movies', query_text='search term', limit=10)
    """
    if not tenant or tenant == "":
        raise ValueError("Tenant (schema) name must be provided to render_sql.")
    # Convert enum to string if needed
    if isinstance(filename, SQLFilePath):
        filename = str(filename)
    
    # Ensure the path ends with .sql
    if not filename.endswith('.sql'):
        filename = filename + '.sql'
    
    # Sanitize all input parameters to prevent SQL injection
    safe_kwargs = sanitize_kwargs(kwargs)
    safe_kwargs['tenant'] = tenant
    
    template = jinja_env.get_template(filename)
    return template.render(**safe_kwargs) 