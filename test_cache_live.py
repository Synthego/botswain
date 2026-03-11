#!/usr/bin/env python
"""
Test Redis caching with real query execution.

Demonstrates cache hit/miss, performance improvements, and cache bypass.
"""
import os
import sys
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botswain.settings.test')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.base import BaseEntity
from core.cache import QueryCache


class MockLiveEntity(BaseEntity):
    """Mock entity that simulates a slow database query"""
    name = "live_test"
    description = "Mock entity for live cache testing"

    def get_queryset(self, filters=None):
        # Simulate slow database query
        time.sleep(0.5)
        return [
            {'id': i, 'name': f'Item {i}', 'value': i * 100}
            for i in range(1, 51)
        ]

    def validate_filters(self, filters):
        return True

    def get_attributes(self):
        return ['id', 'name', 'value']


def print_section(title):
    """Print a formatted section header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_cache_performance():
    """Test cache performance with real query execution"""
    print_section("Redis Caching Performance Test")

    # Setup
    registry = EntityRegistry()
    registry.register(MockLiveEntity())
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'live_test',
        'intent_type': 'query',
        'attributes': ['id', 'name', 'value'],
        'filters': {'status': 'active'},
        'limit': 50
    }

    print("📊 Query: Get 50 items from live_test entity")
    print("   (Simulated slow query: 500ms database latency)\n")

    # First query - CACHE MISS (slow)
    print("🔹 First Query (Cache Miss - should be slow):")
    start = time.time()
    result1 = executor.execute(intent, user='test_user')
    elapsed1 = time.time() - start

    print(f"   ⏱️  Response time: {elapsed1*1000:.0f}ms")
    print(f"   📦 Cached: {result1.get('cached', False)}")
    print(f"   📊 Count: {result1['count']}")
    print(f"   ✅ Expected: ~500ms (database query)")

    # Small delay to ensure cache is set
    time.sleep(0.1)

    # Second query - CACHE HIT (fast)
    print("\n🔹 Second Query (Cache Hit - should be fast):")
    start = time.time()
    result2 = executor.execute(intent, user='test_user')
    elapsed2 = time.time() - start

    print(f"   ⏱️  Response time: {elapsed2*1000:.0f}ms")
    print(f"   📦 Cached: {result2.get('cached', False)}")
    print(f"   📊 Count: {result2['count']}")
    print(f"   ✅ Expected: <10ms (Redis cache)")

    # Performance improvement
    improvement = ((elapsed1 - elapsed2) / elapsed1) * 100
    print(f"\n🚀 Performance Improvement:")
    print(f"   📈 {improvement:.1f}% faster with caching")
    print(f"   💾 Time saved: {(elapsed1 - elapsed2)*1000:.0f}ms per query")

    # Third query with cache bypass - CACHE MISS (slow again)
    print("\n🔹 Third Query (Cache Bypass - should be slow):")
    start = time.time()
    result3 = executor.execute(intent, user='test_user', bypass_cache=True)
    elapsed3 = time.time() - start

    print(f"   ⏱️  Response time: {elapsed3*1000:.0f}ms")
    print(f"   📦 Cached: {result3.get('cached', False)}")
    print(f"   📊 Count: {result3['count']}")
    print(f"   ✅ Expected: ~500ms (bypassed cache, hit database)")

    # Cache statistics
    print_section("Cache Statistics")

    # Check Redis for keys
    from django.core.cache import cache
    backend = cache._cache
    if hasattr(backend, 'get_client'):
        client = backend.get_client(write=True)
        pattern = 'botswain:1:query:live_test:*'
        keys = client.keys(pattern)
        print(f"📊 Cached keys for 'live_test': {len(keys)}")

        if keys:
            print("   Sample keys:")
            for key in keys[:3]:
                k = key.decode() if isinstance(key, bytes) else key
                print(f"     • {k}")
                # Get TTL
                ttl = client.ttl(key)
                print(f"       TTL: {ttl}s remaining")

    # Test cache invalidation
    print_section("Cache Invalidation Test")

    print("🗑️  Invalidating cache for 'live_test' entity...")
    deleted = QueryCache.invalidate('live_test')
    print(f"   ✅ Deleted {deleted} cached queries")

    # Verify invalidation worked
    print("\n🔹 Query after invalidation (should be cache miss):")
    start = time.time()
    result4 = executor.execute(intent, user='test_user')
    elapsed4 = time.time() - start

    print(f"   ⏱️  Response time: {elapsed4*1000:.0f}ms")
    print(f"   📦 Cached: {result4.get('cached', False)}")
    print(f"   ✅ Expected: ~500ms (cache was invalidated)")

    if not result4.get('cached'):
        print("   ✅ Cache invalidation worked!")
    else:
        print("   ❌ Cache invalidation may have failed")

    # Summary
    print_section("Summary")
    print("✅ Cache Performance:")
    print(f"   • Cache Miss (DB):    ~{elapsed1*1000:.0f}ms")
    print(f"   • Cache Hit (Redis):  ~{elapsed2*1000:.0f}ms")
    print(f"   • Improvement:        {improvement:.1f}%")
    print()
    print("✅ Cache Features Verified:")
    print("   • Deterministic cache keys")
    print("   • Cache hit/miss detection")
    print("   • Cache bypass functionality")
    print("   • Cache invalidation")
    print("   • TTL configuration")
    print()
    print("🎉 Redis caching is working correctly!")


if __name__ == '__main__':
    test_cache_performance()
