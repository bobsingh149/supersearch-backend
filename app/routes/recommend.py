from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from sqlalchemy import select, text
from app.database.session import get_async_session, get_tenant_name
from app.models.product import ProductSearchResult, ProductDB
from app.database.sql.sql import render_sql, SQLFilePath
from sqlalchemy.ext.asyncio import AsyncSession


router = APIRouter(prefix="/recommend",tags=["recommend"])

@router.get("/similar/{product_id}", response_model=List[ProductSearchResult])
async def get_similar_products(
    product_id: str,
    match_count: Optional[int] = 10,
    db: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name)
):
    """
    Get similar products based on semantic similarity.
    
    Args:
        product_id: ID of the product to find similar items for
        match_count: Maximum number of similar products to return
        :param db:
    """
    try:
        # Check if product exists using ORM
        query = select(ProductDB).where(ProductDB.id == product_id)
        result = await db.execute(query)
        product = result.scalar_one_or_none()

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Load and execute the similar products SQL template
        sql_query = render_sql(
            SQLFilePath.PRODUCT_SIMILAR_PRODUCTS_SEMANTIC,
            product_id=product_id,
            match_count=match_count,
            tenant=tenant
        )

        # Execute query and fetch results
        results = await db.execute(text(sql_query))
        rows = results.all()
        
        # Convert results to ProductSearchResult objects
        similar_products = [
            ProductSearchResult.model_validate(dict(row._mapping))
             for row in rows
        ]

        return similar_products

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

