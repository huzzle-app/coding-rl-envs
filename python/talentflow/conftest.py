"""
TalentFlow Test Configuration

Pytest fixtures and configuration for the test suite.
"""
import os
import pytest
from datetime import timedelta

# Set Django settings before imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'talentflow.settings.testing')

import django
django.setup()

from django.utils import timezone
from rest_framework.test import APIClient


# ============================================================================
# Factories
# ============================================================================

@pytest.fixture
def api_client():
    """DRF API client."""
    return APIClient()


@pytest.fixture
def company(db):
    """Create a test company."""
    from apps.accounts.models import Company
    return Company.objects.create(
        name='Test Company',
        slug='test-company',
        domain='test.example.com',
        subscription_tier='professional',
    )


@pytest.fixture
def user(db, company):
    """Create a test user."""
    from apps.accounts.models import User
    return User.objects.create_user(
        email='testuser@test.example.com',
        password='testpass123',
        first_name='Test',
        last_name='User',
        company=company,
        role='recruiter',
    )


@pytest.fixture
def admin_user(db, company):
    """Create a test admin user."""
    from apps.accounts.models import User
    return User.objects.create_superuser(
        email='admin@test.example.com',
        password='adminpass123',
        first_name='Admin',
        last_name='User',
        company=company,
    )


@pytest.fixture
def authenticated_client(api_client, user):
    """API client authenticated as regular user."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def skill(db):
    """Create a test skill."""
    from apps.candidates.models import Skill
    obj, _ = Skill.objects.get_or_create(
        name='Python',
        defaults={'category': 'Programming'},
    )
    return obj


@pytest.fixture
def skills(db):
    """Create multiple test skills."""
    from apps.candidates.models import Skill
    return [
        Skill.objects.get_or_create(name='Python', defaults={'category': 'Programming'})[0],
        Skill.objects.get_or_create(name='Django', defaults={'category': 'Framework'})[0],
        Skill.objects.get_or_create(name='PostgreSQL', defaults={'category': 'Database'})[0],
        Skill.objects.get_or_create(name='Redis', defaults={'category': 'Database'})[0],
        Skill.objects.get_or_create(name='Docker', defaults={'category': 'DevOps'})[0],
    ]


@pytest.fixture
def candidate(db, company, user, skill):
    """Create a test candidate."""
    from apps.candidates.models import Candidate, CandidateSkill
    candidate = Candidate.objects.create(
        first_name='John',
        last_name='Doe',
        email='john.doe@example.com',
        company=company,
        status='new',
        title='Software Engineer',
        years_experience=5,
        created_by=user,
    )
    CandidateSkill.objects.create(
        candidate=candidate,
        skill=skill,
        proficiency=4,
        is_primary=True,
    )
    return candidate


@pytest.fixture
def candidates(db, company, user, skills):
    """Create multiple test candidates with skills."""
    from apps.candidates.models import Candidate, CandidateSkill
    candidates = []
    for i in range(10):
        candidate = Candidate.objects.create(
            first_name=f'Candidate{i}',
            last_name='Test',
            email=f'candidate{i}@example.com',
            company=company,
            status='new',
            title='Software Engineer',
            years_experience=i + 1,
            created_by=user,
        )
        # Add some skills
        for skill in skills[:3]:
            CandidateSkill.objects.create(
                candidate=candidate,
                skill=skill,
                proficiency=min(5, i % 5 + 1),
            )
        candidates.append(candidate)
    return candidates


@pytest.fixture
def job(db, company, user, skills):
    """Create a test job."""
    from apps.jobs.models import Job
    job = Job.objects.create(
        title='Senior Python Developer',
        company=company,
        department='Engineering',
        description='We are looking for a senior Python developer.',
        status='open',
        employment_type='full_time',
        experience_level='senior',
        location='San Francisco, CA',
        is_remote=True,
        remote_type='hybrid',
        salary_min=120000,
        salary_max=180000,
        min_experience_years=5,
        pipeline_stages=['Applied', 'Phone Screen', 'Technical', 'Onsite', 'Offer'],
        hiring_manager=user,
        created_by=user,
    )
    job.required_skills.set(skills[:3])
    job.preferred_skills.set(skills[3:])
    return job


@pytest.fixture
def jobs(db, company, user, skills):
    """Create multiple test jobs."""
    from apps.jobs.models import Job
    jobs_list = []
    for i in range(5):
        job = Job.objects.create(
            title=f'Test Job {i}',
            company=company,
            department='Engineering',
            description=f'Test job description {i}',
            status='open',
            employment_type='full_time',
            experience_level='mid',
            location='Remote',
            min_experience_years=i,
            created_by=user,
        )
        job.required_skills.set(skills[:2])
        jobs_list.append(job)
    return jobs_list


@pytest.fixture
def application(db, job, candidate):
    """Create a test application."""
    from apps.jobs.models import Application
    return Application.objects.create(
        job=job,
        candidate=candidate,
        status='pending',
        match_score=0.75,
    )


@pytest.fixture
def interview(db, application, user):
    """Create a test interview."""
    from apps.interviews.models import Interview, InterviewParticipant
    interview = Interview.objects.create(
        application=application,
        interview_type='technical',
        status='scheduled',
        scheduled_at=timezone.now() + timedelta(days=1),
        duration_minutes=60,
        timezone='America/New_York',
        created_by=user,
    )
    InterviewParticipant.objects.create(
        interview=interview,
        user=user,
        role='technical',
        status='accepted',
    )
    return interview


@pytest.fixture
def refresh_token(db, user):
    """Create a test refresh token."""
    from apps.accounts.models import RefreshToken
    import secrets
    return RefreshToken.objects.create(
        user=user,
        token=secrets.token_urlsafe(32),
        expires_at=timezone.now() + timedelta(days=1),
    )


@pytest.fixture
def oauth_state(db):
    """Create a test OAuth state."""
    from apps.accounts.models import OAuthState
    import secrets
    return OAuthState.objects.create(
        state=secrets.token_urlsafe(32),
        provider='google',
        redirect_uri='http://localhost:8000/oauth/callback',
        expires_at=timezone.now() + timedelta(minutes=10),
    )


@pytest.fixture
def interviewer_availability(db, user):
    """Create test interviewer availability."""
    from apps.interviews.models import InterviewerAvailability
    return InterviewerAvailability.objects.create(
        user=user,
        start_time=timezone.now() + timedelta(hours=1),
        end_time=timezone.now() + timedelta(hours=5),
        is_available=True,
    )


# ============================================================================
# Test utilities
# ============================================================================

@pytest.fixture
def mock_redis(mocker):
    """Mock Redis for tests that don't need real Redis."""
    mock = mocker.patch('redis.from_url')
    mock_client = mocker.MagicMock()
    mock.return_value = mock_client
    return mock_client


@pytest.fixture
def celery_eager(settings):
    """Run Celery tasks eagerly (synchronously)."""
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


# ============================================================================
# Database fixtures
# ============================================================================

@pytest.fixture(scope='session')
def django_db_setup():
    """Configure database for tests."""
    pass


@pytest.fixture
def db_connection_count(db):
    """Track database connection count for testing pool issues."""
    from django.db import connection
    return lambda: len(connection.queries)
