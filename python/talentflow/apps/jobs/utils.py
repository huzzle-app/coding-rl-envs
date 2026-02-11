"""
Job utilities for matching and scoring.
"""
# This creates a circular import with candidates.utils
from apps.candidates.utils import get_top_candidates_for_company
from apps.jobs.models import Job, Application


def get_job_pipeline_stats(job_id: int) -> dict:
    """Get pipeline statistics for a job."""
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return {}

    applications = Application.objects.filter(job=job)

    stats = {
        'total': applications.count(),
        'by_status': {},
        'by_stage': {},
    }

    for status_code, status_name in Application.STATUS_CHOICES:
        count = applications.filter(status=status_code).count()
        if count > 0:
            stats['by_status'][status_code] = count

    for stage in job.pipeline_stages:
        count = applications.filter(stage=stage).count()
        stats['by_stage'][stage] = count

    return stats


def get_recommended_candidates(job_id: int, limit: int = 20) -> list:
    """Get recommended candidates for a job based on company's top talent."""
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return []

    # Uses imported function from candidates.utils
    top_candidates = get_top_candidates_for_company(job.company_id, limit * 2)

    # Filter out already applied
    applied_ids = set(
        Application.objects.filter(job=job).values_list('candidate_id', flat=True)
    )

    return [c for c in top_candidates if c.id not in applied_ids][:limit]
