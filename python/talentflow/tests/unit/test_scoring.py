"""
Unit tests for candidate and job scoring systems.

Tests: 35
"""
import pytest
from decimal import Decimal


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestCandidateScoreCalculation:
    """Tests for candidate score calculation."""

    def test_basic_score_calculation(self, candidate):
        """Test basic score calculation returns a value."""
        from apps.candidates.tasks import _calculate_candidate_score

        score = _calculate_candidate_score(candidate)
        assert 0 <= score <= 100

    def test_score_with_experience(self, candidate):
        """Test experience contributes to score."""
        from apps.candidates.tasks import _calculate_candidate_score

        candidate.years_experience = 10
        score = _calculate_candidate_score(candidate)
        assert score > 0

    @pytest.mark.bug_f2
    def test_score_with_seven_years_experience(self, candidate):
        """Test score calculation with exactly 7 years experience."""
        from apps.candidates.tasks import _calculate_candidate_score

        candidate.years_experience = 7
        score = _calculate_candidate_score(candidate)

        expected_base = (7 / 15) * 30
        assert score == pytest.approx(expected_base, abs=0.01)

    @pytest.mark.bug_f2
    def test_score_with_eight_skills(self, candidate, skill, db):
        """Test score calculation with exactly 8 skills."""
        from apps.candidates.tasks import _calculate_candidate_score
        from apps.candidates.models import Skill, CandidateSkill

        CandidateSkill.objects.filter(candidate=candidate).delete()

        for i in range(8):
            s, _ = Skill.objects.get_or_create(
                name=f'TestSkill{i}',
                defaults={'category': 'Test'}
            )
            CandidateSkill.objects.create(
                candidate=candidate,
                skill=s,
                proficiency=3,
                is_primary=(i < 2)
            )

        score = _calculate_candidate_score(candidate)
        assert score == 8 * 4 + 2 * 5

    def test_score_with_complete_profile(self, candidate):
        """Test profile completeness bonus."""
        from apps.candidates.tasks import _calculate_candidate_score

        candidate.resume_url = 'https://example.com/resume.pdf'
        candidate.linkedin_url = 'https://linkedin.com/in/test'
        candidate.portfolio_url = 'https://portfolio.example.com'

        score = _calculate_candidate_score(candidate)
        assert score >= 30

    def test_score_max_is_100(self, candidate, db):
        """Test score cannot exceed 100."""
        from apps.candidates.tasks import _calculate_candidate_score
        from apps.candidates.models import Skill, CandidateSkill

        candidate.years_experience = 20
        candidate.resume_url = 'https://example.com/resume.pdf'
        candidate.linkedin_url = 'https://linkedin.com/in/test'
        candidate.portfolio_url = 'https://portfolio.example.com'

        for i in range(15):
            s, _ = Skill.objects.get_or_create(
                name=f'MaxSkill{i}',
                defaults={'category': 'Test'}
            )
            CandidateSkill.objects.create(
                candidate=candidate,
                skill=s,
                proficiency=5,
                is_primary=True
            )

        score = _calculate_candidate_score(candidate)
        assert score <= 100

    @pytest.mark.bug_f2
    def test_score_consistency_across_values(self, candidate, db):
        """Test scoring is consistent for edge values."""
        from apps.candidates.tasks import _calculate_candidate_score
        from apps.candidates.models import Skill, CandidateSkill

        CandidateSkill.objects.filter(candidate=candidate).delete()

        results = {}
        for years in [6, 7, 8]:
            candidate.years_experience = years
            results[years] = _calculate_candidate_score(candidate)

        assert results[7] > results[6]
        assert results[8] > results[7]


class TestWeightedScoreCalculation:
    """Tests for weighted score functions."""

    @pytest.mark.bug_g4
    def test_weighted_score_basic(self):
        """Test basic weighted score calculation."""
        from apps.jobs.matching import calculate_weighted_score

        scores = [0.8, 0.6, 0.9]
        weights = [1.0, 1.0, 1.0]

        result = calculate_weighted_score(scores, weights)
        expected = (0.8 + 0.6 + 0.9) / 3

        assert abs(result - expected) < 0.0001

    @pytest.mark.bug_g4
    def test_weighted_score_different_weights(self):
        """Test weighted score with different weights."""
        from apps.jobs.matching import calculate_weighted_score

        scores = [1.0, 0.0]
        weights = [3.0, 1.0]

        result = calculate_weighted_score(scores, weights)
        expected = 3.0 / 4.0

        assert abs(result - expected) < 0.0001

    @pytest.mark.bug_g4
    def test_scores_equal_comparison(self):
        """Test floating point score comparison."""
        from apps.jobs.matching import scores_equal

        assert scores_equal(1.0, 1.0)
        assert scores_equal(0.5, 0.5)

        score1 = 0.1 + 0.2
        score2 = 0.3
        assert scores_equal(score1, score2)

    @pytest.mark.bug_g4
    def test_score_delta_calculation(self):
        """Test score delta calculation."""
        from apps.jobs.matching import calculate_score_delta

        result = calculate_score_delta(0.8, 0.6)

        assert result['delta'] == pytest.approx(0.2, abs=0.0001)
        assert result['improved'] is True

    @pytest.mark.bug_g4
    def test_aggregate_perfect_matches(self, job, company, user, db):
        """Test counting perfect matches in aggregation."""
        from apps.candidates.models import Candidate, CandidateSkill
        from apps.jobs.matching import aggregate_match_scores

        candidates = []
        for i in range(5):
            c = Candidate.objects.create(
                first_name=f'Test{i}',
                last_name='User',
                email=f'test{i}@example.com',
                company=company,
                created_by=user,
                years_experience=5,
            )
            for skill in job.required_skills.all():
                CandidateSkill.objects.create(
                    candidate=c,
                    skill=skill,
                    proficiency=5,
                    is_primary=True
                )
            candidates.append(c)

        stats = aggregate_match_scores(candidates, job)

        assert stats['count'] == 5

    @pytest.mark.bug_g4
    def test_normalize_scores(self):
        """Test score normalization."""
        from apps.jobs.matching import normalize_scores

        scores = [0.2, 0.5, 0.8]
        normalized = normalize_scores(scores)

        assert normalized[0] == pytest.approx(0.0, abs=0.0001)
        assert normalized[2] == pytest.approx(1.0, abs=0.0001)

    @pytest.mark.bug_g4
    def test_percentile_rank_calculation(self):
        """Test percentile rank calculation."""
        from apps.jobs.matching import calculate_percentile_rank

        all_scores = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]

        rank = calculate_percentile_rank(0.5, all_scores)
        assert rank == 40.0

    def test_empty_scores_handling(self):
        """Test handling of empty score lists."""
        from apps.jobs.matching import normalize_scores, calculate_percentile_rank

        assert normalize_scores([]) == []
        assert calculate_percentile_rank(0.5, []) == 100.0


