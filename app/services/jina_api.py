from typing import List, Optional, Dict, Any
import aiohttp
from app.models.product import ProductSearchResult
from app.core.appsettings import app_settings

class JinaAPI:
    """
    Async client for Jina AI APIs
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or app_settings.jina.api_key
        if not self.api_key:
            raise ValueError("JINA_API_KEY must be provided in settings")
        
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        self.base_url = 'https://api.jina.ai/v1'

    async def rerank(
        self,
        query: str,
        search_results: List[ProductSearchResult],
        top_n: Optional[int] = None
    ) -> List[ProductSearchResult]:
        """
        Reranks search results using the Jina AI reranking API.
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

        # Prepare request data
        data = {
            "model": "jina-reranker-v2-base-multilingual",
            "query": query,
            "top_n": top_n or len(search_results),
            "documents": documents
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base_url}/rerank',
                    headers=self.headers,
                    json=data
                ) as response:
                    response.raise_for_status()
                    rerank_data = await response.json()

                    # Create a new reranked list based on the response indices
                    reranked_results = []
                    for result in rerank_data['results']:
                        original_result = search_results[result['index']]
                        # Update the score with the relevance_score from reranking
                        original_result.score = result['relevance_score']
                        reranked_results.append(original_result)

                    return reranked_results

        except aiohttp.ClientError as e:
            # Log error in production
            print(f"Error calling rerank API: {str(e)}")
            return search_results  # Return original results if reranking fails

    async def reader(self, url: str) -> str:
        """
        Converts URL content to LLM-friendly text using Jina Reader API
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f'https://r.jina.ai/{url}',
                    headers={'Authorization': f'Bearer {self.api_key}'}
                ) as response:
                    response.raise_for_status()
                    return await response.text()

        except aiohttp.ClientError as e:
            # Log error in production
            print(f"Error calling reader API: {str(e)}")
            raise

    async def segment(
        self, 
        content: str, 
        max_chunk_length: int = 1000,
        return_tokens: bool = True,
        return_chunks: bool = True
    ) -> Dict[str, Any]:
        """
        Segments text content into chunks using Jina Segmenter API
        """
        data = {
            "content": content,
            "return_tokens": return_tokens,
            "return_chunks": return_chunks,
            "max_chunk_length": max_chunk_length
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base_url}/segment',
                    headers=self.headers,
                    json=data
                ) as response:
                    response.raise_for_status()
                    return await response.json()

        except aiohttp.ClientError as e:
            # Log error in production
            print(f"Error calling segment API: {str(e)}")
            raise
