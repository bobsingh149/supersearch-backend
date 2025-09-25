from jinja2 import Environment, FileSystemLoader
import os
from enum import Enum, auto
import re
from typing import Any, Dict, Union, Tuple
import logging

logger = logging.getLogger(__name__)

# Set up Jinja2 environment
TEMPLATE_DIR = os.path.dirname(__file__)
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True,
    autoescape=False  # SQL templates should not be autoescaped for this use case
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

def format_sql_value(value: Any) -> str:
    """
    Format a value for safe SQL insertion with proper data type handling.

    Args:
        value: The value to format

    Returns:
        Properly formatted SQL value string
    """
    import json

    if value is None:
        return 'NULL'

    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, str):
        # Escape single quotes by doubling them (PostgreSQL style)
        escaped = value.replace("'", "''")
        return f"'{escaped}'"

    if isinstance(value, (list, dict)):
        # Convert to JSON string and escape
        json_str = json.dumps(value)
        escaped = json_str.replace("'", "''")
        return f"'{escaped}'"

    # For other types, convert to string and escape
    str_value = str(value)
    escaped = str_value.replace("'", "''")
    return f"'{escaped}'"

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
        render_sql(SQLFilePath.PRODUCT_FULL_TEXT_SEARCH, tenant='tenant', query_text='search term', limit=10)
        render_sql('product/full_text_search', tenant='tenant', query_text='search term', limit=10)
    """
    if not tenant:
        raise ValueError("Tenant (schema) name must be provided to render_sql.")
    # Convert enum to string if needed
    if isinstance(filename, SQLFilePath):
        filename = str(filename)

    # Ensure the path ends with .sql
    if not filename.endswith('.sql'):
        filename = filename + '.sql'

    # For generic CRUD templates, skip sanitization and pass kwargs directly
    if filename.startswith('generic/'):
        safe_kwargs = kwargs
        safe_kwargs['tenant'] = tenant

        template = jinja_env.get_template(filename)
        return template.render(**safe_kwargs)
    else:
        # For other templates, use the existing approach
        if filename == 'product/empty_query.sql':
            # Bypass sanitization for templates that use raw SQL fragments.
            safe_kwargs = kwargs
        else:
            # Sanitize all input parameters to prevent SQL injection
            safe_kwargs = sanitize_kwargs(kwargs)

        safe_kwargs['tenant'] = tenant

        template = jinja_env.get_template(filename)
        return template.render(**safe_kwargs)


def prepare_generic_kwargs(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepare kwargs for generic templates with proper value formatting.

    Args:
        kwargs: Raw parameters

    Returns:
        Processed parameters with formatted values
    """
    processed = {}

    for key, value in kwargs.items():
        if key == 'values' and isinstance(value, dict):
            # Format individual values in the values dict
            processed[key] = {k: format_sql_value(v) for k, v in value.items()}
        elif key == 'items' and isinstance(value, list):
            # Format each item in the items list
            processed[key] = []
            for item in value:
                if isinstance(item, dict):
                    processed[key].append({k: format_sql_value(v) for k, v in item.items()})
                else:
                    processed[key].append(item)
        elif key == 'updates' and isinstance(value, dict):
            # Format update values
            processed[key] = {k: format_sql_value(v) for k, v in value.items()}
        elif key == 'filters' and isinstance(value, dict):
            # Format simple filter values (for get_all, count)
            processed[key] = {k: format_sql_value(v) for k, v in value.items()}
        elif key == 'filters' and isinstance(value, list):
            # Format advanced filter values (for advanced_filter)
            processed[key] = []
            for filter_obj in value:
                formatted_filter = filter_obj.copy()
                if 'value' in filter_obj:
                    operator = filter_obj.get('operator', '=')
                    if operator in ['IN', 'NOT IN'] and isinstance(filter_obj['value'], list):
                        # Format each value in the list
                        formatted_filter['value'] = [format_sql_value(v) for v in filter_obj['value']]
                    elif operator in ['BETWEEN', 'NOT BETWEEN'] and isinstance(filter_obj['value'], list):
                        # Format both values for BETWEEN
                        formatted_filter['value'] = [format_sql_value(v) for v in filter_obj['value']]
                    else:
                        # Format single value
                        formatted_filter['value'] = format_sql_value(filter_obj['value'])
                processed[key].append(formatted_filter)
        else:
            # For other parameters, use format_sql_value if it's a simple value
            # that might be used in WHERE clauses, otherwise keep as is
            if isinstance(value, (str, int, float, bool, type(None), list, dict)):
                processed[key] = format_sql_value(value)
            else:
                processed[key] = value

    return processed