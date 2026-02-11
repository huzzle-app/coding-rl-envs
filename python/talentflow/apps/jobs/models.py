"""
TalentFlow Job Models
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone


class Job(models.Model):
    """Job posting model."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('open', 'Open'),
        ('paused', 'Paused'),
        ('closed', 'Closed'),
        ('filled', 'Filled'),
    ]

    EMPLOYMENT_TYPE_CHOICES = [
        ('full_time', 'Full Time'),
        ('part_time', 'Part Time'),
        ('contract', 'Contract'),
        ('internship', 'Internship'),
        ('temporary', 'Temporary'),
    ]

    EXPERIENCE_LEVEL_CHOICES = [
        ('entry', 'Entry Level'),
        ('mid', 'Mid Level'),
        ('senior', 'Senior Level'),
        ('lead', 'Lead'),
        ('executive', 'Executive'),
    ]

    # Basic info
    title = models.CharField(max_length=255)
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='jobs'
    )
    department = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    requirements = models.TextField(blank=True)
    responsibilities = models.TextField(blank=True)
    benefits = models.TextField(blank=True)

    # Classification
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EMPLOYMENT_TYPE_CHOICES,
        default='full_time'
    )
    experience_level = models.CharField(
        max_length=20,
        choices=EXPERIENCE_LEVEL_CHOICES,
        default='mid'
    )

    # Location
    location = models.CharField(max_length=200)
    is_remote = models.BooleanField(default=False)
    remote_type = models.CharField(
        max_length=20,
        choices=[
            ('no', 'No Remote'),
            ('hybrid', 'Hybrid'),
            ('full', 'Fully Remote'),
        ],
        default='no'
    )

    # Compensation
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default='USD')
    show_salary = models.BooleanField(default=True)

    # Skills
    required_skills = models.ManyToManyField(
        'candidates.Skill',
        related_name='required_for_jobs'
    )
    preferred_skills = models.ManyToManyField(
        'candidates.Skill',
        related_name='preferred_for_jobs',
        blank=True
    )

    # Requirements
    min_experience_years = models.PositiveIntegerField(default=0)
    max_experience_years = models.PositiveIntegerField(null=True, blank=True)
    education_level = models.CharField(
        max_length=50,
        choices=[
            ('none', 'None Required'),
            ('high_school', 'High School'),
            ('associate', 'Associate Degree'),
            ('bachelor', 'Bachelor Degree'),
            ('master', 'Master Degree'),
            ('phd', 'PhD'),
        ],
        default='none'
    )

    # Hiring team
    hiring_manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_jobs'
    )
    recruiters = models.ManyToManyField(
        'accounts.User',
        related_name='assigned_jobs',
        blank=True
    )

    # Pipeline
    pipeline_stages = ArrayField(
        models.CharField(max_length=100),
        default=list
    )

    # Limits
    target_hire_date = models.DateField(null=True, blank=True)
    max_applications = models.PositiveIntegerField(null=True, blank=True)

    # Metadata
    external_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_jobs'
    )
    published_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'jobs_job'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['company', 'status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.title} at {self.company.name}"

    def publish(self):
        self.status = 'open'
        self.published_at = timezone.now()
        self.save()

    def close(self):
        self.status = 'closed'
        self.closed_at = timezone.now()
        self.save()


class Application(models.Model):
    """Job application linking candidates to jobs."""
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('reviewing', 'Under Review'),
        ('shortlisted', 'Shortlisted'),
        ('interviewing', 'Interviewing'),
        ('offer', 'Offer Extended'),
        ('accepted', 'Offer Accepted'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name='applications'
    )
    candidate = models.ForeignKey(
        'candidates.Candidate',
        on_delete=models.CASCADE,
        related_name='applications'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    stage = models.CharField(max_length=100, blank=True)

    # Scoring
    match_score = models.FloatField(null=True, blank=True)
    recruiter_score = models.FloatField(null=True, blank=True)
    interview_score = models.FloatField(null=True, blank=True)

    # Cover letter and notes
    cover_letter = models.TextField(blank=True)
    recruiter_notes = models.TextField(blank=True)

    # Tracking
    applied_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    # Source
    source = models.CharField(max_length=50, blank=True)
    referrer = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referred_applications'
    )

    class Meta:
        db_table = 'jobs_application'
        unique_together = ['job', 'candidate']
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['job', 'status']),
            models.Index(fields=['applied_at']),
            models.Index(fields=['match_score']),
        ]

    def __str__(self):
        return f"{self.candidate} applied to {self.job}"


class ApplicationNote(models.Model):
    """Notes on job applications."""
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name='notes'
    )
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True
    )
    note_type = models.CharField(
        max_length=20,
        choices=[
            ('note', 'Note'),
            ('feedback', 'Feedback'),
            ('status_change', 'Status Change'),
        ],
        default='note'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'jobs_application_note'
        ordering = ['-created_at']
