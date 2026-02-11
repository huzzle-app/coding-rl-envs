"""
Unit tests for accounts app.

Tests: 10
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, company):
        """Test creating a regular user."""
        from apps.accounts.models import User
        user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
        )
        assert user.email == 'test@example.com'
        assert user.check_password('testpass123')
        assert not user.is_staff
        assert not user.is_superuser

    def test_create_user_no_email_raises(self):
        """Test that creating user without email raises."""
        from apps.accounts.models import User
        with pytest.raises(ValueError):
            User.objects.create_user(email='', password='test')

    def test_create_superuser(self, company):
        """Test creating a superuser."""
        from apps.accounts.models import User
        admin = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpass123',
            first_name='Admin',
            last_name='User',
        )
        assert admin.is_staff
        assert admin.is_superuser

    def test_user_update_last_active(self, user):
        """Test updating last active timestamp."""
        old_time = user.last_active
        user.update_last_active()
        assert user.last_active is not None
        assert user.last_active != old_time


class TestRefreshTokenModel:
    """Tests for RefreshToken model."""

    def test_refresh_token_is_valid(self, refresh_token):
        """Test valid refresh token."""
        assert refresh_token.is_valid
        assert not refresh_token.is_expired
        assert not refresh_token.revoked

    def test_refresh_token_expired(self, user):
        """Test expired refresh token."""
        from apps.accounts.models import RefreshToken
        token = RefreshToken.objects.create(
            user=user,
            token='expired-token',
            expires_at=timezone.now() - timedelta(hours=1),
        )
        assert token.is_expired
        assert not token.is_valid

    def test_refresh_token_revoked(self, user):
        """Test revoked refresh token."""
        from apps.accounts.models import RefreshToken
        token = RefreshToken.objects.create(
            user=user,
            token='revoked-token',
            expires_at=timezone.now() + timedelta(days=1),
            revoked=True,
        )
        assert token.revoked
        assert not token.is_valid


class TestOAuthState:
    """Tests for OAuth state model."""

    def test_oauth_state_is_valid(self, oauth_state):
        """Test valid OAuth state."""
        assert oauth_state.is_valid
        assert not oauth_state.used

    def test_oauth_state_expired(self, db):
        """Test expired OAuth state."""
        from apps.accounts.models import OAuthState
        state = OAuthState.objects.create(
            state='expired-state',
            provider='google',
            redirect_uri='http://localhost/callback',
            expires_at=timezone.now() - timedelta(minutes=5),
        )
        assert not state.is_valid

    def test_oauth_state_used(self, oauth_state):
        """Test used OAuth state is not valid."""
        oauth_state.used = True
        oauth_state.save()
        assert not oauth_state.is_valid


class TestJWTGeneration:
    """Tests for JWT token generation."""

    def test_generate_access_token(self, user):
        """Test access token generation."""
        from apps.accounts.oauth import generate_access_token, verify_access_token

        token = generate_access_token(user)
        assert token is not None

        payload = verify_access_token(token)
        assert payload['user_id'] == user.id
        assert payload['email'] == user.email
        assert payload['type'] == 'access'

    def test_generate_refresh_token(self, user):
        """Test refresh token generation."""
        from apps.accounts.oauth import generate_refresh_token

        token = generate_refresh_token(user)
        assert token is not None
        assert token.user == user
        assert token.is_valid
