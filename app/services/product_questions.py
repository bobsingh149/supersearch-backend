from typing import List, Dict, Any, Optional
import logging
import json
from google.genai.types import Content, GenerateContentConfig, AutomaticFunctionCallingConfig
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.vertex import get_genai_client
from app.models.product import ProductSearchResult
from app.models.product_questions import ProductQuestionOutput
from app.database.sql.sql import render_sql, SQLFilePath
from sqlalchemy import text

logger = logging.getLogger(__name__)

class ItemQuestionService:
    """Service for generating questions related to items using Gemini AI"""
    
    @staticmethod
    def format_product_context(product: ProductSearchResult) -> str:
        """
        Format product information into a context string for the LLM
        
        Args:
            product: ProductSearchResult object
        
        Returns:
            str: Formatted context string containing product information
        """
        if not product:
            return ""

        context = f"Product Details:\n"
        context += f"ID: {product.id}\n"
        context += f"Title: {product.title or 'Untitled Item'}\n"
        
        price = "Price not available"
        if product.custom_data and "price" in product.custom_data:
            price = product.custom_data["price"]
            
        context += f"Price: {price}\n"
        context += f"Details: {json.dumps(product.custom_data or {}, indent=2)}\n"
        
        # Add AI summary if available
        if product.ai_summary:
            context += f"AI-Generated Review Summary: {json.dumps(product.ai_summary, indent=2)}\n"
        
        # Add reviews if available
        if product.reviews and len(product.reviews) > 0:
            context += "Customer Reviews:\n"
            # Limit to 3 reviews to avoid making context too large
            for j, review in enumerate(product.reviews[:3], 1):
                context += f"{j}. {review.content[:300]}...\n" if len(review.content) > 300 else f"{j}. {review.content}\n"
            if len(product.reviews) > 3:
                context += f"... and {len(product.reviews) - 3} more reviews\n"
        
        return context
    
    @staticmethod
    async def get_product_by_id(session: AsyncSession, product_id: str) -> Optional[ProductSearchResult]:
        """
        Fetch a product by ID from the database
        
        Args:
            session: Database session
            product_id: Product ID to fetch
            
        Returns:
            Optional[ProductSearchResult]: Product search result or None if not found
        """
        try:
            query = text(render_sql(SQLFilePath.PRODUCT_GET_BY_IDS, product_ids=[product_id]))
            result = await session.execute(query, {"product_ids": [product_id]})
            product_row = result.first()
            
            if not product_row:
                return None
                
            product_data = dict(product_row._mapping)
            return ProductSearchResult.model_validate(product_data)
        except Exception as e:
            logger.error(f"Error fetching product by ID: {str(e)}")
            return None
    
    @staticmethod
    async def generate_questions(item_data: Dict[str, Any], num_questions: int = 5, product_id: Optional[str] = None, session: Optional[AsyncSession] = None) -> ProductQuestionOutput:
        """
        Generate questions related to an item using Gemini AI.
        
        Args:
            item_data: Dictionary containing item data
            num_questions: Number of questions to generate (default: 5)
            product_id: Optional product ID to fetch additional data
            session: Optional database session for fetching product data
            
        Returns:
            ProductQuestionOutput: Structured output with list of questions
        """
        client = get_genai_client()
        
        if not item_data:
            return ProductQuestionOutput(questions=["No item data available for question generation."])
        
        context = ""
        
        # If product_id and session are provided, fetch additional product data
        if product_id and session:
            product = await ItemQuestionService.get_product_by_id(session, product_id)
            if product:
                context = ItemQuestionService.format_product_context(product)
        
        # If no additional context was fetched, use the item_data directly
        if not context:
            context = f"Product Details:\n{json.dumps(item_data, indent=2)}"
        
        # Construct the prompt
        prompt = f"""Generate {num_questions} relevant questions that a customer might ask about this product:

{context}

Provide a response in JSON format with the following structure:
{{
  "questions": [
    "question 1",
    "question 2",
    "question 3",
    "question 4",
    "question 5"
  ]
}}

Each question should:
1. Be specifically answerable using the provided product context
2. Be concise and natural-sounding as if asked by a customer
3. Focus on different aspects of the product (specifications, usage, comparison with alternatives, etc.)
4. Use the actual product name rather than generic references
5. Be phrased as a direct question with a question mark
6. Represent common customer inquiries about this type of product

IMPORTANT: If the product has reviews or an AI review summary, ensure that AT LEAST ONE question is about customer reviews or experiences with the product.

Your response must be valid JSON only, with no additional text before or after.
"""

        try:
            response = await client.aio.models.generate_content(
                model='gemini-2.0-flash-001',
                contents=prompt,
                config=GenerateContentConfig(
                    max_output_tokens=1000,
                    temperature=0.7,
                    automatic_function_calling=AutomaticFunctionCallingConfig(
                        disable=True,
                        maximum_remote_calls=0
                    ),
                ),
            )
            
            # Try to parse JSON response
            try:
                response_text = response.text.strip()
                # Clean up any potential markdown code block formatting
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]
                    
                response_data = json.loads(response_text.strip())
                
                # Create and return a validated model
                return ProductQuestionOutput.model_validate(response_data)
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {str(e)}")
                logger.debug(f"Response text: {response.text}")
                
                # Fallback to manually extracting questions or returning an error
                fallback_questions = [
                    "Failed to generate structured questions from AI response.",
                    "Please try again later."
                ]
                
                return ProductQuestionOutput(questions=fallback_questions)
                
        except Exception as e:
            logger.error(f"Error generating item questions: {str(e)}")
            return ProductQuestionOutput(
                questions=["Failed to generate item questions. Please try again later."]
            ) 