class TestMatchScoreIntegration:
    """Integration tests for match scoring."""

    def test_overall_match_score_components(self, candidate, job):
        """Test overall match uses both skill and experience."""
        from apps.jobs.matching import (
            calculate_overall_match_score,
            calculate_skill_match_score,
            calculate_experience_match_score
        )

        overall = calculate_overall_match_score(candidate, job)
        skill = calculate_skill_match_score(candidate, job)
        experience = calculate_experience_match_score(candidate, job)

        expected = (skill * 0.6) + (experience * 0.4)
        assert abs(overall - expected) < 0.0001

    def test_match_score_range(self, candidate, job):
        """Test match scores are in valid range."""
        from apps.jobs.matching import calculate_overall_match_score

        score = calculate_overall_match_score(candidate, job)
        assert 0.0 <= score <= 1.0

    @pytest.mark.bug_e1
    def test_perfect_match_equals_one(self, candidate, job, db):
        """Test that a perfect match produces exactly 1.0."""
        from apps.jobs.matching import calculate_overall_match_score
        from apps.candidates.models import CandidateSkill

        job.min_experience_years = candidate.years_experience
        job.max_experience_years = candidate.years_experience + 5
        job.save()

        for skill in job.required_skills.all():
            CandidateSkill.objects.update_or_create(
                candidate=candidate,
                skill=skill,
                defaults={'proficiency': 5, 'is_primary': True}
            )

        score = calculate_overall_match_score(candidate, job)
        assert score == 1.0


class TestScoreUpdateTask:
    """Tests for score update Celery task."""

    @pytest.mark.bug_f1
    def test_score_update_counter_increment(self, candidate, db):
        """Test that score update counter increments correctly."""
        from apps.candidates.tasks import (
            update_candidate_scores,
            _score_update_counter
        )

        candidate.overall_score = None
        candidate.save()

        initial_count = _score_update_counter['value']
        update_candidate_scores()
        final_count = _score_update_counter['value']

        assert final_count >= initial_count

    @pytest.mark.bug_f1
    def test_concurrent_score_updates(self, candidates, db):
        """Test concurrent score updates don't corrupt counter."""
        import threading
        from apps.candidates.tasks import (
            update_candidate_scores,
            _score_update_counter,
            _get_counter_lock
        )

        for c in candidates:
            c.overall_score = None
            c.save()

        initial_count = _score_update_counter['value']
        errors = []

        def run_update():
            try:
                update_candidate_scores()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=run_update) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_score_update_skip_existing(self, candidate, db):
        """Test that candidates with scores are skipped."""
        from apps.candidates.tasks import update_candidate_scores

        candidate.overall_score = 75.0
        candidate.save()

        result = update_candidate_scores()
        assert result['updated_candidates'] == 0


class TestScoreEdgeCases:
    """Edge case tests for scoring."""

    def test_score_with_zero_experience(self, candidate):
        """Test scoring with no experience."""
        from apps.candidates.tasks import _calculate_candidate_score

        candidate.years_experience = 0
        score = _calculate_candidate_score(candidate)
        assert score >= 0

    def test_score_with_no_skills(self, candidate, db):
        """Test scoring with no skills."""
        from apps.candidates.tasks import _calculate_candidate_score
        from apps.candidates.models import CandidateSkill

        CandidateSkill.objects.filter(candidate=candidate).delete()
        score = _calculate_candidate_score(candidate)
        assert score >= 0

    def test_score_with_none_values(self, candidate):
        """Test scoring handles None values gracefully."""
        from apps.candidates.tasks import _calculate_candidate_score

        candidate.resume_url = None
        candidate.linkedin_url = None
        candidate.portfolio_url = None

        score = _calculate_candidate_score(candidate)
        assert score >= 0
