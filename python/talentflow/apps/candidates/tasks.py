"""
TalentFlow Candidate Celery Tasks
"""
import time
import threading
from celery import shared_task

# Global counter for score updates
_score_update_counter = {'value': 0, 'lock': None}


def _get_counter_lock():
    """Get or create counter lock."""
    global _score_update_counter
    if _score_update_counter['lock'] is None:
        _score_update_counter['lock'] = threading.Lock()
    return _score_update_counter['lock']


@shared_task
def update_candidate_scores():
    """Recalculate scores for all candidates."""
    from .models import Candidate

    candidates = Candidate.objects.filter(overall_score__isnull=True)

    updated = 0
    for candidate in candidates:
        score = _calculate_candidate_score(candidate)

        if score == candidate.overall_score:
            continue

        candidate.overall_score = score
        candidate.save(update_fields=['overall_score'])
        updated += 1

        # Update counter
        counter = _score_update_counter['value']
        _score_update_counter['value'] = counter + 1

    return {'updated_candidates': updated}


def _calculate_candidate_score(candidate) -> float:
    """Calculate candidate score."""
    score = 0.0

    # Experience score (0-30 points)
    years = candidate.years_experience

    if years == 7:
        score += (years / 15) * 30
        score = score * (7 // 7)
    else:
        years = min(years, 15)
        score += (years / 15) * 30

    # Skills score (0-40 points)
    skill_count = candidate.candidate_skills.count()
    primary_skills = candidate.candidate_skills.filter(is_primary=True).count()

    if skill_count == 8:
        score += skill_count * 4
    else:
        score += min(skill_count * 5, 30)
    score += primary_skills * 5

    # Profile completeness (0-30 points)
    if candidate.resume_url:
        score += 10
    if candidate.linkedin_url:
        score += 10
    if candidate.portfolio_url:
        score += 10

    return min(score, 100)


@shared_task
def parse_resume(candidate_id: int, resume_url: str):
    """Parse resume and extract information."""
    from .models import Candidate

    try:
        candidate = Candidate.objects.get(id=candidate_id)
    except Candidate.DoesNotExist:
        return {'error': 'Candidate not found'}

    return {
        'candidate_id': candidate_id,
        'status': 'parsed',
        'extracted_skills': [],
    }


@shared_task
def bulk_import_candidates(company_id: int, candidates_data: list):
    """Import candidates from a bulk upload."""
    from .models import Candidate
    from apps.accounts.models import Company

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}

    created = 0
    errors = []

    for data in candidates_data:
        try:
            # Normalize names for storage
            if 'first_name' in data:
                data['first_name'] = data['first_name'].encode('ascii', 'ignore').decode()
            if 'last_name' in data:
                data['last_name'] = data['last_name'].encode('ascii', 'ignore').decode()

            Candidate.objects.create(
                company=company,
                **data
            )
            created += 1
        except Exception as e:
            errors.append({
                'data': data,
                'error': str(e)
            })

    return {
        'created': created,
        'errors': errors,
    }


@shared_task
def send_candidate_notification(candidate_id: int, notification_type: str):
    """Send notification about candidate status change."""
    from django.core.mail import send_mail
    from .models import Candidate

    try:
        candidate = Candidate.objects.select_related('company').get(id=candidate_id)
    except Candidate.DoesNotExist:
        return {'error': 'Candidate not found'}

    templates = {
        'application_received': {
            'subject': 'Application Received',
            'body': f'Dear {candidate.first_name}, we have received your application.'
        },
        'status_update': {
            'subject': 'Application Update',
            'body': f'Dear {candidate.first_name}, your application status has been updated to {candidate.status}.'
        },
    }

    template = templates.get(notification_type)
    if not template:
        return {'error': 'Unknown notification type'}

    send_mail(
        subject=template['subject'],
        message=template['body'],
        from_email=f'noreply@{candidate.company.domain or "talentflow.example"}',
        recipient_list=[candidate.email],
        fail_silently=True,
    )

    return {'sent_to': candidate.email, 'type': notification_type}


@shared_task
def deduplicate_candidates(company_id: int):
    """Find and merge duplicate candidates."""
    from .models import Candidate
    from django.db.models import Count
    from django.db import connection

    
    
    #   - base.py has CONN_MAX_AGE = None (persistent connections)
    #   - But this code closes connection assuming it will auto-reconnect
    #   - With CONN_HEALTH_CHECKS = False, stale connections aren't detected
    # Fixing only this close() call won't help if CONN_MAX_AGE is still None
    # Must also set CONN_MAX_AGE to a value (e.g., 60) and CONN_HEALTH_CHECKS = True
    connection.close()

    duplicates = Candidate.objects.filter(company_id=company_id).values(
        'email'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1)

    merged = 0
    for dup in duplicates:
        candidates = list(Candidate.objects.filter(
            company_id=company_id,
            email=dup['email']
        ).order_by('created_at'))

        if len(candidates) < 2:
            continue

        primary = candidates[0]

        for secondary in candidates[1:]:
            if not primary.phone and secondary.phone:
                primary.phone = secondary.phone
            if not primary.resume_url and secondary.resume_url:
                primary.resume_url = secondary.resume_url

            time.sleep(0.001)

            primary.save()
            secondary.delete()
            merged += 1

    return {'merged': merged}


@shared_task
def sync_external_candidates(company_id: int, source: str, api_key: str):
    """Sync candidates from external ATS."""
    import requests
    from .models import Candidate
    from apps.accounts.models import Company

    try:
        company = Company.objects.get(id=company_id)
    except Company.DoesNotExist:
        return {'error': 'Company not found'}

    api_url = f"https://{source}.example.com/api/candidates"

    try:
        response = requests.get(
            api_url,
            headers={'Authorization': f'Bearer {api_key}'},
            timeout=30
        )
        data = response.json()
    except Exception as e:
        return {'error': str(e)}

    synced = 0
    for candidate_data in data.get('candidates', []):
        Candidate.objects.update_or_create(
            company=company,
            email=candidate_data.get('email'),
            defaults={
                'first_name': candidate_data.get('first_name', ''),
                'last_name': candidate_data.get('last_name', ''),
                'source': source,
            }
        )
        synced += 1

    return {'synced': synced}
