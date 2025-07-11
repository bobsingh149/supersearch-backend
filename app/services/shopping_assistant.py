import time
from async_lru import alru_cache
from google import genai
from google.genai.chats import AsyncChat
from google.genai.types import Content, Part, GenerateContentConfig, AutomaticFunctionCallingConfig
from typing import List, Optional, Dict
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
import logging
from sqlalchemy import text
import json

from app.database.session import get_async_session_with_contextmanager
from app.models.product import ProductSearchResult
from app.services.vertex import get_genai_client
from app.database.sql.sql import render_sql, SQLFilePath
from app.models.order import OrderOrm, Order
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

class ResponseSchema(BaseModel):
    query_response: str
    suggested_user_queries: List[str]
    referenced_product_ids: List[str]

class ShoppingAssistantUtils:
    @staticmethod
    def get_site_path_from_tenant(tenant: str) -> str:
        """
        Get the site path based on tenant name
        
        Args:
            tenant: The tenant name
            
        Returns:
            str: The site path for the tenant
        """
        tenant_to_site_mapping = {
            "demo_movies": "demo_site",
            "demo_ecommerce": "demo_ecommerce"
        }
        return tenant_to_site_mapping.get(tenant, "demo_site")
    
    @staticmethod
    def get_system_prompt(tenant: str) -> str:
        """
        Get the system prompt with dynamic site path based on tenant
        
        Args:
            tenant: The tenant name
            
        Returns:
            str: The system prompt with appropriate site path
        """
        site_path = ShoppingAssistantUtils.get_site_path_from_tenant(tenant)
        return f"""You are a helpful search assistant for finding products, content, and information. Help users find items and answer questions about products, orders, and purchases. Respond in the same language as the query.

    CONTEXT USAGE:
    - Use search results (function_call_results) for new item recommendations
    - Use chat history (user_query_context) for items previously discussed
    - For ambiguous references (it, this, that), assume the latest item from chat history
    - Only recommend items directly relevant to the user's query
    - Include product reviews and AI summaries when discussing product opinions

    ORDER STATUS DEFINITIONS:
    - pending/processing: Being prepared for shipping
    - shipped: On its way to delivery address
    - delivered: Successfully delivered
    - cancelled/refunded: Order not processed/refunded

    PRODUCT-SPECIFIC GUIDANCE:
    - For movies: Focus on questions users actually want to know, avoid boring details like runtime
    - For ecommerce products: Provide information that would be helpful to potential buyers based on the product context and what users typically want to know when making purchasing decisions

    FORMATTING:
    - Format item titles as hyperlinks: [Item Title](/{site_path}/:item_id)
    - Use markdown formatting (headers, bullets, etc.)
    - Generate 3 diverse suggested user queries that the user might want to ask you (the shopping assistant) next
    - Include all referenced product IDs at the end
    """
    
    @staticmethod
    def get_json_system_prompt(tenant: str) -> str:
        """
        Get the JSON system prompt with dynamic site path based on tenant
        
        Args:
            tenant: The tenant name
            
        Returns:
            str: The JSON system prompt with appropriate site path
        """
        site_path = ShoppingAssistantUtils.get_site_path_from_tenant(tenant)
        return f"""You are a helpful search assistant for finding products, content, and information. Help users find items and answer questions about products, orders, and purchases. Respond in the same language as the query.

    CONTEXT USAGE:
    - Use search results (function_call_results) for new item recommendations
    - Use chat history (user_query_context) for items previously discussed
    - For ambiguous references (it, this, that), assume the latest item from chat history
    - Only recommend items directly relevant to the user's query
    - Include product reviews and AI summaries when discussing product opinions

    ORDER STATUS DEFINITIONS:
    - pending/processing: Being prepared for shipping
    - shipped: On its way to delivery address
    - delivered: Successfully delivered
    - cancelled/refunded: Order not processed/refunded

    PRODUCT-SPECIFIC GUIDANCE:
    - For movies: Focus on questions users actually want to know, avoid boring details like runtime
    - For ecommerce products: Provide information that would be helpful to potential buyers based on the product context and what users typically want to know when making purchasing decisions

    FORMATTING:
    - Format item titles as hyperlinks: [Item Title](/{site_path}/:item_id)
    - Use markdown formatting (headers, bullets, etc.)
    - Generate 3 diverse suggested user queries that the user might want to ask you (the shopping assistant) next
    - Include all referenced product IDs at the end

    RESPONSE FORMAT:
    Respond with JSON: {{"query_response": "markdown response with [Item Title](/{site_path}/:item_id) links", "suggested_user_queries": ["question1", "question2", "question3"], "referenced_product_ids": ["id1", "id2"]}}
    """
    
    model = "gemini-2.0-flash-001"
    
    @classmethod
    def get_model_config(cls, tenant: str):
        return GenerateContentConfig(
            system_instruction=cls.get_system_prompt(tenant),
            max_output_tokens=1000,
            temperature=0.3,
            automatic_function_calling=AutomaticFunctionCallingConfig(
                disable=True,
                maximum_remote_calls=0
            ),
        )
    
    @classmethod
    def get_json_model_config(cls, tenant: str):
        return GenerateContentConfig(
            system_instruction=cls.get_json_system_prompt(tenant),
            max_output_tokens=1000,
            temperature=0.3,
            automatic_function_calling=AutomaticFunctionCallingConfig(
                disable=True,
                maximum_remote_calls=0
            ),
            response_mime_type='application/json',
            response_schema=ResponseSchema
        )
    


    @staticmethod
    def extract_product_ids(text: str) -> List[str]:
        """
        Extract product IDs from the new format with PRODUCT_IDS_START and PRODUCT_IDS_END markers
        """
        start_marker = "PRODUCT_IDS_START"
        end_marker = "PRODUCT_IDS_END"
        
        start_pos = text.find(start_marker)
        if start_pos == -1:
            return []
            
        start_pos += len(start_marker)
        end_pos = text.find(end_marker, start_pos)
        
        if end_pos == -1:
            return []
            
        ids_str = text[start_pos:end_pos].strip()
        if not ids_str:
            return []
            
        # Split by comma and clean up each ID
        return [id.strip() for id in ids_str.split(',') if id.strip()]

    @staticmethod
    def extract_follow_up_questions(text: str) -> List[str]:
        """
        Extract follow-up questions from the new format with SUGGESTED_USER_QUERIES_START and SUGGESTED_USER_QUERIES_END markers
        
        Args:
            text: The text to extract follow-up questions from
        
        Returns:
            List[str]: List of follow-up questions
        """
        start_marker = "SUGGESTED_USER_QUERIES_START"
        end_marker = "SUGGESTED_USER_QUERIES_END"
        
        start_pos = text.find(start_marker)
        if start_pos == -1:
            return []
            
        start_pos += len(start_marker)
        end_pos = text.find(end_marker, start_pos)
        
        if end_pos == -1:
            return []
            
        questions_str = text[start_pos:end_pos].strip()
        if not questions_str:
            return []
            
        # Split by newlines and clean up each question
        questions = [q.strip() for q in questions_str.split('\n') if q.strip()]
        return questions

    @staticmethod
    def format_product_context(products: List['ProductSearchResult'], tenant: str) -> str:
        """
        Format item information into a context string for the LLM
        
        Args:
            products: List of ProductSearchResult objects
            tenant: The tenant name to determine the site path
        
        Returns:
            str: Formatted context string containing item information
        """
        if not products:
            return ""

        site_path = ShoppingAssistantUtils.get_site_path_from_tenant(tenant)
        context = f"Here are some items that might be relevant. ONLY reference items that are directly relevant to the user's query and ignore the rest. When referencing them, format their titles as hyperlinks like [Item Title](/{site_path}/:product_id):\n\n"

        for i, product in enumerate(products, 1):
            context += f"{i}. Item ID: {product.id}\n"
            context += f"   Title: {product.title or 'Untitled Item'}\n"
            
            price = "Price not available"
            if product.custom_data and "price" in product.custom_data:
                price = product.custom_data["price"]
                
            context += f"   Price: {price}\n"
            context += f"   Details: {product.custom_data or ''}\n"
            
            # Add AI summary if available
            if product.ai_summary:
                context += f"   AI-Generated Review Summary: {json.dumps(product.ai_summary, indent=2)}\n"
            
            # Add reviews if available
            if product.reviews and len(product.reviews) > 0:
                context += "   Customer Reviews:\n"
                # Limit to 3 reviews to avoid making context too large
                for j, review in enumerate(product.reviews[:3], 1):
                    context += f"   {j}. {review.content[:300]}...\n" if len(review.content) > 300 else f"   {j}. {review.content}\n"
                if len(product.reviews) > 3:
                    context += f"   ... and {len(product.reviews) - 3} more reviews\n"
            
            context += "\n"

        return context


    @staticmethod
    async def save_conversation(
        db: AsyncSession,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        context: Optional[str] = None,
        tenant: str = None
    ) -> None:
        """
        Save conversation messages to database
        Args:
            db: Database session
            conversation_id: Unique conversation identifier
            user_message: User's message
            assistant_response: Assistant's response
            context: Optional context provided to the assistant
            tenant: Tenant/schema name
        """
        try:
            # Check if conversation exists
            query = text(f"SELECT * FROM {tenant}.conversations WHERE conversation_id = :conversation_id")
            result = await db.execute(query, {"conversation_id": conversation_id})
            conversation = result.first()
            # Merge context with user message if provided
            user_message_with_context = user_message
            if context:
                user_message_with_context = f"{user_message}\n\nContext:\n{context}"
            new_messages = [
                {"role": "user", "content": user_message_with_context},
                {"role": "model", "content": assistant_response}
            ]
            if conversation:
                # Update existing conversation
                update_query = text(f"""
                    UPDATE {tenant}.conversations 
                    SET messages = messages || CAST(:new_messages AS jsonb)
                    WHERE conversation_id = :conversation_id
                """)
                await db.execute(update_query, {
                    "conversation_id": conversation_id,
                    "new_messages": json.dumps(new_messages)
                })
            else:
                # Insert new conversation
                insert_query = text(f"""
                    INSERT INTO {tenant}.conversations (conversation_id, messages) 
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
        tenant: str,
        context: Optional[str] = None,
        orders_context: Optional[str] = None
    ) -> str:
        """
        Constructs a prompt for the search assistant by combining the user query and context.
        
        Args:
            query: The user's question or request
            tenant: The tenant name to determine the site path
            context: Optional context about items or other relevant information
            orders_context: Optional context about user's recent orders
        
        Returns:
            str: The constructed prompt for the LLM
        """
        prompt = "User Query: " + query + "\n\n"
        
        if context:
            prompt = "Context about items:\n" + context + "\n\n" + prompt
            prompt += """IMPORTANT INSTRUCTIONS FOR CONTEXT USE:
1. If the user is searching for or asking about item recommendations, refer to items in function_call_results (these are semantic search results obtained from the user's current query - use them when they represent fresh search results for the user's query, but ignore them if the user query is referring to past chat history)
2. If the user is asking about specific items they mentioned before, refer to items from recent chat history
3. If the user query does not have search/recommendation intent, ignore function_call_results and refer to recent history instead
4. Only reference items that are DIRECTLY RELEVANT to the user's query
5. Ignore any items that don't match what the user is looking for
6. If the user is asking about reviews or opinions on products, use the product review information if available
7. If there's an AI-generated summary of reviews, use that to provide a comprehensive overview instead of individual reviews
8. If the query is ambiguous about which product it's referring to, check if it refers to items from recent chat history first, then consider items from function_call_results that best match the query
9. NEVER ask the user to clarify which item they are talking about - always make an intelligent assumption
10. If a user refers to a product using pronouns (it, this, that) or generic terms (the product, the item), assume they mean the latest item discussed in the chat history. This is especially important when the query contains words like "this" or "it" without any search or recommendation intent - always assume they are referring to the last item mentioned in the conversation history.
11. When the user's intent is unclear, prioritize chat history over function_call_results for product references

"""
        
        if orders_context:
            prompt += "\nUser's Recent Orders:\n" + orders_context + "\n\n"
            prompt += """ORDERS CONTEXT INSTRUCTIONS:
1. Use this information when the user asks about their orders, order status, or previously purchased items
2. Explain the order status to the user:
   - "pending": The order is being processed and prepared for shipping
   - "processing": The order is being prepared for shipping
   - "shipped": The order has been shipped and is on its way 
   - "delivered": The order has been delivered to the shipping address
   - "cancelled": The order was cancelled and will not be processed
   - "refunded": The order was refunded
3. When the user asks about tracking, provide the tracking number from the order
4. Include information about the items in the order when relevant
5. Only use this order information when directly relevant to the user's query
"""
        
        site_path = ShoppingAssistantUtils.get_site_path_from_tenant(tenant)
        prompt += f"""RESPONSE FORMAT FOR STREAMING:
When mentioning item titles in your response, format them as hyperlinks using markdown, like this: [Item Title](/{site_path}/:product_id).
For example, if you're recommending an item with ID 'abc123' and title 'Documentary Film', format it as [Documentary Film](/{site_path}/abc123).

CRITICAL: Your response will be processed in streaming mode. You MUST use the exact format below:

1. Provide your main response content first
2. When your main content is complete, add the special marker: §
3. After the § marker, add suggested user queries in this EXACT format:
SUGGESTED_USER_QUERIES_START
question1
question2  
question3
SUGGESTED_USER_QUERIES_END

4. Then list referenced product IDs in this EXACT format:
PRODUCT_IDS_START
id1,id2,id3
PRODUCT_IDS_END

MANDATORY: You MUST include the markers even if you have no questions or product IDs:

For no suggested user queries:
SUGGESTED_USER_QUERIES_START
SUGGESTED_USER_QUERIES_END

For no product IDs:
PRODUCT_IDS_START
PRODUCT_IDS_END

IMPORTANT: 
- At least one of your suggested user queries should be about reviews or opinions of the referenced item if applicable
- These are questions from the user's perspective directed to the shopping assistant, not questions the assistant would ask the user
- Focus on objective, informational questions rather than personal subjective ones (e.g., "What do people think of it?" rather than "Have you seen it?" or "What did you think of it?")

Example complete response format:
Here are some great items for you...
§
SUGGESTED_USER_QUERIES_START
question1
question2
question3
SUGGESTED_USER_QUERIES_END

PRODUCT_IDS_START
item123,item456,item789
PRODUCT_IDS_END

DO NOT deviate from this format. The § marker is critical for proper streaming.
"""
        
        return prompt
    
    @staticmethod
    def construct_json_prompt(
        query: str,
        tenant: str,
        context: Optional[str] = None,
        orders_context: Optional[str] = None
    ) -> str:
        """
        Constructs a prompt for the search assistant to return JSON response by combining the user query and context.
        
        Args:
            query: The user's question or request
            tenant: The tenant name to determine the site path
            context: Optional context about items or other relevant information
            orders_context: Optional context about user's recent orders
        
        Returns:
            str: The constructed prompt for the LLM to respond in JSON format
        """
        prompt = "User Query: " + query + "\n\n"
        
        if context:
            prompt = "Context about items:\n" + context + "\n\n" + prompt
            prompt += """IMPORTANT INSTRUCTIONS FOR CONTEXT USE:
1. If the user is searching for or asking about item recommendations, refer to items in function_call_results (these are semantic search results obtained from the user's current query - use them when they represent fresh search results for the user's query, but ignore them if the user query is referring to past chat history)
2. If the user is asking about specific items they mentioned before, refer to items from recent chat history
3. If the user query does not have search/recommendation intent, ignore function_call_results and refer to recent history instead
4. Only reference items that are DIRECTLY RELEVANT to the user's query
5. Ignore any items that don't match what the user is looking for
6. If the user is asking about reviews or opinions on products, use the product review information if available
7. If there's an AI-generated summary of reviews, use that to provide a comprehensive overview instead of individual reviews
8. If the query is ambiguous about which product it's referring to, check if it refers to items from recent chat history first, then consider items from function_call_results that best match the query
9. NEVER ask the user to clarify which item they are talking about - always make an intelligent assumption
10. If a user refers to a product using pronouns (it, this, that) or generic terms (the product, the item), assume they mean the latest item discussed in the chat history. This is especially important when the query contains words like "this" or "it" without any search or recommendation intent - always assume they are referring to the last item mentioned in the conversation history.
11. When the user's intent is unclear, prioritize chat history over function_call_results for product references

"""
        
        if orders_context:
            prompt += "\nUser's Recent Orders:\n" + orders_context + "\n\n"
            prompt += """ORDERS CONTEXT INSTRUCTIONS:
1. Use this information when the user asks about their orders, order status, or previously purchased items
2. Explain the order status to the user:
   - "pending": The order is being processed and prepared for shipping
   - "processing": The order is being prepared for shipping
   - "shipped": The order has been shipped and is on its way 
   - "delivered": The order has been delivered to the shipping address
   - "cancelled": The order was cancelled and will not be processed
   - "refunded": The order was refunded
3. When the user asks about tracking, provide the tracking number from the order
4. Include information about the items in the order when relevant
5. Only use this order information when directly relevant to the user's query
"""
        
        site_path = ShoppingAssistantUtils.get_site_path_from_tenant(tenant)
        prompt += f"""REMEMBER: You MUST respond with a valid JSON object having these fields:
1. "query_response": Your main response to the user (with markdown formatting, hyperlinks like [Item Title](/{site_path}/:product_id))
2. "suggested_user_queries": Array of exactly 3 suggested user queries
3. "referenced_product_ids": Array of product IDs you referenced (or empty array if none)

IMPORTANT: 
- At least one of your suggested user queries should be about reviews or opinions of the referenced item if applicable
- These are questions from the user's perspective directed to the shopping assistant, not questions the assistant would ask the user
- Focus on objective, informational questions rather than personal subjective ones (e.g., "What do people think of it?" rather than "Have you seen it?" or "What did you think of it?")

Example format:
{
  "query_response": "Here are some great items for you...",
  "suggested_user_queries": ["question1", "question2", "question3"],
  "referenced_product_ids": ["item123", "item456", "item789"]
}
"""
        
        return prompt

    @staticmethod
    async def get_products_by_ids(session: AsyncSession, product_ids: List[str], tenant: str) -> List[ProductSearchResult]:
        """
        Fetch products by their IDs from the database
        
        Args:
            session: Database session
            product_ids: List of product IDs to fetch
            tenant: Tenant identifier
            
        Returns:
            List[ProductSearchResult]: List of product search results
        """
        if not product_ids:
            return []
            
        try:
            start_time = time.time()
            query = text(render_sql(SQLFilePath.PRODUCT_GET_BY_IDS, product_ids=product_ids, tenant=tenant))
            result = await session.execute(query, {"product_ids": product_ids})
            products = [row._mapping for row in result]
            
            product_results = []
            for row in products:
                try:
                    product_data = dict(row)
                    product_results.append(ProductSearchResult.model_validate(product_data))
                except Exception as product_error:
                    logger.error(f"Error processing product data: {str(product_error)}")
                    # Continue with other products even if one fails
                    continue
            
            end_time = time.time()
            logger.info(f"Time taken to fetch {len(product_results)} products: {end_time - start_time:.2f} seconds")
            return product_results
        except Exception as e:
            logger.error(f"Error fetching products by IDs: {str(e)}")
            return []

    @staticmethod
    async def get_latest_orders(session: AsyncSession, user_id: str, limit: int = 3) -> List[Order]:
        """
        Fetch the latest orders for a user and update their status based on expected_shipping_date
        
        Args:
            session: Database session
            user_id: User ID (client IP) to fetch orders for
            limit: Maximum number of orders to fetch (default: 3)
            
        Returns:
            List[Dict]: List of orders with updated status
        """

        
        try:
            # Build query to get latest orders
            query = select(OrderOrm).where(OrderOrm.user_id == user_id)
            query = query.order_by(OrderOrm.created_at.desc()).limit(limit)
            
            # Execute query
            result = await session.execute(query)
            orders = result.scalars().all()
            
            # Update status based on expected_shipping_date
            current_date = datetime.now(timezone.utc)
            updated_orders = []
            
            for order in orders:
                # Create a dictionary representation of the order
                order_dict = {c.name: getattr(order, c.name) for c in order.__table__.columns}
                
                # Update status if not in a final state
                if order_dict["status"] not in ["delivered", "cancelled", "refunded"]:
                    if order_dict["expected_shipping_date"]:
                        # Convert to UTC timezone if not already
                        expected_date = order_dict["expected_shipping_date"]
                        
                        # If current date is 1 day after expected shipping date, mark as delivered
                        if current_date >= (expected_date + timedelta(minutes=1)):
                            order_dict["status"] = "delivered"
                        # If current date is on or after expected shipping date, mark as shipped
                        elif current_date >= expected_date:
                            order_dict["status"] = "shipped"
                
                # Convert to Pydantic model
                order_model = Order.model_validate(order_dict)
                updated_orders.append(order_model)
            
            return updated_orders
            
        except Exception as e:
            logger.error(f"Error fetching latest orders: {str(e)}")
            return []

@alru_cache(maxsize=300)
async def get_chat_from_history(conversation_id: str,session : AsyncSession,stream: bool = True, tenant: str = None) -> AsyncChat:
    """
    Get or create a chat session with history from the database
    Uses caching to avoid recreating chat sessions frequently
    Args:
        conversation_id: Unique conversation identifier
        stream: Whether to stream the response. If False, use JSON model config
        tenant: Tenant/schema name
    Returns:
        AsyncChat: Chat session with history
    """
    client: genai.Client = get_genai_client()
    try:
        query = text(f"SELECT * FROM {tenant}.conversations WHERE conversation_id = :conversation_id")
        result = await session.execute(query, {"conversation_id": conversation_id})
        conversation = result.first()
        # Select the appropriate model config based on stream parameter
        model_config = ShoppingAssistantUtils.get_model_config(tenant) if stream else ShoppingAssistantUtils.get_json_model_config(tenant)
        if not conversation:
            # Create new chat without history
            return client.aio.chats.create(
                model=ShoppingAssistantUtils.model,
                config=model_config
            )
        # Convert database history to chat format
        history = []
        for msg in conversation.messages:
            history.append(Content(
                parts=[Part.from_text(text=msg['content'])],
                role=msg['role']
            ))
        return client.aio.chats.create(
            model=ShoppingAssistantUtils.model,
            history=history,
            config=model_config
        )
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise
