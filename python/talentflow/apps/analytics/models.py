"""
TalentFlow Analytics Models
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField


class Report(models.Model):
    """Generated analytics reports."""
    REPORT_TYPES = [
        ('hiring_funnel', 'Hiring Funnel'),
        ('time_to_hire', 'Time to Hire'),
        ('source_effectiveness', 'Source Effectiveness'),
        ('recruiter_performance', 'Recruiter Performance'),
        ('job_analytics', 'Job Analytics'),
        ('diversity', 'Diversity Report'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('generating', 'Generating'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='reports'
    )
    report_type = models.CharField(max_length=50, choices=REPORT_TYPES)
    name = models.CharField(max_length=255)

    # Parameters
    parameters = models.JSONField(default=dict)
    date_range_start = models.DateField(null=True, blank=True)
    date_range_end = models.DateField(null=True, blank=True)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True)

    # Results
    data = models.JSONField(default=dict)
    summary = models.TextField(blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_reports'
    )

    class Meta:
        db_table = 'analytics_report'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.report_type})"


class DailyMetric(models.Model):
    """Daily aggregated metrics for fast querying."""
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='daily_metrics'
    )
    date = models.DateField()

    # Application metrics
    new_applications = models.PositiveIntegerField(default=0)
    applications_reviewed = models.PositiveIntegerField(default=0)
    applications_rejected = models.PositiveIntegerField(default=0)
    applications_shortlisted = models.PositiveIntegerField(default=0)

    # Interview metrics
    interviews_scheduled = models.PositiveIntegerField(default=0)
    interviews_completed = models.PositiveIntegerField(default=0)
    interviews_cancelled = models.PositiveIntegerField(default=0)

    # Hiring metrics
    offers_extended = models.PositiveIntegerField(default=0)
    offers_accepted = models.PositiveIntegerField(default=0)
    offers_declined = models.PositiveIntegerField(default=0)

    # Job metrics
    jobs_opened = models.PositiveIntegerField(default=0)
    jobs_closed = models.PositiveIntegerField(default=0)
    jobs_filled = models.PositiveIntegerField(default=0)

    # Candidate metrics
    new_candidates = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'analytics_daily_metric'
        unique_together = ['company', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"Metrics for {self.company.name} on {self.date}"


class CachedQuery(models.Model):
    """Cached query results for expensive reports."""
    query_hash = models.CharField(max_length=64, unique=True, db_index=True)
    query_type = models.CharField(max_length=50)
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='cached_queries'
    )

    # Cached data
    result_data = models.JSONField(default=dict)

    # TTL
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'analytics_cached_query'
        indexes = [
            models.Index(fields=['query_hash']),
            models.Index(fields=['expires_at']),
        ]

    @property
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() >= self.expires_at
