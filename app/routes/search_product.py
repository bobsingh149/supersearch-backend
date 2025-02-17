from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text, func, select
from app.database.session import get_db
from sqlalchemy.orm import Session
from fastapi import Depends
import logging
from app.models.product import ProductDB, ProductSearchResult
from app.utils.embedding import get_embedding, TaskType
from app.utils.sql import render_query
from typing import List

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"]
)

@router.get("/hybrid", response_model=List[ProductSearchResult])
async def hybrid_search(
    query: str = Query(..., description="Search query text"),
    limit: int = Query(default=10, le=100),
    full_text_weight: float = Query(default=0.4, ge=0, le=1),
    semantic_weight: float = Query(default=0.6, ge=0, le=1),
    rrf_k: int = Query(default=50, ge=1),
    fuzzy_distance: int = Query(default=2, ge=0, le=5),
    db: Session = Depends(get_db)
):
    """
    Perform hybrid search using both full-text and semantic search
    """
    try:
        # Get vector embedding for the query
        query_embedding = await get_embedding(query, TaskType.QUERY)

        sql_query = render_query('product/hybrid_search',
            query_text=query,
            query_embedding=query_embedding,
            match_count=limit,
            full_text_weight=full_text_weight,
            semantic_weight=semantic_weight,
            rrf_k=rrf_k,
            fuzzy_distance=fuzzy_distance
        )
        
        result = db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                score=float(row._mapping['score'] or 0.0)
            ) for row in result
        ]
        
        logger.info(f"Found {len(products)} results for query: {query}")
        return products
    
    except Exception as e:
        logger.error(f"Error in hybrid search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/text", response_model=List[ProductSearchResult])
async def full_text_search(
    query: str = Query(..., description="Search query text"),
    limit: int = Query(default=10, le=100),
    fuzzy_distance: int = Query(default=2, ge=0, le=5),
    db: Session = Depends(get_db)
):
    """
    Perform full-text search using PostgreSQL's full text search capabilities
    """
    try:
        # Render the SQL query with parameters
        sql_query = render_query('product/full_text_search', 
            query_text=query,
            match_count=limit,
            fuzzy_distance=fuzzy_distance
        )
        
        result = db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                score=float(row._mapping['score'] or 0.0)
            ) for row in result
        ]
        
        logger.info(f"Found {len(products)} results for text search query: {query}")
        return products
    
    except Exception as e:
        logger.error(f"Error in full text search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/autocomplete")
async def autocomplete_search(
    query: str = Query(..., description="Search query text"),
    limit: int = Query(default=10, le=100),
    fuzzy_distance: int = Query(default=2, ge=0, le=5),
    db: Session = Depends(get_db)
):
    """
    Perform autocomplete search with fuzzy matching
    """
    try:
        sql_query = render_query('product/autocomplete_search',
            query_text=query,
            match_count=limit,
            fuzzy_distance=fuzzy_distance
        )
        
        result = db.execute(text(sql_query))
        
        products = [
            {
                "data": row._mapping['custom_data'],
                "score": float(row._mapping['score'] or 0.0)
            } 
            for row in result
        ]
        
        logger.info(f"Found {len(products)} results for autocomplete query: {query}")
        return {"results": products}
    
    except Exception as e:
        logger.error(f"Error in autocomplete search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
