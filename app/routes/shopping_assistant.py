from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_async_session, get_tenant_name
from app.database.sql.sql import render_sql, SQLFilePath
from app.models.product import ProductSearchResult
from app.models.shopping_assistant import (
    ConversationDB, ChatResponse, ConversationResponse, Message, 
    StreamingResponse, StreamingResponseType, ChatRequest,
    ConversationSummary, PaginatedConversationSummary
)
from app.models.review import Review, ReviewOrm
from sqlalchemy import text, select, func
from sqlalchemy.sql import desc
import logging
from app.services.shopping_assistant import ShoppingAssistantUtils, get_chat_from_history
from app.services.vertex import get_genai_client, get_embedding, TaskType
from app.services.redis_service import get_redis_service
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
import json
import time
import hashlib

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/shopping-assistant",
    tags=["shopping-assistant"]
)


def generate_cache_key(chat_request: ChatRequest, tenant: str, user_id: str) -> str:
    """
    Generate a cache key for shopping assistant queries.
    
    Args:
        chat_request: The chat request object
        tenant: The tenant name
        user_id: The user ID (client IP)
        
    Returns:
        Cache key string
    """
    # Create a hash of the request parameters
    cache_data = {
        "query": chat_request.query,
        "product_ids": sorted(chat_request.product_ids) if chat_request.product_ids else [],
        "tenant": tenant
    }
    
    # Convert to sorted string and hash
    sorted_data = sorted(cache_data.items())
    data_string = "&".join([f"{k}={v}" for k, v in sorted_data])
    cache_hash = hashlib.md5(data_string.encode()).hexdigest()
    
    return f"shopping_assistant:{cache_hash}"


def exclude_description_from_custom_data(product_data):
    """
    Helper function to exclude description from custom_data if it exists.
    """
    if isinstance(product_data, dict) and 'custom_data' in product_data:
        custom_data = product_data['custom_data']
        if isinstance(custom_data, dict) and 'description' in custom_data:
            # Remove the description field from custom_data
            del custom_data['description']
    return product_data


