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
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
import json
import time

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/shopping-assistant",
    tags=["shopping-assistant"]
)


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
        # Use product_ids list directly
        product_id_list = chat_request.product_ids if chat_request.product_ids else []
        
        # Build context
        context = ""
        
        # Fetch specific products if IDs provided
        if product_id_list:
            # Get context for specific products using utility method
            context_products = await ShoppingAssistantUtils.get_products_by_ids(session, product_id_list)
            
            # Add to context
            if context_products:
                product_context = ShoppingAssistantUtils.format_product_context(context_products)
                context += "user_query_context:\n" + product_context + "\n"
        
        # Always fetch products from database for all queries
        # Get vector embedding for the query
        query_embedding = await get_embedding(chat_request.query, TaskType.QUERY)

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


        
        # Add to context
        if semantic_product_results:
            # No need to call get_products_by_ids again as reviews are already included
            semantic_context = ShoppingAssistantUtils.format_product_context(semantic_product_results)
            context += "function_call_results:\n" + semantic_context
            
        # Fetch user's recent orders (using client IP as user_id)
        orders_context = None
        
        if request.state.client_ip is None:
            raise HTTPException(status_code=400, detail="Client IP not found in request state")
        
        user_id = request.state.client_ip
        logger.info(f"Fetching recent orders for user_id: {user_id}")
        recent_orders = await ShoppingAssistantUtils.get_latest_orders(session, user_id)

        recent_orders_json = [order.model_dump_json(exclude={"id"}) for order in recent_orders]

        if recent_orders:
            # Format orders for context - orders are already JSON serializable
            orders_context = json.dumps(recent_orders_json, indent=2)
            logger.info(f"Found {len(recent_orders)} recent orders for user")
        else:
            logger.info("No recent orders found for user")


        
        # Handle streaming response
        if chat_request.stream:

            # Get chat session with history
            chat = await get_chat_from_history(conversation_id= chat_request.conversation_id, stream=True)


            # Prepare prompt with context merged with user query
            prompt = ShoppingAssistantUtils.construct_prompt(
                chat_request.query,
                context,
                orders_context
            )
            
            async def response_stream_generator():
                # Get the complete response to extract product IDs
                full_response = ""
                marker_found_product = False
                marker_found_questions = False
                
                async for chunk in await chat.send_message_stream(prompt):
                    full_response += chunk.text
                    
                    # Check if this chunk contains the product_ids marker
                    if "product_ids:" in chunk.text and not marker_found_product:
                        marker_found_product = True
                        # Truncate the chunk at the marker
                        marker_pos = chunk.text.find("product_ids:")
                        if marker_pos > 0:  # Only yield if there's content before the marker
                            clean_chunk = chunk.text[:marker_pos].strip()
                            if clean_chunk:
                                content_response = StreamingResponse(
                                    type=StreamingResponseType.CONTENT,
                                    conversation_id=chat_request.conversation_id,
                                    content=clean_chunk
                                )
                                yield json.dumps(content_response.model_dump()) + "\n"
                    # Check if this chunk contains the follow_up_questions marker                        
                    elif "follow_up_questions:" in chunk.text and not marker_found_questions:
                        marker_found_questions = True
                        # Truncate the chunk at the marker
                        marker_pos = chunk.text.find("follow_up_questions:")
                        if marker_pos > 0:  # Only yield if there's content before the marker
                            clean_chunk = chunk.text[:marker_pos].strip()
                            if clean_chunk:
                                content_response = StreamingResponse(
                                    type=StreamingResponseType.CONTENT,
                                    conversation_id=chat_request.conversation_id,
                                    content=clean_chunk
                                )
                                yield json.dumps(content_response.model_dump()) + "\n"
                    elif not marker_found_product and not marker_found_questions:
                        # Only yield if we haven't hit any markers yet
                        content_response = StreamingResponse(
                            type=StreamingResponseType.CONTENT,
                            conversation_id=chat_request.conversation_id,
                            content=chunk.text
                        )
                        yield json.dumps(content_response.model_dump()) + "\n"
                
                # Extract follow-up questions from the response
                follow_up_questions = ShoppingAssistantUtils.extract_follow_up_questions(full_response)
                
                # Yield follow-up questions if any were suggested
                if follow_up_questions:
                    questions_response = StreamingResponse(
                        type=StreamingResponseType.QUESTIONS,
                        conversation_id=chat_request.conversation_id,
                        content=follow_up_questions
                    )
                    yield json.dumps(questions_response.model_dump()) + "\n"
                
                # Extract product IDs mentioned in the response
                referenced_product_ids = ShoppingAssistantUtils.extract_product_ids(full_response)

                # Get referenced products directly from database
                referenced_products = await ShoppingAssistantUtils.get_products_by_ids(session, referenced_product_ids)
                
                # Yield products if any were referenced
                if referenced_products:
                    product_response = StreamingResponse(
                        type=StreamingResponseType.PRODUCTS,
                        conversation_id=chat_request.conversation_id,
                        content=[p.model_dump() for p in referenced_products]
                    )
                    yield json.dumps(product_response.model_dump()) + "\n"
                
                # Save the complete conversation after streaming is done, including context and products
                clean_response = full_response
                
                # Remove follow_up_questions marker and everything after it until product_ids or end of string
                if "follow_up_questions:" in clean_response:
                    question_marker_pos = clean_response.find("follow_up_questions:")
                    product_marker_pos = clean_response.find("product_ids:")
                    
                    if product_marker_pos > question_marker_pos:
                        # If product_ids marker exists after follow_up_questions, remove content between them
                        clean_response = clean_response[:question_marker_pos].strip()
                    else:
                        # Otherwise remove everything after follow_up_questions
                        clean_response = clean_response[:question_marker_pos].strip()
                
                # Remove product_ids marker and everything after it
                if "product_ids:" in clean_response:
                    clean_response = clean_response[:clean_response.find("product_ids:")].strip()
                
                merged_response = clean_response
                if referenced_products:
                    product_info = "\n\nFunction call results for the user query:\n" + "\n".join([
                        f"- {p.model_dump_json()}" for p in referenced_products
                    ])
                    merged_response += product_info
                
                await ShoppingAssistantUtils.save_conversation(session, chat_request.conversation_id, chat_request.query, merged_response, context)
            
            return FastAPIStreamingResponse(response_stream_generator(), media_type="application/json")
        else:
            # Prepare JSON prompt with context merged with user query
            json_prompt = ShoppingAssistantUtils.construct_json_prompt(
                chat_request.query,
                context,
                orders_context
            )
            

            # Using the JSON model config to get a JSON response
            chat = await get_chat_from_history(conversation_id=chat_request.conversation_id,stream=False)
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
                follow_up_questions = response_data.get("follow_up_questions", [])
                referenced_product_ids = response_data.get("referenced_product_ids", [])
                
                # Get referenced products directly from database
                referenced_products = await ShoppingAssistantUtils.get_products_by_ids(session, referenced_product_ids)
                
                # Save conversation with the query response
                merged_response = query_response
                if referenced_products:
                    product_info = "\n\nReferenced Products:\n" + "\n".join([
                        f"- {p.model_dump_json()}" for p in referenced_products
                    ])
                    merged_response += product_info
                
                await ShoppingAssistantUtils.save_conversation(session, chat_request.conversation_id, chat_request.query, merged_response, context)
                
                return ChatResponse(
                    response=query_response,
                    conversation_id=chat_request.conversation_id,
                    products=referenced_products,
                    follow_up_questions=follow_up_questions
                )
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
