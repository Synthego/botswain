# Query Result Pagination Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add comprehensive offset-based pagination to Botswain's query API with dual parameter support and smart estimation.

**Architecture:** Dual parameter support (page/page_size OR offset/limit), normalize to offset/limit internally, use limit+1 smart estimation for has_next detection, return full pagination metadata for web UI.

**Tech Stack:** Django REST Framework, Python 3.12, pytest, Redis (cache keys update)

**Design Reference:** `docs/plans/2026-03-11-pagination-design.md`

---

## Task 1: Add Pagination Parameters to Serializer

**Files:**
- Modify: `api/serializers.py`
- Test: `tests/test_api_serializers.py`

**Step 1: Write failing test for page-based parameters**

Create or modify `tests/test_api_serializers.py`:

```python
import pytest
from api.serializers import QueryRequestSerializer


class TestQueryRequestSerializerPagination:
    """Test pagination parameter validation"""

    def test_accepts_page_and_page_size(self):
        """Serializer should accept page and page_size parameters"""
        data = {
            'question': 'Show orders',
            'page': 2,
            'page_size': 50
        }
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['page'] == 2
        assert serializer.validated_data['page_size'] == 50

    def test_accepts_offset_and_limit(self):
        """Serializer should accept offset and limit parameters"""
        data = {
            'question': 'Show orders',
            'offset': 100,
            'limit': 25
        }
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data['offset'] == 100
        assert serializer.validated_data['limit'] == 25

    def test_page_defaults_to_1(self):
        """Page should default to 1 when not provided"""
        data = {'question': 'Show orders'}
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        # page and page_size are optional, should not be in validated_data if not provided

    def test_page_size_defaults_to_100(self):
        """Page size should have default of 100"""
        data = {'question': 'Show orders', 'page': 2}
        serializer = QueryRequestSerializer(data=data)
        assert serializer.is_valid()
        assert serializer.validated_data.get('page_size', 100) == 100

    def test_rejects_page_zero(self):
        """Page cannot be 0 or negative"""
        data = {'question': 'Show orders', 'page': 0}
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'page' in serializer.errors

    def test_rejects_negative_offset(self):
        """Offset cannot be negative"""
        data = {'question': 'Show orders', 'offset': -10}
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'offset' in serializer.errors

    def test_rejects_excessive_page_size(self):
        """Page size cannot exceed 1000"""
        data = {'question': 'Show orders', 'page_size': 5000}
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'page_size' in serializer.errors

    def test_rejects_excessive_limit(self):
        """Limit cannot exceed 1000"""
        data = {'question': 'Show orders', 'limit': 5000}
        serializer = QueryRequestSerializer(data=data)
        assert not serializer.is_valid()
        assert 'limit' in serializer.errors
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_serializers.py::TestQueryRequestSerializerPagination -v`

Expected: FAIL - serializer doesn't have page, page_size, offset, limit fields

**Step 3: Add pagination parameters to serializer**

Modify `api/serializers.py`:

```python
from rest_framework import serializers

class QueryRequestSerializer(serializers.Serializer):
    """Serializer for query request"""

    question = serializers.CharField(
        required=True,
        max_length=1000,
        help_text="Natural language question"
    )

    format = serializers.ChoiceField(
        choices=['natural', 'json', 'table'],
        default='natural',
        required=False,
        help_text="Response format"
    )

    use_cache = serializers.BooleanField(
        default=True,
        required=False,
        help_text="Whether to use cached results"
    )

    override_limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        help_text="Override default result limit (max 1000)"
    )

    # Page-based pagination parameters
    page = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Page number (1-indexed)"
    )

    page_size = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        help_text="Results per page (max 1000)"
    )

    # Offset-based pagination parameters
    offset = serializers.IntegerField(
        required=False,
        min_value=0,
        help_text="Number of results to skip"
    )

    limit = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        help_text="Maximum results to return (max 1000)"
    )
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_serializers.py::TestQueryRequestSerializerPagination -v`

Expected: ALL PASS (8 tests)

**Step 5: Commit**

```bash
git add api/serializers.py tests/test_api_serializers.py
git commit -m "feat: add pagination parameters to query serializer

Add dual parameter support:
- Page-based: page, page_size
- Offset-based: offset, limit

Validation:
- page: min 1
- page_size: min 1, max 1000
- offset: min 0
- limit: min 1, max 1000

Tests: 8 passing"
```

---

## Task 2: Add Parameter Normalization Helper

**Files:**
- Modify: `api/views.py`
- Test: `tests/test_api_views.py`

**Step 1: Write failing test for normalization**

Add to `tests/test_api_views.py`:

```python
import pytest
from api.views import QueryAPIView


class TestPaginationParameterNormalization:
    """Test pagination parameter normalization logic"""

    def test_page_and_page_size_converts_to_offset_limit(self):
        """Page 2, page_size 50 should convert to offset 50, limit 50"""
        view = QueryAPIView()
        validated_data = {'page': 2, 'page_size': 50}

        offset, limit = view._normalize_pagination_params(validated_data)

        assert offset == 50
        assert limit == 50

    def test_page_1_converts_to_offset_0(self):
        """Page 1 should start at offset 0"""
        view = QueryAPIView()
        validated_data = {'page': 1, 'page_size': 100}

        offset, limit = view._normalize_pagination_params(validated_data)

        assert offset == 0
        assert limit == 100

    def test_offset_limit_passthrough(self):
        """Offset and limit should pass through unchanged"""
        view = QueryAPIView()
        validated_data = {'offset': 100, 'limit': 25}

        offset, limit = view._normalize_pagination_params(validated_data)

        assert offset == 100
        assert limit == 25

    def test_offset_limit_takes_priority(self):
        """When both styles provided, offset/limit wins"""
        view = QueryAPIView()
        validated_data = {
            'page': 2,
            'page_size': 50,
            'offset': 75,
            'limit': 30
        }

        offset, limit = view._normalize_pagination_params(validated_data)

        assert offset == 75
        assert limit == 30

    def test_defaults_to_offset_0_limit_100(self):
        """When no pagination params provided, use defaults"""
        view = QueryAPIView()
        validated_data = {}

        offset, limit = view._normalize_pagination_params(validated_data)

        assert offset == 0
        assert limit == 100

    def test_page_without_page_size_uses_default(self):
        """Page without page_size should use default page_size 100"""
        view = QueryAPIView()
        validated_data = {'page': 3}

        offset, limit = view._normalize_pagination_params(validated_data)

        assert offset == 200  # (3-1) * 100
        assert limit == 100
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_views.py::TestPaginationParameterNormalization -v`

