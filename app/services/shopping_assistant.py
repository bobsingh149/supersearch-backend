from google import genai
from google.genai.chats import AsyncChat
from google.genai.types import Content, Part
from typing import List, Optional, Dict, Any, Union

from sqlalchemy.ext.asyncio import AsyncSession
import logging
from sqlalchemy import text, RowMapping
import json

from app.database.session import get_async_session_with_contextmanager
from app.models.product import ProductSearchResult

logger = logging.getLogger(__name__)

class ShoppingAssistantUtils:
    SYSTEM_PROMPT = """You are a helpful shopping assistant. Your goal is to help users find products 
    and answer questions about shopping. Provide clear, concise, and relevant responses."""

    @staticmethod
    async def determine_intent(client: genai.Client, query: str) -> str:
        """
        Determine if the query requires product fetching or direct response
        Returns: 'fetch_products' or 'direct_response'
        """
        prompt = f"""Determine if this shopping query requires product recommendations from a database or just general advice.
        Query: "{query}"
        
        Return only one word:
        - 'fetch_products' if the query is asking for specific product recommendations
        - 'direct_response' if the query is asking for general advice or comparison
        
        Example:
        "I want to buy a t-shirt" -> "fetch_products"
        "What can I pair with this black shirt?" -> "direct_response"
        "Compare these products" -> "direct_response"
        
        Answer:"""

        try:
            response = await client.aio.models.generate_content(
                model="gemini-2.0-flash-001",
                contents=prompt
            )
            intent = response.text.strip().lower()
            logger.info(f"Determined intent: {intent} for query: {query}")
            return intent
        except Exception as e:
            logger.error(f"Error determining intent: {str(e)}")
            raise

    @staticmethod
    def format_product_context(products: List['ProductSearchResult']) -> str:
        """
        Format product information into a context string for the LLM
        
        Args:
            products: List of ProductSearchResult objects
        
        Returns:
            str: Formatted context string containing product information
        """
        if not products:
            return ""

        context = "Here are some products that might be relevant. ONLY reference products that are directly relevant to the user's query and ignore the rest. When referencing them, format their titles as hyperlinks like [Product Title](/demo_site/:product_id):\n\n"

        for i, product in enumerate(products, 1):
            context += f"{i}. Product ID: {product.id}\n"
            context += f"   Title: {product.title or 'Untitled Product'}\n"
            
            price = "Price not available"
            if product.custom_data and "price" in product.custom_data:
                price = product.custom_data["price"]
                
            context += f"   Price: {price}\n"
            context += f"   Details: {product.searchable_content or ''}\n\n"

        return context

    @staticmethod
    def create_chat_history(messages: List[Dict[str, str]], system_prompt: Optional[str] = None) -> List[Content]:
        """
        Create chat history format for Gemini API
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            system_prompt: Optional system prompt to prepend
        """
        history = []
        
        if system_prompt:
            history.append(Content(
                parts=[Part(text=system_prompt)],
                role="model"
            ))
        
        for msg in messages:
            history.append(Content(
                parts=[Part(text=msg['content'])],
                role=msg['role']
            ))
            
        return history

    @staticmethod
    async def save_conversation(
        db: AsyncSession,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        context: Optional[str] = None
    ) -> None:
        """
        Save conversation messages to database
        
        Args:
            db: Database session
            conversation_id: Unique conversation identifier
            user_message: User's message
            assistant_response: Assistant's response
            context: Optional context provided to the assistant
        """
        try:
            # Check if conversation exists
            query = text("SELECT * FROM demo_movies.conversations WHERE conversation_id = :conversation_id")
            result = await db.execute(query, {"conversation_id": conversation_id})
            conversation = result.first()
            
            new_messages = [
                {"role": "user", "content": user_message}
            ]
            
            if context:
                new_messages.append({
                    "role": "model",
                    "content": f"Context provided:\n{context}"
                })
                
            new_messages.append({
                "role": "model",
                "content": assistant_response
            })
            
            if conversation:
                # Update existing conversation
                update_query = text("""
                    UPDATE demo_movies.conversations 
                    SET messages = messages || CAST(:new_messages AS jsonb)
                    WHERE conversation_id = :conversation_id
                """)
                await db.execute(update_query, {
                    "conversation_id": conversation_id,
                    "new_messages": json.dumps(new_messages)
                })
            else:
                # Insert new conversation
                insert_query = text("""
                    INSERT INTO demo_movies.conversations (conversation_id, messages) 
                    VALUES (:conversation_id, :messages)
                """)
                await db.execute(insert_query, {
                    "conversation_id": conversation_id,
                    "messages": json.dumps(new_messages)
                })

            await db.commit()
            logger.info(f"Saved conversation for ID: {conversation_id}")
            
        except Exception as e:
            logger.error(f"Error saving conversation: {str(e)}")
            await db.rollback()
            raise

    @staticmethod
    def construct_prompt(
        query: str,
        context: Optional[str] = None,
    ) -> str:
        """
        Constructs a prompt for the shopping assistant by combining the user query and context.
        
        Args:
            query: The user's question or request
            context: Optional context about products or other relevant information
        
        Returns:
            str: The constructed prompt for the LLM
        """
        prompt = "User Query: " + query + "\n\n"
        
        if context:
            prompt = "Context about products:\n" + context + "\n\n" + prompt
            prompt += """IMPORTANT INSTRUCTIONS FOR CONTEXT USE:
1. If the user is searching for or asking about product recommendations, refer to products in user_query_search_result
2. If the user is asking about specific products they mentioned before, refer to products in user_query_context and recent history 
3. If the user query does not have product search/recommendation intent, ignore user_query_search_result and refer to recent history and user_query_context instead
4. Only reference products that are DIRECTLY RELEVANT to the user's query
5. Ignore any products that don't match what the user is looking for

"""
        
        prompt += """When mentioning product titles in your response, format them as hyperlinks using markdown, like this: [Product Title](/demo_site/:product_id).
For example, if you're recommending a product with ID 'abc123' and title 'Green T-shirt', format it as [Green T-shirt](/demo_site/abc123).

Remember to list any referenced product IDs at the end of your response using the format product_ids:id1,id2,id3
"""
        
        return prompt

