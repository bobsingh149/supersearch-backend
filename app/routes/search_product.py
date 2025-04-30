from fastapi import APIRouter, HTTPException, Query, Body
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from fastapi import Depends
import logging
from app.models.product import ProductSearchResult
from app.services.vertex import get_embedding, TaskType
from app.database.sql.sql import render_sql, SQLFilePath
from app.services.reranker import rerank_search_results
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from app.models.settings import SettingKey
from app.utils.settings import get_setting_by_key

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["search"]
)

class FilterCondition(BaseModel):
    field: str
    value: Any
    operator: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in"] = "eq"

class FilterOptions(BaseModel):
    conditions: Optional[List[FilterCondition]] = None
    filter_type: Literal["AND", "OR"] = "AND"

class SortOption(BaseModel):
    field: str
    direction: Literal["asc", "desc"] = "asc"

async def validate_filter_sort_fields(filters: Optional[FilterOptions], sort: Optional[SortOption]) -> None:
    """
    Validate that filter and sort fields exist in the configured filter_fields and sortable_fields.
    
    Args:
        filters: Filter options to validate
        sort: Sort option to validate
        
    Raises:
        HTTPException: If any filter or sort field is not found in the configured fields
    """
    # Get search config with filter_fields and sortable_fields
    search_config = await get_setting_by_key(SettingKey.SEARCH_CONFIG)
    if not search_config:
        raise HTTPException(status_code=400, detail="Search configuration not found")
    
    filter_fields = search_config.get("filter_fields", [])
    sortable_fields = search_config.get("sortable_fields", [])
    
    # Validate filter fields
    if filters and filters.conditions:
        for filter_condition in filters.conditions:
            if filter_condition.field not in filter_fields:
                raise HTTPException(
                    status_code=400,
                    detail=f"Filter field '{filter_condition.field}' is not allowed. Allowed fields: {', '.join(filter_fields)}"
                )
    
    # Validate sort field
    if sort and sort.field not in sortable_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Sort field '{sort.field}' is not allowed. Allowed fields: {', '.join(sortable_fields)}"
        )

def build_filter_condition(filters: FilterOptions) -> str:
    """
    Build SQL filter condition from filter options.
    
    Args:
        filters: Filter options
        
    Returns:
        SQL filter condition string
    """
    if not filters or not filters.conditions:
        return ""
    
    conditions = []
    for filter_condition in filters.conditions:
        field = filter_condition.field
        value = filter_condition.value
        operator = filter_condition.operator
        
        if operator == "eq":
            conditions.append(f"(custom_data->>'{field}')::text = '{value}'")
        elif operator == "neq":
            conditions.append(f"(custom_data->>'{field}')::text != '{value}'")
        elif operator == "gt":
            conditions.append(f"(custom_data->>'{field}')::float > {value}")
        elif operator == "gte":
            conditions.append(f"(custom_data->>'{field}')::float >= {value}")
        elif operator == "lt":
            conditions.append(f"(custom_data->>'{field}')::float < {value}")
        elif operator == "lte":
            conditions.append(f"(custom_data->>'{field}')::float <= {value}")
        elif operator == "in":
            if isinstance(value, list):
                value_list = ", ".join([f"'{v}'" for v in value])
                conditions.append(f"(custom_data->>'{field}')::text IN ({value_list})")
            else:
                conditions.append(f"(custom_data->>'{field}')::text = '{value}'")
    
    join_str = f" {filters.filter_type} "
    return f"({join_str.join(conditions)})"

async def handle_empty_query(
    query: str, 
    page: int, 
    size: int, 
    db: AsyncSession, 
    include_search_type: bool = True,
    filters: Optional[FilterOptions] = None,
    sort: Optional[SortOption] = None
) -> List[ProductSearchResult]:
    """
    Utility method to handle empty queries by returning all products in paginated form.
    
    Args:
        query: The search query (expected to be empty or whitespace)
        page: Page number for pagination
        size: Number of results per page
        db: Database session
        include_search_type: Whether to include search_type field in the results
        filters: Optional filter options
        sort: Optional sort option
        
    Returns:
        List of ProductSearchResult objects with all products in paginated form
    """
    if query.strip():
        return None  # Not an empty query, should be handled by the caller
        
    logger.info("Empty query provided, returning all products in paginated form")
    
    # Calculate offset from page and size
    offset = (page - 1) * size
    
    # Build filter condition
    filter_condition = ""
    if filters and filters.conditions:
        filter_condition = f"WHERE {build_filter_condition(filters)}"
    
    # Build sort condition
    sort_condition = "ORDER BY id"
    if sort:
        sort_direction = sort.direction.upper()
        sort_condition = f"ORDER BY (custom_data->>'{sort.field}')::text {sort_direction}, id"
    
    # Simple query to get all products with pagination
    if include_search_type:
        sql_query = f"""
            SELECT 
                id, 
                custom_data, 
                searchable_content,
                image_url,
                0 as score,
                'all_products' as search_type
            FROM products
            {filter_condition}
            {sort_condition}
            LIMIT :limit OFFSET :offset
        """
    else:
        sql_query = f"""
            SELECT 
                id, 
                title,
                custom_data, 
                searchable_content,
                image_url,
                0 as score
            FROM products
            {filter_condition}
            {sort_condition}
            LIMIT :limit OFFSET :offset
        """
    
    result = await db.execute(
        text(sql_query),
        {"limit": size, "offset": offset}
    )
    
    if include_search_type:
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
                score=float(row._mapping['score'] or 0.0),
                search_type=row._mapping['search_type']
            ) for row in result
        ]
    else:
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                title=row._mapping.get('title'),
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
                score=float(row._mapping['score'] or 0.0)
            ) for row in result
        ]
    
    logger.info(f"Found {len(products)} results for empty query (all products)")
    return products

