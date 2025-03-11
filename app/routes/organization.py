from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.organization import Organization, OrganizationDB
from app.database.session import get_async_session
from uuid import uuid4
from sqlalchemy import select

router = APIRouter(
    prefix="/organizations",
    tags=["organizations"]
)

@router.post("", response_model=Organization)
async def create_organization(
    org: Organization, 
    session: AsyncSession = Depends(get_async_session)
):
    # Check if organization with same ID exists
    query = select(OrganizationDB).where(OrganizationDB.id == org.id)
    result = await session.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Organization ID already exists")
    
    # Generate UUID if not provided
    if not org.id:
        org.id = uuid4()
    
    # Create new OrganizationDB instance
    db_org = OrganizationDB(**org.model_dump())
    session.add(db_org)
    await session.commit()
    await session.refresh(db_org)
    return db_org

@router.get("/{org_id}", response_model=Organization)
async def get_organization(
    org_id: str, 
    session: AsyncSession = Depends(get_async_session)
):
    query = select(OrganizationDB).where(OrganizationDB.id == org_id)
    result = await session.execute(query)
    org = result.scalar_one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org

@router.get("", response_model=List[Organization])
async def list_organizations(
    session: AsyncSession = Depends(get_async_session)
):
    query = select(OrganizationDB)
    result = await session.execute(query)
    return result.scalars().all()

@router.put("/{org_id}", response_model=Organization)
async def update_organization(org_id: str, org: Organization, db: AsyncSession = Depends(get_async_session)):
    db_org = await db.get(OrganizationDB, org_id)
    if not db_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Update organization fields
    for key, value in org.model_dump(exclude={'id'}).items():
        setattr(db_org, key, value)
    
    await db.commit()
    await db.refresh(db_org)
    return db_org

@router.delete("/{org_id}")
async def delete_organization(org_id: str, db: AsyncSession = Depends(get_async_session)):
    db_org = await db.get(OrganizationDB, org_id)
    if not db_org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    await db.delete(db_org)
    await db.commit()
    return {"message": "Organization deleted successfully"}
