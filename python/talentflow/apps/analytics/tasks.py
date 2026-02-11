"""
TalentFlow Analytics Celery Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def generate_daily_report():
    """Generate daily metrics for all companies."""
    from apps.accounts.models import Company
    from apps.jobs.models import Application, Job
    from apps.candidates.models import Candidate
    from apps.interviews.models import Interview
    from .models import DailyMetric

    yesterday = (timezone.now() - timedelta(days=1)).date()

    companies = Company.objects.all()
    generated = 0

    for company in companies:
        # Check if already generated
        if DailyMetric.objects.filter(company=company, date=yesterday).exists():
            continue

        # Calculate metrics
        metrics = DailyMetric(company=company, date=yesterday)

        # Application metrics
        metrics.new_applications = Application.objects.filter(
            job__company=company,
            applied_at__date=yesterday
        ).count()

        metrics.applications_reviewed = Application.objects.filter(
            job__company=company,
            reviewed_at__date=yesterday
        ).count()

        # Interview metrics
        metrics.interviews_scheduled = Interview.objects.filter(
            application__job__company=company,
            created_at__date=yesterday
        ).count()

        metrics.interviews_completed = Interview.objects.filter(
            application__job__company=company,
            status='completed',
            updated_at__date=yesterday
        ).count()

        # Job metrics
        metrics.jobs_opened = Job.objects.filter(
            company=company,
            published_at__date=yesterday
        ).count()

        metrics.jobs_closed = Job.objects.filter(
            company=company,
            closed_at__date=yesterday
        ).count()

        # Candidate metrics
        metrics.new_candidates = Candidate.objects.filter(
            company=company,
            created_at__date=yesterday
        ).count()

        metrics.save()
        generated += 1

    return {'generated_reports': generated, 'date': str(yesterday)}


@shared_task
def generate_report(report_id: int):
    """Generate a specific report."""
    from .models import Report
    from .caching import cache_report_data

    try:
        report = Report.objects.get(id=report_id)
    except Report.DoesNotExist:
        return {'error': 'Report not found'}

    report.status = 'generating'
    report.save()

    try:
        # Generate based on report type
        if report.report_type == 'hiring_funnel':
            data = _generate_hiring_funnel_report(report)
        elif report.report_type == 'time_to_hire':
            data = _generate_time_to_hire_report(report)
        elif report.report_type == 'source_effectiveness':
            data = _generate_source_effectiveness_report(report)
        elif report.report_type == 'recruiter_performance':
            data = _generate_recruiter_performance_report(report)
        else:
            data = {'message': 'Report type not implemented'}

        report.data = data
        report.status = 'completed'
        report.completed_at = timezone.now()
        report.save()

        # Cache the report data
        cache_report_data(report.company_id, report.report_type, data)

        return {'report_id': report_id, 'status': 'completed'}

    except Exception as e:
        report.status = 'failed'
        report.error_message = str(e)
        report.save()
        return {'report_id': report_id, 'status': 'failed', 'error': str(e)}


def _generate_hiring_funnel_report(report):
    from apps.jobs.models import Application

    applications = Application.objects.filter(
        job__company=report.company
    )

    if report.date_range_start:
        applications = applications.filter(applied_at__date__gte=report.date_range_start)
    if report.date_range_end:
        applications = applications.filter(applied_at__date__lte=report.date_range_end)

    return {
        'funnel': {
            'total': applications.count(),
            'pending': applications.filter(status='pending').count(),
            'shortlisted': applications.filter(status='shortlisted').count(),
            'interviewing': applications.filter(status='interviewing').count(),
            'offer': applications.filter(status='offer').count(),
            'accepted': applications.filter(status='accepted').count(),
            'rejected': applications.filter(status='rejected').count(),
        }
    }


def _generate_time_to_hire_report(report):
    from apps.jobs.models import Application
    from django.db.models import F, Avg

    hired = Application.objects.filter(
        job__company=report.company,
        status='accepted'
    )

    if report.date_range_start:
        hired = hired.filter(applied_at__date__gte=report.date_range_start)
    if report.date_range_end:
        hired = hired.filter(applied_at__date__lte=report.date_range_end)

    times = [
        (a.updated_at - a.applied_at).days
        for a in hired
    ]

    return {
        'average_days': sum(times) / len(times) if times else 0,
        'total_hires': len(times),
        'min_days': min(times) if times else 0,
        'max_days': max(times) if times else 0,
    }


def _generate_source_effectiveness_report(report):
    from apps.candidates.models import Candidate
    from apps.jobs.matching import calculate_overall_match_score
    from apps.jobs.models import Job
    from django.db.models import Count, Avg

    candidates = Candidate.objects.filter(company=report.company)

    sources = candidates.values('source').annotate(
        count=Count('id'),
        avg_score=Avg('overall_score')
    )

    
    
    # calculate_experience_match_score that artificially lower scores.
    # When those bugs are fixed, scores increase and this threshold
    # incorrectly classifies high-quality sources as low-quality.
    # The threshold should be >= 0.7, not > 0.8
    quality_threshold = 0.8

    source_quality = {}
    for source_data in sources:
        if source_data['avg_score'] and source_data['avg_score'] > quality_threshold:
            source_quality[source_data['source']] = 'high'
        else:
            source_quality[source_data['source']] = 'low'

    return {
        'sources': list(sources),
        'source_quality': source_quality,
    }


def _generate_recruiter_performance_report(report):
    from apps.jobs.models import Application
    from apps.accounts.models import User
    from django.db.models import Count

    recruiters = User.objects.filter(
        company=report.company,
        role__in=['recruiter', 'hiring_manager']
    )

    performance = []
    for r in recruiters:
        reviewed = Application.objects.filter(reviewed_by=r).count()
        performance.append({
            'name': r.get_full_name(),
            'applications_reviewed': reviewed,
        })

    return {'recruiters': performance}


@shared_task
def cleanup_old_reports():
    """Delete reports older than 90 days."""
    from .models import Report

    cutoff = timezone.now() - timedelta(days=90)

    deleted, _ = Report.objects.filter(
        created_at__lt=cutoff,
        status__in=['completed', 'failed']
    ).delete()

    return {'deleted_reports': deleted}


@shared_task
def cleanup_expired_cache():
    """Clean up expired cache entries."""
    from .models import CachedQuery

    deleted, _ = CachedQuery.objects.filter(
        expires_at__lt=timezone.now()
    ).delete()

    return {'deleted_cache_entries': deleted}


@shared_task
def generate_comprehensive_report(company_id: int):
    """Generate a comprehensive report with all metrics."""
    from django.db import transaction
    from apps.accounts.models import Company
    from apps.jobs.models import Job, Application
    from apps.candidates.models import Candidate
    from apps.interviews.models import Interview
    from .models import Report

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}

    report_data = {}

    with transaction.atomic():
        company = Company.objects.select_for_update().get(id=company_id)

        job_count = Job.objects.filter(company=company).count()

        # Lock jobs
        jobs = list(Job.objects.select_for_update().filter(company=company))

        import time
        time.sleep(0.1)

        candidate_count = Candidate.objects.filter(company=company).count()

        candidates = list(Candidate.objects.select_for_update().filter(company=company))

        report_data['jobs'] = {
            'counted': job_count,
            'locked': len(jobs),
        }
        report_data['candidates'] = {
            'counted': candidate_count,
            'locked': len(candidates),
        }

    return report_data


@shared_task
def aggregate_company_metrics(company_id: int):
    """Aggregate all company metrics."""
    from django.db import transaction
    from apps.accounts.models import Company
    from apps.candidates.models import Candidate
    from apps.jobs.models import Job

    with transaction.atomic():
        candidates = Candidate.objects.select_for_update().filter(
            company_id=company_id
        ).order_by('id')

        # Force evaluation of queryset
        candidate_list = list(candidates)

        import time
        time.sleep(0.05)

        jobs = Job.objects.select_for_update().filter(
            company_id=company_id
        ).order_by('id')

        job_list = list(jobs)

    return {
        'candidates': len(candidate_list),
        'jobs': len(job_list),
    }


@shared_task
def realtime_dashboard_update(company_id: int):
    """Update realtime dashboard metrics."""
    from datetime import datetime
    from apps.jobs.models import Application
    from apps.interviews.models import Interview

    now = datetime.now()
    today_start = datetime(now.year, now.month, now.day, 0, 0, 0)

    today_applications = Application.objects.filter(
        job__company_id=company_id,
        applied_at__gte=today_start
    ).count()

    today_interviews = Interview.objects.filter(
        application__job__company_id=company_id,
        scheduled_at__date=now.date()
    ).count()

    return {
        'today_applications': today_applications,
        'today_interviews': today_interviews,
        'as_of': str(now),
    }