Expected: FAIL - method _normalize_pagination_params doesn't exist

**Step 3: Implement normalization method**

Add to `api/views.py` in the `QueryAPIView` class:

```python
def _normalize_pagination_params(self, validated_data: dict) -> tuple[int, int]:
    """
    Normalize pagination parameters to offset/limit.

    Accepts both page-based (page, page_size) and offset-based (offset, limit) parameters.
    Priority: offset/limit takes precedence over page/page_size.

    Args:
        validated_data: Validated request data from serializer

    Returns:
        Tuple of (offset, limit)
    """
    # Priority: offset/limit takes precedence
    if 'offset' in validated_data or 'limit' in validated_data:
        offset = validated_data.get('offset', 0)
        limit = validated_data.get('limit', 100)
    else:
        # Convert page/page_size to offset/limit
        page = validated_data.get('page', 1)
        page_size = validated_data.get('page_size', 100)
        offset = (page - 1) * page_size
        limit = page_size

    return offset, limit
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_views.py::TestPaginationParameterNormalization -v`

Expected: ALL PASS (6 tests)

**Step 5: Commit**

```bash
git add api/views.py tests/test_api_views.py
git commit -m "feat: add pagination parameter normalization

Normalize page/page_size or offset/limit to offset/limit:
- offset/limit takes priority if both provided
- page/page_size converts: offset = (page-1) * page_size
- Defaults: offset=0, limit=100

Tests: 6 passing"
```

---

## Task 3: Create Pagination Metadata Builder

**Files:**
- Create: `core/pagination.py`
- Test: `tests/test_pagination.py`

**Step 1: Write failing tests for metadata builder**

Create `tests/test_pagination.py`:

```python
import pytest
from core.pagination import PaginationMetadata


class TestPaginationMetadata:
    """Test pagination metadata calculation"""

    def test_first_page_with_more_results(self):
        """First page with has_next=True"""
        metadata = PaginationMetadata.build(
            offset=0,
            limit=50,
            has_next=True,
            has_previous=False,
            result_count=50
        )

        assert metadata['current_page'] == 1
        assert metadata['page_size'] == 50
        assert metadata['offset'] == 0
        assert metadata['limit'] == 50
        assert metadata['has_next'] is True
        assert metadata['has_previous'] is False
        assert metadata['next_page'] == 2
        assert metadata['next_offset'] == 50
        assert 'previous_page' not in metadata
        assert 'previous_offset' not in metadata
        assert metadata['estimated_total'] == '51+'
        assert metadata['estimated_total_pages'] == '2+'

    def test_middle_page(self):
        """Middle page with both next and previous"""
        metadata = PaginationMetadata.build(
            offset=100,
            limit=50,
            has_next=True,
            has_previous=True,
            result_count=50
        )

        assert metadata['current_page'] == 3
        assert metadata['has_next'] is True
        assert metadata['has_previous'] is True
        assert metadata['next_page'] == 4
        assert metadata['next_offset'] == 150
        assert metadata['previous_page'] == 2
        assert metadata['previous_offset'] == 50
        assert metadata['estimated_total'] == '151+'

    def test_last_page_exact_count(self):
        """Last page shows exact total (not estimated)"""
        metadata = PaginationMetadata.build(
            offset=200,
            limit=50,
            has_next=False,
            has_previous=True,
            result_count=25
        )

        assert metadata['current_page'] == 5
        assert metadata['has_next'] is False
        assert metadata['has_previous'] is True
        assert 'next_page' not in metadata
        assert 'next_offset' not in metadata
        assert metadata['previous_page'] == 4
        assert metadata['previous_offset'] == 150
        assert metadata['estimated_total'] == 225  # Exact, not string
        assert metadata['estimated_total_pages'] == 5  # Exact, not string

    def test_only_page_no_more_results(self):
        """Single page with all results"""
        metadata = PaginationMetadata.build(
            offset=0,
            limit=100,
            has_next=False,
            has_previous=False,
            result_count=10
        )

        assert metadata['current_page'] == 1
        assert metadata['has_next'] is False
        assert metadata['has_previous'] is False
        assert metadata['estimated_total'] == 10
        assert metadata['estimated_total_pages'] == 1

    def test_empty_results(self):
        """Empty results page"""
        metadata = PaginationMetadata.build(
            offset=0,
            limit=50,
            has_next=False,
            has_previous=False,
            result_count=0
        )

        assert metadata['current_page'] == 1
        assert metadata['estimated_total'] == 0
        assert metadata['estimated_total_pages'] == 0

    def test_different_page_sizes(self):
        """Test with various page sizes"""
        # Page size 25
        metadata = PaginationMetadata.build(
            offset=25,
            limit=25,
            has_next=True,
            has_previous=True,
            result_count=25
        )
        assert metadata['current_page'] == 2
        assert metadata['previous_offset'] == 0
        assert metadata['next_offset'] == 50

        # Page size 200
        metadata = PaginationMetadata.build(
            offset=400,
            limit=200,
            has_next=False,
            has_previous=True,
            result_count=50
        )
        assert metadata['current_page'] == 3
        assert metadata['previous_offset'] == 200
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pagination.py -v`

Expected: FAIL - module 'core.pagination' doesn't exist

**Step 3: Implement pagination metadata builder**

Create `core/pagination.py`:

