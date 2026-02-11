"""
TalentFlow Jobs Celery Tasks

Async tasks for job matching, scoring, and notifications.
"""
from celery import shared_task, chord, group


@shared_task
def calculate_match_scores_for_job(job_id: int):
    """
    Calculate match scores for all candidates for a specific job.

    Uses a chord to parallelize scoring and then aggregate results.
    """
    from .models import Job
    from apps.candidates.models import Candidate

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return {'error': 'Job not found'}

    # Get candidates without applications
    candidates = Candidate.objects.filter(
        company=job.company,
        status__in=['new', 'screening']
    ).exclude(
        applications__job=job
    ).values_list('id', flat=True)[:100]

    if not candidates:
        return {'message': 'No candidates to score', 'job_id': job_id}

    # Use chord pattern for parallel scoring
    header = group(
        score_single_candidate.s(job_id, candidate_id)
        for candidate_id in candidates
    )

    callback = aggregate_scores.s(job_id)

    result = chord(header)(callback)

    return {'message': 'Scoring started', 'job_id': job_id, 'candidates': len(candidates)}


@shared_task(ignore_result=True)
def score_single_candidate(job_id: int, candidate_id: int):
    """
    Calculate match score for a single candidate.
    """
    from .models import Job
    from .matching import calculate_overall_match_score
    from apps.candidates.models import Candidate

    try:
        job = Job.objects.get(id=job_id)
        candidate = Candidate.objects.get(id=candidate_id)
    except (Job.DoesNotExist, Candidate.DoesNotExist):
        return None

    score = calculate_overall_match_score(candidate, job)

    return {
        'candidate_id': candidate_id,
        'job_id': job_id,
        'score': score,
    }


@shared_task
def aggregate_scores(results: list, job_id: int):
    """
    Aggregate scoring results from parallel tasks.
    """
    valid_results = [r for r in results if r is not None]

    if not valid_results:
        return {
            'error': 'No valid results received',
            'job_id': job_id,
            'raw_results_count': len(results),
        }

    # Sort by score
    sorted_results = sorted(valid_results, key=lambda x: x['score'], reverse=True)

    return {
        'job_id': job_id,
        'total_scored': len(valid_results),
        'top_candidates': sorted_results[:10],
        'average_score': sum(r['score'] for r in valid_results) / len(valid_results),
    }


@shared_task
def auto_screen_applications(job_id: int, min_score: float = 0.5):
    """Auto-screen applications based on match score."""
    from .models import Job, Application

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return {'error': 'Job not found'}

    # Get pending applications
    applications = Application.objects.filter(
        job=job,
        status='pending'
    )

    shortlisted = 0
    rejected = 0

    for app in applications:
        if app.match_score and app.match_score >= min_score:
            app.status = 'shortlisted'
            app.save()
            shortlisted += 1
        elif app.match_score and app.match_score < min_score * 0.5:
            app.status = 'rejected'
            app.save()
            rejected += 1

    return {
        'job_id': job_id,
        'shortlisted': shortlisted,
        'rejected': rejected,
        'remaining': applications.count() - shortlisted - rejected,
    }


@shared_task
def notify_recruiters_of_new_applications(job_id: int):
    """Send notifications to recruiters about new applications."""
    from django.core.mail import send_mail
    from .models import Job, Application

    try:
        job = Job.objects.prefetch_related('recruiters').get(id=job_id)
    except Job.DoesNotExist:
        return {'error': 'Job not found'}

    # Count new applications (last 24 hours)
    from django.utils import timezone
    from datetime import timedelta

    yesterday = timezone.now() - timedelta(days=1)
    new_count = Application.objects.filter(
        job=job,
        applied_at__gte=yesterday
    ).count()

    if new_count == 0:
        return {'message': 'No new applications'}

    # Notify recruiters
    for recruiter in job.recruiters.all():
        send_mail(
            subject=f'New applications for {job.title}',
            message=f'{new_count} new applications in the last 24 hours',
            from_email='noreply@talentflow.example',
            recipient_list=[recruiter.email],
            fail_silently=True,
        )

    return {
        'job_id': job_id,
        'new_applications': new_count,
        'recruiters_notified': job.recruiters.count(),
    }


@shared_task
def close_expired_jobs():
    """Close jobs that have passed their target hire date."""
    from django.utils import timezone
    from .models import Job

    today = timezone.now().date()

    expired_jobs = Job.objects.filter(
        status='open',
        target_hire_date__lt=today
    )

    closed_count = 0
    for job in expired_jobs:
        job.close()
        closed_count += 1

    return {'closed_jobs': closed_count}


@shared_task
def update_job_statistics(job_id: int):
    """Update cached statistics for a job."""
    from django.db.models import Avg, Count
    from .models import Job, Application

    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return {'error': 'Job not found'}

    stats = Application.objects.filter(job=job).aggregate(
        total=Count('id'),
        avg_score=Avg('match_score'),
    )

    status_breakdown = dict(
        Application.objects.filter(job=job)
        .values('status')
        .annotate(count=Count('id'))
        .values_list('status', 'count')
    )

    return {
        'job_id': job_id,
        'total_applications': stats['total'],
        'average_match_score': stats['avg_score'],
        'status_breakdown': status_breakdown,
    }
