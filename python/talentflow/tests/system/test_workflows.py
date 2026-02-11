"""
System tests for complete workflows.

Tests: 35
"""
import pytest
from unittest.mock import patch, MagicMock


pytestmark = [pytest.mark.system, pytest.mark.django_db(transaction=True)]


class TestHiringWorkflow:
    """End-to-end tests for the hiring workflow."""

    def test_complete_hiring_pipeline(self, company, user, job, candidate, db):
        """Test complete hiring pipeline from application to hire."""
        from apps.jobs.matching import apply_to_job
        from apps.jobs.models import Application

        app = apply_to_job(candidate, job)

        app.status = 'shortlisted'
        app.save()

        app.status = 'interviewing'
        app.save()

        app.status = 'offer'
        app.save()

        app.status = 'accepted'
        app.save()

        app.refresh_from_db()
        assert app.status == 'accepted'

    def test_rejection_workflow(self, company, user, job, candidate, db):
        """Test candidate rejection workflow."""
        from apps.jobs.matching import apply_to_job
        from apps.jobs.models import Application

        app = apply_to_job(candidate, job)

        app.status = 'rejected'
        app.save()

        app.refresh_from_db()
        assert app.status == 'rejected'

    def test_multiple_candidates_same_job(self, job, candidates, db):
        """Test multiple candidates applying to same job."""
        from apps.jobs.matching import apply_to_job
        from apps.jobs.models import Application

        for candidate in candidates[:3]:
            apply_to_job(candidate, job)

        apps = Application.objects.filter(job=job)
        assert apps.count() == 3

    def test_candidate_multiple_applications(self, candidate, company, user, db):
        """Test candidate applying to multiple jobs."""
        from apps.jobs.models import Job, Application
        from apps.jobs.matching import apply_to_job

        jobs = []
        for i in range(3):
            job = Job.objects.create(
                title=f'Test Job {i}',
                company=company,
                description='Test',
                status='open',
                created_by=user,
                location='Remote'
            )
            jobs.append(job)

        for job in jobs:
            apply_to_job(candidate, job)

        apps = Application.objects.filter(candidate=candidate)
        assert apps.count() == 3


class TestReportingWorkflow:
    """End-to-end tests for reporting workflow."""

    def test_generate_and_cache_report(self, company, db):
        """Test generating and caching a report."""
        from apps.analytics.tasks import generate_report
        from apps.analytics.models import Report

        report = Report.objects.create(
            company=company,
            report_type='hiring_funnel',
            status='pending'
        )

        with patch('apps.analytics.tasks.cache_report_data') as mock_cache:
            result = generate_report(report.id)

            report.refresh_from_db()
            assert report.status == 'completed'

    def test_daily_report_generation(self, company, job, candidate, db):
        """Test daily report generation."""
        from apps.analytics.tasks import generate_daily_report

        result = generate_daily_report()

        assert 'generated_reports' in result

    @pytest.mark.bug_h1
    def test_comprehensive_report_full_cycle(self, company, job, candidate, db):
        """Test comprehensive report generation cycle."""
        from apps.analytics.tasks import generate_comprehensive_report

        result = generate_comprehensive_report(company.id)

        if 'error' not in result:
            assert 'jobs' in result or 'candidates' in result


