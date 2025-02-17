from jinja2 import Environment, FileSystemLoader
import os
from pathlib import Path

# Set up Jinja2 environment
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sql')
jinja_env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    trim_blocks=True,
    lstrip_blocks=True
)

def render_query(filename: str, **kwargs) -> str:
    """
    Loads and renders an SQL template with the given parameters.
    
    Args:
        filename: Name of the SQL file (with or without .sql extension)
                 Can include subfolder path like 'product/full_text_search'
        kwargs: Dictionary of parameters to pass to the template
    
    Returns:
        Rendered SQL query as a string
    
    Example:
        render_query('product/full_text_search', query_text='search term', limit=10)
    """
    # Ensure the path ends with .sql
    if not filename.endswith('.sql'):
        filename = filename + '.sql'
    
    template = jinja_env.get_template(filename)
    return template.render(**kwargs) 