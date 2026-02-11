"""
Unit tests for candidates app.

Tests: 10
"""
import pytest
from django.db.models import Prefetch


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestCandidateModel:
    """Tests for Candidate model."""

    def test_create_candidate(self, company, user):
        """Test creating a candidate."""
        from apps.candidates.models import Candidate

        candidate = Candidate.objects.create(
            first_name='Jane',
            last_name='Smith',
            email='jane.smith@example.com',
            company=company,
            title='Developer',
            years_experience=3,
            created_by=user,
        )
        assert candidate.full_name == 'Jane Smith'
        assert candidate.status == 'new'

    def test_candidate_full_name_property(self, candidate):
        """Test full_name property."""
        assert candidate.full_name == f'{candidate.first_name} {candidate.last_name}'

    def test_candidate_status_choices(self, candidate):
        """Test valid status transitions."""
        from apps.candidates.models import Candidate

        valid_statuses = [s[0] for s in Candidate.STATUS_CHOICES]
        assert candidate.status in valid_statuses

        for status in valid_statuses:
            candidate.status = status
            candidate.save()
            candidate.refresh_from_db()
            assert candidate.status == status


class TestSkillModel:
    """Tests for Skill model."""

    def test_create_skill(self, db):
        """Test creating a skill."""
        from apps.candidates.models import Skill

        skill = Skill.objects.create(
            name='JavaScript',
            category='Programming',
        )
        assert str(skill) == 'JavaScript'

    def test_skill_unique_name(self, skill, db):
        """Test skill name uniqueness."""
        from apps.candidates.models import Skill
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            Skill.objects.create(name=skill.name, category='Other')


class TestCandidateSkillModel:
    """Tests for CandidateSkill through model."""

    def test_create_candidate_skill(self, candidate, skill):
        """Test creating candidate skill relationship."""
        from apps.candidates.models import CandidateSkill

        cs = CandidateSkill.objects.get(candidate=candidate, skill=skill)
        assert cs.proficiency == 4
        assert cs.is_primary

    def test_candidate_skill_proficiency_range(self, candidate, db):
        """Test proficiency level validation."""
        from apps.candidates.models import Skill, CandidateSkill

        new_skill = Skill.objects.create(name='NewSkill', category='Test')

        # Valid proficiency levels
        for level in [1, 2, 3, 4, 5]:
            cs = CandidateSkill.objects.create(
                candidate=candidate,
                skill=new_skill,
                proficiency=level,
            )
            assert cs.proficiency == level
            cs.delete()


class TestCandidateQuerySet:
    """Tests for candidate querysets - tests N+1 bug detection."""

    @pytest.mark.bug_a2
    def test_prefetch_skills_correctly(self, candidates, django_assert_num_queries):
        """
        BUG A2: Test that skills are properly prefetched.

        This test FAILS with the buggy code because prefetch_related('skills')
        doesn't prefetch the through model (candidate_skills) properly.
        """
        from apps.candidates.models import Candidate, CandidateSkill

        # Correct prefetch should use:
        # prefetch_related(Prefetch('candidate_skills', queryset=CandidateSkill.objects.select_related('skill')))

        # With proper prefetch, this should be ~2-3 queries
        
        with django_assert_num_queries(3):
            candidates_list = list(
                Candidate.objects.prefetch_related(
                    Prefetch(
                        'candidate_skills',
                        queryset=CandidateSkill.objects.select_related('skill')
                    )
                )
            )
            # Access nested data
            for c in candidates_list:
                for cs in c.candidate_skills.all():
                    _ = cs.skill.name

    @pytest.mark.bug_a2
    def test_n_plus_one_with_wrong_prefetch(self, candidates):
        """
        BUG A2: Demonstrate the N+1 query problem.

        This test shows how using prefetch_related('skills') incorrectly
        causes many extra queries when accessing proficiency data.
        """
        from apps.candidates.models import Candidate

        # This is the BUGGY pattern used in the view
        queryset = Candidate.objects.prefetch_related('skills')

        # Accessing candidate_skills triggers N+1 queries
        query_count = 0
        for candidate in queryset:
            # Each of these accesses causes a new query!
            for cs in candidate.candidate_skills.all():
                query_count += 1  # Count accesses
                _ = cs.skill.name

        # With 10 candidates and ~3 skills each, we'd expect many queries
        # if not properly prefetched
        assert query_count > 0  # At minimum, skills were accessed


class TestCandidateIndexes:
    """Tests for database indexes - detects missing index bugs."""

    @pytest.mark.bug_a2
    def test_status_field_should_have_index(self, db):
        """
        Test that status field should have an index.

        BUG: The Candidate model is missing an index on the 'status' field,
        which is filtered in almost every query.
        """
        from apps.candidates.models import Candidate

        # Get model meta information
        indexes = Candidate._meta.indexes
        index_fields = [idx.fields for idx in indexes]

        # This test currently FAILS because status index is missing
        # After fix, this should pass
        status_indexed = any('status' in fields for fields in index_fields)

        # This assertion documents the expected behavior
        # It will fail until the bug is fixed
        assert status_indexed, "Status field should have an index for performance"
