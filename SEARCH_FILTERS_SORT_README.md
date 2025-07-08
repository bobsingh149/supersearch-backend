# Search API - Filters and Sort Guide

## 🔍 Overview

This guide covers how to use the advanced filtering and sorting capabilities in the search API. The search endpoints support complex filtering with multiple conditions and flexible sorting options.

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Supported Endpoints](#supported-endpoints)
- [Filter Options](#filter-options)
- [Sort Options](#sort-options)
- [API Examples](#api-examples)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Performance Tips](#performance-tips)

## 🚀 Quick Start

### Basic Filter Example
```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "category",
          "value": "electronics"
        }
      ]
    }
  }'
```

### Basic Sort Example
```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "sort": {
      "field": "price",
      "direction": "desc"
    }
  }'
```

## 🎯 Supported Endpoints

| Endpoint | Filters | Sort | Description |
|----------|---------|------|-------------|
| `POST /search` | ✅ | ✅ | Hybrid search with full filter/sort support |
| `GET /search/semantic` | ❌ | ❌ | Semantic search only |
| `GET /search/keywords` | ❌ | ❌ | Full-text search only |
| `GET /search/autocomplete` | ❌ | ❌ | Autocomplete search only |

## 🔧 Filter Options

### FilterCondition Model
```typescript
{
  field: string,           // Field name in custom_data
  value: any,              // Value to filter by
  operator?: string        // Comparison operator (default: "eq")
}
```

### FilterOptions Model
```typescript
{
  conditions?: FilterCondition[],  // Array of filter conditions
  filter_type?: "AND" | "OR"       // Logic operator (default: "AND")
}
```

### Supported Operators

| Operator | Description | Example Use Case |
|----------|-------------|------------------|
| `eq` | Equal to (default) | `category = "electronics"` |
| `neq` | Not equal to | `status != "discontinued"` |
| `gt` | Greater than | `price > 100` |
| `gte` | Greater than or equal | `rating >= 4.0` |
| `lt` | Less than | `price < 500` |
| `lte` | Less than or equal | `discount <= 20` |
| `in` | Value in list | `brand in ["Apple", "Samsung"]` |

## 📊 Sort Options

### SortOption Model
```typescript
{
  field: string,              // Field name in custom_data
  direction?: "asc" | "desc"  // Sort direction (default: "asc")
}
```

## 📚 API Examples

### 1. Single Filter
Filter products by category:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "page": 1,
    "size": 10,
    "filters": {
      "conditions": [
        {
          "field": "category",
          "value": "electronics",
          "operator": "eq"
        }
      ]
    }
  }'
```

### 2. Multiple Filters (AND Logic)
Filter electronics with price > $100:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "category",
          "value": "electronics",
          "operator": "eq"
        },
        {
          "field": "price",
          "value": 100,
          "operator": "gt"
        }
      ],
      "filter_type": "AND"
    }
  }'
```

### 3. Multiple Filters (OR Logic)
Filter for electronics OR clothing:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "category",
          "value": "electronics",
          "operator": "eq"
        },
        {
          "field": "category",
          "value": "clothing",
          "operator": "eq"
        }
      ],
      "filter_type": "OR"
    }
  }'
```

### 4. IN Operator
Filter by multiple brands:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "brand",
          "value": ["Apple", "Samsung", "Google", "Microsoft"],
          "operator": "in"
        }
      ]
    }
  }'
```

### 5. Range Filter
Filter products with price between $50-$200:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "price",
          "value": 50,
          "operator": "gte"
        },
        {
          "field": "price",
          "value": 200,
          "operator": "lte"
        }
      ],
      "filter_type": "AND"
    }
  }'
```

### 6. Sort Only
Sort products by price (highest first):

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "sort": {
      "field": "price",
      "direction": "desc"
    }
  }'
```

### 7. Combined Filter + Sort
Filter electronics and sort by rating:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "page": 1,
    "size": 20,
    "filters": {
      "conditions": [
        {
          "field": "category",
          "value": "electronics",
          "operator": "eq"
        },
        {
          "field": "rating",
          "value": 4.0,
          "operator": "gte"
        }
      ],
      "filter_type": "AND"
    },
    "sort": {
      "field": "price",
      "direction": "asc"
    }
  }'
```

### 8. Complex Multi-Condition Filter
Electronics OR clothing, with high ratings, under $300:

```bash
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "category",
          "value": "electronics",
          "operator": "eq"
        },
        {
          "field": "category", 
          "value": "clothing",
          "operator": "eq"
        },
        {
          "field": "rating",
          "value": 4.0,
          "operator": "gte"
        },
        {
          "field": "price",
          "value": 300,
          "operator": "lt"
        }
      ],
      "filter_type": "OR"
    }
  }'
