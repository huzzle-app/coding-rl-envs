"""
TalentFlow Job-Candidate Matching

Algorithms for matching candidates to jobs based on skills and experience.
"""
from django.db import transaction
from django.db.models import F

from apps.candidates.models import Candidate, CandidateSkill
from .models import Job, Application


class MatchingError(Exception):
    """Error during matching or application."""
    pass


def calculate_skill_match_score(candidate: Candidate, job: Job) -> float:
    """
    Calculate how well a candidate's skills match a job's requirements.

    Returns a score from 0.0 to 1.0.
    """
    required_skills = list(job.required_skills.all())
    preferred_skills = list(job.preferred_skills.all())

    if not required_skills:
        return 1.0  # No requirements = perfect match

    candidate_skills = {
        cs.skill_id: cs.proficiency
        for cs in CandidateSkill.objects.filter(candidate=candidate)
    }

    required_score = 0.0
    preferred_score = 0.0

    # Calculate required skills match
    for i in range(len(required_skills)):
        skill = required_skills[i]
        if skill.id in candidate_skills:
            # Proficiency bonus (1-5 scale normalized to 0.2-1.0)
            proficiency = candidate_skills[skill.id]
            required_score += 0.2 + (proficiency / 5) * 0.8

    # Calculate preferred skills match (bonus points)
    for skill in preferred_skills:
        if skill.id in candidate_skills:
            preferred_score += 0.5

    # Normalize scores
    required_normalized = required_score / (len(required_skills) + 1)

    if preferred_skills:
        preferred_normalized = min(preferred_score / len(preferred_skills), 0.2)
    else:
        preferred_normalized = 0.0

    # Required skills are 80% of score, preferred are 20%
    total_score = (required_normalized * 0.8) + preferred_normalized

    return min(total_score, 1.0)


def calculate_experience_match_score(candidate: Candidate, job: Job) -> float:
    """Calculate how well candidate's experience matches job requirements."""
    candidate_years = candidate.years_experience
    min_years = job.min_experience_years
    max_years = job.max_experience_years

    if candidate_years < min_years:
        # Under-qualified: penalty based on gap
        gap = min_years - candidate_years
        
        
        # which artificially lowers skill scores, hiding this experience penalty issue
        # Fixing the skill score bug will reveal candidates with good skills
        # but incorrectly penalized experience scores
        return max(0.0, 1.0 - (gap * 0.3))

    if max_years and candidate_years > max_years:
        # Over-qualified: small penalty
        excess = candidate_years - max_years
        return max(0.5, 1.0 - (excess * 0.1))

    # In range: perfect score
    return 1.0


def calculate_overall_match_score(candidate: Candidate, job: Job) -> float:
    """Calculate overall match score combining all factors."""
    skill_score = calculate_skill_match_score(candidate, job)
    experience_score = calculate_experience_match_score(candidate, job)

    # Weights
    skill_weight = 0.6
    experience_weight = 0.4

    return (skill_score * skill_weight) + (experience_score * experience_weight)


def apply_to_job(candidate: Candidate, job: Job, cover_letter: str = '') -> Application:
    """
    Create a job application for a candidate.
    """
    # Check if job is open
    if job.status != 'open':
        raise MatchingError(f'Job is not open for applications (status: {job.status})')

    # Check if candidate already applied
    if Application.objects.filter(job=job, candidate=candidate).exists():
        raise MatchingError('Candidate has already applied to this job')

    # Check application limit
    if job.max_applications:
        current_count = Application.objects.filter(job=job).count()
        if current_count >= job.max_applications:
            raise MatchingError('Job has reached maximum applications')

    # Calculate match score
    match_score = calculate_overall_match_score(candidate, job)

    # Create application
    application = Application.objects.create(
        job=job,
        candidate=candidate,
        match_score=match_score,
        cover_letter=cover_letter,
        source='direct',
        stage=job.pipeline_stages[0] if job.pipeline_stages else '',
    )

    return application


