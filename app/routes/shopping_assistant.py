from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from app.database.sql.sql import render_sql, SQLFilePath
from app.models.product import ProductSearchResult
from app.models.shopping_assistant import (
    ConversationDB, ChatResponse, ConversationResponse, Message, 
    StreamingResponse, StreamingResponseType, ChatRequest,
    ConversationSummary, PaginatedConversationSummary
)
from sqlalchemy import text, select, func
from sqlalchemy.sql import desc
import logging
from app.services.shopping_assistant import ShoppingAssistantUtils, get_chat_from_history
from app.services.vertex import get_genai_client, get_embedding, TaskType
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
import json


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/shopping-assistant",
    tags=["shopping-assistant"]
)


@router.post("/chat")
async def chat_with_assistant(
    request: ChatRequest,
    session: AsyncSession = Depends(get_async_session)
):
    """Chat with the shopping assistant"""
    try:
        # Use product_ids list directly
        product_id_list = request.product_ids if request.product_ids else []
        
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
        query_embedding = await get_embedding(request.query, TaskType.QUERY)

        sql_query = render_sql(SQLFilePath.PRODUCT_SEMANTIC_SEARCH,
                            query_embedding=query_embedding,
                            match_count=3,
                            offset=0)
        result = await session.execute(text(sql_query))
        semantic_db_products = [row._mapping for row in result]

        # Convert to ProductSearchResult
        semantic_product_results = [
            ProductSearchResult.model_validate(dict(row))
            for row in semantic_db_products
        ]
        
        # Add to context
        if semantic_product_results:
            semantic_context = ShoppingAssistantUtils.format_product_context(semantic_product_results)
            context += "function_call_results:\n" + semantic_context
        
        # Get chat session with history
        chat = await get_chat_from_history(request.conversation_id)
        
        # Prepare prompt with context merged with user query
        prompt = ShoppingAssistantUtils.construct_prompt(
            request.query,
            context,
        )
        
        # Handle streaming response
        if request.stream:
            async def response_stream_generator():
                # Get the complete response to extract product IDs
                full_response = ""
                marker_found = False
                
                async for chunk in await chat.send_message_stream(prompt):
                    full_response += chunk.text
                    
                    # Check if this chunk contains the product_ids marker
                    if "product_ids:" in chunk.text and not marker_found:
                        marker_found = True
                        # Truncate the chunk at the marker
                        marker_pos = chunk.text.find("product_ids:")
                        if marker_pos > 0:  # Only yield if there's content before the marker
                            clean_chunk = chunk.text[:marker_pos].strip()
                            if clean_chunk:
                                content_response = StreamingResponse(
                                    type=StreamingResponseType.CONTENT,
                                    conversation_id=request.conversation_id,
                                    content=clean_chunk
                                )
                                yield json.dumps(content_response.model_dump()) + "\n"
                    elif not marker_found:
                        # Only yield if we haven't hit the marker yet
                        content_response = StreamingResponse(
                            type=StreamingResponseType.CONTENT,
                            conversation_id=request.conversation_id,
                            content=chunk.text
                        )
                        yield json.dumps(content_response.model_dump()) + "\n"
                
                # Extract product IDs mentioned in the response
                referenced_product_ids = ShoppingAssistantUtils.extract_product_ids(full_response)

                print(f"Referenced product IDs: {referenced_product_ids}")
                
                # Get referenced products directly from database
                referenced_products = await ShoppingAssistantUtils.get_products_by_ids(session, referenced_product_ids)
                
                # Yield products if any were referenced
                if referenced_products:
                    product_response = StreamingResponse(
                        type=StreamingResponseType.PRODUCTS,
                        conversation_id=request.conversation_id,
                        content=[p.model_dump() for p in referenced_products]
                    )
                    yield json.dumps(product_response.model_dump()) + "\n"
                
                # Save the complete conversation after streaming is done, including context and products
                clean_response = full_response
                if "product_ids:" in full_response:
                    clean_response = full_response[:full_response.find("product_ids:")].strip()
                
                merged_response = clean_response
                if referenced_products:
                    product_info = "\n\nFunction call results for the user query:\n" + "\n".join([
                        f"- {p.model_dump_json()}" for p in referenced_products
                    ])
                    merged_response += product_info
                
                await ShoppingAssistantUtils.save_conversation(session, request.conversation_id, request.query, merged_response, context)
            
            return FastAPIStreamingResponse(response_stream_generator(), media_type="application/json")
        else:
            # Get regular response
            response = await chat.send_message(prompt)
            
            # Extract product IDs mentioned in the response
            referenced_product_ids = ShoppingAssistantUtils.extract_product_ids(response.text)
            
            # Get referenced products directly from database
            referenced_products = await ShoppingAssistantUtils.get_products_by_ids(session, referenced_product_ids)
            
            # Clean up the response to remove the product_ids marker
            clean_response = response.text
            if "product_ids:" in response.text:
                clean_response = response.text[:response.text.find("product_ids:")].strip()
            
            # Merge products with the response
            merged_response = clean_response
            if referenced_products:
                product_info = "\n\nReferenced Products:\n" + "\n".join([
                    f"- {p.model_dump_json()}" for p in referenced_products
                ])
                merged_response += product_info
            
            # Save conversation with merged response
            await ShoppingAssistantUtils.save_conversation(session, request.conversation_id, request.query, merged_response, context)
            
            return ChatResponse(
                response=clean_response,
                conversation_id=request.conversation_id,
                products=referenced_products
            )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/conversation/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_history(
    conversation_id: str,
    session: AsyncSession = Depends(get_async_session)
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
    session: AsyncSession = Depends(get_async_session)
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
