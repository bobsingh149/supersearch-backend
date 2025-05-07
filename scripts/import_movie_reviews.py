import asyncio
import csv
import logging
import sys
import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

# Add the root directory to path so we can import app modules
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

from sqlalchemy import text, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import AsyncSessionLocal
from app.models.review import ReviewOrm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Path to the CSV file
CSV_FILE = Path(__file__).parent.parent / "datasets" / "movie_reviews.csv"

async def get_valid_product_ids(session: AsyncSession) -> set:
    """Fetch all product IDs from the products table"""
    result = await session.execute(text("SELECT id FROM demo_movies.products"))
    product_ids = {row[0] for row in result.fetchall()}
    logger.info(f"Found {len(product_ids)} valid product IDs in the database")
    return product_ids

async def process_batch(session: AsyncSession, reviews_batch: list) -> tuple[int, int]:
    """Insert a batch of reviews into the database
    
    Returns:
        tuple[int, int]: (imported_count, duplicate_count)
    """
    if not reviews_batch:
        return 0, 0
        
    imported_count = 0
    duplicate_count = 0
    
    try:
        # Check for existing reviews with same content and product_id
        for review in reviews_batch:
            query = select(ReviewOrm).where(
                ReviewOrm.product_id == review['product_id'],
                ReviewOrm.content == review['content']
            )
            if review.get('author'):
                query = query.where(ReviewOrm.author == review['author'])
            
            result = await session.execute(query)
            if result.first():
                logger.info(f"Skipping duplicate review for product {review['product_id']}")
                duplicate_count += 1
                continue
                
            # Create insert statement for non-duplicate review
            stmt = insert(ReviewOrm).values(review)
            await session.execute(stmt)
            imported_count += 1
            
        await session.commit()
        logger.info(f"Successfully processed batch of {len(reviews_batch)} reviews: {imported_count} imported, {duplicate_count} duplicates skipped")
        return imported_count, duplicate_count
    except Exception as e:
        await session.rollback()
        logger.error(f"Error processing batch: {str(e)}")
        raise

async def import_reviews():
    """Main function to import reviews from CSV file"""
    logger.info(f"Starting import from {CSV_FILE}")
    
    # Ensure the schema exists and is set as search path
    async with AsyncSessionLocal() as session:
        await session.execute(text("CREATE SCHEMA IF NOT EXISTS demo_movies"))
        await session.execute(text("SET search_path TO demo_movies"))
        await session.commit()
        
        # Get valid product IDs
        valid_product_ids = await get_valid_product_ids(session)
        
        if not valid_product_ids:
            logger.error("No products found in the database. Please import products first.")
            return
    
    # Count total rows for progress reporting
    total_rows = sum(1 for _ in open(CSV_FILE, 'r', encoding='utf-8')) - 1  # Subtract header
    logger.info(f"Found {total_rows} reviews to process in the CSV")
    
    batch_size = 1000
    reviews_batch = []
    
    # Process the CSV file
    with open(CSV_FILE, 'r', encoding='utf-8', newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        
        async with AsyncSessionLocal() as session:
            count = 0
            validation_skipped = 0
            processed = 0
            total_imported = 0
            total_duplicates = 0
            
            for row in reader:
                count += 1
                
                # Skip rows with missing required fields
                if not row.get('movie_id') or not row.get('review_content'):
                    validation_skipped += 1
                    continue
                
                # Skip if movie_id doesn't exist in products table
                if row['movie_id'] not in valid_product_ids:
                    validation_skipped += 1
                    if count % 10000 == 0:  # Log occasionally to avoid excessive logging
                        logger.warning(f"Skipping review for movie_id {row['movie_id']} - not found in products table")
                    continue
                
                # Parse the created_at date or use current date
                try:
                    created_at = datetime.fromisoformat(row.get('created_at')) if row.get('created_at') else datetime.now()
                except ValueError:
                    created_at = datetime.now()
                
                # Create review object
                review = {
                    'id': uuid4(),
                    'product_id': row['movie_id'],
                    'content': row['review_content'],
                    'author': row.get('author'),  # Get author from CSV, will be None if not present
                    'created_at': created_at,
                    'updated_at': created_at
                }
                
                reviews_batch.append(review)
                processed += 1
                
                # Process in batches
                if len(reviews_batch) >= batch_size:
                    imported, duplicates = await process_batch(session, reviews_batch)
                    total_imported += imported
                    total_duplicates += duplicates
                    reviews_batch = []
                    logger.info(f"Progress: {count}/{total_rows} reviews checked, {processed} valid reviews processed")
            
            # Process any remaining reviews
            if reviews_batch:
                imported, duplicates = await process_batch(session, reviews_batch)
                total_imported += imported
                total_duplicates += duplicates
            
            logger.info(f"Import completed. Total {count} reviews checked:")
            logger.info(f"- {total_imported} reviews successfully imported")
            logger.info(f"- {total_duplicates} duplicate reviews skipped")
            logger.info(f"- {validation_skipped} reviews skipped due to validation issues")
            logger.info(f"- Total skipped: {validation_skipped + total_duplicates}")

if __name__ == "__main__":
    asyncio.run(import_reviews()) 