```

## ⚙️ Configuration

### Required Settings
Before using filters and sort, configure allowed fields in your search settings:

```json
{
  "filter_fields": [
    "category",
    "brand", 
    "price",
    "rating",
    "color",
    "size",
    "in_stock",
    "discount_percentage"
  ],
  "sortable_fields": [
    "price",
    "rating", 
    "created_at",
    "updated_at",
    "popularity",
    "discount_percentage"
  ]
}
```

### Data Structure Example
Your products should have a `custom_data` field with the filterable/sortable fields:

```json
{
  "id": 123,
  "title": "iPhone 15 Pro",
  "custom_data": {
    "category": "electronics",
    "brand": "Apple",
    "price": 999.99,
    "rating": 4.8,
    "color": "natural titanium",
    "size": "128GB",
    "in_stock": true,
    "discount_percentage": 0,
    "created_at": "2024-01-15T10:30:00Z"
  },
  "searchable_content": "iPhone 15 Pro smartphone...",
  "image_url": "https://example.com/iphone15pro.jpg"
}
```

## 🐛 Error Handling

### Common Error Responses

#### Invalid Filter Field
```json
{
  "detail": "Filter field 'invalid_field' is not allowed. Allowed fields: category, brand, price, rating"
}
```

#### Invalid Sort Field
```json
{
  "detail": "Sort field 'invalid_field' is not allowed. Allowed fields: price, rating, created_at"
}
```

#### Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "filters", "conditions", 0, "operator"],
      "msg": "value is not a valid enumeration member; permitted: 'eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'in'",
      "type": "type_error.enum"
    }
  ]
}
```

## 🚀 Performance Tips

### 1. Use Appropriate Data Types
- **Text fields**: `category`, `brand`, `color`, `size`
- **Numeric fields**: `price`, `rating`, `discount_percentage`
- **Boolean fields**: `in_stock`, `featured`

### 2. Optimize Filter Conditions
```bash
# ✅ Good: Use specific operators for numeric fields
{
  "field": "price",
  "value": 100,
  "operator": "gte"
}

# ❌ Avoid: Using text operators on numeric fields
{
  "field": "price", 
  "value": "100",
  "operator": "eq"
}
```

### 3. Use Pagination
Always use pagination for better performance:
```json
{
  "page": 1,
  "size": 20
}
```

### 4. Limit Filter Conditions
- Keep filter conditions reasonable (< 10 conditions)
- Use database indexes on frequently filtered fields
- Consider using `IN` operator instead of multiple `OR` conditions

### 5. Empty Query Optimization
When using empty queries (`query: ""`), the API:
- Returns all products matching filters
- Applies sorting efficiently
- Uses pagination for better performance

## 📖 Response Format

The API returns an array of `ProductSearchResult` objects:

```json
[
  {
    "id": 123,
    "title": "iPhone 15 Pro",
    "custom_data": {
      "category": "electronics",
      "brand": "Apple", 
      "price": 999.99,
      "rating": 4.8
    },
    "searchable_content": "iPhone 15 Pro smartphone...",
    "image_url": "https://example.com/iphone15pro.jpg",
    "score": 0.95
  }
]
```

## 🔍 Testing Your Filters

### Test Filter Configuration
```bash
# Test if a field is allowed for filtering
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "test_field",
          "value": "test_value"
        }
      ]
    }
  }'
```

### Test Different Operators
```bash
# Test numeric operators
curl -X POST "{BASE_URL}/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "",
    "filters": {
      "conditions": [
        {
          "field": "price",
          "value": 0,
          "operator": "gt"
        }
      ]
    }
  }'
```

## 🎨 Frontend Integration Examples

### JavaScript/TypeScript
```typescript
interface FilterCondition {
  field: string;
  value: any;
  operator?: 'eq' | 'neq' | 'gt' | 'gte' | 'lt' | 'lte' | 'in';
}

interface FilterOptions {
  conditions?: FilterCondition[];
  filter_type?: 'AND' | 'OR';
}

interface SortOption {
  field: string;
  direction?: 'asc' | 'desc';
}

async function searchProducts(
  query: string = '',
  filters?: FilterOptions,
  sort?: SortOption,
  page: number = 1,
  size: number = 10
) {
  const response = await fetch('/search', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      query,
      page,
      size,
      filters,
      sort
    })
  });
  
  return response.json();
}

// Usage examples
const results1 = await searchProducts('', {
  conditions: [
    { field: 'category', value: 'electronics' },
    { field: 'price', value: 100, operator: 'gt' }
  ],
  filter_type: 'AND'
});

const results2 = await searchProducts('', null, {
  field: 'price',
  direction: 'desc'
});
```

### React Hook Example
```typescript
import { useState, useEffect } from 'react';

function useProductSearch() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  
  const search = async (filters?: FilterOptions, sort?: SortOption) => {
    setLoading(true);
    try {
      const results = await searchProducts('', filters, sort);
      setProducts(results);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setLoading(false);
    }
  };
  
  return { products, loading, search };
}
```

---

## 📞 Support

If you encounter issues or need help:

1. Check the error response for specific field validation errors
2. Verify your search configuration includes the required fields
3. Test with simple single-condition filters first
4. Check the server logs for detailed error information

Happy searching! 🎉 