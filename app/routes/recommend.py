from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from sqlalchemy.orm import Session
from app.database.session import get_async_session
from app.models.product import ProductSearchResult
from app.database.sql.sql import render_sql

router = APIRouter(prefix="/recommend",tags=["recommend"])

@router.get("similar/{product_id}", response_model=List[ProductSearchResult])
async def get_similar_products(
    product_id: str,
    match_count: Optional[int] = 10,
    full_text_weight: Optional[float] = 0.5,
    semantic_weight: Optional[float] = 0.5,
    rrf_k: Optional[int] = 60,
    db: Session = Depends(get_async_session)
):
    """
    Get similar products based on hybrid search combining semantic and keyword similarity.
    
    Args:
        product_id: ID of the product to find similar items for
        match_count: Maximum number of similar products to return
        full_text_weight: Weight for keyword/BM25 search results (0-1)
        semantic_weight: Weight for semantic search results (0-1)
        rrf_k: Reciprocal Rank Fusion constant
    """
    try:
        # First get the product to find similar items for
        product = db.execute(
            "SELECT searchable_content FROM products WHERE id = :id",
            {"id": product_id}
        ).fetchone()

        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Load and execute the similar products SQL template
        sql_template = render_sql("product/similar_products_hybrid.sql")
        sql_query = sql_template.render(
            product_id=product_id,
            searchable_content=product.searchable_content,
            match_count=match_count,
            full_text_weight=full_text_weight,
            semantic_weight=semantic_weight,
            rrf_k=rrf_k
        )

        # Execute query and fetch results
        results = db.execute(sql_query).fetchall()
        
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
