from typing import List, Optional, Dict, Any
import cohere
from app.models.product import ProductSearchResult
from app.core.settings import settings

class CohereAPI:
    """
    Async client for Cohere APIs
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.cohere.api_key
        if not self.api_key:
            raise ValueError("COHERE_API_KEY must be provided in settings")
        
        self.client = cohere.AsyncClientV2(api_key=self.api_key)
        self.model = "rerank-v3.5"  # Using the latest rerank model

    async def rerank(
        self,
        query: str,
        search_results: List[ProductSearchResult],
        top_n: Optional[int] = None
    ) -> List[ProductSearchResult]:
        """
        Reranks search results using the Cohere reranking API.
        """
        if not search_results:
            return []

        # Prepare documents list using searchable_content
        documents = [
            result.searchable_content for result in search_results 
            if result.searchable_content is not None
        ]

        if not documents:
            return search_results

        # Default top_n to the length of search results if not specified
        top_n = top_n or len(search_results)

        try:
            # Call Cohere rerank API
            response = await self.client.rerank(
                model=self.model,
                query=query,
                documents=documents,
                top_n=top_n
            )

            # Create a new reranked list based on the response indices
            reranked_results = []
            for result in response.results:
                original_result = search_results[result.index]
                # Update the score with the relevance_score from reranking
                original_result.score = result.relevance_score
                reranked_results.append(original_result)

            return reranked_results

        except Exception as e:
            # Log error in production
            print(f"Error calling Cohere rerank API: {str(e)}")
            return search_results  # Return original results if reranking fails 