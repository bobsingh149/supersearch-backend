from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from app.database.session import get_async_session
from app.models.product import ProductSearchResult, ProductDB
from app.database.sql.sql import render_sql, SQLFilePath


router = APIRouter(prefix="/recommend",tags=["recommend"])

@router.get("similar/{product_id}", response_model=List[ProductSearchResult])
async def get_similar_products(
    product_id: str,
    match_count: Optional[int] = 10,
    db: Session = Depends(get_async_session)
):
    """
    Get similar products based on semantic similarity.
    
    Args:
        product_id: ID of the product to find similar items for
        match_count: Maximum number of similar products to return
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
            match_count=match_count
        )

        # Execute query and fetch results
        results = await db.execute(text(sql_query))
        results = await results.fetchall()
        
        # Convert results to ProductSearchResult objects
        similar_products = [
            ProductSearchResult(
                id=row.id,
                custom_data=row.custom_data,
                searchable_content=row.searchable_content,
                score=float(row.score or 0.0)
            ) for row in results
        ]

        return similar_products

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
