from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
import uuid
from app.utils.jina_api import JinaAPI
from app.models.document import Document, DocumentDB, DocumentSearchResult
from app.utils.embedding import get_embedding, TaskType
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_async_session
from sqlalchemy import select, delete
from asyncio import TaskGroup, sleep

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/from-url", response_model=List[Document])
async def create_documents_from_url(
    url: str,
    session: AsyncSession = Depends(get_async_session)
) -> List[Document]:
    """
    Creates documents from a website URL:
    1. Reads the URL content using Jina Reader
    2. Segments the content into chunks
    3. Creates embeddings for each chunk
    4. Stores the chunks as separate documents
    """
    try:
        # Initialize Jina API
        jina_api = JinaAPI()
        
        # Get content from URL
        content = await jina_api.reader(url)
        
        # Segment content into chunks
        segments = await jina_api.segment(
            content=content,
            max_chunk_length=1000,  # Adjust chunk size as needed
            return_chunks=True,
            return_tokens=False
        )
        
        documents = []
        # Process each chunk
        for chunk in segments['chunks']:
            # Generate embedding for the chunk
            embedding = await get_embedding(chunk, TaskType.DOCUMENT)
            
            # Create document
            doc = DocumentDB(
                id=str(uuid.uuid4()),
                content=chunk,
                text_embedding=embedding
            )
            
            session.add(doc)
            documents.append(doc)
        
        # Commit all documents to database
        await session.commit()
        
        # Convert to Pydantic models for response
        return [Document.model_validate(doc) for doc in documents]

    except Exception as e:
        await session.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error processing URL: {str(e)}"
        )

@router.post("/", response_model=List[Document])
async def create_documents(
    documents: List[Document],
    session: AsyncSession = Depends(get_async_session)
):
    """
    Bulk create documents with embeddings
    """
    try:
        processed_documents = []
        async with TaskGroup() as tg:
            for doc in documents:
                if not doc.id:
                    doc.id = str(uuid.uuid4())
                if doc.content and not doc.text_embedding:
                    doc.text_embedding = await get_embedding(doc.content, TaskType.DOCUMENT)
                db_doc = DocumentDB(**doc.model_dump())
                session.add(db_doc)
                processed_documents.append(db_doc)
                await sleep(0.1)
        
        await session.commit()
        return [Document.model_validate(doc) for doc in processed_documents]
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{document_id}", response_model=Document)
async def update_document(
    document_id: str,
    document: Document,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Update a single document
    """
    try:
        result = await session.get(DocumentDB, document_id)
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Update embedding if content changed
        if document.content != result.content:
            document.text_embedding = await get_embedding(document.content, TaskType.DOCUMENT)
        
        for key, value in document.model_dump(exclude={'id'}).items():
            setattr(result, key, value)
        
        await session.commit()
        return Document.model_validate(result)
    except Exception as e:
        await session.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}", response_model=Document)
async def get_document(
    document_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Retrieve a single document by ID
    """
    result = await session.get(DocumentDB, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    return Document.model_validate(result)

@router.get("/", response_model=List[Document])
async def list_documents(
    session: AsyncSession = Depends(get_async_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000)
):
    """
    List all documents with pagination
    """
    query = select(DocumentDB).offset(skip).limit(limit)
    result = await session.execute(query)
    documents = result.scalars().all()
    
    return [Document.model_validate(doc) for doc in documents]

@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Delete a single document
    """
    result = await session.get(DocumentDB, document_id)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found")
    
    await session.delete(result)
    await session.commit()
    return {"message": "Document deleted successfully"}

@router.delete("/")
async def delete_all_documents(
    session: AsyncSession = Depends(get_async_session)
):
    """
    Delete all documents (use with caution)
    """
    query = delete(DocumentDB)
    await session.execute(query)
    await session.commit()
    return {"message": "All documents deleted successfully"}
