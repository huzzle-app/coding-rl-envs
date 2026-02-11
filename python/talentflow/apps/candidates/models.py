"""
TalentFlow Candidate Models

Data models for managing candidates in the talent management system.
"""
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone


class Skill(models.Model):
    """Skill taxonomy model."""
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100)
    aliases = ArrayField(
        models.CharField(max_length=100),
        default=list,
        blank=True
    )

    class Meta:
        db_table = 'candidates_skill'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return self.name


class Candidate(models.Model):
    """
    Candidate model representing job applicants.
    """
    STATUS_CHOICES = [
        ('new', 'New'),
        ('screening', 'Screening'),
        ('interviewing', 'Interviewing'),
        ('offer', 'Offer'),
        ('hired', 'Hired'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn'),
    ]

    # Basic info
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=20, blank=True)

    # Company relationship
    company = models.ForeignKey(
        'accounts.Company',
        on_delete=models.CASCADE,
        related_name='candidates'
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='new'
    )
    status_updated_at = models.DateTimeField(auto_now=True)

    # Professional info
    title = models.CharField(max_length=200, blank=True)
    current_company = models.CharField(max_length=200, blank=True)
    years_experience = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=200, blank=True)

    # Skills - Many-to-Many relationship
    skills = models.ManyToManyField(
        Skill,
        through='CandidateSkill',
        related_name='candidates'
    )

    # Resume and documents
    resume_url = models.URLField(blank=True)
    resume_text = models.TextField(blank=True)
    linkedin_url = models.URLField(blank=True)
    portfolio_url = models.URLField(blank=True)

    # Scoring
    overall_score = models.FloatField(null=True, blank=True)
    skill_match_score = models.FloatField(null=True, blank=True)
    experience_score = models.FloatField(null=True, blank=True)

    # Source tracking
    source = models.CharField(
        max_length=50,
        choices=[
            ('direct', 'Direct Application'),
            ('referral', 'Referral'),
            ('linkedin', 'LinkedIn'),
            ('indeed', 'Indeed'),
            ('glassdoor', 'Glassdoor'),
            ('agency', 'Agency'),
            ('other', 'Other'),
        ],
        default='direct'
    )
    source_details = models.CharField(max_length=255, blank=True)
    referred_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )

    # Notes
    notes = models.TextField(blank=True)
    tags = ArrayField(
        models.CharField(max_length=50),
        default=list,
        blank=True
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_candidates'
    )

    class Meta:
        db_table = 'candidates_candidate'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class CandidateSkill(models.Model):
    """Through model for Candidate-Skill relationship with proficiency."""
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='candidate_skills'
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='skill_candidates'
    )
    proficiency = models.PositiveIntegerField(
        default=3,
        choices=[
            (1, 'Beginner'),
            (2, 'Elementary'),
            (3, 'Intermediate'),
            (4, 'Advanced'),
            (5, 'Expert'),
        ]
    )
    years_used = models.PositiveIntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    verified = models.BooleanField(default=False)

    class Meta:
        db_table = 'candidates_candidate_skill'
        unique_together = ['candidate', 'skill']

    def __str__(self):
        return f"{self.candidate} - {self.skill} ({self.get_proficiency_display()})"


class CandidateNote(models.Model):
    """Notes and activity log for candidates."""
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='activity_notes'
    )
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='candidate_notes'
    )
    note_type = models.CharField(
        max_length=20,
        choices=[
            ('note', 'Note'),
            ('call', 'Call'),
            ('email', 'Email'),
            ('meeting', 'Meeting'),
            ('status_change', 'Status Change'),
            ('system', 'System'),
        ],
        default='note'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'candidates_candidate_note'
        ordering = ['-created_at']

    def __str__(self):
        return f"Note on {self.candidate} by {self.author}"


class CandidateDocument(models.Model):
    """Documents attached to candidates."""
    candidate = models.ForeignKey(
        Candidate,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    name = models.CharField(max_length=255)
    document_type = models.CharField(
        max_length=20,
        choices=[
            ('resume', 'Resume'),
            ('cover_letter', 'Cover Letter'),
            ('portfolio', 'Portfolio'),
            ('certification', 'Certification'),
            ('reference', 'Reference'),
            ('other', 'Other'),
        ]
    )
    file_url = models.URLField()
    file_size = models.PositiveIntegerField(default=0)
    mime_type = models.CharField(max_length=100, blank=True)
    uploaded_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'candidates_candidate_document'

    def __str__(self):
        return f"{self.name} ({self.document_type})"