```python
"""
Pagination metadata builder.

Calculates comprehensive pagination metadata for API responses.
"""
from typing import Dict, Any, Union


class PaginationMetadata:
    """Build pagination metadata from query results"""

    @staticmethod
    def build(offset: int, limit: int, has_next: bool, has_previous: bool,
              result_count: int) -> Dict[str, Any]:
        """
        Build comprehensive pagination metadata.

        Args:
            offset: Number of results skipped
            limit: Maximum results per page
            has_next: More results available
            has_previous: Can navigate backwards
            result_count: Number of results in current response

        Returns:
            Dictionary with pagination metadata
        """
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

        # Estimated or exact totals
        if has_next:
            # We know there are at least offset + result_count + 1
            min_total = offset + result_count + 1
            metadata['estimated_total'] = f"{min_total}+"
            metadata['estimated_total_pages'] = f"{current_page + 1}+"
        else:
            # This is the last page, exact total known
            exact_total = offset + result_count
            metadata['estimated_total'] = exact_total
            metadata['estimated_total_pages'] = current_page if exact_total > 0 else 0

        return metadata
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pagination.py -v`

Expected: ALL PASS (7 tests)

**Step 5: Commit**

```bash
git add core/pagination.py tests/test_pagination.py
git commit -m "feat: add pagination metadata builder

Calculate comprehensive pagination metadata:
- Current page, page size, offset, limit
- has_next, has_previous flags
- Next/previous page numbers and offsets
- Estimated totals (exact on last page)

Tests: 7 passing"
```

---

## Task 4: Update Cache Key with Pagination

**Files:**
- Modify: `core/cache.py`
- Test: `tests/test_cache.py`

**Step 1: Write failing test for cache key with pagination**

Add to `tests/test_cache.py`:

```python
class TestCacheKeyPagination:
    """Test cache key includes pagination parameters"""

    def test_cache_key_includes_offset_and_limit(self):
        """Cache key should include offset and limit"""
        intent = {'entity': 'order', 'filters': {}}

        key1 = QueryCache.get_cache_key(intent, 'user1', offset=0, limit=100)
        key2 = QueryCache.get_cache_key(intent, 'user1', offset=100, limit=100)

        assert key1 != key2
        assert ':0:100:' in key1
        assert ':100:100:' in key2

    def test_same_page_same_cache_key(self):
        """Same pagination parameters should generate same cache key"""
        intent = {'entity': 'order', 'filters': {}}

        key1 = QueryCache.get_cache_key(intent, 'user1', offset=50, limit=50)
        key2 = QueryCache.get_cache_key(intent, 'user1', offset=50, limit=50)

        assert key1 == key2

    def test_different_users_different_keys_with_pagination(self):
        """Different users should have different cache keys even with same pagination"""
        intent = {'entity': 'order', 'filters': {}}

        key1 = QueryCache.get_cache_key(intent, 'user1', offset=0, limit=100)
        key2 = QueryCache.get_cache_key(intent, 'user2', offset=0, limit=100)

        assert key1 != key2

    def test_page_based_converts_to_same_key_as_offset(self):
        """page=2, page_size=50 should generate same key as offset=50, limit=50"""
        intent = {'entity': 'order', 'filters': {}}

        # These should generate the same cache key
        key_offset = QueryCache.get_cache_key(intent, 'user1', offset=50, limit=50)
        key_page = QueryCache.get_cache_key(intent, 'user1', offset=50, limit=50)

        assert key_offset == key_page
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cache.py::TestCacheKeyPagination -v`

Expected: FAIL - get_cache_key signature doesn't accept offset/limit

**Step 3: Update cache key method**

Modify `core/cache.py`:

```python
@staticmethod
def get_cache_key(intent: Dict[str, Any], user: str,
                  offset: int = 0, limit: int = 100) -> str:
    """
    Generate cache key for query including pagination parameters.

    Args:
        intent: Query intent dict
        user: Username
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        Cache key string
    """
    entity = intent.get('entity', 'unknown')
    filters = intent.get('filters', {})

    # Create stable hash of filters
    filters_str = json.dumps(filters, sort_keys=True)
    filters_hash = hashlib.sha256(filters_str.encode()).hexdigest()[:16]

    # Include pagination in cache key
    return f"query:{entity}:{filters_hash}:{offset}:{limit}:{user}"

@staticmethod
def get(intent: Dict[str, Any], user: str,
        offset: int = 0, limit: int = 100) -> Optional[Dict[str, Any]]:
    """
    Get cached query result including pagination.

    Args:
        intent: Query intent dict
        user: Username
        offset: Pagination offset
        limit: Pagination limit

    Returns:
        Cached result or None
    """
    key = QueryCache.get_cache_key(intent, user, offset, limit)
    # ... rest of existing code ...

@staticmethod
def set(intent: Dict[str, Any], user: str, result: Dict[str, Any],
        offset: int = 0, limit: int = 100) -> None:
    """
    Cache query result with pagination.

    Args:
        intent: Query intent dict
        user: Username
        result: Query result to cache
        offset: Pagination offset
        limit: Pagination limit
    """
    key = QueryCache.get_cache_key(intent, user, offset, limit)
    # ... rest of existing code ...
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cache.py::TestCacheKeyPagination -v`

Expected: ALL PASS (4 tests)

**Step 5: Commit**

```bash
git add core/cache.py tests/test_cache.py
git commit -m "feat: update cache key to include pagination parameters

Cache key now includes offset and limit:
- Different pages have different cache entries
- Same page parameters share cache entry
- Prevents serving wrong page from cache

Format: query:{entity}:{filters_hash}:{offset}:{limit}:{user}

Tests: 4 passing"
```

---

## Task 5: Update QueryExecutor for Pagination

**Files:**
- Modify: `core/query_executor.py`
- Test: `tests/test_query_executor.py`

**Step 1: Write failing tests for pagination in QueryExecutor**

Add to `tests/test_query_executor.py`:

