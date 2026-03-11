# Botswain API Documentation

## POST /api/query

Execute a natural language query with optional pagination.

### Endpoint

```
POST http://localhost:8002/api/query
Content-Type: application/json
```

### Request Parameters

| Parameter | Type | Required | Default | Validation | Description |
|-----------|------|----------|---------|------------|-------------|
| `question` | string | **Yes** | - | Max 1000 chars | Natural language question |
| `format` | string | No | `'natural'` | `'natural'`, `'json'`, `'table'` | Response format |
| `use_cache` | boolean | No | `true` | - | Use cached results |
| `page` | integer | No | `1` | Min: 1 | Page number (1-indexed) |
| `page_size` | integer | No | `100` | Min: 1, Max: 1000 | Results per page |
| `offset` | integer | No | `0` | Min: 0 | Number of results to skip |
| `limit` | integer | No | `100` | Min: 1, Max: 1000 | Maximum results to return |

**Pagination Priority:** If both `page`/`page_size` and `offset`/`limit` are provided, `offset`/`limit` takes precedence.

**Conversion Formula:** `offset = (page - 1) * page_size`

### Response Format

```json
{
  "question": "Show orders",
  "response": "Found 245 orders (showing results 51-100)",
  "results": [...],
  "count": 50,
  "pagination": {
    "current_page": 2,
    "page_size": 50,
    "offset": 50,
    "limit": 50,
    "has_next": true,
    "has_previous": true,
    "next_page": 3,
    "previous_page": 1,
    "next_offset": 100,
    "previous_offset": 0,
    "estimated_total": "100+",
    "estimated_total_pages": "3+"
  },
  "layout": [
    {
      "type": "summary",
      "content": "Found 245 orders (showing results 51-100)"
    },
    {
      "type": "table",
      "data": [...],
      "columns": [...]
    }
  ],
  "intent": {
    "entity": "order",
    "intent_type": "query",
    "filters": {},
    "limit": 50
  },
  "cached": false
}
```

### Pagination Metadata Fields

| Field | Type | Description | Always Present? |
|-------|------|-------------|-----------------|
| `current_page` | int | Current page number (1-indexed) | Yes |
| `page_size` | int | Results per page | Yes |
| `offset` | int | Number of results skipped | Yes |
| `limit` | int | Maximum results in response | Yes |
| `has_next` | bool | More results available after this page | Yes |
| `has_previous` | bool | Can navigate backwards | Yes |
| `next_page` | int | Next page number | Only if `has_next=true` |
| `previous_page` | int | Previous page number | Only if `has_previous=true` |
| `next_offset` | int | Offset for next page | Only if `has_next=true` |
| `previous_offset` | int | Offset for previous page | Only if `has_previous=true` |
| `estimated_total` | string/int | Total results available | Yes |
| `estimated_total_pages` | string/int | Total pages available | Yes |

**Estimated Totals:**
- **String format** (`"100+"`) when more results exist (not on last page)
- **Integer format** (`125`) on the last page (exact count known)

### Examples

#### Page-Based Pagination

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders from last month",
    "page": 2,
    "page_size": 25
  }'
```

**Response:**
```json
{
  "question": "Show orders from last month",
  "response": "Found 150+ orders (showing results 26-50)",
  "count": 25,
  "pagination": {
    "current_page": 2,
    "page_size": 25,
    "offset": 25,
    "limit": 25,
    "has_next": true,
    "has_previous": true,
    "next_page": 3,
    "previous_page": 1,
    "next_offset": 50,
    "previous_offset": 0,
    "estimated_total": "51+",
    "estimated_total_pages": "3+"
  }
}
```

#### Offset-Based Pagination

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders from last month",
    "offset": 50,
    "limit": 25
  }'
```

**Response:**
```json
{
  "question": "Show orders from last month",
  "response": "Found 150+ orders (showing results 51-75)",
  "count": 25,
  "pagination": {
    "current_page": 3,
    "page_size": 25,
    "offset": 50,
    "limit": 25,
    "has_next": true,
    "has_previous": true,
    "next_page": 4,
    "previous_page": 2,
    "next_offset": 75,
    "previous_offset": 25,
    "estimated_total": "76+",
    "estimated_total_pages": "4+"
  }
}
```

#### Last Page (Exact Total)

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders from last month",
    "page": 5,
    "page_size": 25
  }'
```

**Response:**
```json
{
  "question": "Show orders from last month",
  "response": "Found 125 orders (showing results 101-125)",
  "count": 25,
  "pagination": {
    "current_page": 5,
    "page_size": 25,
    "offset": 100,
    "limit": 25,
    "has_next": false,
    "has_previous": true,
    "previous_page": 4,
    "previous_offset": 75,
    "estimated_total": 125,
    "estimated_total_pages": 5
  }
}
```

#### Default Pagination (No Parameters)

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders"
  }'
```

**Response:**
```json
{
  "question": "Show orders",
  "response": "Found 245+ orders (showing results 1-100)",
  "count": 100,
  "pagination": {
    "current_page": 1,
    "page_size": 100,
    "offset": 0,
    "limit": 100,
    "has_next": true,
    "has_previous": false,
    "next_page": 2,
    "next_offset": 100,
    "estimated_total": "101+",
    "estimated_total_pages": "2+"
  }
}
```

