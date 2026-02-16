"""
TalentFlow Interview Scheduling

Functions for managing interviewer availability and scheduling interviews.
"""
from datetime import datetime, timedelta
from typing import List, Optional

import pytz
from django.utils import timezone

from apps.accounts.models import User
from .models import Interview, InterviewerAvailability


class SchedulingError(Exception):
    """Error during interview scheduling."""
    pass


def get_interviewer_availability(
    user: User,
    start_date: datetime,
    end_date: datetime,
    user_timezone: str = 'UTC'
) -> List[dict]:
    """
    Get available time slots for an interviewer.
    """
    slots = InterviewerAvailability.objects.filter(
        user=user,
        is_available=True,
        start_time__gte=start_date,
        end_time__lte=end_date,
    )

    available_slots = []
    for slot in slots:
        # Check for conflicting interviews
        conflicts = Interview.objects.filter(
            interviewers=user,
            status__in=['scheduled', 'confirmed'],
            scheduled_at__lt=slot.end_time,
            scheduled_at__gte=slot.start_time,
        )

        if not conflicts.exists():
            available_slots.append({
                'start': slot.start_time,
                'end': slot.end_time,
                'user_id': user.id,
            })

    return available_slots


def find_common_availability(
    interviewers: List[User],
    date: datetime,
    duration_minutes: int = 60,
    preferred_timezone: str = 'America/New_York'
) -> List[dict]:
    """
    Find common available time slots for multiple interviewers.
    """
    # Set up day boundaries
    start_of_day = datetime(date.year, date.month, date.day, 9, 0, 0)
    end_of_day = datetime(date.year, date.month, date.day, 18, 0, 0)

    all_availability = []
    for user in interviewers:
        availability = get_interviewer_availability(
            user,
            start_of_day,
            end_of_day,
            preferred_timezone
        )
        all_availability.append({
            'user': user,
            'slots': availability,
        })

    # Find overlapping slots
    common_slots = _find_overlapping_slots(all_availability, duration_minutes)

    return common_slots


def _find_overlapping_slots(
    all_availability: List[dict],
    duration_minutes: int
) -> List[dict]:
    """Find time slots where all interviewers are available."""
    if not all_availability:
        return []

    # Start with first interviewer's slots
    common = all_availability[0]['slots'].copy()

    # Intersect with each other interviewer's availability
    for avail in all_availability[1:]:
        common = _intersect_slots(common, avail['slots'], duration_minutes)

    return common


def _intersect_slots(slots1: List[dict], slots2: List[dict], min_duration: int) -> List[dict]:
    """Find intersection of two slot lists."""
    result = []

    for s1 in slots1:
        for s2 in slots2:
            overlap_start = max(s1['start'], s2['start'])
            overlap_end = min(s1['end'], s2['end'])

            # Check if overlap is long enough
            duration = (overlap_end - overlap_start).total_seconds() / 60

            if duration >= min_duration:
                result.append({
                    'start': overlap_start,
                    'end': overlap_end,
                })

    return result


def schedule_interview(
    application_id: int,
    interview_type: str,
    scheduled_at: datetime,
    duration_minutes: int,
    interviewer_ids: List[int],
    interview_timezone: str = 'UTC',
    created_by: User = None,
) -> Interview:
    """
    Schedule a new interview.
    """
    from apps.jobs.models import Application

    try:
        application = Application.objects.get(id=application_id)
    except Application.DoesNotExist:
        raise SchedulingError('Application not found')

    # Handle timezone awareness
    if not timezone.is_aware(scheduled_at):
        scheduled_at = timezone.make_aware(scheduled_at)

    # Check interviewer availability
    interviewers = User.objects.filter(id__in=interviewer_ids)

    for interviewer in interviewers:
        if not _is_interviewer_available(interviewer, scheduled_at, duration_minutes):
            raise SchedulingError(
                f'Interviewer {interviewer.email} is not available at this time'
            )

    interview = Interview.objects.create(
        application=application,
        interview_type=interview_type,
        scheduled_at=scheduled_at,
        duration_minutes=duration_minutes,
        timezone=interview_timezone,
        created_by=created_by,
    )

    # Add interviewers
    for interviewer in interviewers:
        interview.participants.create(
            user=interviewer,
            role='technical',
            status='pending',
        )

    return interview


def _is_interviewer_available(
    interviewer: User,
    start_time: datetime,
    duration_minutes: int
) -> bool:
    """Check if an interviewer is available at a specific time."""
    end_time = start_time + timedelta(minutes=duration_minutes)

    # Check for conflicts
    conflicts = Interview.objects.filter(
        interviewers=interviewer,
        status__in=['scheduled', 'confirmed'],
    ).filter(
        # Interview overlaps with requested time
        scheduled_at__lt=end_time,
    )

    # Additional filter for end time
    for interview in conflicts:
        if interview.end_time > start_time:
            return False

    return True


def suggest_interview_times(
    application_id: int,
    interviewer_ids: List[int],
    duration_minutes: int = 60,
    days_ahead: int = 7,
    preferred_timezone: str = 'America/New_York'
) -> List[dict]:
    """
    Suggest available interview times.
    """
    interviewers = User.objects.filter(id__in=interviewer_ids)

    
    
    # that spans multiple files:
    #   1. base.py: CELERY_ENABLE_UTC = False
    #   2. celery.py: enable_utc = True (contradicts base.py)
    #   3. This file: naive datetime usage
    # Fixing only this file won't fully resolve the issue - all three
    # must be consistent for scheduled tasks to run at correct times
    today = datetime.now()
    suggestions = []

    for day_offset in range(days_ahead):
        check_date = today + timedelta(days=day_offset)

        common = find_common_availability(
            list(interviewers),
            check_date,
            duration_minutes,
            preferred_timezone
        )

        for slot in common:
            suggestions.append({
                'start': slot['start'],
                'end': slot['end'],
                'date': check_date.date(),
                'interviewers': [u.id for u in interviewers],
            })

    return suggestions[:10]  # Return top 10 suggestions


def check_availability_for_reschedule(
    interview: Interview,
    new_time: datetime,
    new_duration: int = None
) -> dict:
    """
    Check if an interview can be rescheduled to a new time.
    """
    duration = new_duration or interview.duration_minutes

    # Get all interviewers
    interviewer_ids = list(
        interview.participants.values_list('user_id', flat=True)
    )
    interviewers = User.objects.filter(id__in=interviewer_ids)

    available = True
    unavailable_interviewers = []

    for interviewer in interviewers:
        if not _is_interviewer_available(interviewer, new_time, duration):
            available = False
            unavailable_interviewers.append(interviewer.email)

    return {
        'available': available,
        'unavailable_interviewers': unavailable_interviewers,
        'requested_time': new_time,
        'duration_minutes': duration,
    }


def find_available_slots(
    user_ids: List[int],
    start_date: datetime,
    end_date: datetime,
) -> List[dict]:
    """Find available interview slots for given users within a date range."""
    users = User.objects.filter(id__in=user_ids)
    all_slots = []
    for user in users:
        slots = get_interviewer_availability(user, start_date, end_date)
        all_slots.extend(slots)
    return all_slots
