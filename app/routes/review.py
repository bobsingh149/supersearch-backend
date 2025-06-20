from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, update, delete, text
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import json

from app.database.session import get_async_session, get_tenant_name
from app.models.review import Review, ReviewCreate, ReviewUpdate, ReviewOrm
from app.services.review import generate_review_summary, ReviewSummaryOutput, generate_fake_reviews_and_summary

router = APIRouter(
    prefix="/reviews",
    tags=["reviews"],
)


@router.post("/", response_model=None, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_in: ReviewCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new review.
    """
    db_review = ReviewOrm(
        content=review_in.content,
        product_id=review_in.product_id,
    )
    session.add(db_review)
    await session.commit()
    return None


@router.get("/", response_model=List[Review])
async def get_reviews(
    product_id: Optional[str] = None,
    page_number: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    session: AsyncSession = Depends(get_async_session),
) -> List[Review]:
    """
    Get all reviews with optional filtering by product_id.
    Supports pagination using page_number and page_size.
    """
    query = select(ReviewOrm)
    if product_id:
        query = query.where(ReviewOrm.product_id == product_id)
    
    skip = (page_number - 1) * page_size
    query = query.offset(skip).limit(page_size)
    result = await session.execute(query)
    reviews = result.scalars().all()
    return reviews


@router.get("/{review_id}", response_model=Review)
async def get_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> Review:
    """
    Get a specific review by ID.
    """
    query = select(ReviewOrm).where(ReviewOrm.id == review_id)
    result = await session.execute(query)
    review = result.scalars().first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    
    return review


@router.put("/{review_id}", response_model=Review)
async def update_review(
    review_id: UUID,
    review_in: ReviewUpdate,
    session: AsyncSession = Depends(get_async_session),
) -> Review:
    """
    Update a review.
    """
    # Check if review exists
    query = select(ReviewOrm).where(ReviewOrm.id == review_id)
    result = await session.execute(query)
    review = result.scalars().first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    
    # Update review
    update_data = review_in.model_dump(exclude_unset=True)
    update_stmt = (
        update(ReviewOrm)
        .where(ReviewOrm.id == review_id)
        .values(**update_data)
        .returning(ReviewOrm)
    )
    
    result = await session.execute(update_stmt)
    updated_review = result.scalars().first()
    await session.commit()
    
    return updated_review


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: UUID,
    session: AsyncSession = Depends(get_async_session),
) -> None:
    """
    Delete a review.
    """
    # Check if review exists
    query = select(ReviewOrm).where(ReviewOrm.id == review_id)
    result = await session.execute(query)
    review = result.scalars().first()
    
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found",
        )
    
    # Delete review
    delete_stmt = delete(ReviewOrm).where(ReviewOrm.id == review_id)
    await session.execute(delete_stmt)
    await session.commit()


class ReviewSummaryResponse(BaseModel):
    """Response model for review summary"""
    product_id: str
    summary: str

@router.get("/{product_id}/summary", response_model=ReviewSummaryOutput)
async def get_review_summary(
    product_id: str,
    session: AsyncSession = Depends(get_async_session),
    tenant: str = Depends(get_tenant_name)
) -> ReviewSummaryOutput:
    """
    Get an AI-generated summary of reviews for a specific product.
    Returns structured data with a summary, pros list, and cons list.
    
    First checks if reviews exist in the products table.
    If reviews exist, returns the existing summary.
    If no reviews exist, generates fake reviews and summary and stores them.
    """
    # First, check if there are existing reviews and summary in the products table
    check_reviews_query = text(f"""
        SELECT reviews, ai_summary FROM {tenant}.products 
        WHERE id = :product_id
    """)
    result = await session.execute(check_reviews_query, {"product_id": product_id})
    product_data = result.first()
    
    if not product_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    
    existing_reviews, existing_summary = product_data
    
    # If reviews exist, return the existing summary
    if existing_reviews and existing_summary:
        return ReviewSummaryOutput.model_validate(existing_summary)
    
    # If no existing reviews, generate fake reviews and summary
    generated_data = await generate_fake_reviews_and_summary(product_id, session, tenant)
    
    # Store both the generated reviews and summary in the products table
    update_query = text(f"""
        UPDATE {tenant}.products 
        SET reviews = :reviews, ai_summary = :ai_summary
        WHERE id = :product_id
    """)
    
    # Convert Pydantic models to dict for storage
    reviews_dict = [review for review in generated_data.reviews]
    summary_dict = generated_data.summary.model_dump()
    
    await session.execute(
        update_query,
        {
            "product_id": product_id,
            "reviews": json.dumps(reviews_dict),
            "ai_summary": json.dumps(summary_dict)
        }
    )
    await session.commit()
    
    return generated_data.summary 