async def get_chat_from_history(conversation_id: str, client: genai.Client) -> AsyncChat:
    """
    Get or create a chat session with history from the database
    Uses caching to avoid recreating chat sessions frequently
    """
    try:
        # Get conversation history from database
        async with get_async_session_with_contextmanager() as session:
            query = text("SELECT * FROM demo_movies.conversations WHERE conversation_id = :conversation_id")
            result = await session.execute(query, {"conversation_id": conversation_id})
            conversation = result.first()

        SYSTEM_PROMPT = """You are a friendly and helpful shopping assistant. Your goal is to help users find products 
        and answer questions about products and shopping. Provide clear, concise, and relevant responses.
        Respond in the same language as the query.
        
        CONTEXT USAGE GUIDELINES:
        - You will see two types of product contexts: user_query_context and user_query_search_result
        - user_query_context: Products the user has explicitly asked about or mentioned earlier
        - user_query_search_result: Products found by semantic search based on the current query
        
        Follow these rules when using context:
        1. If the user is searching for or asking about product recommendations, refer primarily to products in user_query_search_result
        2. If the user is asking about specific products they mentioned before, refer to products in user_query_context
        3. If the user query does not have product search/recommendation intent, ignore user_query_search_result and refer to recent history and user_query_context instead
        4. ONLY recommend products that are DIRECTLY RELEVANT to the user's specific query
        5. IGNORE any products that don't match what the user is asking for, even if they're in the context
        6. If the user's query is not about shopping or products, ignore ALL product context
        7. Don't force product recommendations when they're not appropriate
        
        FORMATTING INSTRUCTIONS:
        - When mentioning product titles in your response, format them as hyperlinks using markdown, like this: [Product Title](/demo_site/:product_id)
        - For example, if you're recommending a product with ID 'abc123' and title 'Green T-shirt', format it as [Green T-shirt](/demo_site/abc123)
        - Use proper markdown formatting for the rest of your response (headings, bullet points, etc.)
        
        IMPORTANT: At the end of your response (after a blank line), list ALL referenced product IDs in this exact format:
        product_ids:id1,id2,id3
        where id1, id2, id3 are the IDs of products you referenced or recommended in your response.
        If you did not reference any specific products, do not include this line.
        
        Nicely format your responses using valid markdown:
        """
        if not conversation:
            # Create new chat without history
            return client.aio.chats.create(
                model="gemini-2.0-flash-001",
                history=[
                    Content(parts=[Part(text=SYSTEM_PROMPT)], role="model")
                ]
            )

        # Convert database history to chat format
        history = []
        for msg in conversation.messages:
            history.append(Content(
                parts=[Part(text=msg['content'])],
                role=msg['role']
            ))

        return client.aio.chats.create(
            model="gemini-2.0-flash-001",
            history=history
        )
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise


