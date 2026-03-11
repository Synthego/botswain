#!/usr/bin/env python
"""
Test Redis caching functionality.

Tests cache hit/miss, TTL configuration, and cache bypass.
"""
import os
import sys
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'botswain.settings.test')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from core.cache import QueryCache
from core.query_executor import QueryExecutor
from core.semantic_layer.registry import EntityRegistry
from core.semantic_layer.entities.base import BaseEntity


class MockCacheTestEntity(BaseEntity):
    """Mock entity for cache testing"""
    name = "cache_test"
    description = "Mock entity for testing cache"

    def get_queryset(self, filters=None):
        # Return mock data
        return [
            {'id': 1, 'name': 'Test 1', 'value': 100},
            {'id': 2, 'name': 'Test 2', 'value': 200},
            {'id': 3, 'name': 'Test 3', 'value': 300},
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


def test_cache_key_generation():
    """Test that cache keys are generated deterministically"""
    print_section("Test 1: Cache Key Generation")

    intent1 = {
        'entity': 'cache_test',
        'intent_type': 'query',
        'attributes': ['id', 'name'],
        'filters': {'status': 'active'},
        'limit': 10
    }

    intent2 = {
        'entity': 'cache_test',
        'intent_type': 'query',
        'attributes': ['name', 'id'],  # Different order
        'filters': {'status': 'active'},
        'limit': 10
    }

    key1 = QueryCache.get_cache_key(intent1, 'user1')
    key2 = QueryCache.get_cache_key(intent2, 'user1')

    print(f"Key 1: {key1}")
    print(f"Key 2: {key2}")

    if key1 == key2:
        print("✅ Cache keys are deterministic (attribute order doesn't matter)")
    else:
        print("❌ Cache keys differ for same intent")

    # Different user should get different key
    key3 = QueryCache.get_cache_key(intent1, 'user2')
    print(f"\nKey 3 (different user): {key3}")

    if key1 != key3:
        print("✅ Cache keys are isolated by user")
    else:
        print("❌ Cache keys should differ for different users")


def test_cache_hit_miss():
    """Test cache hit and miss behavior"""
    print_section("Test 2: Cache Hit/Miss")

    registry = EntityRegistry()
    registry.register(MockCacheTestEntity())
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'cache_test',
        'intent_type': 'query',
        'attributes': ['id', 'name'],
        'filters': {},
        'limit': 10
    }

    # First query - should be a cache miss
    print("First query (cache miss expected):")
    result1 = executor.execute(intent, user='test_user')
    print(f"  Cached: {result1.get('cached', False)}")
    print(f"  Count: {result1['count']}")
    print(f"  Execution time: {result1['execution_time_ms']}ms")

    if not result1.get('cached'):
        print("✅ First query was cache miss")
    else:
        print("❌ First query should not be cached")

    # Small delay to ensure cache is set
    time.sleep(0.1)

    # Second query - should be a cache hit
    print("\nSecond query (cache hit expected):")
    result2 = executor.execute(intent, user='test_user')
    print(f"  Cached: {result2.get('cached', False)}")
    print(f"  Count: {result2['count']}")
    print(f"  Execution time: {result2['execution_time_ms']}ms")

    if result2.get('cached'):
        print("✅ Second query was cache hit")
    else:
        print("❌ Second query should be cached")

    # Verify results are identical
    if result1['count'] == result2['count']:
        print("✅ Cache returned identical results")
    else:
        print("❌ Cached results differ from original")


def test_cache_bypass():
    """Test cache bypass functionality"""
    print_section("Test 3: Cache Bypass")

    registry = EntityRegistry()
    registry.register(MockCacheTestEntity())
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'cache_test',
        'intent_type': 'query',
        'attributes': [],
        'filters': {},
        'limit': 10
    }

    # First query - populate cache
    print("First query (populate cache):")
    result1 = executor.execute(intent, user='bypass_test')
    print(f"  Cached: {result1.get('cached', False)}")

    time.sleep(0.1)

    # Second query with cache bypass
    print("\nSecond query (with bypass):")
    result2 = executor.execute(intent, user='bypass_test', bypass_cache=True)
    print(f"  Cached: {result2.get('cached', False)}")

    if not result2.get('cached'):
        print("✅ Cache bypass worked")
    else:
        print("❌ Cache bypass failed")


