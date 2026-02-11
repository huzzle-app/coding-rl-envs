"""
TalentFlow Interview Celery Tasks
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta


@shared_task
def process_scheduled_interviews():
    """Process interviews that are about to start."""
    from .models import Interview

    # Find interviews starting in the next 15 minutes
    now = timezone.now()
    upcoming = now + timedelta(minutes=15)

    interviews = Interview.objects.filter(
        status='confirmed',
        scheduled_at__gte=now,
        scheduled_at__lte=upcoming,
    )

    processed = 0
    for interview in interviews:
        interview.status = 'in_progress'
        interview.save()
        processed += 1

        # Trigger notifications
        send_interview_starting_notification.delay(interview.id)

    return {'processed_interviews': processed}


@shared_task
def send_interview_starting_notification(interview_id: int):
    """Send notification that interview is starting."""
    from django.core.mail import send_mail
    from .models import Interview

    try:
        interview = Interview.objects.select_related(
            'application__candidate',
            'application__job'
        ).prefetch_related(
            'participants__user'
        ).get(id=interview_id)
    except Interview.DoesNotExist:
        return {'error': 'Interview not found'}

    candidate = interview.application.candidate

    # Notify candidate
    send_mail(
        subject=f'Your interview is starting soon',
        message=f'Your {interview.interview_type} interview for {interview.application.job.title} is starting soon.',
        from_email='noreply@talentflow.example',
        recipient_list=[candidate.email],
        fail_silently=True,
    )

    # Notify interviewers
    for participant in interview.participants.all():
        send_mail(
            subject=f'Interview starting soon: {candidate.full_name}',
            message=f'Your interview with {candidate.full_name} is starting soon.',
            from_email='noreply@talentflow.example',
            recipient_list=[participant.user.email],
            fail_silently=True,
        )

    return {'interview_id': interview_id, 'notified': True}


@shared_task
def send_interview_reminder(interview_id: int):
    """Send reminder 24 hours before interview."""
    from django.core.mail import send_mail
    from .models import Interview

    try:
        interview = Interview.objects.select_related(
            'application__candidate',
            'application__job'
        ).prefetch_related(
            'participants__user'
        ).get(id=interview_id)
    except Interview.DoesNotExist:
        return {'error': 'Interview not found'}

    candidate = interview.application.candidate

    # Notify candidate
    send_mail(
        subject=f'Interview Reminder: {interview.application.job.title}',
        message=f'Reminder: Your interview is scheduled for {interview.scheduled_at}.',
        from_email='noreply@talentflow.example',
        recipient_list=[candidate.email],
        fail_silently=True,
    )

    return {'interview_id': interview_id, 'reminded': True}


@shared_task
def collect_interview_feedback(interview_id: int):
    """Request feedback from interviewers after interview completion."""
    from django.core.mail import send_mail
    from .models import Interview, InterviewFeedback

    try:
        interview = Interview.objects.prefetch_related(
            'participants__user'
        ).get(id=interview_id)
    except Interview.DoesNotExist:
        return {'error': 'Interview not found'}

    pending_feedback = 0
    for participant in interview.participants.all():
        # Check if feedback already submitted
        existing = InterviewFeedback.objects.filter(
            interview=interview,
            interviewer=participant.user
        ).exists()

        if not existing:
            send_mail(
                subject='Please submit your interview feedback',
                message=f'Please submit your feedback for the interview.',
                from_email='noreply@talentflow.example',
                recipient_list=[participant.user.email],
                fail_silently=True,
            )
            pending_feedback += 1

    return {'interview_id': interview_id, 'feedback_requested': pending_feedback}


@shared_task
def cleanup_cancelled_interviews():
    """Clean up interviews that have been cancelled for more than 30 days."""
    from .models import Interview

    cutoff = timezone.now() - timedelta(days=30)

    deleted, _ = Interview.objects.filter(
        status='cancelled',
        updated_at__lt=cutoff
    ).delete()

    return {'deleted_interviews': deleted}
