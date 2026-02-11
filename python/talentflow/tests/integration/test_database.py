"""
Integration tests for database operations.

Tests: 10 - Focus on connection pool and race condition bugs
"""
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from django.db import connection, connections


pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


class TestConnectionPool:
    """Tests for database connection pool - detects Bug A1."""

    @pytest.mark.bug_a1
    @pytest.mark.slow
    def test_parallel_queries_connection_exhaustion(self, candidates, db):
        """
        BUG A1: Test connection pool exhaustion under parallel load.

        With CONN_MAX_AGE=None and no health checks, stale connections
        accumulate and can exhaust the pool.
        """
        from apps.candidates.models import Candidate

        errors = []

        def query_candidates():
            try:
                # Force a new connection by closing current
                list(Candidate.objects.all()[:5])
                return True
            except Exception as e:
                errors.append(str(e))
                return False

        # Run many parallel queries
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(query_candidates) for _ in range(50)]
            results = [f.result() for f in as_completed(futures)]

        
        # After fix, all queries should succeed
        success_rate = sum(results) / len(results)
        assert success_rate >= 0.95, f"Too many connection errors: {errors[:5]}"

    @pytest.mark.bug_a1
    def test_connection_health_check(self, db):
        """
        BUG A1: Test that unhealthy connections are detected.

        With CONN_HEALTH_CHECKS=False, stale connections aren't
        detected before use.
        """
        from django.conf import settings

        db_settings = settings.DATABASES['default']

        
        # After fix, this assertion should pass
        assert db_settings.get('CONN_HEALTH_CHECKS', False) is True, \
            "CONN_HEALTH_CHECKS should be enabled"

    @pytest.mark.bug_a1
    def test_connection_max_age_configuration(self, db):
        """
        BUG A1: Test connection max age configuration.

        CONN_MAX_AGE=None means connections never close, which can
        cause issues with stale connections.
        """
        from django.conf import settings

        db_settings = settings.DATABASES['default']
        conn_max_age = db_settings.get('CONN_MAX_AGE')

        
        assert conn_max_age is not None and conn_max_age > 0, \
            f"CONN_MAX_AGE should be a positive number, got {conn_max_age}"


class TestTransactionRaceCondition:
    """Tests for transaction race conditions - detects Bug A3."""

    @pytest.mark.bug_a3
    def test_concurrent_application_limit_check(self, job, candidates, user):
        """
        BUG A3: Test race condition in application limit check.

        When multiple candidates apply simultaneously, the limit check
        can be bypassed because it's not atomic.
        """
        from apps.jobs.matching import apply_to_job, MatchingError
        from apps.jobs.models import Application

        # Set a low application limit
        job.max_applications = 3
        job.save()

        # Clear any existing applications
        Application.objects.filter(job=job).delete()

        successful_applications = []
        errors = []

        def apply(candidate):
            try:
                app = apply_to_job(candidate, job, 'Cover letter')
                successful_applications.append(app)
                return True
            except MatchingError as e:
                errors.append(str(e))
                return False
            except Exception as e:
                errors.append(str(e))
                return False

        # Apply with multiple candidates simultaneously
        # Use more candidates than the limit
        test_candidates = candidates[:6]

        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [executor.submit(apply, c) for c in test_candidates]
            [f.result() for f in as_completed(futures)]

        actual_count = Application.objects.filter(job=job).count()

        
        # After fix, this should be exactly max_applications
        # This test may pass or fail randomly due to race condition timing
        if actual_count > job.max_applications:
            pytest.fail(
                f"Race condition: {actual_count} applications created, "
                f"limit was {job.max_applications}"
            )

    @pytest.mark.bug_a3
    def test_safe_apply_with_locking(self, job, candidates, user):
        """
        Test the fixed version with select_for_update.

        This uses apply_to_job_safe which properly locks the job row.
        """
        from apps.jobs.matching import apply_to_job_safe, MatchingError
        from apps.jobs.models import Application

        # Set a low application limit
        job.max_applications = 2
        job.save()

        # Clear any existing applications
        Application.objects.filter(job=job).delete()

        successful = []
        errors = []

        def apply_safe(candidate):
            try:
                app = apply_to_job_safe(candidate, job, 'Cover letter')
                successful.append(app)
                return True
            except MatchingError as e:
                errors.append(str(e))
                return False
            except Exception as e:
                errors.append(str(e))
                return False

        # Try to apply with 5 candidates
        test_candidates = candidates[:5]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(apply_safe, c) for c in test_candidates]
            [f.result() for f in as_completed(futures)]

        actual_count = Application.objects.filter(job=job).count()

        # With proper locking, exactly max_applications should be created
        assert actual_count <= job.max_applications, \
            f"Expected <= {job.max_applications}, got {actual_count}"

    @pytest.mark.bug_a3
    def test_duplicate_application_prevention(self, job, candidate):
        """Test that duplicate applications are prevented."""
        from apps.jobs.matching import apply_to_job, MatchingError
        from apps.jobs.models import Application

        # Clear existing applications
        Application.objects.filter(job=job).delete()

        # First application should succeed
        app1 = apply_to_job(candidate, job, 'First')
        assert app1 is not None

        # Second application should fail
        with pytest.raises(MatchingError, match='already applied'):
            apply_to_job(candidate, job, 'Second')


class TestQueryPerformance:
    """Tests for query performance - detects N+1 bugs."""

    @pytest.mark.bug_a2
    def test_candidate_list_query_count(self, candidates, user, authenticated_client, django_assert_num_queries):
        """
        BUG A2: Test query count for candidate listing.

        With improper prefetching, the view generates N+1 queries.
        """
        # Note: This test requires django_assert_num_queries from pytest-django
        # The actual query count depends on implementation

        # With 10 candidates and proper prefetching, should be ~3-5 queries
        # With N+1 bug, could be 30+ queries

        from apps.candidates.models import Candidate, CandidateSkill
        from django.db.models import Prefetch

        # Simulate what the view should do (correct version)
        with django_assert_num_queries(5) as captured:
            candidates_list = list(
                Candidate.objects.filter(company=user.company)
                .select_related('created_by', 'referred_by')
                .prefetch_related(
                    Prefetch(
                        'candidate_skills',
                        queryset=CandidateSkill.objects.select_related('skill')
                    )
                )
            )
            # Force evaluation of nested data
            for c in candidates_list:
                for cs in c.candidate_skills.all():
                    _ = cs.skill.name
                    _ = cs.proficiency