@router.post("", response_model=List[ProductSearchResult])
async def hybrid_search(
    query: str = Query(default="", description="Search query text"),
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    filters: Optional[FilterOptions] = Body(default=None, description="Filter options"),
    sort: Optional[SortOption] = Body(default=None, description="Sort option"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Perform hybrid search using both full-text and semantic search with pagination.
    If query is empty, returns all products in paginated form without any ranking.
    Supports filtering with AND/OR logic and sorting by a single field.
    """
    try:
        # Validate filter and sort fields
        await validate_filter_sort_fields(filters, sort)
        
        # Handle empty query
        empty_results = await handle_empty_query(query, page, size, db, include_search_type=False, 
                                                filters=filters, sort=sort)
        if empty_results is not None:
            return empty_results
            
        # Calculate offset from page and size
        offset = (page - 1) * size
        
        # Get vector embedding for the query
        query_embedding = await get_embedding(query, TaskType.QUERY)

        # Build filter condition
        filter_condition = ""
        filter_type = "AND"
        if filters:
            filter_condition = build_filter_condition(filters)
            filter_type = filters.filter_type
            
        # Build sort option
        sort_option = None
        if sort:
            sort_option = {
                "field": sort.field,
                "direction": sort.direction
            }

        sql_query = render_sql(SQLFilePath.PRODUCT_HYBRID_SEARCH,
                               query_text=query,
                               query_embedding=query_embedding,
                               match_count=size,
                               offset=offset,
                               full_text_weight=0.1,
                               semantic_weight=0.9,
                               rrf_k=10,
                               fuzzy_distance=1,
                               filter_condition=filter_condition,
                               filter_type=filter_type,
                               sort_option=sort_option
                               )
        print(sql_query)
        result = await db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                title=row._mapping['title'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
                score=float(row._mapping['score'] or 0.0)
            ) for row in result
        ]
        
        logger.info(f"Found {len(products)} results for query: {query}")
        return products
    
    except Exception as e:
        logger.error(f"Error in hybrid search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/keywords", response_model=List[ProductSearchResult])
async def full_text_search(
    query: str = Query(default="", description="Search query text"),
    limit: int = Query(default=10, le=100),
    fuzzy_distance: int = Query(default=1, ge=0, le=5),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Perform full-text search using PostgreSQL's full text search capabilities.
    If query is empty, returns all products up to the limit without any ranking.
    """
    try:
        # If query is empty, return all products up to the limit
        if not query.strip():
            logger.info("Empty query provided, returning all products up to the limit")
            
            # Simple query to get all products
            sql_query = """
                SELECT 
                    id, 
                    custom_data, 
                    searchable_content,
                    image_url,
                    0 as score
                FROM products
                ORDER BY id
                LIMIT :limit
            """
            
            result = await db.execute(
                text(sql_query),
                {"limit": limit}
            )
            
            products = [
                ProductSearchResult(
                    id=row._mapping['id'],
                    custom_data=row._mapping['custom_data'],
                    searchable_content=row._mapping['searchable_content'],
                    image_url=row._mapping.get('image_url'),
                    score=float(row._mapping['score'] or 0.0)
                ) for row in result
            ]
            
            logger.info(f"Found {len(products)} results for empty query (all products)")
            return products
        
        # Use full-text search for short queries or when semantic search fails
        sql_query = render_sql(SQLFilePath.PRODUCT_FULL_TEXT_SEARCH,
                              query_text=query,
                              fuzzy_distance=fuzzy_distance,
                              match_count=limit)
        
        result = await db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
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
    query: str = Query(default="", description="Search query text"),
    limit: int = Query(default=10, le=100),
    fuzzy_distance: int = Query(default=1, ge=0, le=5),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Perform autocomplete search with fuzzy matching.
    If query is empty, returns all products up to the limit without any ranking.
    """
    try:
        # If query is empty, return all products up to the limit
        if not query.strip():
            logger.info("Empty query provided, returning all products up to the limit for autocomplete")
            
            # Simple query to get all products
            sql_query = """
                SELECT 
                    custom_data,
                    0 as score
                FROM products
                ORDER BY id
                LIMIT :limit
            """
            
            result = await db.execute(
                text(sql_query),
                {"limit": limit}
            )
            
            products = [
                {
                    "data": row._mapping['custom_data'],
                    "score": float(row._mapping['score'] or 0.0)
                } 
                for row in result
            ]
            
            logger.info(f"Found {len(products)} results for empty autocomplete query")
            return {"results": products}
            
        sql_query = render_sql(SQLFilePath.PRODUCT_AUTOCOMPLETE_SEARCH,
                              prefix=query,
                              match_count=limit)
        
        result = await db.execute(text(sql_query))
        
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

@router.get("/semantic", response_model=List[ProductSearchResult])
async def semantic_search(
    query: str = Query(default="", description="Search query text"),
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Perform semantic search using vector embeddings with pagination.
    If query is empty, returns all products in paginated form without any ranking.
    """
    try:
        # Handle empty query
        empty_results = await handle_empty_query(query, page, size, db, include_search_type=False)
        if empty_results is not None:
            return empty_results
            
        # Calculate offset from page and size
        offset = (page - 1) * size
        
        # Get vector embedding for the query
        query_embedding = await get_embedding(query, TaskType.QUERY)

        sql_query = render_sql(SQLFilePath.PRODUCT_SEMANTIC_SEARCH,
                              query_embedding=query_embedding,
                              match_count=size,
                              offset=offset)
        print(sql_query)
        result = await db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
                score=float(row._mapping['score'] or 0.0)
            ) for row in result
        ]
        
        logger.info(f"Found {len(products)} semantic search results for query: {query}")
        return products
    
    except Exception as e:
        logger.error(f"Error in semantic search: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hybrid-without-ranking", response_model=List[ProductSearchResult])
