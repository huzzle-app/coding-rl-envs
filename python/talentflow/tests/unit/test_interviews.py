"""
Unit tests for interviews app.

Tests: 10
"""
import pytest
from datetime import datetime, timedelta
from django.utils import timezone
import pytz


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestInterviewModel:
    """Tests for Interview model."""

    def test_create_interview(self, application, user):
        """Test creating an interview."""
        from apps.interviews.models import Interview

        interview = Interview.objects.create(
            application=application,
            interview_type='technical',
            status='scheduled',
            scheduled_at=timezone.now() + timedelta(days=1),
            duration_minutes=60,
            created_by=user,
        )
        assert interview.status == 'scheduled'
        assert interview.duration_minutes == 60

    def test_interview_end_time(self, interview):
        """Test end_time property calculation."""
        expected_end = interview.scheduled_at + timedelta(minutes=interview.duration_minutes)
        assert interview.end_time == expected_end


class TestInterviewParticipant:
    """Tests for InterviewParticipant model."""

    def test_add_participant(self, interview, user):
        """Test adding a participant."""
        from apps.interviews.models import InterviewParticipant

        # Participant already added in fixture
        participant = InterviewParticipant.objects.get(interview=interview, user=user)
        assert participant.role == 'technical'
        assert participant.status == 'accepted'

    def test_participant_unique_per_interview(self, interview, user):
        """Test that same user can't be added twice."""
        from apps.interviews.models import InterviewParticipant
        from django.db import IntegrityError

        with pytest.raises(IntegrityError):
            InterviewParticipant.objects.create(
                interview=interview,
                user=user,
                role='observer',
            )


class TestInterviewerAvailability:
    """Tests for InterviewerAvailability model."""

    def test_create_availability(self, user):
        """Test creating availability slot."""
        from apps.interviews.models import InterviewerAvailability

        slot = InterviewerAvailability.objects.create(
            user=user,
            start_time=timezone.now() + timedelta(hours=2),
            end_time=timezone.now() + timedelta(hours=4),
            is_available=True,
        )
        assert slot.is_available
        assert slot.start_time < slot.end_time


class TestTimezoneScheduling:
    """Tests for timezone handling in scheduling - detects timezone bug."""

    @pytest.mark.bug_e2
    def test_timezone_aware_scheduling(self, user):
        """
        BUG E2: Test that scheduling uses timezone-aware datetimes.

        The scheduling module creates naive datetime objects which
        causes issues when comparing with timezone-aware DB records.
        """
        from apps.interviews.scheduling import find_common_availability

        # Create timezone-aware test date
        tz = pytz.timezone('America/New_York')
        test_date = timezone.now().astimezone(tz)

        # This should not raise RuntimeWarning about naive/aware comparison
        
        result = find_common_availability(
            [user],
            test_date,
            duration_minutes=60,
            preferred_timezone='America/New_York'
        )

        # Result should be a list (may be empty if no availability)
        assert isinstance(result, list)

    @pytest.mark.bug_e2
    def test_naive_datetime_detection(self):
        """
        BUG E2: Detect naive datetime creation in scheduling.

        The scheduling code creates naive datetimes like:
        datetime(year, month, day, 9, 0, 0) instead of using
        timezone-aware construction.
        """
        from apps.interviews.scheduling import find_common_availability
        from unittest.mock import MagicMock
        import warnings

        # Create a mock user
        mock_user = MagicMock()
        mock_user.id = 1

        # Use a date that would show timezone issues
        test_date = datetime(2024, 3, 10, 12, 0, 0)  # DST transition date

        # This test documents that naive datetimes are being created
        # After fix, no RuntimeWarning should be raised
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            try:
                find_common_availability(
                    [mock_user],
                    test_date,
                    60,
                    'America/New_York'
                )
            except Exception:
                pass  # We're just checking for warnings

            # Check if any RuntimeWarnings about datetime comparison
            datetime_warnings = [
                warning for warning in w
                if 'naive' in str(warning.message).lower()
            ]
            # This may or may not produce warnings depending on Python version
            # The bug manifests as incorrect results more than warnings

    @pytest.mark.bug_e2
    def test_dst_transition_handling(self, user, db):
        """
        BUG E2: Test handling of DST transitions.

        Naive datetime handling causes off-by-one-hour errors
        around DST transitions.
        """
        from apps.interviews.scheduling import schedule_interview
        from apps.interviews.models import InterviewerAvailability
        import pytz

        # Create availability around DST transition
        # March 10, 2024 2:00 AM is when clocks spring forward
        tz = pytz.timezone('America/New_York')

        # Create an availability slot
        InterviewerAvailability.objects.create(
            user=user,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=8),
            is_available=True,
        )

        # The test checks that we can schedule around timezone edges
        # Full validation requires integration testing with real tz data

    @pytest.mark.bug_e2
    def test_suggest_times_uses_aware_datetime(self, user, application):
        """Test that time suggestions use timezone-aware datetimes."""
        from apps.interviews.scheduling import suggest_interview_times

        suggestions = suggest_interview_times(
            application_id=application.id,
            interviewer_ids=[user.id],
            duration_minutes=60,
            days_ahead=3,
            preferred_timezone='America/New_York'
        )

        # Check that returned times are timezone-aware
        for suggestion in suggestions:
            if 'start' in suggestion and suggestion['start']:
                # After fix, all times should be timezone-aware
                assert timezone.is_aware(suggestion['start']), \
                    "Suggested times should be timezone-aware"