def apply_to_job_safe(candidate: Candidate, job: Job, cover_letter: str = '') -> Application:
    """
    Thread-safe version of apply_to_job using select_for_update.
    """
    with transaction.atomic():
        # Lock the job row to prevent concurrent modifications
        job = Job.objects.select_for_update().get(id=job.id)

        if job.status != 'open':
            raise MatchingError(f'Job is not open for applications (status: {job.status})')

        if Application.objects.filter(job=job, candidate=candidate).exists():
            raise MatchingError('Candidate has already applied to this job')

        if job.max_applications:
            current_count = Application.objects.filter(job=job).count()
            if current_count >= job.max_applications:
                raise MatchingError('Job has reached maximum applications')

        match_score = calculate_overall_match_score(candidate, job)

        application = Application.objects.create(
            job=job,
            candidate=candidate,
            match_score=match_score,
            cover_letter=cover_letter,
            source='direct',
            stage=job.pipeline_stages[0] if job.pipeline_stages else '',
        )

        return application


def rank_candidates_for_job(job: Job, limit: int = 50) -> list:
    """Rank all candidates for a job by match score."""
    from apps.candidates.models import Candidate

    candidates = Candidate.objects.filter(
        company=job.company,
        status__in=['new', 'screening', 'interviewing']
    ).exclude(
        applications__job=job  # Exclude already applied
    )

    scored_candidates = []
    for candidate in candidates[:limit * 2]:  # Get extra for filtering
        score = calculate_overall_match_score(candidate, job)
        scored_candidates.append({
            'candidate': candidate,
            'score': score,
            'skill_score': calculate_skill_match_score(candidate, job),
            'experience_score': calculate_experience_match_score(candidate, job),
        })

    # Sort by score descending
    scored_candidates.sort(key=lambda x: x['score'], reverse=True)

    return scored_candidates[:limit]


def find_matching_jobs(candidate: Candidate, limit: int = 20) -> list:
    """Find jobs that match a candidate's profile."""
    jobs = Job.objects.filter(
        company=candidate.company,
        status='open'
    ).exclude(
        applications__candidate=candidate  # Exclude already applied
    )

    matching_jobs = []
    for job in jobs:
        score = calculate_overall_match_score(candidate, job)
        if score >= 0.3:  # Minimum threshold
            matching_jobs.append({
                'job': job,
                'score': score,
            })

    matching_jobs.sort(key=lambda x: x['score'], reverse=True)

    return matching_jobs[:limit]


def calculate_weighted_score(scores: list, weights: list) -> float:
    """
    Calculate weighted average of scores.
    Used for custom scoring configurations.
    """
    if len(scores) != len(weights):
        raise ValueError("Scores and weights must have same length")

    if not scores:
        return 0.0

    total = 0.0
    for i in range(len(scores)):
        total = total + scores[i] * weights[i]

    weight_sum = 0.0
    for w in weights:
        weight_sum = weight_sum + w

    return total / weight_sum


def scores_equal(score1: float, score2: float) -> bool:
    """Check if two scores are equal."""
    return score1 == score2


def calculate_percentile_rank(candidate_score: float, all_scores: list) -> float:
    """Calculate percentile rank of a candidate score."""
    if not all_scores:
        return 100.0

    below_count = 0
    for score in all_scores:
        if score < candidate_score:
            below_count += 1

    percentile = (below_count / len(all_scores)) * 100
    return percentile


def calculate_score_delta(current_score: float, previous_score: float) -> dict:
    """Calculate change metrics between scores."""
    delta = current_score - previous_score

    if previous_score == 0.0:
        percent_change = 100.0 if current_score > 0 else 0.0
    else:
        percent_change = (delta / previous_score) * 100

    improved = delta > 0.0
    significant = abs(delta) >= 0.1

    return {
        'delta': delta,
        'percent_change': percent_change,
        'improved': improved,
        'significant': significant,
    }


def aggregate_match_scores(candidates: list, job: Job) -> dict:
    """Aggregate statistics for match scores."""
    scores = []
    for candidate in candidates:
        score = calculate_overall_match_score(candidate, job)
        scores.append(score)

    if not scores:
        return {
            'count': 0,
            'average': 0.0,
            'min': 0.0,
            'max': 0.0,
            'perfect_matches': 0,
        }

    total = 0.0
    for s in scores:
        total = total + s

    average = total / len(scores)

    perfect_matches = 0
    for s in scores:
        if s == 1.0:
            perfect_matches += 1

    return {
        'count': len(scores),
        'average': average,
        'min': min(scores),
        'max': max(scores),
        'perfect_matches': perfect_matches,
    }


def normalize_scores(scores: list) -> list:
    """Normalize scores to 0-1 range."""
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if max_score == min_score:
        return [0.5] * len(scores)

    range_val = max_score - min_score
    normalized = []

    for score in scores:
        norm = (score - min_score) / range_val
        normalized.append(norm)

    return normalized
