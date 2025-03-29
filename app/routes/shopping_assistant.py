from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from app.database.sql.sql import render_sql, SQLFilePath
from app.models.product import ProductDB, ProductSearchResult
from app.models.shopping_assistant import (
    ConversationDB, ChatResponse, ConversationResponse, Message, 
    StreamingResponse, StreamingResponseType, ChatRequest
)
from sqlalchemy import text, select
import logging
from app.services.shopping_assistant import ShoppingAssistantUtils, get_chat_from_history
from app.services.vertex import get_genai_client, get_embedding, TaskType
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
from typing import List, Dict
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
        client = get_genai_client()
        
        # Use product_ids list directly
        product_id_list = request.product_ids if request.product_ids else []
        
        # Build context
        context = ""
        all_products: Dict[str, ProductSearchResult] = {}  # Dictionary to store products by ID
        
        # Fetch specific products if IDs provided
        if product_id_list:
            # Get context for specific products
            query_stmt = select(ProductDB.id, ProductDB.title, ProductDB.custom_data, ProductDB.searchable_content, ProductDB.image_url).where(ProductDB.id.in_(product_id_list))
            result = await session.execute(query_stmt)
            id_lookup_products = [row._mapping for row in result]
            
            # Convert to ProductSearchResult
            product_search_results = [
                ProductSearchResult.model_validate(dict(row)) 
                for row in id_lookup_products
            ]
            
            # Add to context and product map
            product_context = ShoppingAssistantUtils.format_product_context(product_search_results)
            context += "user_query_context:\n" + product_context + "\n"
            
            # Add to product map
            for p in product_search_results:
                all_products[p.id] = p
        
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
        
        # Add to context and product map
        semantic_context = ShoppingAssistantUtils.format_product_context(semantic_product_results)
        context += "user_query_search_result:\n" + semantic_context
        
        # Add to product map
        for p in semantic_product_results:
            if p.id not in all_products:  # Only add if not already in map
                all_products[p.id] = p
        
        # Get chat session with history
        chat = await get_chat_from_history(request.conversation_id, client)
        
        # Prepare prompt with context
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
                referenced_product_ids = extract_product_ids(full_response)

                print(f"Referenced product IDs: {referenced_product_ids}")
                
                # Get referenced products
                referenced_products = [
                    all_products[prod_id] for prod_id in referenced_product_ids 
                    if prod_id in all_products
                ]
                
                # Yield products if any were referenced
                if referenced_products:
                    product_response = StreamingResponse(
                        type=StreamingResponseType.PRODUCTS,
                        conversation_id=request.conversation_id,
                        content=referenced_products
                    )
                    yield json.dumps(product_response.model_dump()) + "\n"
                
                # Save the complete conversation after streaming is done
                await ShoppingAssistantUtils.save_conversation(session, request.conversation_id, request.query, full_response, context)
            
            return FastAPIStreamingResponse(response_stream_generator(), media_type="application/json")
        else:
            # Get regular response
            response = await chat.send_message(prompt)
            
            # Extract product IDs mentioned in the response
            referenced_product_ids = extract_product_ids(response.text)
            
            # Get referenced products
            referenced_products = [
                all_products[prod_id] for prod_id in referenced_product_ids 
                if prod_id in all_products
            ]
            
            # Save conversation
            await ShoppingAssistantUtils.save_conversation(session, request.conversation_id, request.query, response.text, context)
            
            return ChatResponse(
                response=response.text,
                conversation_id=request.conversation_id,
                products=referenced_products
            )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


def extract_product_ids(text: str) -> List[str]:
    """
    Extract product IDs from the format 'product_ids:id1,id2,id3' in the text
    """
    marker = "product_ids:"
    if marker in text:
        # Find the position of the marker
        start_pos = text.find(marker) + len(marker)
        # Extract everything after the marker to the end of the text
        ids_str = text[start_pos:].strip()
        # If there's a newline after the IDs, remove everything after it
        if "\n" in ids_str:
            ids_str = ids_str.split("\n")[0].strip()
        # Split by comma and clean up each ID
        return [id.strip() for id in ids_str.split(',')]
    return []

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
            
        return ConversationResponse(
            conversation_id=conversation_id,
            messages=[Message.model_validate(msg) for msg in conversation.messages],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