@router.post("/chat")
async def chat_with_assistant(
    request: Request,
    chat_request: ChatRequest,
    session: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name)
):
    """
    Chat with the shopping assistant.
    
    This endpoint provides conversational shopping assistance, including:
    - Product search and recommendations
    - Information about products, reviews, and features
    - Details about the user's recent orders and their status
    - Tracking information for shipped orders
    
    The assistant uses the client IP to identify the user and fetch their recent orders.
    """
    try:
        # Get Redis service
        redis_service = get_redis_service()
        
        # Get user ID from client IP
        if request.state.client_ip is None:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        user_id = request.state.client_ip
        
        # Generate cache key
        cache_key = generate_cache_key(chat_request, tenant, user_id)
        
        # Check cache first (only for non-streaming requests)
        if not chat_request.stream:
            cached_response = redis_service.get(cache_key)
            if cached_response is not None:
                logger.info(f"Cache hit for shopping assistant query: {cache_key}")
                # Save conversation to database even for cached responses
                await ShoppingAssistantUtils.save_conversation(
                    session, 
                    chat_request.conversation_id, 
                    chat_request.query, 
                    cached_response["response"], 
                    cached_response.get("context", ""), 
                    tenant=tenant
                )
                return ChatResponse(**cached_response)
        
        # Use product_ids list directly
        product_id_list = chat_request.product_ids if chat_request.product_ids else []
        
        # Start with the original query
        enhanced_query = chat_request.query
        
        # Fetch specific products if IDs provided and append to query
        if product_id_list:
            # Get context for specific products using utility method
            context_products = await ShoppingAssistantUtils.get_products_by_ids(session, product_id_list, tenant)
            
            # Append product context to the query
            if context_products:
                product_context = ShoppingAssistantUtils.format_product_context(context_products, tenant)
                enhanced_query += f"\n\nProduct context for items mentioned:\n{product_context}"
        
        # Get vector embedding for the enhanced query (with product context if any)
        query_embedding = await get_embedding(enhanced_query, TaskType.QUERY)

        sql_query = render_sql(SQLFilePath.PRODUCT_SEMANTIC_SEARCH_WITH_REVIEWS,
                            query_embedding=query_embedding,
                            match_count=3,
                            offset=0,
                            tenant=tenant)
        
        start_time = time.time()
        result = await session.execute(text(sql_query))
        end_time = time.time()
        logger.info(f"Time taken to execute semantic search query: {end_time - start_time:.2f} seconds")
        semantic_db_products = [row._mapping for row in result]

        # Convert to ProductSearchResult
        semantic_product_results = [
            ProductSearchResult.model_validate(dict(row))
            for row in semantic_db_products
        ]

        # Build context for function call results
        context = ""
        if semantic_product_results:
            # No need to call get_products_by_ids again as reviews are already included
            semantic_context = ShoppingAssistantUtils.format_product_context(semantic_product_results, tenant)
            context += "function_call_results:\n" + semantic_context
            
        # Fetch user's recent orders (using client IP as user_id)
        orders_context = None
        
        recent_orders = await ShoppingAssistantUtils.get_latest_orders(session, user_id)

        recent_orders_json = [order.model_dump_json(exclude={"id"}) for order in recent_orders]

        if recent_orders:
            # Format orders for context - orders are already JSON serializable
            orders_context = json.dumps(recent_orders_json, indent=2)
            # logger.info(f"Found {len(recent_orders)} recent orders for user")
        else:
            logger.info("No recent orders found for user")

        # Handle streaming response
        if chat_request.stream:

            # Get chat session with history
            chat = await get_chat_from_history(conversation_id= chat_request.conversation_id, session=session, stream=True, tenant=tenant)

            # Prepare prompt with context merged with user query
            prompt = ShoppingAssistantUtils.construct_prompt(
                enhanced_query,  # Use enhanced query with product context
                tenant,
                context,
                orders_context
            )
            
            async def response_stream_generator():
                # Track the complete response and parsing state
                full_response = ""
                content_sent_length = 0  # Track how much content we've already sent
                parsing_state = "content"  # content, collecting
                
                async for chunk in await chat.send_message_stream(prompt):
                    full_response += chunk.text

                    # Check for the end-of-content marker
                    if "§" in chunk.text and parsing_state == "content":
                        # We've hit the end-of-content marker
                        parsing_state = "collecting"
                        
                        # Extract the main content (everything before §)
                        marker_pos = full_response.find("§")
                        main_content = full_response[:marker_pos]
                        
                        # Send any remaining content that wasn't sent yet
                        if len(main_content) > content_sent_length:
                            remaining_content = main_content[content_sent_length:]
                            if remaining_content:
                                content_response = StreamingResponse(
                                    type=StreamingResponseType.CONTENT,
                                    conversation_id=chat_request.conversation_id,
                                    content=remaining_content
                                )
                                # logger.info(f"final content_response: {content_response}")
                                yield json.dumps(content_response.model_dump()) + "\n"
                        continue
                    
                    elif parsing_state == "content":
                        # We're still in the main content, stream it
                        content_response = StreamingResponse(
                            type=StreamingResponseType.CONTENT,
                            conversation_id=chat_request.conversation_id,
                            content=chunk.text
                        )
                        # logger.info(f"main content_response: {content_response}")
                        yield json.dumps(content_response.model_dump()) + "\n"
                        
                        # Update the length of content we've sent
                        content_sent_length += len(chunk.text)
                    
                    # If we're in collecting state, we just accumulate in full_response
                    # and don't stream the chunk

                # print(f"full response : {full_response}")
                # Extract and send follow-up questions using new format only
                follow_up_questions = ShoppingAssistantUtils.extract_follow_up_questions(full_response)
                
                if follow_up_questions:
                    questions_response = StreamingResponse(
                        type=StreamingResponseType.QUESTIONS,
                        conversation_id=chat_request.conversation_id,
                        content=follow_up_questions
                    )
                    yield json.dumps(questions_response.model_dump()) + "\n"
                
                # Extract product IDs using new format only
                referenced_product_ids = ShoppingAssistantUtils.extract_product_ids(full_response)
                
                referenced_products = await ShoppingAssistantUtils.get_products_by_ids(session, referenced_product_ids, tenant)
                
                # Send products if any were referenced
                if referenced_products:
                    # Process products to exclude description from custom_data
                    processed_products = []
                    for p in referenced_products:
                        product_data = p.model_dump(include={"id", "title", "image_url", "custom_data"})
                        processed_products.append(exclude_description_from_custom_data(product_data))
                    
                    product_response = StreamingResponse(
                        type=StreamingResponseType.PRODUCTS,
                        conversation_id=chat_request.conversation_id,
                        content=processed_products
                    )
                    yield json.dumps(product_response.model_dump()) + "\n"
                
                # Clean the response for saving to database - remove marker and format sections
                clean_response = full_response
                
                # Remove everything from § marker onwards
                marker_pos = clean_response.find("§")
                if marker_pos != -1:
                    clean_response = clean_response[:marker_pos].strip()
                
                # Save conversation with clean response
                merged_response = clean_response
                if referenced_products:
                    product_info = "\n\nFunction call results for the user query:\n" + "\n".join([
                        f"- {p.model_dump_json()}" for p in referenced_products
                    ])
                    merged_response += product_info
                
                await ShoppingAssistantUtils.save_conversation(session, chat_request.conversation_id, chat_request.query, merged_response, context, tenant=tenant)
                
                # Send completion marker to signal end of stream
                completion_response = StreamingResponse(
                    type=StreamingResponseType.COMPLETE,
                    conversation_id=chat_request.conversation_id,
                    content="stream_complete"
                )
                yield json.dumps(completion_response.model_dump()) + "\n"
            
            return FastAPIStreamingResponse(response_stream_generator(), media_type="text/event-stream")
        else:
            # Prepare JSON prompt with context merged with user query
            json_prompt = ShoppingAssistantUtils.construct_json_prompt(
                enhanced_query,  # Use enhanced query with product context
                tenant,
                context,
                orders_context
            )
            

            # Using the JSON model config to get a JSON response
            chat = await get_chat_from_history(conversation_id=chat_request.conversation_id,session=session, stream=False, tenant=tenant)
            # Override the config to use JSON format
                        # Get regular response in JSON format
            start_time = time.time()
            response = await chat.send_message(json_prompt)
            end_time = time.time()
            execution_time = end_time - start_time
            logger.info(f"chat.send_message execution time: {execution_time:.2f} seconds")
            
            try:
                # Parse the JSON response
                response_data = json.loads(response.text)
                

                # Extract data from JSON
                query_response = response_data.get("query_response", "")
                follow_up_questions = response_data.get("suggested_user_queries", [])
                referenced_product_ids = response_data.get("referenced_product_ids", [])
                
                # Get referenced products directly from database
                referenced_products = await ShoppingAssistantUtils.get_products_by_ids(session, referenced_product_ids, tenant)
                
                # Save conversation with the query response
                merged_response = query_response
                if referenced_products:
                    product_info = "\n\nReferenced Products:\n" + "\n".join([
                        f"- {p.model_dump_json()}" for p in referenced_products
                    ])
                    merged_response += product_info
                
                await ShoppingAssistantUtils.save_conversation(session, chat_request.conversation_id, chat_request.query, merged_response, context, tenant=tenant)
                
                # Process products to exclude description from custom_data
                processed_products = []
                for p in referenced_products:
                    product_data = p.model_dump(include={"id", "title", "image_url", "custom_data", "searchable_content"})
                    processed_products.append(exclude_description_from_custom_data(product_data))
                
                # Create response object
                chat_response = ChatResponse(
                    response=query_response,
                    conversation_id=chat_request.conversation_id,
                    products=processed_products,
                    suggested_user_queries=follow_up_questions
                )
                
                # Cache the response (only for non-streaming requests)
                if not chat_request.stream:
                    cache_data = {
                        "response": query_response,
                        "conversation_id": chat_request.conversation_id,
                        "products": processed_products,
                        "suggested_user_queries": follow_up_questions,
                        "context": context
                    }
                    redis_service.set(cache_key, cache_data, ttl=21600)  # 6 hours TTL
                    logger.info(f"Cached shopping assistant response for key: {cache_key}")
                
                return chat_response
            except json.JSONDecodeError:
                # Fallback to old method if JSON parsing fails
                logger.error("Failed to parse JSON response, falling back to traditional parsing")
                raise HTTPException(status_code=500, detail="Failed to parse JSON response")

        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/conversation/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_history(
    conversation_id: str,
    session: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name)
):
    """Get the conversation history"""
    try:
        conversation = await session.get(ConversationDB, conversation_id)

        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Generate name from the first 3 words of the last message
        name = ""
        if conversation.messages and len(conversation.messages) > 0:
            last_message = conversation.messages[-1]
            if last_message.get("role") == "user" and last_message.get("content"):
                name = " ".join(last_message.get("content").split()[:3])
                if len(name) > 50:
                    name = name[:50]

        return ConversationResponse(
            conversation_id=conversation_id,
            messages=[Message.model_validate(msg) for msg in conversation.messages],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
            name=name
        )

    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations", response_model=PaginatedConversationSummary)
