"""
Unit tests for jobs app.

Tests: 10
"""
import pytest
from django.utils import timezone


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestJobModel:
    """Tests for Job model."""

    def test_create_job(self, company, user):
        """Test creating a job."""
        from apps.jobs.models import Job

        job = Job.objects.create(
            title='Software Engineer',
            company=company,
            description='A great opportunity',
            status='draft',
            created_by=user,
            location='Remote',
        )
        assert job.status == 'draft'
        assert str(job) == f'{job.title} at {company.name}'

    def test_job_publish(self, job):
        """Test publishing a job."""
        job.status = 'draft'
        job.save()

        job.publish()
        job.refresh_from_db()

        assert job.status == 'open'
        assert job.published_at is not None

    def test_job_close(self, job):
        """Test closing a job."""
        job.close()
        job.refresh_from_db()

        assert job.status == 'closed'
        assert job.closed_at is not None


class TestApplicationModel:
    """Tests for Application model."""

    def test_create_application(self, job, candidate):
        """Test creating an application."""
        from apps.jobs.models import Application

        app = Application.objects.create(
            job=job,
            candidate=candidate,
        )
        assert app.status == 'pending'
        assert str(app) == f'{candidate} applied to {job}'

    def test_application_unique_constraint(self, application, job, candidate):
        """Test that same candidate can't apply twice."""
        from apps.jobs.models import Application
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Application.objects.create(
                job=job,
                candidate=candidate,
            )


class TestSkillMatching:
    """Tests for skill matching - detects off-by-one bug."""

    @pytest.mark.bug_e1
    def test_perfect_skill_match_score(self, candidate, job, skills):
        """
        BUG E1: Test that perfect skill match returns 1.0, not 0.99.

        The matching algorithm has an off-by-one error that causes
        perfect matches to return 0.99 instead of 1.0.
        """
        from apps.jobs.matching import calculate_skill_match_score
        from apps.candidates.models import CandidateSkill

        # Give candidate all required skills with max proficiency
        for skill in job.required_skills.all():
            CandidateSkill.objects.get_or_create(
                candidate=candidate,
                skill=skill,
                defaults={'proficiency': 5, 'is_primary': True}
            )

        score = calculate_skill_match_score(candidate, job)

        # Perfect match should be exactly 1.0 — off-by-one bug produces ~0.99
        assert score == 1.0, f"Perfect match should be 1.0, got {score}"

    @pytest.mark.bug_e1
    def test_skill_match_with_no_requirements(self, candidate, company, user):
        """Test matching when job has no skill requirements."""
        from apps.jobs.models import Job
        from apps.jobs.matching import calculate_skill_match_score

        job = Job.objects.create(
            title='No Skills Job',
            company=company,
            description='No skills needed',
            status='open',
            created_by=user,
            location='Anywhere',
        )

        score = calculate_skill_match_score(candidate, job)
        assert score == 1.0  # No requirements = perfect match

    @pytest.mark.bug_e1
    def test_skill_match_partial(self, candidate, job, skills, db):
        """Test partial skill matching."""
        from apps.jobs.matching import calculate_skill_match_score
        from apps.candidates.models import CandidateSkill

        # Candidate only has some skills
        CandidateSkill.objects.filter(candidate=candidate).delete()
        first_skill = job.required_skills.first()
        if first_skill:
            CandidateSkill.objects.create(
                candidate=candidate,
                skill=first_skill,
                proficiency=3,
            )

        score = calculate_skill_match_score(candidate, job)

        # Partial match should be between 0 and 1
        assert 0 < score < 1


class TestExperienceMatching:
    """Tests for experience matching."""

    def test_experience_match_in_range(self, candidate, job):
        """Test candidate with experience in expected range."""
        from apps.jobs.matching import calculate_experience_match_score

        candidate.years_experience = 7
        job.min_experience_years = 5
        job.max_experience_years = 10

        score = calculate_experience_match_score(candidate, job)
        assert score == 1.0

    def test_experience_match_under_qualified(self, candidate, job):
        """Test under-qualified candidate."""
        from apps.jobs.matching import calculate_experience_match_score

        candidate.years_experience = 2
        job.min_experience_years = 5

        score = calculate_experience_match_score(candidate, job)
        assert score < 1.0

    def test_experience_match_over_qualified(self, candidate, job):
        """Test over-qualified candidate."""
        from apps.jobs.matching import calculate_experience_match_score

        candidate.years_experience = 20
        job.min_experience_years = 5
        job.max_experience_years = 10

        score = calculate_experience_match_score(candidate, job)
        assert score < 1.0
        assert score >= 0.5  # Over-qualification has smaller penalty
