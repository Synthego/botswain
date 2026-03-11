"""
Redis caching for Botswain query results.

Implements per-entity TTL configuration with cache key generation.
"""
import hashlib
import json
from typing import Dict, Any, Optional
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class QueryCache:
    """
    Manages Redis caching for query results.

    Features:
    - Per-entity TTL configuration
    - Deterministic cache key generation
    - Cache bypass support
    - Cache hit/miss metrics logging
    """

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
    def _sort_dict(d: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively sort dictionary for deterministic hashing"""
        if not isinstance(d, dict):
            return d
        return {k: QueryCache._sort_dict(v) if isinstance(v, dict) else v
                for k, v in sorted(d.items())}

    @staticmethod
    def get_ttl(entity: str) -> int:
        """
        Get cache TTL for entity.

        Args:
            entity: Entity name

        Returns:
            TTL in seconds
        """
        return settings.ENTITY_CACHE_TTL.get(
            entity,
            settings.CACHES['default']['TIMEOUT']
        )

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
        cache_key = QueryCache.get_cache_key(intent, user, offset, limit)
        entity = intent.get('entity', 'unknown')

        try:
            result = cache.get(cache_key)
            if result is not None:
                logger.info(f"Cache HIT: {entity} (key: {cache_key})")
                # Add cached flag to result
                result['cached'] = True
                return result
            else:
                logger.info(f"Cache MISS: {entity} (key: {cache_key})")
                return None
        except Exception as e:
            logger.error(f"Cache GET error for {entity}: {e}", exc_info=True)
            return None

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
        cache_key = QueryCache.get_cache_key(intent, user, offset, limit)
        entity = intent.get('entity', 'unknown')
        ttl = QueryCache.get_ttl(entity)

        try:
            # Don't cache the cached flag itself
            result_to_cache = {k: v for k, v in result.items() if k != 'cached'}
            cache.set(cache_key, result_to_cache, timeout=ttl)
            logger.info(f"Cache SET: {entity} (key: {cache_key}, TTL: {ttl}s)")
            return True
        except Exception as e:
            logger.error(f"Cache SET error for {entity}: {e}", exc_info=True)
            return False

    @staticmethod
    def invalidate(entity: str) -> int:
        """
        Invalidate all cached queries for an entity.

        Args:
            entity: Entity name

        Returns:
            Number of keys deleted
        """
        try:
            # Get the underlying Redis client
            # Django's cache is a ConnectionProxy that wraps RedisCacheClient
            backend = cache._cache
            if hasattr(backend, 'get_client'):
                client = backend.get_client(write=True)

                # Django uses format: {prefix}:{version}:{key}
                # Default version is 1
                prefix = cache.key_prefix
                pattern = f"{prefix}:1:query:{entity}:*"
                keys = client.keys(pattern)

                if keys:
                    # Delete using the underlying client
                    deleted = client.delete(*keys)
                    logger.info(f"Cache INVALIDATE: {entity} ({deleted} keys deleted)")
                    return deleted
                return 0
            else:
                # Fallback for non-Redis cache backends
                logger.warning(f"Cache INVALIDATE not supported for {type(cache).__name__}")
                return 0
        except Exception as e:
            logger.error(f"Cache INVALIDATE error for {entity}: {e}", exc_info=True)
            return 0

    @staticmethod
    def should_bypass(request) -> bool:
        """
        Check if cache should be bypassed for this request.

        Args:
            request: Django request object

        Returns:
            True if cache should be bypassed
        """
        if not hasattr(request, 'META'):
            return False

        # Check for cache bypass header
        bypass_header = settings.CACHE_BYPASS_HEADER
        return request.META.get(f'HTTP_{bypass_header.upper().replace("-", "_")}') == '1'

    @staticmethod
    def get_stats() -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with cache stats (if available)
        """
        try:
            # Try to get Redis info
            from django.core.cache.backends.redis import RedisCache
            if isinstance(cache, RedisCache):
                client = cache._cache.get_client()
                info = client.info('stats')
                return {
                    'total_commands': info.get('total_commands_processed', 0),
                    'keyspace_hits': info.get('keyspace_hits', 0),
                    'keyspace_misses': info.get('keyspace_misses', 0),
                    'used_memory_human': info.get('used_memory_human', 'N/A'),
                }
        except Exception as e:
            logger.debug(f"Could not get cache stats: {e}")

        return {'error': 'Stats not available'}
