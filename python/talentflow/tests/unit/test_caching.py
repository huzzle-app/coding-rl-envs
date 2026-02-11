"""
Unit tests for caching system.

Tests: 25
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestAnalyticsCache:
    """Tests for AnalyticsCache class."""

    def test_cache_key_generation(self):
        """Test cache key namespacing."""
        from apps.analytics.caching import AnalyticsCache

        cache = AnalyticsCache(prefix='test')
        key = cache._make_key('mykey')

        assert key == 'test:mykey'

    def test_cache_key_with_special_chars(self):
        """Test cache key with special characters."""
        from apps.analytics.caching import AnalyticsCache

        cache = AnalyticsCache(prefix='test')
        key = cache._make_key('company:123:report:daily')

        assert key == 'test:company:123:report:daily'

    @patch('apps.analytics.caching.redis')
    def test_cache_get_returns_none_on_miss(self, mock_redis):
        """Test cache get returns None on miss."""
        from apps.analytics.caching import AnalyticsCache

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis.from_url.return_value = mock_client

        cache = AnalyticsCache()
        result = cache.get('nonexistent')

        assert result is None

    @patch('apps.analytics.caching.redis')
    def test_cache_set_serializes_data(self, mock_redis):
        """Test cache set serializes data correctly."""
        from apps.analytics.caching import AnalyticsCache

        mock_client = MagicMock()
        mock_redis.from_url.return_value = mock_client

        cache = AnalyticsCache()
        data = {'key': 'value', 'number': 42}
        cache.set('testkey', data, ttl_seconds=300)

        mock_client.setex.assert_called_once()
        call_args = mock_client.setex.call_args
        assert call_args[0][1] == 300


class TestQueryResultCache:
    """Tests for QueryResultCache - tests memory leak bug."""

    @pytest.mark.bug_f3
    def test_connection_accumulation(self):
        """Test that QueryResultCache accumulates connections."""
        from apps.analytics.caching import QueryResultCache

        cache = QueryResultCache()

        with patch('apps.analytics.caching.redis') as mock_redis:
            mock_conn = MagicMock()
            mock_redis.from_url.return_value = mock_conn

            for _ in range(10):
                cache.cache_query_result('hash1', {'data': 'value'})

            assert len(cache._connections) == 10

    @pytest.mark.bug_f3
    def test_batch_cache_creates_many_connections(self):
        """Test batch_cache creates connection per item."""
        from apps.analytics.caching import QueryResultCache

        cache = QueryResultCache()

        with patch('apps.analytics.caching.redis') as mock_redis:
            mock_conn = MagicMock()
            mock_redis.from_url.return_value = mock_conn

            items = [{'id': i, 'value': f'item{i}'} for i in range(5)]
            cache.batch_cache(items)

            assert len(cache._connections) == 5

    @pytest.mark.bug_f3
    def test_get_query_cache_accumulates(self):
        """Test that get_query_cache accumulates caches."""
        from apps.analytics.caching import get_query_cache, _query_caches

        initial_count = len(_query_caches)

        for i in range(5):
            get_query_cache(f'request_{i}')

        final_count = len(_query_caches)
        assert final_count >= initial_count + 5

    @pytest.mark.bug_f3
    def test_query_cache_no_cleanup(self):
        """Test that query caches are never cleaned up."""
        from apps.analytics.caching import QueryResultCache

        cache = QueryResultCache()

        with patch('apps.analytics.caching.redis') as mock_redis:
            mock_conn = MagicMock()
            mock_redis.from_url.return_value = mock_conn

            cache.cache_query_result('hash1', {})
            cache.get_query_result('hash2')
            cache.cache_query_result('hash3', {})

            assert len(cache._connections) == 3


class TestCacheReportData:
    """Tests for report caching functions."""

    @patch('apps.analytics.caching.get_analytics_cache')
    def test_cache_report_data(self, mock_get_cache):
        """Test caching report data."""
        from apps.analytics.caching import cache_report_data

        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        cache_report_data(1, 'hiring_funnel', {'total': 100})

        mock_cache.set.assert_called_once()

    @patch('apps.analytics.caching.get_analytics_cache')
    def test_get_cached_report(self, mock_get_cache):
        """Test getting cached report."""
        from apps.analytics.caching import get_cached_report

        mock_cache = MagicMock()
        mock_cache.get.return_value = {'total': 100}
        mock_get_cache.return_value = mock_cache

        result = get_cached_report(1, 'hiring_funnel')

        assert result == {'total': 100}

    @patch('apps.analytics.caching.get_analytics_cache')
    def test_invalidate_company_cache(self, mock_get_cache):
        """Test invalidating company cache."""
        from apps.analytics.caching import invalidate_company_cache

        mock_cache = MagicMock()
        mock_get_cache.return_value = mock_cache

        invalidate_company_cache(1)

        mock_cache.invalidate_pattern.assert_called_once_with('*:1:*')


class TestSafeAnalyticsCache:
    """Tests for SafeAnalyticsCache using Django cache framework."""

    @patch('django.core.cache.cache')
    def test_safe_cache_uses_django_cache(self, mock_cache):
        """Test SafeAnalyticsCache uses Django's cache."""
        from apps.analytics.caching import SafeAnalyticsCache

        safe_cache = SafeAnalyticsCache()

        mock_cache.get.return_value = None
        result = safe_cache.get('testkey')

        assert result is None

    @patch('django.core.cache.cache')
    def test_safe_cache_set(self, mock_cache):
        """Test SafeAnalyticsCache set operation."""
        from apps.analytics.caching import SafeAnalyticsCache

        safe_cache = SafeAnalyticsCache()
        result = safe_cache.set('testkey', {'data': 'value'}, 600)

        assert result is True

    @patch('django.core.cache.cache')
    def test_safe_cache_delete(self, mock_cache):
        """Test SafeAnalyticsCache delete operation."""
        from apps.analytics.caching import SafeAnalyticsCache

        safe_cache = SafeAnalyticsCache()
        result = safe_cache.delete('testkey')

        assert result is True


