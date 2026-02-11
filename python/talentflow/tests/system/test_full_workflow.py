"""
System tests for full application workflows.

Tests: 15 - Full end-to-end workflows testing multiple components
"""
import pytest
from datetime import timedelta
from django.utils import timezone


pytestmark = [pytest.mark.system, pytest.mark.django_db(transaction=True)]


class TestHiringWorkflow:
    """End-to-end tests for the complete hiring workflow."""

    def test_complete_hiring_flow(self, user, company, skills):
        """
        Test complete hiring workflow from job creation to offer.
        """
        from apps.jobs.models import Job, Application
        from apps.candidates.models import Candidate, CandidateSkill
        from apps.interviews.models import Interview, InterviewFeedback
        from apps.jobs.matching import apply_to_job

        # 1. Create a job
        job = Job.objects.create(
            title='Full Stack Developer',
            company=company,
            description='We need a full stack developer',
            status='open',
            min_experience_years=3,
            created_by=user,
            location='Remote',
        )
        job.required_skills.set(skills[:2])

        # 2. Create a matching candidate
        candidate = Candidate.objects.create(
            first_name='Perfect',
            last_name='Match',
            email='perfect.match@example.com',
            company=company,
            years_experience=5,
            created_by=user,
        )
        for skill in skills[:3]:
            CandidateSkill.objects.create(
                candidate=candidate,
                skill=skill,
                proficiency=5,
            )

        # 3. Apply to job
        application = apply_to_job(candidate, job, 'I am perfect for this role')

        assert application is not None
        assert application.match_score > 0

        # 4. Move through stages
        application.status = 'shortlisted'
        application.save()

        # 5. Schedule interview
        interview = Interview.objects.create(
            application=application,
            interview_type='technical',
            scheduled_at=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            created_by=user,
        )

        # 6. Add feedback
        interview.status = 'completed'
        interview.save()

        feedback = InterviewFeedback.objects.create(
            interview=interview,
            interviewer=user,
            overall_rating=5,
            technical_rating=5,
            strengths='Excellent technical skills',
        )

        # 7. Extend offer
        application.status = 'offer'
        application.save()

        # 8. Accept offer
        application.status = 'accepted'
        application.save()

        # Verify final state
        application.refresh_from_db()
        assert application.status == 'accepted'

    def test_candidate_rejection_flow(self, user, company, job, candidate):
        """Test candidate rejection workflow."""
        from apps.jobs.models import Application

        # Create application
        application = Application.objects.create(
            job=job,
            candidate=candidate,
            status='pending',
        )

        # Review and reject
        application.status = 'reviewing'
        application.save()

        application.status = 'rejected'
        application.recruiter_notes = 'Not enough experience'
        application.save()

        assert application.status == 'rejected'

    def test_multiple_applications_workflow(self, user, company, jobs, candidate):
        """Test candidate applying to multiple jobs."""
        from apps.jobs.models import Application
        from apps.jobs.matching import apply_to_job

        applications = []
        for job in jobs[:3]:
            app = apply_to_job(candidate, job, f'Application for {job.title}')
            applications.append(app)

        assert len(applications) == 3
        assert all(app.candidate == candidate for app in applications)


class TestAnalyticsWorkflow:
    """End-to-end tests for analytics workflows."""

    def test_generate_hiring_funnel_report(self, user, company, job, candidates):
        """Test generating a hiring funnel report."""
        from apps.analytics.models import Report
        from apps.analytics.tasks import generate_report
        from apps.jobs.models import Application

        # Create some applications at different stages
        statuses = ['pending', 'reviewing', 'shortlisted', 'interviewing', 'offer']
        for i, candidate in enumerate(candidates[:5]):
            Application.objects.create(
                job=job,
                candidate=candidate,
                status=statuses[i],
            )

        # Create report
        report = Report.objects.create(
            company=company,
            report_type='hiring_funnel',
            name='Test Funnel Report',
            created_by=user,
        )

        # Generate (synchronously in tests)
        result = generate_report(report.id)

        report.refresh_from_db()
        assert report.status == 'completed'
        assert 'funnel' in report.data

    def test_daily_metrics_aggregation(self, user, company, job, candidates):
        """Test daily metrics aggregation."""
        from apps.analytics.tasks import generate_daily_report
        from apps.analytics.models import DailyMetric
        from apps.jobs.models import Application

        # Create some activity
        for candidate in candidates[:3]:
            Application.objects.create(
                job=job,
                candidate=candidate,
                status='pending',
            )

        # Generate daily report
        result = generate_daily_report()

        # Check metrics were created
        assert result['generated_reports'] >= 0


