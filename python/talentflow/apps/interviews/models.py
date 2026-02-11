"""
TalentFlow Interview Models
"""
from django.db import models
from django.utils import timezone


class Interview(models.Model):
    """Interview scheduling model."""
    TYPE_CHOICES = [
        ('phone', 'Phone Screen'),
        ('video', 'Video Call'),
        ('onsite', 'On-site'),
        ('technical', 'Technical'),
        ('panel', 'Panel'),
        ('final', 'Final Round'),
    ]

    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
        ('rescheduled', 'Rescheduled'),
    ]

    # Links
    application = models.ForeignKey(
        'jobs.Application',
        on_delete=models.CASCADE,
        related_name='interviews'
    )

    # Type and status
    interview_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
    round_number = models.PositiveIntegerField(default=1)

    # Scheduling - Note: These are stored as timezone-aware in DB
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    timezone = models.CharField(max_length=50, default='UTC')

    # Location
    location = models.CharField(max_length=255, blank=True)
    meeting_url = models.URLField(blank=True)
    meeting_id = models.CharField(max_length=100, blank=True)
    meeting_password = models.CharField(max_length=50, blank=True)

    # Interviewers
    interviewers = models.ManyToManyField(
        'accounts.User',
        through='InterviewParticipant',
        related_name='interviews'
    )

    # Instructions
    candidate_instructions = models.TextField(blank=True)
    interviewer_instructions = models.TextField(blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_interviews'
    )

    class Meta:
        db_table = 'interviews_interview'
        ordering = ['scheduled_at']

    def __str__(self):
        return f"{self.interview_type} for {self.application.candidate} on {self.scheduled_at}"

    @property
    def end_time(self):
        from datetime import timedelta
        return self.scheduled_at + timedelta(minutes=self.duration_minutes)


class InterviewParticipant(models.Model):
    """Interviewer participation in interviews."""
    ROLE_CHOICES = [
        ('lead', 'Lead Interviewer'),
        ('technical', 'Technical Interviewer'),
        ('hr', 'HR Representative'),
        ('observer', 'Observer'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('accepted', 'Accepted'),
        ('declined', 'Declined'),
        ('tentative', 'Tentative'),
    ]

    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        related_name='participants'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='interview_participations'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='technical')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    class Meta:
        db_table = 'interviews_interview_participant'
        unique_together = ['interview', 'user']


class InterviewFeedback(models.Model):
    """Feedback from interviewers."""
    RATING_CHOICES = [
        (1, 'Strong No'),
        (2, 'No'),
        (3, 'Neutral'),
        (4, 'Yes'),
        (5, 'Strong Yes'),
    ]

    interview = models.ForeignKey(
        Interview,
        on_delete=models.CASCADE,
        related_name='feedback'
    )
    interviewer = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='given_feedback'
    )

    # Ratings
    overall_rating = models.PositiveIntegerField(choices=RATING_CHOICES)
    technical_rating = models.PositiveIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    communication_rating = models.PositiveIntegerField(choices=RATING_CHOICES, null=True, blank=True)
    culture_fit_rating = models.PositiveIntegerField(choices=RATING_CHOICES, null=True, blank=True)

    # Comments
    strengths = models.TextField(blank=True)
    weaknesses = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Metadata
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'interviews_interview_feedback'
        unique_together = ['interview', 'interviewer']


class InterviewerAvailability(models.Model):
    """Interviewer availability slots."""
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='availability_slots'
    )

    # Time slot - stored as timezone-aware
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()

    # Recurrence
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=255, blank=True)  # iCal format

    # Status
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = 'interviews_interviewer_availability'
        indexes = [
            models.Index(fields=['user', 'start_time']),
        ]

    def __str__(self):
        return f"{self.user} available {self.start_time} - {self.end_time}"
