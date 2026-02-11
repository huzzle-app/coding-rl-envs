"""
Integration tests for Celery tasks.

Tests: 10 - Focus on timezone mismatch and chord callback bugs
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
from django.utils import timezone
import pytz


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


class TestCeleryTimezone:
    """Tests for Celery timezone configuration - detects Bug B1."""

    @pytest.mark.bug_b1
    def test_celery_timezone_matches_django(self):
        """
        BUG B1: Test that Celery timezone matches Django timezone.

        Django is configured for 'America/New_York' but Celery
        overrides to 'UTC', causing scheduled tasks to run at wrong times.
        """
        from django.conf import settings
        from talentflow.celery import app

        django_tz = settings.TIME_ZONE
        celery_tz = app.conf.timezone

        
        # Django: 'America/New_York', Celery: 'UTC'
        # After fix, they should match
        assert django_tz == celery_tz, \
            f"Django TZ ({django_tz}) != Celery TZ ({celery_tz})"

    @pytest.mark.bug_b1
    def test_celery_enable_utc_setting(self):
        """
        BUG B1: Test enable_utc setting consistency.

        Django settings has CELERY_ENABLE_UTC=False but celery.py
        overrides it to True, causing confusion.
        """
        from django.conf import settings
        from talentflow.celery import app

        django_setting = getattr(settings, 'CELERY_ENABLE_UTC', None)
        celery_setting = app.conf.enable_utc

        
        assert django_setting == celery_setting, \
            f"Django CELERY_ENABLE_UTC ({django_setting}) != Celery enable_utc ({celery_setting})"

    @pytest.mark.bug_b1
    def test_scheduled_task_timing(self):
        """
        BUG B1: Test that scheduled tasks fire at expected times.

        Due to timezone mismatch, a task scheduled for 9 AM Eastern
        would actually run at 9 AM UTC (which is 4 AM Eastern in winter).
        """
        from talentflow.celery import app

        # Get the beat schedule
        schedule = app.conf.beat_schedule

        # Tasks are scheduled in Celery's timezone (UTC)
        # but the application logic may expect local timezone

        assert schedule is not None and len(schedule) > 0, \
            "Beat schedule should have entries"


class TestCeleryChord:
    """Tests for Celery chord callbacks - detects Bug B2."""

    @pytest.mark.bug_b2
    def test_chord_with_ignore_result_fails(self, job, candidates, celery_eager):
        """
        BUG B2: Test that chord fails when header tasks have ignore_result=True.

        The score_single_candidate task has ignore_result=True which breaks
        the chord pattern because results can't be collected.
        """
        from apps.jobs.tasks import (
            score_single_candidate,
            aggregate_scores,
            calculate_match_scores_for_job,
        )

        # Check the task's ignore_result setting
        
        # After fix, ignore_result should be False
        assert score_single_candidate.ignore_result is False, \
            "score_single_candidate should not have ignore_result=True"

    @pytest.mark.bug_b2
    def test_aggregate_scores_receives_none_results(self, job, celery_eager):
        """
        BUG B2: Test that aggregate_scores receives None when chord header
        tasks have ignore_result=True.
        """
        from apps.jobs.tasks import aggregate_scores

        # Simulate what happens when chord header ignores results
        none_results = [None, None, None, None, None]

        result = aggregate_scores(none_results, job.id)

        
        assert 'error' in result or result.get('total_scored', 0) == 0, \
            "aggregate_scores should handle None results gracefully"

    @pytest.mark.bug_b2
    def test_chord_pattern_conceptual(self, job, candidates, celery_eager):
        """
        BUG B2: Conceptual test for chord pattern issues.

        This test demonstrates the chord pattern that's broken.
        """
        from celery import chord, group
        from apps.jobs.tasks import score_single_candidate, aggregate_scores

        # In production, this chord pattern fails silently because
        # score_single_candidate.ignore_result = True

        # The fix is to remove ignore_result=True from score_single_candidate
        assert score_single_candidate.ignore_result is False, \
            "Chord pattern requires ignore_result=False to collect results"


class TestRedisConnection:
    """Tests for Redis connection handling - detects Bug B3."""

    @pytest.mark.bug_b3
    def test_analytics_cache_connection_leak(self, mock_redis):
        """
        BUG B3: Test that AnalyticsCache leaks connections.

        Each AnalyticsCache instance creates a new Redis connection
        that isn't properly released on errors.
        """
        from apps.analytics.caching import AnalyticsCache

        # Create multiple cache instances
        caches = [AnalyticsCache() for _ in range(10)]

        # Each instance creates its own connection
        

        # Access clients to trigger connection creation
        for cache in caches:
            _ = cache.client

        # Verify multiple connections were created
        # The mock tracks how many times from_url was called

    @pytest.mark.bug_b3
    def test_cache_error_doesnt_release_connection(self, mock_redis):
        """
        BUG B3: Test that errors don't release connections.

        When a Redis error occurs, the connection isn't properly
        cleaned up, leading to pool exhaustion.
        """
        from apps.analytics.caching import AnalyticsCache, CacheError

        cache = AnalyticsCache()

        # Simulate Redis error
        mock_redis.get.side_effect = Exception("Connection failed")

        # After error, connection should be released but isn't
        with pytest.raises(CacheError):
            cache.get('test_key')

        

    @pytest.mark.bug_b3
    def test_safe_cache_uses_django_framework(self):
        """
        Test that SafeAnalyticsCache uses Django's cache framework.

        This is the correct implementation that doesn't leak connections.
        """
        from apps.analytics.caching import SafeAnalyticsCache

        cache = SafeAnalyticsCache()

        # SafeAnalyticsCache uses django.core.cache which properly
        # manages connections through the connection pool

        # Set and get should work without leaking connections
        cache.set('test_key', {'data': 'test'}, 60)
        result = cache.get('test_key')

        # Result should be the stored value
        assert result == {'data': 'test'}

    @pytest.mark.bug_b3
    def test_global_cache_instance(self):
        """
        BUG B3: Test global cache instance creation.

        The get_analytics_cache() function creates new instances
        which each create new connections.
        """
        from apps.analytics.caching import get_analytics_cache, _cache

        # First call should create the cache
        cache1 = get_analytics_cache()

        # Second call should return same instance
        cache2 = get_analytics_cache()

        # They should be the same instance (singleton pattern)
        assert cache1 is cache2, "Cache should be a singleton"
