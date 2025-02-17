from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from google import genai
from google.ai.generativelanguage import Content, Part
from app.database.session import AsyncSessionLocal, get_db
from app.models.product import ProductDB
from app.models.conversation import ConversationDB, ChatRequest, ChatResponse, ConversationResponse, Message
from sqlalchemy import text, select
import json
import logging
from functools import lru_cache
from app.utils.sql import render_query
from app.utils.shopping_assistant import ShoppingAssistantUtils

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/shopping-assistant",
    tags=["shopping-assistant"]
)

SYSTEM_PROMPT = """You are a helpful shopping assistant. Your goal is to help users find products 
and answer questions about shopping. Provide clear, concise, and relevant responses."""

async def determine_intent(client: genai.Client, query: str) -> str:
    return await ShoppingAssistantUtils.determine_intent(client, query)

@lru_cache(maxsize=1000)
async def get_chat_from_history(conversation_id: str, client: genai.Client):
    """
    Get or create a chat session with history from the database
    Uses caching to avoid recreating chat sessions frequently
    """
    try:
        # Get conversation history from database
        async with AsyncSessionLocal() as session:
            conversation = await session.get(ConversationDB, conversation_id)
        
        if not conversation:
            # Create new chat without history
            return client.chats.create(
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
        
        return client.chats.create(
            model="gemini-2.0-flash-001",
            history=history
        )
    except Exception as e:
        logger.error(f"Error getting chat history: {str(e)}")
        raise

async def save_conversation(session: AsyncSession, conversation_id: str, user_message: str, assistant_response: str):
    await ShoppingAssistantUtils.save_conversation(session, conversation_id, user_message, assistant_response)

@router.post("/chat", response_model=ChatResponse)
async def chat_with_assistant(
    chat_request: ChatRequest,
    session: AsyncSession = Depends(get_db)
):
    """Chat with the shopping assistant"""
    try:
        client = genai.Client(vertexai=True, project="spheric-hawk-449810-a2", 
                            location="us-central1")
        
        # Use chat_request fields
        query = chat_request.query
        conversation_id = chat_request.conversation_id
        product_ids = chat_request.product_ids
        
        # Determine intent
        intent = await determine_intent(client, query)
        
        # Build context
        context = ""
        if intent == "fetch_products":
            # Fetch products from database for recommendations
            sql_query = render_query('product/hybrid_search',
                query_text=query,
                match_count=5,
                fuzzy_distance=2
            )
            result = await session.execute(text(sql_query))
            products = [row._mapping for row in result]
            
            context = ShoppingAssistantUtils.format_product_context(products)
        elif product_ids:
            # Get context for specific products
            query = select(ProductDB).where(ProductDB.id.in_(product_ids))
            result = await session.execute(query)
            products = result.scalars().all()
            context = ShoppingAssistantUtils.format_product_context(
                [{"title": p.title, "searchable_content": p.searchable_content} for p in products],
                context_type="comparison" if "compare" in query.lower() else "general"
            )

        
        # Get chat session with history
        chat = await get_chat_from_history(conversation_id, client)
        
        # Prepare prompt with context
        prompt = ShoppingAssistantUtils.construct_prompt(
            query,
            context,
        )
        
        # Get response
        response = chat.send_message(prompt)
        
        # Save conversation
        await save_conversation(session, conversation_id, query, response.text)
        
        return ChatResponse(
            response=response.text,
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/conversation/{conversation_id}", response_model=ConversationResponse)
async def get_conversation_history(
    conversation_id: str,
    session: AsyncSession = Depends(get_db)
):
    """Get the conversation history"""
    try:
        conversation = await session.get(ConversationDB, conversation_id)
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
            
        return ConversationResponse(
            conversation_id=conversation_id,
            messages=[Message(**msg) for msg in conversation.messages],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at
        )
        
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
