import logging
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from app.models.product import Product, ProductDB, ProductInput, PaginatedProductsResponse
from app.services.product import process_product_data
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
            
            products.append(
                Product(
                    id=product_id,
                    custom_data=item,
                    title=item.get(bulk_input.title_field),
                    searchable_content=searchable_content
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
    Get a single product's custom_data by ID
    """
    result = await session.get(ProductDB, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return result.custom_data

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

# Sample data to test with POST /sync/add:

# You can use this data by making a POST request to /sync/add with the above list 