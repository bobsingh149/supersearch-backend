import sys
from pathlib import Path

# Add the root directory to path so we can import app modules
root_dir = Path(__file__).parent.parent
sys.path.append(str(root_dir))

import asyncio
import logging
from datetime import datetime
from sqlalchemy import select, update
from app.database.session import get_async_session_with_contextmanager
from app.models.product import ProductDB

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIN_PRICE = 5
MAX_PRICE = 30

async def calculate_price(release_date_str: str, vote_average: float) -> float:
    """
    Calculate price based on release date and vote average.
    
    Args:
        release_date_str: Release date in format "MM/DD/YYYY" or "YYYY-MM-DD"
        vote_average: Vote average on scale of 0 to 10
        
    Returns:
        Price between MIN_PRICE and MAX_PRICE
    """
    try:
        # Try to parse the release date with different formats
        try:
            # Try MM/DD/YYYY format first
            release_date = datetime.strptime(release_date_str, "%m/%d/%Y")
        except ValueError:
            # Try YYYY-MM-DD format
            release_date = datetime.strptime(release_date_str, "%Y-%m-%d")
        
        # Calculate a base price based on recency (newer = more expensive)
        current_year = datetime.now().year
        years_old = current_year - release_date.year
        
        # Newer movies are more expensive
        # Scale from 0 (current year) to 1 (movies from 40+ years ago)
        recency_factor = min(years_old / 40, 1.0)
        recency_price = MAX_PRICE - (recency_factor * (MAX_PRICE - MIN_PRICE) * 0.7)
        
        # Higher rated movies are more expensive
        # Scale from 0 (0 rating) to 1 (10 rating)
        rating_factor = vote_average / 10
        rating_price = MIN_PRICE + (rating_factor * (MAX_PRICE - MIN_PRICE) * 0.5)
        
        # Combine the two factors
        final_price = (recency_price * 0.7) + (rating_price * 0.3)
        
        # Ensure price stays within bounds
        final_price = max(MIN_PRICE, min(MAX_PRICE, final_price))
        
        # Round to 2 decimal places
        return round(final_price, 2)
    except Exception as e:
        logger.error(f"Error calculating price: {str(e)}")
        return MIN_PRICE  # Default to minimum price if calculation fails

async def update_product_prices():
    """Update all products in the database with calculated prices."""
    try:
        async with get_async_session_with_contextmanager() as session:
            # Get all products
            query = select(ProductDB)
            result = await session.execute(query)
            products = result.scalars().all()
            
            logger.info(f"Found {len(products)} products to update")
            
            # Process each product
            update_count = 0
            skip_count = 0
            
            for product in products:
                if not product.custom_data:
                    logger.warning(f"Product {product.id} has no custom_data, skipping")
                    skip_count += 1
                    continue
                
                release_date = product.custom_data.get("release_date")
                vote_average = product.custom_data.get("vote_average")
                
                if not release_date or not vote_average:
                    logger.warning(f"Product {product.id} missing required fields, skipping")
                    skip_count += 1
                    continue
                
                try:
                    # Convert vote_average to float if it's a string
                    if isinstance(vote_average, str):
                        vote_average = float(vote_average)
                    
                    # Calculate price
                    price = await calculate_price(release_date, vote_average)
                    
                    # Update custom_data with the price
                    product.custom_data["price"] = price
                    
                    # Update the product in the database
                    update_stmt = (
                        update(ProductDB)
                        .where(ProductDB.id == product.id)
                        .values(custom_data=product.custom_data)
                    )
                    await session.execute(update_stmt)
                    update_count += 1
                    
                    if update_count % 100 == 0:
                        # Commit in batches to avoid long transactions
                        await session.commit()
                        logger.info(f"Updated {update_count} products so far")
                
                except Exception as e:
                    logger.error(f"Error updating product {product.id}: {str(e)}")
                    skip_count += 1
            
            # Final commit for any remaining products
            await session.commit()
            
            logger.info(f"Price update complete. Updated: {update_count}, Skipped: {skip_count}")
    
    except Exception as e:
        logger.error(f"Error in update_product_prices: {str(e)}")
        raise

async def main():
    logger.info("Starting price update process")
    await update_product_prices()
    logger.info("Price update process completed")

if __name__ == "__main__":
    asyncio.run(main()) 