async def hybrid_search_without_ranking(
    query: str = Query(default="", description="Search query text"),
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    rerank: bool = Query(default=True, description="Whether to rerank the results"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Perform hybrid search without ranking using both full-text and semantic search with pagination,
    optionally reranking the results using the reranker service.
    If query is empty, returns all products in paginated form without any ranking.
    """
    try:
        # Handle empty query
        empty_results = await handle_empty_query(query, page, size, db, include_search_type=True)
        if empty_results is not None:
            return empty_results
            
        # Calculate offset from page and size
        offset = (page - 1) * size
        
        # Get vector embedding for the query
        query_embedding = await get_embedding(query, TaskType.QUERY)

        sql_query = render_sql(SQLFilePath.PRODUCT_HYBRID_SEARCH_WITHOUT_RANKING,
                               query_text=query,
                               query_embedding=query_embedding,
                               match_count=size,
                               offset=offset)
        
        result = await db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
                score=float(row._mapping['score'] or 0.0),
                search_type=row._mapping['search_type']
            ) for row in result
        ]
        
        logger.info(f"Found {len(products)} results for unranked hybrid query: {query}")
        
        # Rerank the results if requested
        if rerank and products:
            logger.info(f"Reranking {len(products)} results for query: {query}")
            products = await rerank_search_results(query, products)
            logger.info(f"Reranking complete for query: {query}")
        
        return products
    
    except Exception as e:
        logger.error(f"Error in hybrid search without ranking: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/hybrid-reranked", response_model=List[ProductSearchResult])
async def hybrid_search_with_reranking(
    query: str = Query(default="", description="Search query text"),
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=10, ge=1, le=100, description="Results per page"),
    top_n: Optional[int] = Query(default=None, description="Number of top results to return after reranking"),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Perform hybrid search without ranking and then rerank the results using the reranker service.
    This endpoint always applies reranking to the search results.
    If query is empty, returns all products in paginated form without any ranking.
    """
    try:
        # Handle empty query
        empty_results = await handle_empty_query(query, page, size, db, include_search_type=True)
        if empty_results is not None:
            return empty_results
            
        # Calculate offset from page and size
        offset = (page - 1) * size
        
        # Get vector embedding for the query
        query_embedding = await get_embedding(query, TaskType.QUERY)

        # Use a larger match count for reranking to get better results
        # We'll retrieve more results than requested and then rerank them
        rerank_pool_size = size*3  # Get 2x results
        
        sql_query = render_sql(SQLFilePath.PRODUCT_HYBRID_SEARCH_WITHOUT_RANKING,
                               query_text=query,
                               query_embedding=query_embedding,
                               match_count=rerank_pool_size,
                               offset=offset)
        
        result = await db.execute(text(sql_query))
        
        products = [
            ProductSearchResult(
                id=row._mapping['id'],
                custom_data=row._mapping['custom_data'],
                searchable_content=row._mapping['searchable_content'],
                image_url=row._mapping.get('image_url'),
                score=float(row._mapping['score'] or 0.0),
                search_type=row._mapping['search_type']
            ) for row in result
        ]
        
        logger.info(f"Found {len(products)} results for hybrid query before reranking: {query}")
        
        # Apply reranking
        if products:
            logger.info(f"Reranking {len(products)} results for query: {query}")
            reranked_products = await rerank_search_results(query, products, top_n or size)
            logger.info(f"Reranking complete, returning {len(reranked_products)} results for query: {query}")
            return reranked_products
        
        return products
    
    except Exception as e:
        logger.error(f"Error in hybrid search with reranking: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