class TestCacheErrorHandling:
    """Tests for cache error handling."""

    def test_cache_error_exception(self):
        """Test CacheError is raised correctly."""
        from apps.analytics.caching import CacheError

        with pytest.raises(CacheError):
            raise CacheError("Test error")

    @patch('apps.analytics.caching.redis')
    def test_get_raises_cache_error_on_redis_failure(self, mock_redis):
        """Test get raises CacheError on Redis failure."""
        from apps.analytics.caching import AnalyticsCache, CacheError
        import redis as redis_module

        mock_client = MagicMock()
        mock_client.get.side_effect = redis_module.RedisError("Connection failed")
        mock_redis.from_url.return_value = mock_client
        mock_redis.RedisError = redis_module.RedisError

        cache = AnalyticsCache()

        with pytest.raises(CacheError):
            cache.get('testkey')

    @patch('apps.analytics.caching.redis')
    def test_set_raises_cache_error_on_redis_failure(self, mock_redis):
        """Test set raises CacheError on Redis failure."""
        from apps.analytics.caching import AnalyticsCache, CacheError
        import redis as redis_module

        mock_client = MagicMock()
        mock_client.setex.side_effect = redis_module.RedisError("Connection failed")
        mock_redis.from_url.return_value = mock_client
        mock_redis.RedisError = redis_module.RedisError

        cache = AnalyticsCache()

        with pytest.raises(CacheError):
            cache.set('testkey', {'data': 'value'})


class TestGetOrSetPattern:
    """Tests for get-or-set caching pattern."""

    @patch('apps.analytics.caching.redis')
    def test_get_or_set_cache_hit(self, mock_redis):
        """Test get_or_set returns cached value."""
        from apps.analytics.caching import AnalyticsCache

        mock_client = MagicMock()
        mock_client.get.return_value = json.dumps({'cached': True})
        mock_redis.from_url.return_value = mock_client

        cache = AnalyticsCache()
        compute_called = False

        def compute():
            nonlocal compute_called
            compute_called = True
            return {'computed': True}

        result = cache.get_or_set('testkey', compute)

        assert result == {'cached': True}
        assert not compute_called

    @patch('apps.analytics.caching.redis')
    def test_get_or_set_cache_miss(self, mock_redis):
        """Test get_or_set computes on cache miss."""
        from apps.analytics.caching import AnalyticsCache

        mock_client = MagicMock()
        mock_client.get.return_value = None
        mock_redis.from_url.return_value = mock_client

        cache = AnalyticsCache()

        def compute():
            return {'computed': True}

        result = cache.get_or_set('testkey', compute)

        assert result == {'computed': True}
        mock_client.setex.assert_called_once()