class TestCandidateLifecycle:
    """Tests for candidate lifecycle management."""

    def test_candidate_creation_to_hire(self, company, user, job, db):
        """Test full candidate lifecycle from creation to hire."""
        from apps.candidates.models import Candidate
        from apps.jobs.matching import apply_to_job
        from apps.candidates.tasks import _calculate_candidate_score

        candidate = Candidate.objects.create(
            first_name='Lifecycle',
            last_name='Test',
            email='lifecycle@example.com',
            company=company,
            created_by=user,
            years_experience=5
        )

        score = _calculate_candidate_score(candidate)
        candidate.overall_score = score
        candidate.save()

        app = apply_to_job(candidate, job)

        candidate.status = 'hired'
        candidate.save()

        assert candidate.status == 'hired'
        assert candidate.overall_score >= 0

    def test_candidate_with_notes_and_skills(self, company, user, db):
        """Test candidate with full profile data."""
        from apps.candidates.models import Candidate, CandidateSkill, CandidateNote, Skill

        candidate = Candidate.objects.create(
            first_name='Full',
            last_name='Profile',
            email='fullprofile@example.com',
            company=company,
            created_by=user,
            years_experience=10,
            resume_url='https://example.com/resume.pdf',
            linkedin_url='https://linkedin.com/in/test'
        )

        skill, _ = Skill.objects.get_or_create(name='FullTest', defaults={'category': 'Test'})
        CandidateSkill.objects.create(candidate=candidate, skill=skill, proficiency=5)

        CandidateNote.objects.create(
            candidate=candidate,
            author=user,
            content='Excellent candidate',
            note_type='general'
        )

        assert candidate.candidate_skills.count() == 1
        assert candidate.activity_notes.count() == 1


class TestBulkOperations:
    """Tests for bulk operations."""

    @pytest.mark.bug_g3
    def test_bulk_candidate_import(self, company, db):
        """Test bulk candidate import workflow."""
        from apps.candidates.tasks import bulk_import_candidates

        candidates_data = [
            {'first_name': f'Bulk{i}', 'last_name': 'Test', 'email': f'bulk{i}@test.com'}
            for i in range(10)
        ]

        result = bulk_import_candidates(company.id, candidates_data)

        assert result['created'] <= len(candidates_data)

    def test_bulk_deduplication(self, company, user, db):
        """Test bulk deduplication workflow."""
        from apps.candidates.models import Candidate
        from apps.candidates.tasks import deduplicate_candidates

        for i in range(3):
            Candidate.objects.create(
                first_name=f'Dup{i}',
                last_name='Test',
                email='duplicate_bulk@test.com',
                company=company,
                created_by=user
            )

        result = deduplicate_candidates(company.id)

        remaining = Candidate.objects.filter(
            company=company,
            email='duplicate_bulk@test.com'
        ).count()

        assert remaining == 1 or result['merged'] > 0


class TestJobPublishingWorkflow:
    """Tests for job publishing workflow."""

    def test_job_draft_to_publish_to_close(self, company, user, db):
        """Test job lifecycle from draft to closed."""
        from apps.jobs.models import Job

        job = Job.objects.create(
            title='Lifecycle Job',
            company=company,
            description='Test lifecycle',
            status='draft',
            created_by=user,
            location='Remote'
        )

        assert job.status == 'draft'

        job.publish()
        assert job.status == 'open'
        assert job.published_at is not None

        job.close()
        assert job.status == 'closed'
        assert job.closed_at is not None

    def test_job_with_skills_requirements(self, company, user, db):
        """Test job with skill requirements."""
        from apps.jobs.models import Job
        from apps.candidates.models import Skill

        skill1, _ = Skill.objects.get_or_create(name='Required1', defaults={'category': 'Tech'})
        skill2, _ = Skill.objects.get_or_create(name='Preferred1', defaults={'category': 'Tech'})

        job = Job.objects.create(
            title='Skilled Job',
            company=company,
            description='Needs skills',
            status='open',
            created_by=user,
            location='Remote'
        )

        job.required_skills.add(skill1)
        job.preferred_skills.add(skill2)

        assert job.required_skills.count() == 1
        assert job.preferred_skills.count() == 1


