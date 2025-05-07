from fastapi import APIRouter, HTTPException, Depends, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from uuid import UUID

from app.models.lead import LeadDB, Lead, LeadCreate, LeadUpdate
from app.database.session import get_async_session

router = APIRouter(
    prefix="/leads",
    tags=["leads"]
)

@router.post("", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_lead(
    lead_data: LeadCreate,
    session: AsyncSession = Depends(get_async_session)
):
    """Create a new lead"""
    # Check if lead with same email exists
    query = select(LeadDB).where(LeadDB.business_email == lead_data.business_email)
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lead with this email already exists"
        )
    
    # Convert Pydantic model to SQLAlchemy model
    db_lead = LeadDB(**lead_data.model_dump())
    
    # Add to database
    session.add(db_lead)
    await session.commit()
    return None


@router.get("", response_model=List[Lead])
async def get_leads(
    session: AsyncSession = Depends(get_async_session)
):
    """Get all leads"""
    query = select(LeadDB)
    result = await session.execute(query)
    return result.scalars().all()

@router.get("/{lead_id}", response_model=Lead)
async def get_lead(
    lead_id: UUID,
    session: AsyncSession = Depends(get_async_session)
):
    """Get a specific lead by ID"""
    query = select(LeadDB).where(LeadDB.id == lead_id)
    result = await session.execute(query)
    lead = result.scalar_one_or_none()
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    return lead

@router.patch("/{lead_id}", response_model=None)
async def update_lead(
    lead_id: UUID,
    lead_data: LeadUpdate,
    session: AsyncSession = Depends(get_async_session)
):
    """Update a lead"""
    # Get the lead from the database
    query = select(LeadDB).where(LeadDB.id == lead_id)
    result = await session.execute(query)
    db_lead = result.scalar_one_or_none()
    
    if not db_lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found"
        )
    
    # Check if updating email to one that already exists
    if lead_data.business_email and lead_data.business_email != db_lead.business_email:
        email_query = select(LeadDB).where(LeadDB.business_email == lead_data.business_email)
        email_result = await session.execute(email_query)
        if email_result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lead with this email already exists"
            )
    
    # Update lead fields
    update_data = lead_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(db_lead, key, value)
    
    await session.commit()
    return None