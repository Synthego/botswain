# Botswain Query Result Pagination - Design Document

**Date:** 2026-03-11
**Author:** Dana Janezic
**Status:** Approved

---

## Executive Summary

Add comprehensive offset-based pagination to Botswain's query API to support the upcoming web interface. Implement smart estimation (limit+1 trick) to provide pagination metadata without expensive COUNT queries, maintaining fast performance across all data sources.

**Key Features:**
- Dual parameter support (page/page_size OR offset/limit)
- Full pagination metadata (next/previous helpers, estimated totals)
- Smart estimation (no COUNT queries)
- Cache-aware (pagination parameters in cache key)
- Non-breaking changes (backward compatible)

**Performance:** Single query with limit+1 (no COUNT overhead)
**Compatibility:** Works with all data sources (SQL, APIs, logs, GitHub)

---

## Current State

**What Exists:**
- ✅ Basic limit parameter (default 100, max 1000)
- ✅ LayoutAnalyzer shows "showing first X" hint for large datasets
- ✅ `override_limit` parameter in API

**Limitations:**
- ❌ No offset parameter (can't paginate through results)
- ❌ No pagination metadata (frontend must calculate manually)
- ❌ `count` field returns len(results), not total available
- ❌ No has_next/has_previous flags

---

## Design Goals

1. **Support Web Interface** - Provide all metadata needed for pagination UI components
2. **Fast Performance** - Avoid expensive COUNT queries across diverse data sources
3. **Flexible Parameters** - Accept both page-based and offset-based styles
4. **Cache Efficient** - Cache pagination results without mixing pages
5. **Non-Breaking** - Existing CLI and API clients continue working

---

## Architecture

### Parameter Styles (Both Supported)

**Style 1: Page-Based (User-Friendly)**
```json
{
  "question": "Show orders",
  "page": 2,
  "page_size": 50
}
```

**Style 2: Offset-Based (Developer-Friendly)**
```json
{
  "question": "Show orders",
  "offset": 50,
  "limit": 50
}
```

**Normalization:** Convert page/page_size to offset/limit internally
```python
offset = (page - 1) * page_size
limit = page_size
```

**Priority:** If both styles provided, offset/limit takes precedence.

---

## Smart Estimation Strategy

**Problem:** COUNT queries are expensive, especially with complex filters.

**Solution:** Fetch limit+1 results to determine if more exist.

```python
# Fetch one extra result
results = queryset[offset:offset + limit + 1]

# Check if more results exist
has_next = len(results) > limit

# Trim to requested limit
if has_next:
    results = results[:limit]

has_previous = offset > 0
```

**Benefits:**
- Single query (no separate COUNT)
- Works with all data sources
- Provides has_next/has_previous flags
- Can estimate total count conservatively

**Trade-off:** No exact total count, but can provide "at least N results" estimates.

---

## Response Format

### Full Pagination Metadata

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
  "intent": {...},
  "cached": false
}
```

### Metadata Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `current_page` | int | Current page number (1-indexed) |
| `page_size` | int | Results per page |
| `offset` | int | Number of results skipped |
| `limit` | int | Maximum results in response |
| `has_next` | bool | More results available |
| `has_previous` | bool | Can navigate backwards |
| `next_page` | int? | Next page number (if has_next) |
| `previous_page` | int? | Previous page number (if has_previous) |
| `next_offset` | int? | Offset for next page (if has_next) |
| `previous_offset` | int? | Offset for previous page (if has_previous) |
| `estimated_total` | str/int | Total results ("100+" or exact on last page) |
| `estimated_total_pages` | str/int | Total pages ("3+" or exact on last page) |

---

## Metadata Calculation Logic

```python
def build_pagination_metadata(offset, limit, has_next, has_previous, result_count):
    """Build comprehensive pagination metadata."""
    current_page = (offset // limit) + 1

    metadata = {
        'current_page': current_page,
        'page_size': limit,
        'offset': offset,
        'limit': limit,
        'has_next': has_next,
        'has_previous': has_previous,
    }

    # Add next/previous helpers
    if has_next:
        metadata['next_page'] = current_page + 1
        metadata['next_offset'] = offset + limit

    if has_previous:
        metadata['previous_page'] = current_page - 1
        metadata['previous_offset'] = max(0, offset - limit)

    # Estimated totals (conservative)
    if has_next:
        # We know there are at least offset + result_count + 1
        min_total = offset + result_count + 1
        metadata['estimated_total'] = f"{min_total}+"
        metadata['estimated_total_pages'] = f"{current_page + 1}+"
    else:
        # This is the last page, exact total known
        exact_total = offset + result_count
        metadata['estimated_total'] = exact_total
        metadata['estimated_total_pages'] = current_page

    return metadata
```

---

## Cache Handling

### Updated Cache Key

**Before:**
```python
key = f"query:{entity}:{filters_hash}:{user}"
```

**After:**
```python
key = f"query:{entity}:{filters_hash}:{offset}:{limit}:{user}"
```

### Cache Behavior

- Each page is cached independently
- `page=1, page_size=50` and `offset=0, limit=50` → same cache entry
- Cache TTL remains per-entity (30s - 1hr)
- Cache invalidation clears all pages for an entity

**Example:**
```
Query: "Show orders" (page 1) → Cache key: ...offset:0:limit:100...
Query: "Show orders" (page 2) → Cache key: ...offset:100:limit:100...
Query: "Show orders" (page 1) → Cache hit!
```

**Trade-off:** More cache entries (one per page), but popular pages (page 1) benefit most.

---

## Data Flow

```
1. API Request
   POST /api/query
   {"question": "Show orders", "page": 2, "page_size": 50}
   ↓

2. Serializer Validation (api/serializers.py)
   - Validate page/page_size or offset/limit
   - Apply min/max constraints
   ↓

3. Parameter Normalization (api/views.py)
   - Convert page/page_size → offset/limit
   - Default: offset=0, limit=100
   ↓

4. Query Execution (core/query_executor.py)
   - Check cache (key includes offset/limit)
   - Fetch limit+1 results (smart estimation)
   - Determine has_next, has_previous
   - Trim to requested limit
   - Build pagination metadata
   - Cache result
   ↓

5. Layout Analysis (core/layout_analyzer.py)
   - Update summary with pagination info
   - "Found 245 orders (showing results 51-100)"
   ↓

6. Response
   {
     "results": [...],
     "count": 50,
     "pagination": {...}
   }
```

---

## Implementation Components

### 1. API Serializer (`api/serializers.py`)

**Add to QueryRequestSerializer:**
```python
# Page-based parameters
page = serializers.IntegerField(
    required=False,
    min_value=1,
    help_text="Page number (1-indexed)"
)
page_size = serializers.IntegerField(
    required=False,
    min_value=1,
    max_value=1000,
    default=100,
    help_text="Results per page"
)

# Offset-based parameters
offset = serializers.IntegerField(
    required=False,
    min_value=0,
    help_text="Number of results to skip"
)
limit = serializers.IntegerField(
    required=False,
    min_value=1,
    max_value=1000,
    help_text="Maximum results to return"
)
```

### 2. Parameter Normalization (`api/views.py`)

```python
def _normalize_pagination_params(self, validated_data):
    """Convert page/page_size to offset/limit."""
    # Priority: offset/limit takes precedence
    if 'offset' in validated_data or 'limit' in validated_data:
        offset = validated_data.get('offset', 0)
        limit = validated_data.get('limit', 100)
    else:
        page = validated_data.get('page', 1)
        page_size = validated_data.get('page_size', 100)
        offset = (page - 1) * page_size
        limit = page_size

    return offset, limit
```

### 3. Query Executor (`core/query_executor.py`)

**Update execute() signature:**
```python
def execute(self, intent: Dict[str, Any], user: str,
            offset: int = 0, limit: int = 100,
            bypass_cache: bool = False) -> Dict[str, Any]:
```

**Smart estimation logic:**
```python
# Fetch limit+1 for has_next detection
fetch_limit = limit + 1

if hasattr(queryset, '__getitem__'):
    results = list(queryset[offset:offset + fetch_limit])
else:
    results = list(queryset)[offset:offset + fetch_limit]

# Determine pagination state
has_next = len(results) > limit
if has_next:
    results = results[:limit]

has_previous = offset > 0

# Build pagination metadata
pagination = self._build_pagination_metadata(
    offset, limit, has_next, has_previous, len(results)
)
```

### 4. Cache Key Update (`core/cache.py`)

```python
@staticmethod
def get_cache_key(intent: Dict[str, Any], user: str,
                  offset: int = 0, limit: int = 100) -> str:
    """Generate cache key including pagination parameters."""
    entity = intent.get('entity', 'unknown')
    filters = intent.get('filters', {})
    filters_str = json.dumps(filters, sort_keys=True)
    filters_hash = hashlib.sha256(filters_str.encode()).hexdigest()[:16]

    return f"query:{entity}:{filters_hash}:{offset}:{limit}:{user}"
```

### 5. Layout Analyzer (`core/layout_analyzer.py`)

**Update summary text:**
```python
if count >= 5:
    # Use pagination metadata if available
    if 'pagination' in results:
        page = results['pagination']['current_page']
        start = results['pagination']['offset'] + 1
        end = start + count - 1
        summary = f'Found {results["pagination"]["estimated_total"]} {entity} (showing results {start}-{end})'
    else:
        # Fallback for non-paginated
        summary = f'Found {count} {entity}'
```

---

## Edge Cases & Error Handling

### Invalid Combinations

| Input | Behavior |
|-------|----------|
| `page=0` | Validation error (min_value=1) |
| `offset=-10` | Validation error (min_value=0) |
| `page_size=5000` | Validation error (max_value=1000) |
| `page=2, offset=50` | offset/limit wins (priority) |
| No pagination params | Default: offset=0, limit=100 |

### Last Page Handling

```python
# When has_next=False, we know exact total
if not has_next:
    metadata['estimated_total'] = offset + result_count  # Exact
    metadata['estimated_total_pages'] = current_page  # Exact
```

### Empty Results

```python
if result_count == 0:
    metadata['estimated_total'] = 0
    metadata['estimated_total_pages'] = 0
    metadata['has_next'] = False
```

### First Page Optimization

```python
if offset == 0:
    metadata['has_previous'] = False
    # No previous_page or previous_offset fields
```

---

## Testing Strategy

### Unit Tests

1. **Parameter Normalization**
   - page/page_size → offset/limit conversion
   - offset/limit passthrough
   - Priority (offset/limit wins)
   - Defaults

2. **Pagination Metadata**
   - has_next=True (more results exist)
   - has_next=False (last page)
   - has_previous=True (not first page)
   - has_previous=False (first page)
   - Estimated totals vs exact totals

3. **Smart Estimation**
   - Fetch limit+1 behavior
   - Trim to limit when has_next=True
   - Correct result count

4. **Cache Keys**
   - Offset/limit included in key
   - Different pages → different cache entries
   - Same page → cache hit

### Integration Tests

1. **End-to-End Pagination**
   - Query page 1 → results 1-50
   - Query page 2 → results 51-100
   - Query page 3 → results 101-150

2. **Cross-Parameter Style**
   - page=1, page_size=50
   - offset=0, limit=50
   - Both should return identical results

3. **Cache Behavior**
   - Page 1 cached
   - Page 2 different cache entry
   - Page 1 again → cache hit

### API Tests

1. **Valid Requests**
   - POST with page/page_size
   - POST with offset/limit
   - POST with no pagination (defaults)

2. **Invalid Requests**
   - page=0 → 400 Bad Request
   - offset=-1 → 400 Bad Request
   - page_size=10000 → 400 Bad Request

---

## Performance Considerations

### Query Performance

**Before:**
```sql
SELECT * FROM orders LIMIT 100;  -- Single query
```

**After:**
```sql
SELECT * FROM orders OFFSET 50 LIMIT 51;  -- Single query (limit+1)
```

**Impact:** Negligible (~1-2ms overhead for fetching 1 extra result)

### Cache Impact

**Cache Entries:**
- Before: 1 entry per query
- After: 1 entry per (query, page)

**Typical Usage:** Most users only view pages 1-3, so cache overhead is minimal.

**Cache Size:** With 10 entities × 3 pages = 30 cache entries (acceptable)

### Database Offset Performance

**Concern:** Large offsets can be slow (e.g., OFFSET 10000).

**Mitigation:**
- Max limit of 1000 constrains page depth
- Most users don't paginate past page 10
- Read-replica usage prevents impact on primary database

---

## Migration Path

### Phase 1: Add Pagination (This Design)
- Add pagination parameters
- Return pagination metadata
- Update cache keys
- Non-breaking (defaults preserve existing behavior)

### Phase 2: Web UI Integration (Separate Work)
- Build pagination components
- Use pagination metadata from API
- Previous/Next buttons
- Page number display

### Phase 3: Optimization (Future)
- Cursor-based pagination for deep paging (if needed)
- Pre-fetch next page for instant navigation
- Total count caching for popular queries

---

## Backward Compatibility

**Existing Behavior Preserved:**
- Requests without pagination params → offset=0, limit=100 (same as before)
- Response includes new `pagination` field (non-breaking addition)
- Existing fields unchanged (`results`, `count`, `response`, etc.)
- CLI works without modification
- Cache still works (new key format doesn't conflict)

**Breaking Changes:** None

---

## Success Criteria

✅ **Functional:**
- Users can paginate through results using page/page_size or offset/limit
- Pagination metadata includes all helper fields
- Smart estimation provides has_next/has_previous without COUNT query
- Cache correctly isolates different pages

✅ **Performance:**
- Single query per page (no COUNT overhead)
- < 5ms overhead for pagination logic
- Cache hit rate maintained for popular pages

✅ **Compatibility:**
- Existing API clients continue working (no breaking changes)
- Web UI can build pagination components from metadata
- Works with all data sources (SQL, APIs, logs, GitHub)

✅ **Testing:**
- 100% test coverage for pagination logic
- Integration tests for end-to-end pagination
- API tests for parameter validation

---

## Future Enhancements (Out of Scope)

**Cursor-Based Pagination:**
- For deep paging (> 100 pages)
- More efficient than large offsets
- Requires entity support for cursor fields

**Exact Total Counts:**
- Optional COUNT query for entities that support it
- Configurable per entity
- Trade-off: accuracy vs performance

**Pre-fetching:**
- Automatically fetch next page in background
- Instant page navigation
- Requires cache warming strategy

---

## References

- **Current Code:**
  - `api/views.py` - Query API endpoint
  - `api/serializers.py` - Request validation
  - `core/query_executor.py` - Query execution
  - `core/cache.py` - Redis caching
  - `core/layout_analyzer.py` - Response formatting

- **Related Features:**
  - Redis Caching (`CACHING.md`)
  - Multi-Entity Queries (`core/query_planner.py`)
  - Safety Validation (`core/safety.py`)

- **Standards:**
  - REST API pagination best practices
  - Django pagination patterns
  - Offset-based pagination
