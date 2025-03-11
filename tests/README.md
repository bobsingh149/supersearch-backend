# SuperSearch API Tests

This directory contains test cases for the SuperSearch API routes.

## Test Structure

The tests are organized by route modules:

- `test_health.py`: Tests for the health check endpoint
- `test_organization_routes.py`: Tests for organization routes
- `test_product_routes.py`: Tests for product routes
- `test_recommend_routes.py`: Tests for recommendation routes
- `test_search_product_routes.py`: Tests for search routes
- `test_shopping_assistant_routes.py`: Tests for shopping assistant routes
- `test_sync_product_routes.py`: Tests for product sync routes

## Running Tests

To run the tests, you need to have pytest and pytest-asyncio installed. You can install them using pip:

```bash
pip install pytest pytest-asyncio httpx
```

### Running All Tests

```bash
pytest tests/
```

### Running Specific Test Files

```bash
pytest tests/test_product_routes.py
```

### Running Specific Test Functions

```bash
pytest tests/test_product_routes.py::test_create_products
```

## Test Database

The tests use a separate test database to avoid affecting your development or production data. The test database URL is derived from your main database URL by prefixing the database name with "test_".

For example, if your main database URL is `postgresql+asyncpg://user:password@localhost/supersearch`, the test database URL will be `postgresql+asyncpg://user:password@localhost/test_supersearch`.

Make sure the test database exists before running the tests.

## Mocking External Services

Some tests may require external services like Google's Generative AI or Temporal. The tests are designed to handle cases where these services are not available, but for complete testing, you may need to set up mock services or provide valid credentials.

## Test Data

The tests use sample data defined in each test file. This data is created at the beginning of relevant tests and cleaned up afterward.

## Continuous Integration

These tests can be integrated into a CI/CD pipeline to ensure that changes to the codebase don't break existing functionality.

Example GitHub Actions workflow:

```yaml
name: Run Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: timescale/timescaledb:latest-pg14
        env:
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
          POSTGRES_DB: test_supersearch
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.10'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-asyncio httpx
    - name: Run tests
      run: |
        pytest tests/
      env:
        DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost/test_supersearch
```

## Testing Guide

### Using the Async Client Fixture

We've added a common async client fixture in `tests/common.py` that can be used across all test files. This helps maintain consistency and reduces code duplication.

To use the async_client fixture in your tests:

1. Import the fixture from the common module:
```python
from tests.common import async_client
```

2. Use it as a parameter in your test functions:
```python
@pytest.mark.asyncio
async def test_your_endpoint(async_client):
    response = await async_client.get("/your/endpoint")
    assert response.status_code == 200
```

### Benefits of Using the Common Fixture

- Reduces code duplication
- Ensures consistent test client configuration
- Makes tests cleaner and more readable
- Centralizes client configuration changes

### Example Test

```python
import pytest
from fastapi import status
from tests.common import async_client

@pytest.mark.asyncio
async def test_example(async_client):
    # Test your API endpoint
    response = await async_client.get("/api/v1/example")
    assert response.status_code == status.HTTP_200_OK
    
    data = response.json()
    assert "key" in data
``` 