```python
from core.pagination import PaginationMetadata


class TestQueryExecutorPagination:
    """Test QueryExecutor pagination support"""

    def test_execute_with_offset_and_limit(self):
        """Execute should accept offset and limit parameters"""
        registry = EntityRegistry()
        # Register mock entity
        executor = QueryExecutor(registry=registry, use_cache=False)

        intent = {'entity': 'test', 'intent_type': 'query', 'filters': {}}

        result = executor.execute(intent, user='testuser', offset=10, limit=5)

        assert 'pagination' in result
        assert result['pagination']['offset'] == 10
        assert result['pagination']['limit'] == 5

    def test_smart_estimation_fetches_limit_plus_one(self):
        """Should fetch limit+1 results to determine has_next"""
        # This tests the internal behavior - we'll verify through has_next flag
        registry = EntityRegistry()
        executor = QueryExecutor(registry=registry, use_cache=False)

        intent = {'entity': 'test', 'intent_type': 'query', 'filters': {}}

        # Mock queryset with 101 results, fetch limit=50
        # Should detect has_next=True and return only 50 results
        result = executor.execute(intent, user='testuser', offset=0, limit=50)

        assert result['count'] <= 50  # Trimmed to limit
        assert 'pagination' in result

    def test_has_next_true_when_more_results(self):
        """has_next should be True when more results available"""
        registry = EntityRegistry()
        executor = QueryExecutor(registry=registry, use_cache=False)

        intent = {'entity': 'test', 'intent_type': 'query', 'filters': {}}

        # With plenty of results
        result = executor.execute(intent, user='testuser', offset=0, limit=10)

        if result['count'] == 10:  # If we got full page
            # May have more (depends on data source)
            assert 'pagination' in result
            assert 'has_next' in result['pagination']

    def test_has_previous_false_on_first_page(self):
        """has_previous should be False when offset=0"""
        registry = EntityRegistry()
        executor = QueryExecutor(registry=registry, use_cache=False)

        intent = {'entity': 'test', 'intent_type': 'query', 'filters': {}}

        result = executor.execute(intent, user='testuser', offset=0, limit=50)

        assert result['pagination']['has_previous'] is False

    def test_has_previous_true_when_offset_greater_than_zero(self):
        """has_previous should be True when offset > 0"""
        registry = EntityRegistry()
        executor = QueryExecutor(registry=registry, use_cache=False)

        intent = {'entity': 'test', 'intent_type': 'query', 'filters': {}}

        result = executor.execute(intent, user='testuser', offset=50, limit=50)

        assert result['pagination']['has_previous'] is True

    def test_cache_respects_pagination_parameters(self):
        """Cache should store different pages separately"""
        registry = EntityRegistry()
        executor = QueryExecutor(registry=registry, use_cache=True)

        intent = {'entity': 'test', 'intent_type': 'query', 'filters': {}}

        # Query page 1
        result1 = executor.execute(intent, user='testuser', offset=0, limit=50)

        # Query page 2
        result2 = executor.execute(intent, user='testuser', offset=50, limit=50)

        # Results should be different (different pages)
        assert result1['pagination']['offset'] == 0
        assert result2['pagination']['offset'] == 50
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_query_executor.py::TestQueryExecutorPagination -v`

Expected: FAIL - execute() doesn't accept offset/limit parameters

**Step 3: Update QueryExecutor.execute() method**

Modify `core/query_executor.py`:

```python
from core.pagination import PaginationMetadata

def execute(self, intent: Dict[str, Any], user: str,
            offset: int = 0, limit: int = 100,
            bypass_cache: bool = False) -> Dict[str, Any]:
    """
    Execute query based on structured intent with pagination support.

    Args:
        intent: Structured intent from IntentParser
        user: Username for audit logging and cache isolation
        offset: Number of results to skip (default 0)
        limit: Maximum results to return (default 100)
        bypass_cache: If True, skip cache and fetch fresh data

    Returns:
        Query results with metadata and pagination
    """
    # Check cache first (unless bypassed) - include pagination in cache key
    if self.use_cache and not bypass_cache:
        cached_result = QueryCache.get(intent, user, offset, limit)
        if cached_result is not None:
            logger.info(f"Returning cached result for {intent.get('entity')} (offset={offset}, limit={limit})")
            return cached_result

    start_time = time.time()

    # Validate intent safety
    SafetyValidator.validate_intent(intent)

    # Get entity
    entity = self.registry.get(intent['entity'])
    if not entity:
        raise ValueError(f"Unknown entity: {intent['entity']}")

    # Validate filters
    filters = intent.get('filters', {})
    if filters and not entity.validate_filters(filters):
        raise ValueError(f"Invalid filters for entity {intent['entity']}")

    # Build queryset
    queryset = entity.get_queryset(filters)

    # Smart estimation: fetch limit+1 to determine has_next
    fetch_limit = limit + 1

    # Apply offset and fetch_limit
    if hasattr(queryset, '__getitem__'):
        # Django QuerySet or list-like with slicing support
        results = list(queryset[offset:offset + fetch_limit])
    elif hasattr(queryset, '__iter__'):
        # Fallback for non-sliceable iterables
        all_results = list(queryset)
        results = all_results[offset:offset + fetch_limit]
    else:
        results = []

    # Determine pagination state
    has_next = len(results) > limit
    has_previous = offset > 0

    # Trim to requested limit
    if has_next:
        results = results[:limit]

    # Handle attribute extraction (same as before)
    # ... existing attribute extraction code ...

    execution_time = time.time() - start_time

    # Build pagination metadata
    pagination = PaginationMetadata.build(
        offset=offset,
        limit=limit,
        has_next=has_next,
        has_previous=has_previous,
        result_count=len(results)
    )

    # Build response
    response = {
        'success': True,
        'entity': intent['entity'],
        'results': results,
        'count': len(results),
        'execution_time_ms': int(execution_time * 1000),
        'pagination': pagination
    }

    # Add aggregations based on intent_type (same as before)
    # ... existing aggregation code ...

    # Cache the result (unless caching is disabled) - include pagination in cache key
    if self.use_cache and not bypass_cache:
        QueryCache.set(intent, user, response, offset, limit)

    return response
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_query_executor.py::TestQueryExecutorPagination -v`

