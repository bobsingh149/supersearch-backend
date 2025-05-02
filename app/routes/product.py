import logging
import json
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from app.models.product import Product, ProductDB, ProductInput, PaginatedProductsResponse
from app.models.product_questions import ProductQuestionsResponse
from app.services.product import process_product_data
from app.services.product_questions import ItemQuestionService
from uuid import uuid4
from asyncio import TaskGroup
from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert
from starlette import status

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/products",
    tags=["products"]
)

@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_products(
    bulk_input: ProductInput,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Bulk insert products with embeddings using TaskGroup for concurrent processing.
    Accepts product data with specified fields for ID, title, and searchable attributes.
    """
    try:
        logger.info(f"Processing {len(bulk_input.data)} products for insertion")
        
        # Convert input data to Product format
        products = []
        for item in bulk_input.data:
            product_id = str(item.get(bulk_input.id_field)) if item.get(bulk_input.id_field) else str(uuid4())
            
            # Combine searchable attributes into a single string
            searchable_content = " ".join(
                str(item.get(field, "")) 
                for field in bulk_input.searchable_attribute_fields 
                if item.get(field)
            )
            
            # Get image URL if field is specified
            image_url = None
            if bulk_input.image_url_field:
                image_url = item.get(bulk_input.image_url_field)
            
            products.append(
                Product(
                    id=product_id,
                    custom_data=item,
                    title=item.get(bulk_input.title_field),
                    searchable_content=searchable_content,
                    image_url=image_url
                )
            )
        
        # Process products concurrently using TaskGroup
        async with TaskGroup() as tg:
            tasks = []
            for product in products:
                tasks.append(tg.create_task(process_product_data(product)))

        # Collect results from all tasks
        processed_products = [task.result() for task in tasks]
        
        # Convert processed products to dictionaries for bulk insert, excluding timestamp fields
        products_to_insert = [
            product.model_dump(exclude={'created_at', 'updated_at'}) 
            for product in processed_products
        ]
        
        # Bulk insert using insert()
        stmt = insert(ProductDB).values(products_to_insert)
        await session.execute(stmt)
        await session.commit()
        
        logger.info(f"Successfully inserted {len(products)} products")
        return None
    except Exception as e:
        logger.error(f"Error inserting products: {str(e)}")
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{product_id}", response_model=Product)
async def update_product(
    product_id: str,
    product: Product,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Update a single product with new embeddings
    """
    try:
        result = await session.get(ProductDB, product_id)
        if not result:
            raise HTTPException(status_code=404, detail="Product not found")
        
        processed_product = await process_product_data(product)
        
        # Update product fields
        for key, value in processed_product.model_dump(exclude={'id'}).items():
            setattr(result, key, value)
        
        await session.commit()
        return Product.model_validate(result)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{product_id}")
async def get_product(
    product_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get a single product's custom_data by ID using raw SQL
    """

    query = text("SELECT custom_data FROM demo_movies.products WHERE id = :product_id")
    result = await session.execute(query, {"product_id": product_id})
    product = result.scalar_one_or_none()
    
    if not product:
        raise HTTPException(status_code=500, detail="XYZ WTF Product not found")
    return product

@router.get("", response_model=PaginatedProductsResponse)
async def list_products(
    session: AsyncSession = Depends(get_async_session),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=1000, description="Items per page")
):
    """
    List all products' custom_data with pagination.
    Uses page and size parameters for pagination.
    Returns a paginated response with products, page info, and has_more flag.
    """
    # Calculate offset from page and size
    offset = (page - 1) * size
    
    # Get products for current page
    query = text("SELECT custom_data FROM products OFFSET :offset LIMIT :size")
    result = await session.execute(query, {"offset": offset, "size": size})
    products = [p.custom_data for p in result.all()]
    
    # Check if there are more products
    has_more_query = text("SELECT EXISTS(SELECT 1 FROM products OFFSET :next_offset LIMIT 1)")
    has_more_result = await session.execute(has_more_query, {"next_offset": offset + size})
    has_more = has_more_result.scalar()
    
    # Return paginated response
    return PaginatedProductsResponse.model_validate({
        "products": products,
        "page": page,
        "size": size,
        "has_more": has_more
    })

@router.delete("/{product_id}")
async def delete_product(
    product_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Delete a single product
    """
    result = await session.get(ProductDB, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await session.delete(result)
    await session.commit()
    return {"message": "Product deleted successfully"}

@router.delete("")
async def delete_all_products(
    session: AsyncSession = Depends(get_async_session)
):
    """
    Delete all products (use with caution)
    """
    query = delete(ProductDB)
    await session.execute(query)
    await session.commit()
    return {"message": "All products deleted successfully"}

@router.get("/{product_id}/questions", response_model=ProductQuestionsResponse)
async def generate_item_questions(
    product_id: str,
    num_questions: int = Query(5, ge=1, le=10, description="Number of questions to generate"),
    force_regenerate: bool = Query(False, description="Force regeneration of questions even if cached questions exist"),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Generate relevant questions related to a specific item using AI.
    The questions are based on the item's custom data.
    
    If suggested_questions is already available for the product, those will be returned
    unless force_regenerate is set to True.
    
    Args:
        product_id: ID of the item to generate questions for
        num_questions: Number of questions to generate (default: 5)
        force_regenerate: Force regeneration of questions even if cached questions exist
        
    Returns:
        List of item-related questions
    """
    # First, fetch the product from the database
    query = text("""
        SELECT 
            custom_data, 
            suggested_questions 
        FROM products 
        WHERE id = :product_id
    """)
    result = await session.execute(query, {"product_id": product_id})
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    
    item_data = row.custom_data
    existing_questions = row.suggested_questions
    
    # If we have suggested questions and aren't forcing regeneration, return those
    if existing_questions and not force_regenerate:
        return ProductQuestionsResponse(questions=existing_questions)
    
    # Generate questions using the service
    questions_response = await ItemQuestionService.generate_questions(
        item_data=item_data,
        num_questions=num_questions
    )
    
    # Store the generated questions in the database
    update_query = text("""
        UPDATE products
        SET suggested_questions = :questions
        WHERE id = :product_id
    """)
    
    # Convert questions list to JSON string for storage
    questions_json = json.dumps(questions_response.questions)
    
    await session.execute(
        update_query, 
        {
            "product_id": product_id, 
            "questions": questions_json
        }
    )
    await session.commit()
    
    return ProductQuestionsResponse(questions=questions_response.questions)

# Sample data to test with POST /sync/add:

# You can use this data by making a POST request to /sync/add with the above list 