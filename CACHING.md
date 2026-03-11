# Botswain Redis Caching

## Overview

Botswain uses Redis caching to improve performance and reduce load on backend systems. Each datasource has a configured TTL (Time To Live) based on how frequently the data changes.

**Benefits**:
- ⚡ Faster response times for repeated queries
- 💰 Reduced load on production databases and APIs
- 📊 Lower AWS Bedrock token usage (cached responses)

---

## Cache TTL Configuration

Cache TTLs are configured per entity in `botswain/settings/base.py`:

| Entity | TTL | Rationale |
|--------|-----|-----------|
| **synthesizer** | 30s | Status changes frequently (running/idle) |
| **instrument** | 30s | Status changes frequently (running/idle) |
| **workflow** | 60s | Execution status changes actively |
| **ecs_service** | 60s | Deployment status needs to be current |
| **order** | 5 min | Orders rarely change once placed |
| **netsuite_order** | 10 min | Synced from external system |
| **github_issue** | 5 min | Can tolerate some staleness |
| **rds_database** | 5 min | Metrics update periodically |
| **git_commit** | 1 hour | Historical data, doesn't change |

### Configuration

```python
# botswain/settings/base.py
ENTITY_CACHE_TTL = {
    'synthesizer': 30,
    'instrument': 30,
    'workflow': 60,
    'ecs_service': 60,
    'order': 300,
    'netsuite_order': 600,
    'github_issue': 300,
    'rds_database': 300,
    'git_commit': 3600,
}
```

---

## Cache Keys

Cache keys are generated deterministically from:
- Entity name
- Intent type (query, count, aggregate)
- Filters
- Attributes
- Sort order
- Limit
- User (for cache isolation)

**Example key**: `botswain:query:synthesizer:a1b2c3d4e5f6g7h8`

---

## Cache Bypass

### Using HTTP Header

To force fresh data (bypass cache), add header to API request:

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -H "X-Botswain-Cache-Bypass: 1" \
  -d '{"question": "How many synthesizers are online?"}'
```

**When to use**:
- Debugging data freshness issues
- Getting real-time status after changes
- Testing without cached data

### Programmatically

```python
from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry

registry = EntityRegistry()
executor = QueryExecutor(registry=registry)

# Bypass cache for this query
result = executor.execute(intent, user='admin', bypass_cache=True)
```

---

## Cache Operations

### Check Cache Hit/Miss

Cache hits and misses are logged:

```
INFO Cache HIT: synthesizer (key: query:synthesizer:a1b2c3d4e5f6g7h8)
INFO Cache MISS: instrument (key: query:instrument:f9e8d7c6b5a4)
INFO Cache SET: workflow (key: query:workflow:1a2b3c4d, TTL: 60s)
```

### Invalidate Entity Cache

```python
from core.cache import QueryCache

# Invalidate all cached queries for an entity
deleted_count = QueryCache.invalidate('synthesizer')
print(f"Deleted {deleted_count} cached queries")
```

**When to invalidate**:
- After bulk data changes
- When data freshness is critical
- During testing

### Get Cache Statistics

```python
from core.cache import QueryCache

stats = QueryCache.get_stats()
print(f"Cache hits: {stats.get('keyspace_hits')}")
print(f"Cache misses: {stats.get('keyspace_misses')}")
print(f"Memory used: {stats.get('used_memory_human')}")
```

---

## Redis Configuration

### Local Development

```bash
# .env
REDIS_URL=redis://localhost:6379/0
```

Start Redis:
```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Production

```bash
# .envs/.env.prod
REDIS_URL=redis://<elasticache-endpoint>:6379/0
```

**AWS ElastiCache**:
- Use Redis 7.x cluster
- Enable automatic failover
- Set max memory policy: `allkeys-lru`
- Monitor with CloudWatch

---

## Cache Response Format

Cached responses include a `cached` flag:

```json
{
  "question": "How many synthesizers are online?",
  "response": "There are 42 synthesizers online.",
  "intent": {...},
  "results": {...},
  "cached": true,  // Indicates cache hit
  "format_tokens": {...}
}
```

---

## Testing

### Test Cache Functionality

```python
# test_cache.py
from core.cache import QueryCache
from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry

def test_cache_hit():
    registry = EntityRegistry()
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'filters': {'status': 'online'},
        'limit': 10
    }

    # First query - cache miss
    result1 = executor.execute(intent, user='test')
    assert result1['cached'] == False

    # Second query - cache hit
    result2 = executor.execute(intent, user='test')
    assert result2['cached'] == True

    # Results should be identical
    assert result1['count'] == result2['count']

def test_cache_bypass():
    registry = EntityRegistry()
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'synthesizer',
        'intent_type': 'query',
        'filters': {},
        'limit': 10
    }

    # First query - populates cache
    result1 = executor.execute(intent, user='test')

    # Bypass cache - should not return cached result
    result2 = executor.execute(intent, user='test', bypass_cache=True)
    assert result2.get('cached') != True
```

---

## Monitoring

### Redis Metrics

**Key metrics to monitor**:
- **Hit rate**: `keyspace_hits / (keyspace_hits + keyspace_misses)`
- **Memory usage**: `used_memory` / `maxmemory`
- **Evicted keys**: `evicted_keys`
- **Connected clients**: `connected_clients`

### Application Logs

Filter logs for cache operations:

```bash
# Cache hits and misses
grep "Cache HIT\|Cache MISS" botswain.log

# Cache sets
grep "Cache SET" botswain.log

# Cache errors
grep "Cache.*error" botswain.log
```

---

## Troubleshooting

### Cache Not Working

1. **Check Redis connection**:
   ```bash
   redis-cli ping
   # Should return: PONG
   ```

2. **Verify settings**:
   ```python
   from django.conf import settings
   print(settings.CACHES)
   print(settings.ENTITY_CACHE_TTL)
   ```

3. **Check for bypass header**:
   ```bash
   # Request should NOT have X-Botswain-Cache-Bypass header
   ```

### Cache Stale Data

1. **Check TTL configuration** - Is TTL too long for entity?
2. **Invalidate cache**:
   ```python
   QueryCache.invalidate('entity_name')
   ```
3. **Use cache bypass header** for fresh data

### High Cache Miss Rate

1. **Check if queries are identical** - Cache keys must match exactly
2. **Review TTL settings** - May be too short
3. **Check Redis memory** - May be evicting keys too aggressively

---

## Best Practices

1. **Set appropriate TTLs**:
   - Real-time data: 30-60 seconds
   - Semi-static data: 5-10 minutes
   - Historical data: 1+ hours

2. **Use cache bypass sparingly**:
   - Only when fresh data is required
   - Don't use for every request

3. **Monitor cache hit rate**:
   - Target >70% hit rate for repeated queries
   - Investigate if <50%

4. **Invalidate after bulk changes**:
   - Use `QueryCache.invalidate()` after imports
   - Clear entity cache after schema changes

5. **Isolate by user**:
   - Cache keys include username
   - Prevents data leakage between users

---

## Future Enhancements

Potential improvements:

1. **Cache warming**: Pre-populate cache for common queries
2. **Smart invalidation**: Invalidate on data changes (webhooks)
3. **Tiered caching**: Memory cache + Redis
4. **Cache analytics**: Dashboard for hit rates per entity
5. **Adaptive TTL**: Adjust TTL based on query frequency