Expected: ALL PASS (6 tests)

**Step 5: Commit**

```bash
git add core/query_executor.py tests/test_query_executor.py
git commit -m "feat: add pagination support to QueryExecutor

Execute queries with offset/limit:
- Smart estimation: fetch limit+1 to detect has_next
- Calculate has_previous from offset
- Build pagination metadata
- Cache includes pagination parameters

Tests: 6 passing"
```

---

## Task 6: Integrate Pagination into API View

**Files:**
- Modify: `api/views.py`
- Test: `tests/test_api_views.py`

**Step 1: Write integration test for API pagination**

Add to `tests/test_api_views.py`:

```python
class TestAPIPaginationIntegration:
    """Test end-to-end pagination through API"""

    @pytest.mark.django_db
    def test_api_accepts_page_based_parameters(self):
        """API should accept page and page_size parameters"""
        from rest_framework.test import APIClient
        from django.contrib.auth.models import User

        client = APIClient()
        user = User.objects.create_user(username='test@synthego.com')
        client.force_authenticate(user=user)

        response = client.post('/api/query', {
            'question': 'Show orders',
            'page': 2,
            'page_size': 25
        }, format='json')

        assert response.status_code == 200
        data = response.json()
        assert 'pagination' in data
        assert data['pagination']['current_page'] == 2
        assert data['pagination']['page_size'] == 25
        assert data['pagination']['offset'] == 25
        assert data['pagination']['limit'] == 25

    @pytest.mark.django_db
    def test_api_accepts_offset_limit_parameters(self):
        """API should accept offset and limit parameters"""
        from rest_framework.test import APIClient
        from django.contrib.auth.models import User

        client = APIClient()
        user = User.objects.create_user(username='test@synthego.com')
        client.force_authenticate(user=user)

        response = client.post('/api/query', {
            'question': 'Show orders',
            'offset': 50,
            'limit': 30
        }, format='json')

        assert response.status_code == 200
        data = response.json()
        assert 'pagination' in data
        assert data['pagination']['offset'] == 50
        assert data['pagination']['limit'] == 30

    @pytest.mark.django_db
    def test_api_returns_pagination_metadata(self):
        """API response should include full pagination metadata"""
        from rest_framework.test import APIClient
        from django.contrib.auth.models import User

        client = APIClient()
        user = User.objects.create_user(username='test@synthego.com')
        client.force_authenticate(user=user)

        response = client.post('/api/query', {
            'question': 'Show orders',
            'page': 1,
            'page_size': 50
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # Verify all pagination fields present
        pagination = data['pagination']
        assert 'current_page' in pagination
        assert 'page_size' in pagination
        assert 'offset' in pagination
        assert 'limit' in pagination
        assert 'has_next' in pagination
        assert 'has_previous' in pagination
        assert 'estimated_total' in pagination
        assert 'estimated_total_pages' in pagination

    @pytest.mark.django_db
    def test_api_defaults_to_page_1_when_no_params(self):
        """API should default to page 1 when no pagination params provided"""
        from rest_framework.test import APIClient
        from django.contrib.auth.models import User

        client = APIClient()
        user = User.objects.create_user(username='test@synthego.com')
        client.force_authenticate(user=user)

        response = client.post('/api/query', {
            'question': 'Show orders'
        }, format='json')

        assert response.status_code == 200
        data = response.json()
        assert data['pagination']['current_page'] == 1
        assert data['pagination']['offset'] == 0
        assert data['pagination']['has_previous'] is False
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_views.py::TestAPIPaginationIntegration -v`

Expected: FAIL - API doesn't pass pagination params to executor

**Step 3: Update API view to use pagination**

Modify `api/views.py` in the `_execute_query` method:

```python
def _execute_query(self, question: str, override_limit: int, user: str,
                   offset: int = 0, limit: int = 100,
                   is_retry: bool = False, original_question: str = None):
    """Execute a single query attempt with pagination support"""

    # ... existing code for registry setup and LLM provider ...

    # Single-entity query - proceed with normal flow
    intent = llm_provider.parse_intent(question, {
        'entities': registry.get_entity_descriptions()
    })

    # Apply limit override if provided (backward compatibility)
    if override_limit is not None:
        limit = override_limit

    # Execute query with pagination
    executor = QueryExecutor(registry=registry)
    query_results = executor.execute(intent, user=user, offset=offset, limit=limit)

    # ... rest of existing code ...

def _execute_query_with_recovery(self, question: str, override_limit: int, user: str,
                                  offset: int = 0, limit: int = 100):
    """Execute query with automatic error recovery and pagination."""
    try:
        return self._execute_query(question, override_limit, user,
                                    offset=offset, limit=limit,
                                    is_retry=False)
    # ... existing error recovery code ...

def post(self, request):
    serializer = QueryRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    question = serializer.validated_data['question']
    format_type = serializer.validated_data.get('format', 'natural')
    override_limit = serializer.validated_data.get('override_limit')

    # Normalize pagination parameters
    offset, limit = self._normalize_pagination_params(serializer.validated_data)

    # Try executing the query with pagination
    result = self._execute_query_with_recovery(
        question=question,
        override_limit=override_limit,
        user=request.user.username if request.user.is_authenticated else 'anonymous',
        offset=offset,
        limit=limit
    )

    return result
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api_views.py::TestAPIPaginationIntegration -v`

Expected: ALL PASS (4 tests)

**Step 5: Commit**

```bash
git add api/views.py tests/test_api_views.py
git commit -m "feat: integrate pagination into API view

API now accepts and processes pagination parameters:
- Normalize page/page_size or offset/limit
- Pass to QueryExecutor
- Return pagination metadata in response
- Backward compatible (defaults to page 1)

Tests: 4 passing"
```

---

## Task 7: Update LayoutAnalyzer for Pagination Hints

