import logging
from typing import List, Optional
import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database.session import get_async_session
from app.models.generate_content import (
    GenerateContentRequest,
    ContentGenerationResponse,
    ContentGenerationResult,
    ContentGenerationStatus
)
from app.models.product import Product
from app.services.content_generator import ContentGenerator

router = APIRouter(
    prefix="/generate-content",
    tags=["content"]
)

logger = logging.getLogger(__name__)

@router.post("/", response_model=ContentGenerationResponse)
async def generate_content(
    request: GenerateContentRequest,
    db: AsyncSession = Depends(get_async_session)
):
    """
    Generate AI content for products based on specified topics.
    
    Accepts either a list of product IDs or a flag to process all products,
    along with a list of content topics to generate.
    """
    try:
        # Get the products to process
        products = []
        
        if request.product_ids:
            # Get specific products by IDs
            placeholders = ", ".join([f"'{pid}'" for pid in request.product_ids])
            query = text(f"""
                SELECT * FROM demo_movies.products 
                WHERE id IN ({placeholders})
            """)
            result = await db.execute(query)
            product_data = result.all()
            
            if not product_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No products found with the specified IDs"
                )
            
            # Convert raw data to Product models
            for row in product_data:
                product_dict = {column: value for column, value in row._mapping.items()}
                products.append(Product.model_validate(product_dict))
            
        elif request.all_products:
            # Get all products
            query = text("SELECT * FROM demo_movies.products LIMIT 100")  # Add limit for safety
            result = await db.execute(query)
            product_data = result.all()
            
            if not product_data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No products found in the database"
                )
            
            # Convert raw data to Product models
            for row in product_data:
                product_dict = {column: value for column, value in row._mapping.items()}
                products.append(Product.model_validate(product_dict))
        
        # Generate content for each product and topic
        generation_tasks = []
        for product in products:
            for topic in request.topics:
                generation_tasks.append(ContentGenerator.generate_content_for_product(product, topic))
        
        # Execute all generation tasks concurrently
        generation_results = await asyncio.gather(*generation_tasks)
        
        # Update the database with the generated content
        successful_results = []
        failed_product_ids = []
        
        for result in generation_results:
            if result.status == ContentGenerationStatus.COMPLETED:
                # Update the product's AI-generated content
                success = await ContentGenerator.update_product_content(
                    db, result.product_id, result.topic, result.content
                )
                
                if success:
                    successful_results.append(result)
                else:
                    # Mark as failed if we couldn't update the database
                    failed_product_ids.append(result.product_id)
            else:
                failed_product_ids.append(result.product_id)
        
        # Commit the changes
        await db.commit()
        
        # Remove duplicates from failed product IDs
        unique_failed_ids = list(set(failed_product_ids))
        
        # Return the response
        return ContentGenerationResponse(
            results=successful_results,
            failed_product_ids=unique_failed_ids,
            total_processed=len(generation_results),
            total_failed=len(unique_failed_ids)
        )
    
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        logger.error(f"Error generating content: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate content: {str(e)}"
        ) 