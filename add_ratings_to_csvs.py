#!/usr/bin/env python3
"""
Script to add rating fields to fashion product CSV files.
Adds average_rating (1-5) with bell curve distribution and random rating_count.
"""

import pandas as pd
import numpy as np
import os
import glob
from pathlib import Path


def generate_bell_curve_rating():
    """
    Generate a rating between 1-5 with higher probability for middle values.
    Uses a truncated normal distribution centered at 3.5.
    """
    # Generate rating using normal distribution centered at 3.5
    # Standard deviation of 0.8 gives good bell curve within 1-5 range
    rating = np.random.normal(3.5, 0.8)
    
    # Clip to ensure it's within 1-5 range
    rating = np.clip(rating, 1.0, 5.0)
    
    # Round to 1 decimal place for realistic ratings
    return round(rating, 1)


def generate_rating_count():
    """
    Generate a random rating count with realistic distribution.
    Most products have fewer reviews, some have many.
    """
    # Use exponential distribution for realistic review counts
    # Most products will have fewer reviews, some will have many
    count = np.random.exponential(scale=50)
    
    # Add some minimum and maximum bounds
    count = max(1, min(int(count), 2000))
    
    return count


def add_ratings_to_csv(file_path):
    """
    Add rating fields to a single CSV file.
    
    Args:
        file_path (str): Path to the CSV file
    """
    print(f"Processing: {file_path}")
    
    try:
        # Read the CSV file
        df = pd.read_csv(file_path)
        
        # Check if rating columns already exist
        if 'average_rating' in df.columns or 'rating_count' in df.columns:
            print(f"  ⚠️  Rating columns already exist in {file_path}, skipping...")
            return
        
        # Generate ratings for each product
        num_products = len(df)
        
        # Generate average ratings with bell curve distribution
        average_ratings = [generate_bell_curve_rating() for _ in range(num_products)]
        
        # Generate rating counts
        rating_counts = [generate_rating_count() for _ in range(num_products)]
        
        # Add new columns to dataframe
        df['average_rating'] = average_ratings
        df['rating_count'] = rating_counts
        
        # Save the updated CSV
        df.to_csv(file_path, index=False)
        
        print(f"  ✅ Added ratings to {num_products} products")
        print(f"     Average rating range: {min(average_ratings):.1f} - {max(average_ratings):.1f}")
        print(f"     Rating count range: {min(rating_counts)} - {max(rating_counts)}")
        
    except Exception as e:
        print(f"  ❌ Error processing {file_path}: {str(e)}")


def main():
    """
    Main function to process all CSV files in the ecommerce_batches directory.
    """
    # Set random seed for reproducible results (optional)
    np.random.seed(42)
    
    # Define the directory containing CSV files
    csv_directory = "datasets/ecommerce_batches"
    
    # Check if directory exists
    if not os.path.exists(csv_directory):
        print(f"❌ Directory {csv_directory} does not exist!")
        return
    
    # Find all CSV files in the directory
    csv_pattern = os.path.join(csv_directory, "fashion_products_batch_*.csv")
    csv_files = glob.glob(csv_pattern)
    
    if not csv_files:
        print(f"❌ No CSV files found matching pattern: {csv_pattern}")
        return
    
    # Sort files for consistent processing order
    csv_files.sort()
    
    print(f"🚀 Found {len(csv_files)} CSV files to process")
    print(f"📁 Directory: {csv_directory}")
    print("=" * 60)
    
    # Process each CSV file
    total_products = 0
    for csv_file in csv_files:
        add_ratings_to_csv(csv_file)
        
        # Count total products processed
        try:
            df = pd.read_csv(csv_file)
            total_products += len(df)
        except:
            pass
        
        print()  # Add blank line between files
    
    print("=" * 60)
    print(f"✅ Processing complete!")
    print(f"📊 Total products processed: {total_products}")
    print(f"📈 Rating distribution info:")
    print(f"   - Average rating: Bell curve centered at 3.5 (range 1.0-5.0)")
    print(f"   - Rating count: Exponential distribution (range 1-2000)")


def test_rating_distribution():
    """
    Test function to show the distribution of generated ratings.
    """
    print("🧪 Testing rating distribution...")
    
    # Generate sample ratings
    sample_size = 1000
    ratings = [generate_bell_curve_rating() for _ in range(sample_size)]
    counts = [generate_rating_count() for _ in range(sample_size)]
    
    print(f"\n📊 Sample of {sample_size} ratings:")
    print(f"Average rating: {np.mean(ratings):.2f}")
    print(f"Rating std dev: {np.std(ratings):.2f}")
    print(f"Rating range: {min(ratings):.1f} - {max(ratings):.1f}")
    
    print(f"\nRating distribution:")
    for i in range(1, 6):
        count_in_range = sum(1 for r in ratings if i <= r < i+1)
        percentage = (count_in_range / sample_size) * 100
        print(f"  {i}.0-{i}.9: {count_in_range:3d} ({percentage:5.1f}%)")
    
    print(f"\n📊 Sample of {sample_size} rating counts:")
    print(f"Average count: {np.mean(counts):.1f}")
    print(f"Count range: {min(counts)} - {max(counts)}")


if __name__ == "__main__":
    # Uncomment the line below to test the distribution first
    # test_rating_distribution()
    
    # Run the main processing
    main() 