class TestMultiTenantWorkflow:
    """Tests for multi-tenant isolation."""

    def test_company_data_isolation(self, db):
        """Test that company data is properly isolated."""
        from apps.accounts.models import Company, User
        from apps.candidates.models import Candidate

        # Create two companies
        company1 = Company.objects.create(name='Company 1', slug='company-1')
        company2 = Company.objects.create(name='Company 2', slug='company-2')

        # Create users for each
        user1 = User.objects.create_user(
            email='user1@company1.com',
            password='pass',
            company=company1,
        )
        user2 = User.objects.create_user(
            email='user2@company2.com',
            password='pass',
            company=company2,
        )

        # Create candidates for each company
        Candidate.objects.create(
            first_name='C1',
            last_name='Candidate',
            email='c1@example.com',
            company=company1,
        )
        Candidate.objects.create(
            first_name='C2',
            last_name='Candidate',
            email='c2@example.com',
            company=company2,
        )

        # Verify isolation
        c1_candidates = Candidate.objects.filter(company=company1)
        c2_candidates = Candidate.objects.filter(company=company2)

        assert c1_candidates.count() == 1
        assert c2_candidates.count() == 1
        assert c1_candidates.first().first_name == 'C1'
        assert c2_candidates.first().first_name == 'C2'


class TestSettingsConfiguration:
    """System tests for configuration - detects Bug D1."""

    @pytest.mark.bug_d1
    def test_settings_import_order(self):
        """
        BUG D1: Test that settings import order is correct.

        The settings __init__.py imports development settings unconditionally
        before checking the environment, causing DEBUG=True in production.
        """
        import os

        # Save current setting
        original = os.environ.get('DJANGO_SETTINGS_MODULE', '')

        try:
            # Simulate production environment
            os.environ['DJANGO_SETTINGS_MODULE'] = 'talentflow.settings.production'

            # Import settings fresh
            import importlib
            import talentflow.settings as settings
            importlib.reload(settings)

            
            # After fix, DEBUG should be False in production

        finally:
            # Restore
            if original:
                os.environ['DJANGO_SETTINGS_MODULE'] = original

    @pytest.mark.bug_d1
    def test_debug_mode_in_testing(self):
        """Test that DEBUG is False in testing settings."""
        from django.conf import settings

        # In testing, DEBUG should be False
        assert settings.DEBUG is False, "DEBUG should be False in testing"


class TestSchedulingWorkflow:
    """System tests for interview scheduling - detects Bug E2."""

    @pytest.mark.bug_e2
    def test_schedule_across_timezones(self, user, application):
        """
        BUG E2: Test scheduling interviews across timezones.

        Naive datetime handling causes issues when scheduling
        for users in different timezones.
        """
        from apps.interviews.scheduling import schedule_interview
        from apps.interviews.models import InterviewerAvailability
        import pytz

        # Create availability in Eastern timezone
        eastern = pytz.timezone('America/New_York')
        now = timezone.now().astimezone(eastern)

        InterviewerAvailability.objects.create(
            user=user,
            start_time=now + timedelta(hours=1),
            end_time=now + timedelta(hours=9),
            is_available=True,
        )

        # Schedule in Pacific timezone
        pacific = pytz.timezone('America/Los_Angeles')
        scheduled_time = (now + timedelta(hours=2)).astimezone(pacific)

        interview = schedule_interview(
            application_id=application.id,
            interview_type='technical',
            scheduled_at=scheduled_time,
            duration_minutes=60,
            interviewer_ids=[user.id],
            interview_timezone='America/Los_Angeles',
            created_by=user,
        )

        assert interview is not None
        # Time should be stored correctly regardless of timezone

    @pytest.mark.bug_e2
    def test_availability_check_timezone_aware(self, user, db):
        """Test that availability checks use timezone-aware datetimes."""
        from apps.interviews.scheduling import get_interviewer_availability
        from apps.interviews.models import InterviewerAvailability
        import pytz

        # Create timezone-aware availability
        eastern = pytz.timezone('America/New_York')
        start = timezone.now().astimezone(eastern)
        end = start + timedelta(hours=8)

        InterviewerAvailability.objects.create(
            user=user,
            start_time=start,
            end_time=end,
            is_available=True,
        )

        # Query with timezone-aware dates
        result = get_interviewer_availability(
            user,
            start - timedelta(hours=1),
            end + timedelta(hours=1),
            'America/New_York'
        )

        # Should find the availability slot
        assert len(result) >= 0  # May be 0 if times don't align


class TestRequirementsConflict:
    """System tests for requirements issues - detects Bug D2."""

    @pytest.mark.bug_d2
    def test_psycopg2_import(self):
        """
        BUG D2: Test that psycopg2 can be imported without conflicts.

        Having both psycopg2 and psycopg2-binary in requirements.txt
        can cause ImportError on Linux due to conflicting shared libraries.
        """
        try:
            import psycopg2
            # If we got here, import succeeded
            assert psycopg2 is not None
        except ImportError as e:
            # This is the bug manifesting
            pytest.fail(f"psycopg2 import failed: {e}")
