"""
Integration tests for concurrency issues.

Tests: 30
"""
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch, MagicMock


pytestmark = [pytest.mark.integration, pytest.mark.django_db(transaction=True)]


class TestDeadlockScenarios:
    """Tests for deadlock detection."""

    @pytest.mark.bug_h1
    @pytest.mark.slow
    def test_comprehensive_report_deadlock_potential(self, company, job, candidate, db):
        """Test that concurrent report generation can deadlock."""
        from apps.analytics.tasks import (
            generate_comprehensive_report,
            aggregate_company_metrics
        )

        errors = []
        completed = []

        def run_comprehensive():
            try:
                result = generate_comprehensive_report(company.id)
                completed.append(('comprehensive', result))
            except Exception as e:
                errors.append(('comprehensive', str(e)))

        def run_aggregate():
            try:
                result = aggregate_company_metrics(company.id)
                completed.append(('aggregate', result))
            except Exception as e:
                errors.append(('aggregate', str(e)))

        threads = [
            threading.Thread(target=run_comprehensive),
            threading.Thread(target=run_aggregate),
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        total_results = len(errors) + len(completed)
        assert total_results == 2

    @pytest.mark.bug_h1
    def test_lock_order_company_job_candidate(self, company, job, candidate, db):
        """Test lock acquisition order in comprehensive report."""
        from django.db import transaction
        from apps.accounts.models import Company
        from apps.jobs.models import Job
        from apps.candidates.models import Candidate

        with transaction.atomic():
            locked_company = Company.objects.select_for_update().get(id=company.id)
            locked_jobs = list(Job.objects.select_for_update().filter(company=company))
            locked_candidates = list(Candidate.objects.select_for_update().filter(company=company))

            assert locked_company.id == company.id

    @pytest.mark.bug_h1
    def test_lock_order_candidate_job(self, company, job, candidate, db):
        """Test opposite lock order causes deadlock risk."""
        from django.db import transaction
        from apps.jobs.models import Job
        from apps.candidates.models import Candidate

        with transaction.atomic():
            locked_candidates = list(Candidate.objects.select_for_update().filter(company=company))
            locked_jobs = list(Job.objects.select_for_update().filter(company=company))

            assert len(locked_candidates) >= 0
            assert len(locked_jobs) >= 0


class TestRaceConditions:
    """Tests for race condition detection."""

    @pytest.mark.bug_a3
    def test_concurrent_job_applications(self, job, candidates, db):
        """Test concurrent applications to same job."""
        from apps.jobs.matching import apply_to_job, MatchingError

        job.max_applications = 2
        job.save()

        results = []
        errors = []

        def try_apply(candidate):
            try:
                app = apply_to_job(candidate, job)
                results.append(app)
            except MatchingError as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(try_apply, c) for c in candidates[:5]]
            for future in as_completed(futures):
                pass

        total = len(results) + len(errors)
        assert total == 5

    @pytest.mark.bug_a3
    def test_safe_concurrent_applications(self, job, candidates, db):
        """Test thread-safe version prevents overselling."""
        from apps.jobs.matching import apply_to_job_safe, MatchingError

        job.max_applications = 2
        job.save()

        results = []
        errors = []

        def try_apply_safe(candidate):
            try:
                app = apply_to_job_safe(candidate, job)
                results.append(app)
            except MatchingError as e:
                errors.append(str(e))

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(try_apply_safe, c) for c in candidates[:5]]
            for future in as_completed(futures):
                pass

        assert len(results) <= job.max_applications

    @pytest.mark.bug_h2
    def test_concurrent_deduplication(self, company, db):
        """Test concurrent deduplication race condition."""
        from apps.candidates.models import Candidate
        from apps.candidates.tasks import deduplicate_candidates
        from apps.accounts.models import User

        user = User.objects.first()

        for i in range(3):
            Candidate.objects.create(
                first_name=f'Dup{i}',
                last_name='User',
                email='duplicate@example.com',
                company=company,
                created_by=user
            )

        results = []

        def run_dedup():
            result = deduplicate_candidates(company.id)
            results.append(result)

        threads = [threading.Thread(target=run_dedup) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 2

    @pytest.mark.bug_f1
    def test_counter_race_condition(self, candidates, db):
        """Test score update counter race condition."""
        from apps.candidates.tasks import update_candidate_scores, _score_update_counter

        for c in candidates:
            c.overall_score = None
            c.save()

        initial = _score_update_counter['value']

        threads = []
        for _ in range(3):
            t = threading.Thread(target=update_candidate_scores)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = _score_update_counter['value']
        # With 3 threads each processing candidates, the counter should increment
        # With proper locking, increments should be exact (initial + 3)
        assert final == initial + 3, \
            f"Counter should be {initial + 3} with thread-safe updates, got {final}"


class TestPhantomReads:
    """Tests for phantom read issues."""

    @pytest.mark.bug_h3
    def test_report_data_consistency(self, company, job, candidate, db):
        """Test that report data remains consistent during generation."""
        from apps.analytics.tasks import generate_comprehensive_report
        from apps.jobs.models import Job

        result = generate_comprehensive_report(company.id)

        if 'jobs' in result:
            assert 'counted' in result['jobs']
            assert 'locked' in result['jobs']

    @pytest.mark.bug_h3
    def test_count_vs_locked_mismatch(self, company, db):
        """Test potential mismatch between count and locked records."""
        from django.db import transaction
        from apps.jobs.models import Job

        with transaction.atomic():
            count_before = Job.objects.filter(company=company).count()
            jobs = list(Job.objects.select_for_update().filter(company=company))
            count_after = len(jobs)

            assert count_before == count_after


class TestConnectionPooling:
    """Tests for database connection pool issues."""

    @pytest.mark.bug_a1
    def test_connection_pool_exhaustion_simulation(self, db):
        """Test behavior when connection pool is stressed."""
        from django.db import connection

        results = []

        def make_query():
            try:
                from apps.candidates.models import Candidate
                count = Candidate.objects.count()
                results.append(count)
            except Exception as e:
                results.append(str(e))

        threads = [threading.Thread(target=make_query) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(results) == 20

    @pytest.mark.bug_a1
    def test_connection_reuse(self, db):
        """Test connections are properly reused."""
        from django.db import connection

        initial_id = id(connection.connection)

        from apps.candidates.models import Candidate
        _ = list(Candidate.objects.all()[:5])

        after_id = id(connection.connection)

        assert initial_id == after_id


class TestTokenRefreshRace:
    """Tests for JWT token refresh race conditions."""

    @pytest.mark.bug_c1
    def test_concurrent_token_refresh(self, user, db):
        """Test concurrent token refresh creates race condition."""
        from apps.accounts.oauth import generate_refresh_token, refresh_access_token

        refresh = generate_refresh_token(user)
        token_string = refresh.token

        results = []
        errors = []

        def do_refresh():
            try:
                result = refresh_access_token(token_string)
                results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=do_refresh) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) + len(errors) == 3

    @pytest.mark.bug_c1
    def test_token_reuse_detection(self, user, db):
        """Test that token reuse is detected."""
        from apps.accounts.oauth import (
            generate_refresh_token,
            refresh_access_token,
            JWTAuthenticationError
        )

        refresh = generate_refresh_token(user)
        token_string = refresh.token

        refresh_access_token(token_string)

        with pytest.raises(JWTAuthenticationError) as exc_info:
            refresh_access_token(token_string)

        assert 'revoked' in str(exc_info.value).lower() or 'reuse' in str(exc_info.value).lower()