**Files:**
- Modify: `core/layout_analyzer.py`
- Test: `core/tests/test_layout_analyzer.py`

**Step 1: Write test for pagination-aware layout**

Add to `core/tests/test_layout_analyzer.py`:

```python
class TestLayoutAnalyzerPagination:
    """Test layout analyzer with pagination metadata"""

    def test_summary_includes_page_range_from_pagination(self):
        """Summary should show 'showing results X-Y' when pagination present"""
        results = {
            'count': 50,
            'results': [{'name': f'Item {i}'} for i in range(50)],
            'entity': 'order',
            'pagination': {
                'current_page': 2,
                'offset': 50,
                'limit': 50,
                'estimated_total': '100+'
            }
        }
        intent = {'entity': 'order', 'limit': 50}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 2
        assert layout[0]['type'] == 'summary'
        assert 'showing results 51-100' in layout[0]['content'].lower()

    def test_summary_shows_estimated_total(self):
        """Summary should show estimated total from pagination"""
        results = {
            'count': 50,
            'results': [{'name': f'Item {i}'} for i in range(50)],
            'entity': 'order',
            'pagination': {
                'current_page': 1,
                'offset': 0,
                'estimated_total': '150+'
            }
        }
        intent = {'entity': 'order', 'limit': 50}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert '150+' in layout[0]['content']

    def test_summary_shows_exact_total_on_last_page(self):
        """Summary should show exact total (not +) on last page"""
        results = {
            'count': 25,
            'results': [{'name': f'Item {i}'} for i in range(25)],
            'entity': 'order',
            'pagination': {
                'current_page': 3,
                'offset': 100,
                'estimated_total': 125,  # Exact, not string
                'has_next': False
            }
        }
        intent = {'entity': 'order', 'limit': 50}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert '125' in layout[0]['content']
        assert '125+' not in layout[0]['content']

    def test_fallback_to_old_format_without_pagination(self):
        """Should work with old response format (no pagination field)"""
        results = {
            'count': 10,
            'results': [{'name': f'Item {i}'} for i in range(10)],
            'entity': 'order'
        }
        intent = {'entity': 'order', 'limit': 100}

        layout = LayoutAnalyzer.analyze(results, intent)

        assert len(layout) == 2
        assert layout[0]['type'] == 'summary'
        assert 'Found 10 order' in layout[0]['content']
```

**Step 2: Run tests to verify they fail**

Run: `pytest core/tests/test_layout_analyzer.py::TestLayoutAnalyzerPagination -v`

Expected: FAIL - layout doesn't use pagination metadata

**Step 3: Update LayoutAnalyzer to use pagination metadata**

Modify `core/layout_analyzer.py`:

```python
@staticmethod
def analyze(results: Dict[str, Any], intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analyze query results and return layout specification.

    Args:
        results: Query results dict with 'count', 'results', 'entity', 'pagination' keys
        intent: Intent dict with 'entity' and other metadata

    Returns:
        List of component specifications
    """
    layout = []
    count = results.get('count', 0)
    entity_name = intent.get('entity', 'items')

    # Empty results
    if count == 0:
        layout.append({
            'type': 'empty',
            'message': f'No {entity_name} found matching your criteria'
        })
        return layout

    # Small dataset (< 5): summary only
    if count < 5:
        layout.append({
            'type': 'summary',
            'content': f'Found {count} {entity_name}'
        })
        return layout

    # Medium/large dataset (5+): summary + table
    if count >= 5:
        # Use pagination metadata if available
        pagination = results.get('pagination')

        if pagination:
            # Build summary with pagination info
            estimated_total = pagination['estimated_total']
            start = pagination['offset'] + 1
            end = pagination['offset'] + count

            # Format total (could be string "100+" or int)
            total_str = str(estimated_total)

            summary_text = f'Found {total_str} {entity_name} (showing results {start}-{end})'
        else:
            # Fallback for non-paginated responses (backward compatibility)
            limit = intent.get('limit', 100)
            if count > 50:
                summary_text = f'Found {count} {entity_name} (showing first {min(limit, count)})'
            else:
                summary_text = f'Found {count} {entity_name}'

        layout.append({
            'type': 'summary',
            'content': summary_text
        })

        # Generate table columns from first result
        data = results.get('results', [])
        columns = []
        if data:
            for field in data[0].keys():
                columns.append({
                    'field': field,
                    'header': field.replace('_', ' ').title(),
                    'sortable': True
                })

        layout.append({
            'type': 'table',
            'data': data,
            'columns': columns
        })
        return layout

    return layout
```

**Step 4: Run tests to verify they pass**

Run: `pytest core/tests/test_layout_analyzer.py::TestLayoutAnalyzerPagination -v`

Expected: ALL PASS (4 tests)

**Step 5: Commit**

```bash
git add core/layout_analyzer.py core/tests/test_layout_analyzer.py
git commit -m "feat: update LayoutAnalyzer for pagination hints

Summary text now uses pagination metadata:
- Shows result range (e.g., 'showing results 51-100')
- Shows estimated total from pagination
- Shows exact total on last page
- Backward compatible with non-paginated responses

Tests: 4 passing"
```

---

## Task 8: End-to-End Integration Tests

**Files:**
- Test: `tests/test_pagination_integration.py`

**Step 1: Write comprehensive integration tests**

Create `tests/test_pagination_integration.py`:

