from google import genai
from google.genai.types import Content, Part
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
import logging
from sqlalchemy import text
import json

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
            response = client.models.generate_content(
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
    def format_product_context(products: List[Dict[str, Any]]) -> str:
        """
        Format product information into a context string for the LLM
        
        Args:
            products: List of product dictionaries
        
        Returns:
            str: Formatted context string containing product information
        """
        if not products:
            return ""

        context = "Available Products:\n"

        for i, product in enumerate(products, 1):
            title = product.get('title', 'Untitled Product')
            content = product.get('searchable_content', '')
            price = product.get('custom_data', {}).get('price', 'Price not available')
            
            context += f"{i}. {title}\n"
            context += f"   Price: {price}\n"
            context += f"   Details: {content}\n\n"

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
            query = text("SELECT * FROM conversations WHERE conversation_id = :conversation_id")
            result = await db.execute(query, {"conversation_id": conversation_id})
            conversation = result.first()
            
            new_messages = [
                {"role": "user", "content": user_message}
            ]
            
            if context:
                new_messages.append({
                    "role": "system",
                    "content": f"Context provided:\n{context}"
                })
                
            new_messages.append({
                "role": "model",
                "content": assistant_response
            })
            
            if conversation:
                # Update existing conversation
                update_query = text("""
                    UPDATE conversations 
                    SET messages = messages || :new_messages::jsonb 
                    WHERE conversation_id = :conversation_id
                """)
                await db.execute(update_query, {
                    "conversation_id": conversation_id,
                    "new_messages": json.dumps(new_messages)
                })
            else:
                # Insert new conversation
                insert_query = text("""
                    INSERT INTO conversations (conversation_id, messages) 
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
        if context:
            return f"""
Context about relevant products:
{context}

User Query: {query}

Please provide a helpful response based on the above context and query."""
        
        return f"""User Query: {query}

Please provide a helpful response to the user's query."""
