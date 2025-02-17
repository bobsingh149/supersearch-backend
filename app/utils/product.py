from app.models.product import Product
from app.utils.embedding import get_embedding, TaskType


async def process_product_data(product: Product) -> Product:
    """
    Process product data and generate embeddings
    """
    # Set title from custom_data if available
    if product.custom_data and 'title' in product.custom_data:
        product.title = product.custom_data['title']
    
    # Generate searchable content from product data
    searchable_content = generate_searchable_content(product)
    product.searchable_content = searchable_content
    
    # Generate embeddings
    if product.custom_data:  # Assuming text description is in custom_data
        product.text_embedding = await get_embedding(searchable_content,TaskType.DOCUMENT)
    
    return product

def generate_searchable_content(product: Product) -> str:
    """
    Generate searchable content from product data
    """
    content_parts = []
    
    if product.custom_data:
        # Add relevant fields from custom_data
        for field in ['title', 'description', 'brand', 'category', 'tags']:
            if field in product.custom_data:
                content_parts.append(str(product.custom_data[field]))
    


    return ' '.join(content_parts)