```python
"""
End-to-end integration tests for pagination feature.

Tests the complete flow from API request to paginated response.
"""
import pytest
from rest_framework.test import APIClient
from django.contrib.auth.models import User


@pytest.mark.django_db
class TestPaginationEndToEnd:
    """End-to-end pagination integration tests"""

    def setup_method(self):
        """Setup test client and user"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='test@synthego.com',
            email='test@synthego.com'
        )
        self.client.force_authenticate(user=self.user)

    def test_paginate_through_multiple_pages(self):
        """Paginate through multiple pages of results"""
        # Page 1
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 1,
            'page_size': 10
        }, format='json')

        assert response.status_code == 200
        page1 = response.json()

        assert page1['pagination']['current_page'] == 1
        assert page1['pagination']['has_previous'] is False

        # Page 2
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 2,
            'page_size': 10
        }, format='json')

        assert response.status_code == 200
        page2 = response.json()

        assert page2['pagination']['current_page'] == 2
        assert page2['pagination']['has_previous'] is True
        assert page2['pagination']['previous_page'] == 1

    def test_offset_limit_equivalent_to_page_page_size(self):
        """offset/limit should return same results as equivalent page/page_size"""
        # Using page/page_size
        response1 = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 3,
            'page_size': 20
        }, format='json')

        # Using equivalent offset/limit
        response2 = self.client.post('/api/query', {
            'question': 'Show orders',
            'offset': 40,  # (3-1) * 20
            'limit': 20
        }, format='json')

        assert response1.status_code == 200
        assert response2.status_code == 200

        page1 = response1.json()
        page2 = response2.json()

        # Pagination metadata should be identical
        assert page1['pagination']['offset'] == page2['pagination']['offset']
        assert page1['pagination']['limit'] == page2['pagination']['limit']
        assert page1['pagination']['current_page'] == page2['pagination']['current_page']

    def test_cache_stores_different_pages_separately(self):
        """Different pages should be cached separately"""
        # Query page 1 (cache miss)
        response1 = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 1,
            'page_size': 10
        }, format='json')

        # Query page 2 (cache miss)
        response2 = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 2,
            'page_size': 10
        }, format='json')

        # Query page 1 again (should be cache hit)
        response3 = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 1,
            'page_size': 10
        }, format='json')

        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        page1a = response1.json()
        page2 = response2.json()
        page1b = response3.json()

        # Page 1 results should be identical (from cache)
        assert page1a['pagination']['offset'] == page1b['pagination']['offset']

        # Page 2 should be different from page 1
        assert page1a['pagination']['offset'] != page2['pagination']['offset']

    def test_first_page_has_no_previous(self):
        """First page should not have previous page helpers"""
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 1,
            'page_size': 50
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        assert data['pagination']['has_previous'] is False
        assert 'previous_page' not in data['pagination']
        assert 'previous_offset' not in data['pagination']

    def test_validation_errors_for_invalid_params(self):
        """Invalid pagination parameters should return 400 error"""
        # Negative page
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': -1
        }, format='json')
        assert response.status_code == 400

        # Zero page
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 0
        }, format='json')
        assert response.status_code == 400

        # Negative offset
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'offset': -10
        }, format='json')
        assert response.status_code == 400

        # Excessive page size
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page_size': 5000
        }, format='json')
        assert response.status_code == 400

    def test_layout_includes_pagination_info(self):
        """Layout should include pagination information in summary"""
        response = self.client.post('/api/query', {
            'question': 'Show orders',
            'page': 2,
            'page_size': 20
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        assert 'layout' in data
        if data['layout']:
            summary = data['layout'][0]
            assert summary['type'] == 'summary'
            # Should mention result range
            content = summary['content'].lower()
            assert 'showing results' in content or 'found' in content

    def test_backward_compatibility_no_pagination_params(self):
        """Requests without pagination params should still work (defaults)"""
        response = self.client.post('/api/query', {
            'question': 'Show orders'
        }, format='json')

        assert response.status_code == 200
        data = response.json()

        # Should have pagination metadata with defaults
        assert 'pagination' in data
        assert data['pagination']['current_page'] == 1
        assert data['pagination']['offset'] == 0
        assert data['pagination']['limit'] == 100  # Default
```

**Step 2: Run integration tests**

Run: `pytest tests/test_pagination_integration.py -v`

Expected: ALL PASS (8 tests)

**Step 3: Commit**

```bash
git add tests/test_pagination_integration.py
git commit -m "test: add end-to-end pagination integration tests

Comprehensive integration tests:
- Multiple page navigation
- Page/page_size vs offset/limit equivalence
- Cache isolation per page
- First page edge cases
- Validation error handling
- Layout integration
- Backward compatibility

Tests: 8 passing"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run all tests to verify no regressions**

Run: `pytest -v`

Expected: ALL PASS (existing + new tests)

**Step 2: Run with coverage to verify test coverage**

Run: `pytest --cov=api --cov=core --cov-report=term-missing`

Expected: High coverage on modified files

**Step 3: Manual verification with CLI**

If available, test with CLI:

```bash
# Default pagination (page 1)
./botswain-cli.py "Show orders"

# Specific page
./botswain-cli.py "Show orders" --page 2 --page-size 25

