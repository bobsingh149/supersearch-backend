# Generic SQL Templates

This directory contains SQL templates for common database operations with multi-tenant support.

## Available Templates

### Basic CRUD Operations

- **get_by_id.sql**: Retrieve a single record by ID
- **get_all.sql**: Retrieve multiple records with filtering and sorting
- **insert.sql**: Insert a new record
- **bulk_insert.sql**: Insert multiple records in a single operation
- **update.sql**: Update an existing record by ID
- **delete.sql**: Delete a record by ID
- **count.sql**: Count records with optional filtering
- **advanced_filter.sql**: Advanced filtering with comparison operators

## Usage Examples

### Get By ID

```python
from app.database.sql import render_sql, SQLFilePath

query = render_sql(
    SQLFilePath.GENERIC_GET_BY_ID,
    tenant="customer_schema",
    table_name="users",
    id="f47ac10b-58cc-4372-a567-0e02b2c3d479"
)
```

### Get All with Filters and Sorting

```python
query = render_sql(
    SQLFilePath.GENERIC_GET_ALL,
    tenant="customer_schema",
    table_name="products",
    filters={"category": "electronics", "in_stock": True},
    sort_by="created_at",
    sort_direction="DESC",
    limit=10,
    offset=0
)
```

### Insert Record

```python
query = render_sql(
    SQLFilePath.GENERIC_INSERT,
    tenant="customer_schema",
    table_name="orders",
    columns=["user_id", "amount", "status"],
    values={
        "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "amount": 99.99,
        "status": "pending"
    }
)
```

### Bulk Insert

```python
query = render_sql(
    SQLFilePath.GENERIC_BULK_INSERT,
    tenant="customer_schema",
    table_name="products",
    columns=["name", "price", "category"],
    items=[
        {"name": "Product 1", "price": 19.99, "category": "electronics"},
        {"name": "Product 2", "price": 29.99, "category": "electronics"},
        {"name": "Product 3", "price": 39.99, "category": "accessories"}
    ]
)
```

### Update Record

```python
query = render_sql(
    SQLFilePath.GENERIC_UPDATE,
    tenant="customer_schema",
    table_name="users",
    id="f47ac10b-58cc-4372-a567-0e02b2c3d479",
    updates={
        "email": "new_email@example.com",
        "is_verified": True
    }
)
```

### Advanced Filtering

```python
query = render_sql(
    SQLFilePath.GENERIC_ADVANCED_FILTER,
    tenant="customer_schema",
    table_name="products",
    filters=[
        {
            "column": "price",
            "operator": ">=",
            "value": 100
        },
        {
            "column": "category",
            "operator": "IN",
            "value": ["electronics", "computers"],
            "logic_operator": "AND"
        },
        {
            "column": "discontinued",
            "operator": "IS NULL",
            "logic_operator": "OR"
        }
    ],
    sort_by="price",
    sort_direction="ASC",
    limit=20
)
``` 