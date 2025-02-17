import logging
from fastapi import APIRouter, HTTPException, Depends, Body, Query
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from app.models.product import Product, ProductDB, ProductSearchResult, ProductInput
from app.utils.product import process_product_data
from uuid import uuid4
from asyncio import TaskGroup, sleep
from sqlalchemy import select, delete

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/products",
    tags=["products"]
)

@router.post("/", response_model=List[Product])
async def create_products(
    products: List[ProductInput],
    session: AsyncSession = Depends(get_async_session)
):
    """
    Bulk insert products with embeddings using TaskGroup for concurrent processing.
    Only requires product ID and custom_data for input.
    """
    try:
        logger.info(f"Processing {len(products)} products for insertion")
        
        # Generate IDs for products that don't have one
        for product in products:
            if not product.id:
                product.id = str(uuid4())
        
        # Convert ProductInput to Product for processing
        full_products = [
            Product(
                id=p.id,
                custom_data=p.custom_data,
                title=p.custom_data.get('title') if p.custom_data else None,
                searchable_content=p.custom_data.get('description') if p.custom_data else None
            ) 
            for p in products
        ]
        
        # Process products concurrently using TaskGroup
        processed_products = []
        async with TaskGroup() as tg:
            tasks = []
            for product in full_products:
                tasks.append(tg.create_task(process_product_data(product)))
                await sleep(0.1)  # Add small delay between task creation
        
        # Collect results from all tasks
        processed_products = [task.result() for task in tasks]
        
        # Bulk insert
        for product in processed_products:
            session.add(ProductDB(**product.model_dump()))
        await session.commit()
        
        logger.info(f"Successfully inserted {len(products)} products")
        return processed_products
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

@router.get("/{product_id}", response_model=Product)
async def get_product(
    product_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get a single product by ID
    """
    result = await session.get(ProductDB, product_id)
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product.model_validate(result)

@router.get("/", response_model=List[Product])
async def list_products(
    session: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    List all products with pagination
    """
    query = select(ProductDB).offset(skip).limit(limit)
    result = await session.execute(query)
    products = result.scalars().all()
    return [Product.model_validate(p) for p in products]

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

@router.delete("/")
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