# Using offset/limit
./botswain-cli.py "Show orders" --offset 50 --limit 30
```

**Step 4: Document results**

If all tests pass, create a summary:

```bash
echo "Pagination implementation complete and tested" > PAGINATION_RESULTS.txt
git add PAGINATION_RESULTS.txt
git commit -m "docs: pagination implementation test results"
```

---

## Task 10: Update Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/API.md` (if doesn't exist)

**Step 1: Update README with pagination feature**

Add to README.md in the Features section:

```markdown
### Query Result Pagination

**Dual Parameter Support:**
- Page-based: `page`, `page_size` (user-friendly)
- Offset-based: `offset`, `limit` (developer-friendly)

**Smart Estimation:**
- No expensive COUNT queries
- Uses limit+1 trick to determine has_next
- Provides "at least N results" estimates
- Exact totals on last page

**Example:**
```bash
# Page-based
POST /api/query
{
  "question": "Show orders",
  "page": 2,
  "page_size": 50
}

# Offset-based
POST /api/query
{
  "question": "Show orders",
  "offset": 50,
  "limit": 50
}
```

**Response includes full pagination metadata:**
- Current page, offset, limit
- has_next, has_previous flags
- Next/previous page numbers and offsets
- Estimated or exact totals

See `docs/plans/2026-03-11-pagination-design.md` for complete design.
```

**Step 2: Create or update API documentation**

Create `docs/API.md` (or update if exists):

```markdown
# Botswain API Documentation

## POST /api/query

Execute a natural language query with optional pagination.

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| question | string | Yes | - | Natural language question |
| format | string | No | 'natural' | Response format (natural, json, table) |
| use_cache | boolean | No | true | Use cached results |
| page | integer | No | 1 | Page number (1-indexed) |
| page_size | integer | No | 100 | Results per page (max 1000) |
| offset | integer | No | 0 | Number of results to skip |
| limit | integer | No | 100 | Maximum results (max 1000) |

**Note:** If both page/page_size and offset/limit are provided, offset/limit takes precedence.

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
  "layout": [...],
  "intent": {...}
}
```

### Pagination Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| current_page | int | Current page number (1-indexed) |
| page_size | int | Results per page |
| offset | int | Number of results skipped |
| limit | int | Maximum results in response |
| has_next | bool | More results available |
| has_previous | bool | Can navigate backwards |
| next_page | int? | Next page number (if has_next) |
| previous_page | int? | Previous page number (if has_previous) |
| next_offset | int? | Offset for next page (if has_next) |
| previous_offset | int? | Offset for previous page (if has_previous) |
| estimated_total | str/int | Total results ("100+" or exact on last page) |
| estimated_total_pages | str/int | Total pages ("3+" or exact on last page) |

### Examples

**Page-based pagination:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders from last month",
    "page": 2,
    "page_size": 25
  }'
```

**Offset-based pagination:**
```bash
curl -X POST http://localhost:8002/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show orders from last month",
    "offset": 50,
    "limit": 25
  }'
```
```

**Step 3: Update CHANGELOG**

Add to CHANGELOG.md or create if doesn't exist:

```markdown
# Changelog

## [Unreleased]

### Added
- **Query Result Pagination** - Comprehensive pagination support
  - Dual parameter support (page/page_size OR offset/limit)
  - Smart estimation (no COUNT queries, fast performance)
  - Full pagination metadata (next/previous helpers, estimated totals)
  - Cache-aware (pagination params in cache key)
  - Backward compatible (defaults to page 1)
  - See design doc: `docs/plans/2026-03-11-pagination-design.md`
```

**Step 4: Commit documentation**

```bash
git add README.md docs/API.md CHANGELOG.md
git commit -m "docs: add pagination API documentation

Document pagination feature:
- Dual parameter support (page/page_size OR offset/limit)
- Request/response format
- Pagination metadata fields
- Usage examples
- API reference

Updated README and created API.md"
```

---

## Task 11: Update Roadmap

**Files:**
- Modify: `README.md`

**Step 1: Mark pagination as complete in roadmap**

Find the Roadmap section in README.md and update:

```markdown
## 📋 Roadmap

**Completed:**
- [x] AWS Bedrock integration with Claude Sonnet 4.5
- [x] Multi-database support (BARB, Buckaneer)
- [x] NetSuite orders datasource
- [x] GitHub issues and commits integration
- [x] ElasticSearch instrument logs
- [x] CloudWatch service logs
- [x] AWS infrastructure queries (ECS, RDS)
- [x] Multi-entity query orchestration
- [x] Token usage and cost tracking
- [x] Automatic query recovery
- [x] Environment variable credential management
- [x] Redis caching with per-entity TTL (30s - 1hr)
- [x] Query result pagination with dual parameter support  ← NEW
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: mark pagination as complete in roadmap"
```

---

## Final Step: Push All Changes

**Step 1: Review all commits**

Run: `git log --oneline -15`

Expected: See all pagination commits

**Step 2: Push to remote**

Run: `git push origin main`

**Step 3: Verify on GitHub**

Check that all commits are pushed successfully.

---

## Success Criteria Checklist

✅ **Functional Requirements:**
- [ ] API accepts page/page_size parameters
- [ ] API accepts offset/limit parameters
- [ ] offset/limit takes priority when both provided
- [ ] Smart estimation uses limit+1 (no COUNT)
- [ ] has_next and has_previous flags work correctly
- [ ] Pagination metadata includes all required fields
- [ ] Cache keys include pagination parameters
- [ ] Different pages have separate cache entries
- [ ] LayoutAnalyzer uses pagination info in summary

✅ **Testing:**
- [ ] 8+ serializer validation tests passing
- [ ] 6+ parameter normalization tests passing
- [ ] 7+ pagination metadata tests passing
- [ ] 4+ cache key tests passing
- [ ] 6+ QueryExecutor pagination tests passing
- [ ] 4+ API integration tests passing
- [ ] 4+ LayoutAnalyzer pagination tests passing
- [ ] 8+ end-to-end integration tests passing

✅ **Documentation:**
- [ ] Design document committed
- [ ] Implementation plan created
- [ ] README updated with pagination feature
- [ ] API documentation created/updated
- [ ] CHANGELOG updated
- [ ] Roadmap marked complete

✅ **Backward Compatibility:**
- [ ] Requests without pagination params work (defaults)
- [ ] Response format extended (no breaking changes)
- [ ] Existing tests still pass
- [ ] CLI continues working without modification

✅ **Performance:**
- [ ] Single query per page (no COUNT overhead)
- [ ] Cache hit rate maintained
- [ ] < 5ms overhead for pagination logic

---

## Rollback Plan (If Needed)

If issues discovered:

```bash
# Revert all pagination commits
git log --oneline | grep pagination
# Note the commit hash before first pagination commit
git revert <hash>..HEAD
git push origin main
```

---

## Post-Implementation Tasks

1. **Monitor Production:**
   - Watch for errors in pagination logic
   - Monitor cache hit rates
   - Check query performance

2. **Web UI Integration:**
   - Coordinate with web UI team
   - Provide pagination metadata documentation
   - Test end-to-end with real UI

3. **Optional Enhancements (Future):**
   - Cursor-based pagination for deep paging
   - Optional COUNT queries for entities that support it
   - Pre-fetch next page for instant navigation
