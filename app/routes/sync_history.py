import logging
from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_async_session
from app.models.sync_history import SyncHistory, SyncHistoryDB, PaginatedSyncHistoryResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/sync-history",
    tags=["sync-history"]
)


@router.get("", response_model=PaginatedSyncHistoryResponse)
async def list_sync_histories(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List all sync histories with pagination
    
    Args:
        page: Page number (starts at 1)
        size: Number of items per page (default 10)
        
    Returns:
        Paginated list of sync histories
    """
    try:
        # Calculate offset from page and size
        offset = (page - 1) * size
        
        # Get paginated results
        query = select(SyncHistoryDB).order_by(SyncHistoryDB.created_at.desc()).offset(offset).limit(size + 1)
        result = await session.execute(query)
        items = result.scalars().all()
        
        # Check if there are more items
        has_more = len(items) > size
        if has_more:
            items = items[:size]  # Remove the extra item we fetched
        
        return PaginatedSyncHistoryResponse(
            items=list(items),
            page=page,
            size=size,
            has_more=has_more
        )
    except Exception as e:
        logger.error(f"Error listing sync histories: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/{sync_id}", response_model=SyncHistory)
async def get_sync_history_by_id(
    sync_id: UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """
    Get sync history by ID
    
    Args:
        sync_id: The ID of the sync history record
        
    Returns:
        The sync history record
    """
    try:
        # Get the sync history record
        sync_history_db = await session.get(SyncHistoryDB, sync_id)
        
        if not sync_history_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"Sync history record not found with ID: {sync_id}"
            )
        
        return sync_history_db
    except Exception as e:
        logger.error(f"Error getting sync history by ID: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) 