async def get_conversation_summaries(
    page: int | None = 1,
    page_size: int | None = 10,
    session: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name)
):
    """Get a paginated list of conversation summaries"""
    try:
        # Calculate offset for pagination
        offset = (page - 1) * page_size
        
        # Get total count
        count_query = select(func.count()).select_from(ConversationDB)
        result = await session.execute(count_query)
        total = result.scalar_one()
        
        # Get conversations ordered by updated_at desc with pagination
        query = select(ConversationDB).order_by(desc(ConversationDB.updated_at)).offset(offset).limit(page_size)
        result = await session.execute(query)
        conversations = result.scalars().all()
        
        # Build conversation summaries
        items = []
        for conv in conversations:
            # Generate name from the first 3 words of the last message from user
            name = ""
            if conv.messages and len(conv.messages) > 0:
                # Find the last user message
                user_messages = [msg for msg in conv.messages if msg.get("role") == "user"]
                if user_messages:
                    last_user_msg = user_messages[-1]
                    if last_user_msg.get("content"):
                        name = " ".join(last_user_msg.get("content").split()[:3])
                        if len(name) > 50:
                            name = name[:50]
            
            items.append(ConversationSummary(
                conversation_id=conv.conversation_id,
                name=name,
                updated_at=conv.updated_at
            ))
        
        return PaginatedConversationSummary(
            items=items,
            total=total,
            page=page,
            page_size=page_size
        )
    
    except Exception as e:
        logger.error(f"Error getting conversation summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