### Error Responses

#### Invalid Page Number

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders",
    "page": 0
  }'
```

**Response (400 Bad Request):**
```json
{
  "page": [
    "Ensure this value is greater than or equal to 1."
  ]
}
```

#### Excessive Page Size

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders",
    "page_size": 5000
  }'
```

**Response (400 Bad Request):**
```json
{
  "page_size": [
    "Ensure this value is less than or equal to 1000."
  ]
}
```

#### Negative Offset

**Request:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders",
    "offset": -10
  }'
```

**Response (400 Bad Request):**
```json
{
  "offset": [
    "Ensure this value is greater than or equal to 0."
  ]
}
```

## Performance Considerations

### Smart Estimation

Botswain uses the **limit+1 trick** to avoid expensive COUNT queries:

1. Query requests `limit=50`, but Botswain fetches `51` results
2. If `51` results returned → `has_next=true`, trim to `50` for response
3. If `≤50` results returned → `has_next=false`, return all results

**Benefits:**
- **Single query** (no separate COUNT)
- **Fast** (< 2ms overhead)
- **Works with all data sources** (SQL, APIs, logs, GitHub)
- **Exact totals on last page** (when `has_next=false`)

### Caching

Each page is cached independently:

```
Cache Key Format:
query:{entity}:{filters_hash}:{offset}:{limit}:{user}

Examples:
query:order:a1b2c3d4:0:100:dana       # Page 1 (default)
query:order:a1b2c3d4:100:100:dana     # Page 2
query:order:a1b2c3d4:0:50:dana        # Page 1 (page_size=50)
```

**Cache Behavior:**
- `page=2, page_size=50` and `offset=50, limit=50` → **same cache entry**
- Different pages → **different cache entries**
- Cache TTL: Per-entity (30s - 1hr)
- Cache invalidation clears **all pages** for an entity

### Database Performance

**Offset Performance:**
- Large offsets (e.g., `offset=10000`) can be slow in SQL databases
- **Mitigation:** Max limit of 1000 constrains page depth
- Most users don't paginate past page 10
- Read-replica usage prevents impact on primary database

**Query Patterns:**
```sql
-- Before: No pagination
SELECT * FROM orders LIMIT 100;

-- After: With pagination (limit+1 for has_next detection)
SELECT * FROM orders OFFSET 50 LIMIT 51;
```

## Integration Examples

### JavaScript/TypeScript

```typescript
interface PaginationParams {
  page?: number;
  page_size?: number;
  offset?: number;
  limit?: number;
}

async function queryBotswain(
  question: string,
  pagination?: PaginationParams
) {
  const response = await fetch('http://localhost:8002/api/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      ...pagination
    })
  });

  return await response.json();
}

// Page-based
const page1 = await queryBotswain('Show orders', { page: 1, page_size: 50 });

// Offset-based
const page2 = await queryBotswain('Show orders', { offset: 50, limit: 50 });

// Navigate to next page
if (page1.pagination.has_next) {
  const nextPage = await queryBotswain('Show orders', {
    page: page1.pagination.next_page,
    page_size: page1.pagination.page_size
  });
}
```

### Python

```python
import requests

def query_botswain(question, page=None, page_size=None, offset=None, limit=None):
    payload = {'question': question}

    if offset is not None or limit is not None:
        # Offset-based
        payload['offset'] = offset if offset is not None else 0
        payload['limit'] = limit if limit is not None else 100
    elif page is not None or page_size is not None:
        # Page-based
        payload['page'] = page if page is not None else 1
        payload['page_size'] = page_size if page_size is not None else 100

    response = requests.post(
        'http://localhost:8002/api/query',
        json=payload
    )
    return response.json()

# Page-based
page1 = query_botswain('Show orders', page=1, page_size=50)

# Offset-based
page2 = query_botswain('Show orders', offset=50, limit=50)

# Navigate to next page
if page1['pagination']['has_next']:
    next_page = query_botswain(
        'Show orders',
        page=page1['pagination']['next_page'],
        page_size=page1['pagination']['page_size']
    )
```

### cURL Pagination Loop

```bash
#!/bin/bash

PAGE=1
PAGE_SIZE=25

while true; do
  echo "Fetching page $PAGE..."

  RESPONSE=$(curl -s -X POST http://localhost:8002/api/query \
    -H "Content-Type: application/json" \
    -d "{
      \"question\": \"Show orders\",
      \"page\": $PAGE,
      \"page_size\": $PAGE_SIZE
    }")

  echo "$RESPONSE" | jq '.count' | xargs -I {} echo "Got {} results"

  HAS_NEXT=$(echo "$RESPONSE" | jq -r '.pagination.has_next')

  if [ "$HAS_NEXT" != "true" ]; then
    echo "Reached last page"
    break
  fi

  PAGE=$((PAGE + 1))
done
```

## Design Documentation

For complete design details, see:
- Design document: `docs/plans/2026-03-11-pagination-design.md`
- Implementation plan: `docs/plans/2026-03-11-pagination-implementation.md`

## Backward Compatibility

Pagination is fully backward compatible:
- Requests without pagination parameters default to `page=1, limit=100`
- Existing API clients continue working without changes
- Response includes new `pagination` field (non-breaking addition)
- All existing fields (`results`, `count`, `response`, etc.) unchanged
