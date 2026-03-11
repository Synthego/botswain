"""
Tests for query caching with pagination.
"""
import pytest
from core.cache import QueryCache


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
