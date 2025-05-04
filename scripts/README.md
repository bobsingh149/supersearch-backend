# Scripts

This directory contains utility scripts for the SuperSearch application.

## Movie Reviews Import Script

The `import_movie_reviews.py` script imports movie reviews from the `datasets/movie_reviews.csv` file into the database.

### Prerequisites

- PostgreSQL database running with connection details configured in your environment
- Python 3.8+ with required dependencies installed
- Products must be already imported into the `products` table in the `demo_movies` schema

### Usage

To run the script:

```bash
# From the project root directory
python -m scripts.import_movie_reviews
```

### What the script does

1. Retrieves all existing product IDs from the database
2. Reads movie reviews from the CSV file in batches
3. Validates that each review corresponds to an existing product ID
4. Transforms the data to match the database schema
5. Inserts only the valid reviews into the `reviews` table in the `demo_movies` schema
6. Handles errors and provides progress updates

### CSV Format

The expected CSV format is:
```
movie_id,movie_title,review_content,author,created_at
```

Where:
- `movie_id`: ID of the movie (maps to `product_id` in the database)
- `movie_title`: Title of the movie (not stored in the reviews table)
- `review_content`: The review text (maps to `content` in the database)
- `author`: Author of the review (not currently stored)
- `created_at`: Timestamp when the review was created (ISO format)

### Validation
The script will only import reviews where:
- The movie_id exists in the products table
- The review_content is not empty 