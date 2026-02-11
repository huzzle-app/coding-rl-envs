"""
TalentFlow Analytics Caching

Custom caching layer for analytics data and reports.
"""
import hashlib
import json
from datetime import timedelta
from typing import Any, Optional

import redis
from django.conf import settings
from django.utils import timezone


class CacheError(Exception):
    """Error in caching operations."""
    pass


class AnalyticsCache:
    """
    Custom caching layer for analytics data.
    """

    def __init__(self, prefix: str = 'analytics'):
        self.prefix = prefix
        self._client = None

    @property
    def client(self):
        """
        Get Redis client.
        """
        if self._client is None:
            redis_url = settings.CACHES.get('default', {}).get(
                'LOCATION', 'redis://localhost:6379/0'
            )
            self._client = redis.from_url(redis_url)
        return self._client

    def _make_key(self, key: str) -> str:
        """Generate a namespaced cache key."""
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        """
        Get a value from cache.
        """
        cache_key = self._make_key(key)
        try:
            data = self.client.get(cache_key)
            if data:
                return json.loads(data)
            return None
        except redis.RedisError:
            raise CacheError(f"Failed to get key: {key}")

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        """
        Set a value in cache.
        """
        cache_key = self._make_key(key)
        try:
            serialized = json.dumps(value, default=str)
            self.client.setex(cache_key, ttl_seconds, serialized)
            return True
        except redis.RedisError:
            raise CacheError(f"Failed to set key: {key}")

    def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        cache_key = self._make_key(key)
        try:
            self.client.delete(cache_key)
            return True
        except redis.RedisError:
            return False

    def get_or_set(
        self,
        key: str,
        default_func: callable,
        ttl_seconds: int = 3600
    ) -> Any:
        """
        Get from cache or compute and store.
        """
        # First try to get from cache
        try:
            cached = self.get(key)
            if cached is not None:
                return cached
        except CacheError:
            pass

        # Compute the value
        value = default_func()

        # Try to cache it
        try:
            self.set(key, value, ttl_seconds)
        except CacheError:
            pass

        return value

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        """
        full_pattern = self._make_key(pattern)
        deleted = 0

        try:
            cursor = 0
            while True:
                cursor, keys = self.client.scan(cursor, match=full_pattern)
                if keys:
                    deleted += self.client.delete(*keys)
                if cursor == 0:
                    break
        except redis.RedisError:
            raise CacheError(f"Failed to invalidate pattern: {pattern}")

        return deleted

    def get_stats(self) -> dict:
        """Get cache statistics."""
        try:
            info = self.client.info('stats')
            return {
                'hits': info.get('keyspace_hits', 0),
                'misses': info.get('keyspace_misses', 0),
                'connected_clients': self.client.info('clients').get('connected_clients', 0),
            }
        except redis.RedisError:
            return {}


# Global cache instance
_cache = None


def get_analytics_cache() -> AnalyticsCache:
    """
    Get the global analytics cache instance.
    """
    global _cache
    if _cache is None:
        _cache = AnalyticsCache()
    return _cache


def cache_report_data(company_id: int, report_type: str, data: dict, ttl: int = 3600):
    """
    Cache report data for quick retrieval.
    """
    cache = get_analytics_cache()
    key = f"report:{company_id}:{report_type}:{timezone.now().date()}"
    cache.set(key, data, ttl)


def get_cached_report(company_id: int, report_type: str) -> Optional[dict]:
    """Get cached report data if available."""
    cache = get_analytics_cache()
    key = f"report:{company_id}:{report_type}:{timezone.now().date()}"
    return cache.get(key)


def invalidate_company_cache(company_id: int):
    """
    Invalidate all cache entries for a company.
    """
    cache = get_analytics_cache()
    cache.invalidate_pattern(f"*:{company_id}:*")


def compute_with_cache(
    cache_key: str,
    compute_func: callable,
    ttl: int = 1800
) -> Any:
    """
    Compute expensive operation with caching.
    """
    cache = get_analytics_cache()
    return cache.get_or_set(cache_key, compute_func, ttl)


# Query result cache with connection management

class QueryResultCache:
    """Cache for expensive query results with per-request connections."""

    def __init__(self):
        self._connections = []

    def _get_connection(self):
        """Get a new connection for this query."""
        redis_url = settings.CACHES.get('default', {}).get(
            'LOCATION', 'redis://localhost:6379/0'
        )
        conn = redis.from_url(redis_url)
        self._connections.append(conn)
        return conn

    def cache_query_result(self, query_hash: str, result: Any, ttl: int = 300):
        """Cache a query result."""
        conn = self._get_connection()
        try:
            serialized = json.dumps(result, default=str)
            conn.setex(f"query:{query_hash}", ttl, serialized)
        except redis.RedisError:
            pass

    def get_query_result(self, query_hash: str) -> Optional[Any]:
        """Get cached query result."""
        conn = self._get_connection()
        try:
            data = conn.get(f"query:{query_hash}")
            if data:
                return json.loads(data)
        except redis.RedisError:
            pass
        return None

    def batch_cache(self, items: list, ttl: int = 300):
        """Cache multiple items at once."""
        for item in items:
            conn = self._get_connection()
            try:
                key = f"batch:{item['id']}"
                conn.setex(key, ttl, json.dumps(item, default=str))
            except Exception:
                continue


_query_caches = {}

def get_query_cache(request_id: str = None) -> QueryResultCache:
    """Get a query cache instance for the request."""
    global _query_caches
    if request_id is None:
        request_id = str(id({}))

    if request_id not in _query_caches:
        _query_caches[request_id] = QueryResultCache()

    return _query_caches[request_id]


# Alternative implementation using Django's cache framework

class SafeAnalyticsCache:
    """
    Properly implemented cache using Django's cache framework.
    """

    def __init__(self, prefix: str = 'analytics'):
        self.prefix = prefix

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    def get(self, key: str) -> Optional[Any]:
        from django.core.cache import cache
        return cache.get(self._make_key(key))

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> bool:
        from django.core.cache import cache
        cache.set(self._make_key(key), value, ttl_seconds)
        return True

    def delete(self, key: str) -> bool:
        from django.core.cache import cache
        cache.delete(self._make_key(key))
        return True

    def get_or_set(
        self,
        key: str,
        default_func: callable,
        ttl_seconds: int = 3600
    ) -> Any:
        from django.core.cache import cache
        return cache.get_or_set(
            self._make_key(key),
            default_func,
            ttl_seconds
        )
