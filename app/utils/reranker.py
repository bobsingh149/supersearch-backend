from typing import List, Optional
from app.models.product import ProductSearchResult
from app.utils.jina_api import JinaAPI

async def rerank_search_results(
    query: str,
    search_results: List[ProductSearchResult],
    top_n: Optional[int] = None
) -> List[ProductSearchResult]:
    """
    Reranks search results using the Jina AI reranking API.
    
    Args:
        query: The search query
        search_results: List of ProductSearchResult objects
        top_n: Number of top results to return (defaults to length of search_results if None)
    
    Returns:
        Reranked list of ProductSearchResult objects
    """
    try:
        jina_api = JinaAPI()
        return await jina_api.rerank(query, search_results, top_n)
    except Exception as e:
        # Log error in production
        print(f"Error in reranking: {str(e)}")
        return search_results  # Return original results if reranking fails