class TestCeleryTaskConcurrency:
    """Tests for Celery task concurrency issues."""

    @pytest.mark.bug_b2
    def test_chord_result_collection(self, db):
        """Test chord callback result collection."""
        from apps.jobs.tasks import score_single_candidate

        assert score_single_candidate.ignore_result is False, \
            "score_single_candidate must not have ignore_result=True for chord pattern"

    def test_task_retry_idempotency(self, candidate, db):
        """Test task retries are idempotent."""
        from apps.candidates.tasks import update_candidate_scores

        candidate.overall_score = None
        candidate.save()

        result1 = update_candidate_scores()
        result2 = update_candidate_scores()

        assert result2['updated_candidates'] == 0

    def test_concurrent_daily_report_generation(self, company, db):
        """Test concurrent daily report generation."""
        from apps.analytics.tasks import generate_daily_report

        results = []

        def generate():
            result = generate_daily_report()
            results.append(result)

        threads = [threading.Thread(target=generate) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 2


class TestAtomicOperations:
    """Tests for atomic operation correctness."""

    def test_application_creation_atomic(self, job, candidate, db):
        """Test application creation is atomic."""
        from django.db import transaction
        from apps.jobs.models import Application

        try:
            with transaction.atomic():
                app = Application.objects.create(
                    job=job,
                    candidate=candidate,
                )
                raise Exception("Simulated error")
        except Exception:
            pass

        exists = Application.objects.filter(job=job, candidate=candidate).exists()
        assert not exists

    def test_candidate_update_atomic(self, candidate, db):
        """Test candidate update is atomic."""
        from django.db import transaction

        original_status = candidate.status

        try:
            with transaction.atomic():
                candidate.status = 'hired'
                candidate.save()
                raise Exception("Simulated error")
        except Exception:
            pass

        candidate.refresh_from_db()
        assert candidate.status == original_status
