"""
TalentFlow Accounts Models

Custom user model and related authentication models.
"""
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager for TalentFlow users."""

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user model for TalentFlow."""

    username = None  # Remove username field
    email = models.EmailField('email address', unique=True)

    # Profile fields
    company = models.ForeignKey(
        'Company',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    role = models.CharField(
        max_length=50,
        choices=[
            ('admin', 'Administrator'),
            ('recruiter', 'Recruiter'),
            ('hiring_manager', 'Hiring Manager'),
            ('interviewer', 'Interviewer'),
            ('viewer', 'Viewer'),
        ],
        default='viewer'
    )
    phone = models.CharField(max_length=20, blank=True)
    timezone = models.CharField(max_length=50, default='UTC')
    avatar_url = models.URLField(blank=True)

    # Metadata
    last_active = models.DateTimeField(null=True, blank=True)
    email_verified = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        db_table = 'accounts_user'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['company', 'role']),
        ]

    def __str__(self):
        return self.email

    def update_last_active(self):
        self.last_active = timezone.now()
        self.save(update_fields=['last_active'])


class Company(models.Model):
    """Company/Organization model."""

    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    domain = models.CharField(max_length=255, blank=True)

    # Settings
    settings = models.JSONField(default=dict)
    subscription_tier = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('starter', 'Starter'),
            ('professional', 'Professional'),
            ('enterprise', 'Enterprise'),
        ],
        default='free'
    )

    # OAuth2 credentials for this company's integrations
    oauth_credentials = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_company'
        verbose_name_plural = 'Companies'

    def __str__(self):
        return self.name


class RefreshToken(models.Model):
    """
    Custom refresh token model for JWT authentication.
    Used alongside OAuth2 provider tokens.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='refresh_tokens')
    token = models.CharField(max_length=255, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)

    # For tracking token lineage (refresh token rotation)
    parent_token = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children'
    )

    class Meta:
        db_table = 'accounts_refresh_token'
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['user', 'revoked']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        return f"RefreshToken for {self.user.email}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_valid(self):
        return not self.revoked and not self.is_expired


class OAuthState(models.Model):
    """
    Store OAuth state parameters for CSRF protection.
    """
    state = models.CharField(max_length=255, unique=True, db_index=True)
    redirect_uri = models.URLField()
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    # Additional context
    provider = models.CharField(max_length=50)  # google, github, etc.
    code_verifier = models.CharField(max_length=255, blank=True)  # For PKCE

    class Meta:
        db_table = 'accounts_oauth_state'

    @property
    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at
