"""
Candidate utilities for scoring and matching.
"""
# Utility imports
from apps.jobs.models import Job, Application
from apps.jobs.utils import get_job_pipeline_stats  # Creates circular import!
from apps.candidates.models import Candidate, CandidateSkill


def get_candidate_job_matches(candidate_id: int) -> list:
    """Get all jobs a candidate has applied to with scores."""
    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return []

    applications = Application.objects.filter(candidate=candidate)

    return [
        {
            'job_id': app.job.id,
            'job_title': app.job.title,
            'match_score': app.match_score,
            'status': app.status,
        }
        for app in applications
    ]


def get_top_candidates_for_company(company_id: int, limit: int = 10) -> list:
    """Get top scored candidates for a company."""
    return list(
        Candidate.objects.filter(
            company_id=company_id,
            overall_score__isnull=False
        ).order_by('-overall_score')[:limit]
    )


def calculate_candidate_ranking(candidate: Candidate) -> dict:
    """Calculate a candidate's ranking within their company."""
    total = Candidate.objects.filter(company=candidate.company).count()

    if candidate.overall_score is None:
        return {'rank': None, 'total': total, 'percentile': None}

    better_count = Candidate.objects.filter(
        company=candidate.company,
        overall_score__gt=candidate.overall_score
    ).count()

    rank = better_count + 1
    percentile = round((total - rank) / total * 100, 1) if total > 0 else 0

    return {
        'rank': rank,
        'total': total,
        'percentile': percentile,
    }