class TestAuthenticationWorkflow:
    """Tests for authentication workflow."""

    def test_login_generate_tokens(self, user, db):
        """Test login generates access and refresh tokens."""
        from apps.accounts.oauth import generate_access_token, generate_refresh_token

        access = generate_access_token(user)
        refresh = generate_refresh_token(user)

        assert access is not None
        assert refresh.token is not None

    @pytest.mark.bug_c1
    def test_token_refresh_workflow(self, user, db):
        """Test token refresh workflow."""
        from apps.accounts.oauth import (
            generate_refresh_token,
            refresh_access_token
        )

        refresh = generate_refresh_token(user)
        token_string = refresh.token

        result = refresh_access_token(token_string)

        assert 'access_token' in result
        assert 'refresh_token' in result
        assert result['refresh_token'] != token_string

    def test_logout_revoke_tokens(self, user, db):
        """Test logout revokes all tokens."""
        from apps.accounts.oauth import (
            generate_refresh_token,
            revoke_all_tokens
        )

        generate_refresh_token(user)
        generate_refresh_token(user)
        generate_refresh_token(user)

        count = revoke_all_tokens(user)

        assert count == 3


class TestInterviewScheduling:
    """Tests for interview scheduling workflow."""

    def test_schedule_interview(self, user, application, db):
        """Test scheduling an interview."""
        from apps.interviews.models import Interview
        from django.utils import timezone
        from datetime import timedelta

        interview = Interview.objects.create(
            application=application,
            scheduled_at=timezone.now() + timedelta(days=2),
            duration_minutes=60,
            interview_type='phone'
        )
        interview.interviewers.add(user)

        assert interview.interviewers.count() == 1
        assert interview.status == 'scheduled'

    @pytest.mark.bug_e2
    def test_find_available_slots(self, user, db):
        """Test finding available interview slots."""
        from apps.interviews.scheduling import find_available_slots
        from django.utils import timezone
        from datetime import timedelta

        start = timezone.now()
        end = start + timedelta(days=5)

        slots = find_available_slots(
            user_ids=[user.id],
            start_date=start,
            end_date=end
        )

        assert isinstance(slots, list)


class TestDataExport:
    """Tests for data export workflows."""

    @pytest.mark.bug_g2
    def test_export_candidates_csv(self, candidates, db):
        """Test exporting candidates to CSV."""
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Name', 'Email', 'Status'])

        for c in candidates:
            writer.writerow([c.full_name, c.email, c.status])

        content = output.getvalue()
        lines = content.strip().split('\n')

        assert len(lines) == len(candidates) + 1

    def test_export_report_json(self, company, db):
        """Test exporting report as JSON."""
        import json
        from apps.analytics.tasks import generate_daily_report

        result = generate_daily_report()

        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        assert parsed == result


class TestSearchWorkflow:
    """Tests for search functionality."""

    def test_basic_candidate_search(self, candidates, db):
        """Test basic candidate search."""
        from apps.candidates.models import Candidate

        query = candidates[0].first_name[:3]
        results = Candidate.objects.filter(first_name__icontains=query)

        assert results.count() >= 1

    @pytest.mark.bug_i1
    def test_advanced_search_workflow(self, user, candidates, db):
        """Test advanced search with filters."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        response = api_client.post(
            '/api/v1/candidates/advanced-search/',
            {'query': 'test', 'order_by': 'created_at'},
            format='json'
        )

        assert response.status_code in [200, 404]


class TestCleanupWorkflow:
    """Tests for cleanup operations."""

    def test_cleanup_old_reports(self, company, db):
        """Test cleaning up old reports."""
        from apps.analytics.tasks import cleanup_old_reports
        from apps.analytics.models import Report
        from django.utils import timezone
        from datetime import timedelta

        old_report = Report.objects.create(
            company=company,
            report_type='hiring_funnel',
            status='completed',
            created_at=timezone.now() - timedelta(days=100)
        )
        old_report.created_at = timezone.now() - timedelta(days=100)
        old_report.save()

        result = cleanup_old_reports()

        assert 'deleted_reports' in result

    def test_cleanup_expired_cache(self, db):
        """Test cleaning up expired cache entries."""
        from apps.analytics.tasks import cleanup_expired_cache

        result = cleanup_expired_cache()

        assert 'deleted_cache_entries' in result
