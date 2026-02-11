"""
Auth service models.
"""
from datetime import datetime, timedelta
from uuid import uuid4
from django.db import models


class User(models.Model):
    """User model for authentication."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    password_hash = models.CharField(max_length=255)
    account_type = models.CharField(max_length=50, default="individual")

    
    is_admin = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    trading_enabled = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login = models.DateTimeField(null=True, blank=True)

    
    # Missing: failed_login_count, last_failed_login

    class Meta:
        app_label = "auth"
        db_table = "users"


class RefreshToken(models.Model):
    """Refresh token storage."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="refresh_tokens")
    token = models.CharField(max_length=255, unique=True)
    
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    revoked = models.BooleanField(default=False)
    

    class Meta:
        app_label = "auth"
        db_table = "refresh_tokens"
        
        # indexes = [models.Index(fields=['token'])]


class APIKey(models.Model):
    """API key storage."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_keys")
    key_hash = models.CharField(max_length=255)
    name = models.CharField(max_length=100)
    
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "auth"
        db_table = "api_keys"


class OAuthState(models.Model):
    """OAuth state storage for CSRF protection."""

    state = models.CharField(max_length=255, primary_key=True)
    user_id = models.UUIDField(null=True, blank=True)
    redirect_uri = models.URLField()
    provider = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    

    class Meta:
        app_label = "auth"
        db_table = "oauth_states"


class Permission(models.Model):
    """Permission model."""

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    resource = models.CharField(max_length=100)
    action = models.CharField(max_length=50)

    class Meta:
        app_label = "auth"
        db_table = "permissions"


class UserPermission(models.Model):
    """User permission assignment."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="permissions")
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    granted_at = models.DateTimeField(auto_now_add=True)
    granted_by = models.UUIDField()
    

    class Meta:
        app_label = "auth"
        db_table = "user_permissions"
        unique_together = [["user", "permission"]]