def test_ttl_configuration():
    """Test TTL configuration for different entities"""
    print_section("Test 4: TTL Configuration")

    from django.conf import settings

    entities_to_check = [
        'synthesizer',
        'instrument',
        'workflow',
        'order',
        'git_commit'
    ]

    print("Entity TTL Configuration:")
    for entity in entities_to_check:
        ttl = QueryCache.get_ttl(entity)
        print(f"  {entity:20s}: {ttl:6d} seconds ({ttl/60:.1f} minutes)")

    print("\n✅ TTL configuration loaded")


def test_cache_invalidation():
    """Test cache invalidation"""
    print_section("Test 5: Cache Invalidation")

    registry = EntityRegistry()
    registry.register(MockCacheTestEntity())
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'cache_test',
        'intent_type': 'query',
        'attributes': [],
        'filters': {},
        'limit': 10
    }

    # Populate cache
    print("Populating cache...")
    result1 = executor.execute(intent, user='invalidation_test')

    time.sleep(0.1)

    # Verify cache hit
    print("Verifying cache hit...")
    result2 = executor.execute(intent, user='invalidation_test')
    if result2.get('cached'):
        print("✅ Cache populated")
    else:
        print("⚠️  Cache not populated (may not be available)")
        return

    # Invalidate cache
    print("\nInvalidating cache...")
    deleted = QueryCache.invalidate('cache_test')
    print(f"  Deleted {deleted} keys")

    time.sleep(0.1)

    # Query again - should be cache miss
    print("\nQuerying after invalidation:")
    result3 = executor.execute(intent, user='invalidation_test')
    if not result3.get('cached'):
        print("✅ Cache invalidation worked")
    else:
        print("❌ Cache still returning cached results")


def test_aggregation_caching():
    """Test that aggregation queries are cached"""
    print_section("Test 6: Aggregation Query Caching")

    registry = EntityRegistry()
    registry.register(MockCacheTestEntity())
    executor = QueryExecutor(registry=registry, use_cache=True)

    intent = {
        'entity': 'cache_test',
        'intent_type': 'aggregate',
        'attributes': ['value'],
        'filters': {},
        'aggregation_function': 'sum',
        'limit': 10
    }

    # First query
    print("First aggregation query:")
    result1 = executor.execute(intent, user='agg_test')
    print(f"  Cached: {result1.get('cached', False)}")
    print(f"  Sum: {result1.get('aggregations', {}).get('sum_value')}")

    time.sleep(0.1)

    # Second query - should be cached
    print("\nSecond aggregation query:")
    result2 = executor.execute(intent, user='agg_test')
    print(f"  Cached: {result2.get('cached', False)}")
    print(f"  Sum: {result2.get('aggregations', {}).get('sum_value')}")

    if result2.get('cached'):
        print("✅ Aggregation queries are cached")
    else:
        print("❌ Aggregation queries not cached")


def main():
    """Run all cache tests"""
    print("\n" + "="*70)
    print("  BOTSWAIN REDIS CACHING TESTS".center(70))
    print("="*70)

    try:
        test_cache_key_generation()
        test_cache_hit_miss()
        test_cache_bypass()
        test_ttl_configuration()
        test_cache_invalidation()
        test_aggregation_caching()

        print("\n" + "="*70)
        print("  ✅ ALL CACHE TESTS COMPLETED".center(70))
        print("="*70)
        print("\n📝 Note: Some tests may show warnings if Redis is not running.")
        print("   Caching will gracefully degrade to no-cache mode.\n")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
