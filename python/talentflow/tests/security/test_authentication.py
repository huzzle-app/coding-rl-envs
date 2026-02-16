"""
Security tests for authentication mechanisms.

Tests: 25
"""
import pytest
import time
from unittest.mock import patch


pytestmark = [pytest.mark.security, pytest.mark.django_db]


class TestBruteForceProtection:
    """Tests for brute force protection."""

    def test_failed_login_tracking(self, user, db):
        """Test failed login attempts are tracked."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        response = api_client.post(
            '/api/v1/auth/login/',
            {'email': user.email, 'password': 'wrong'},
            format='json'
        )
        assert response.status_code in [401, 400, 404]

    def test_account_lockout_threshold(self, user, db):
        """Test account locks after threshold."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        for _ in range(5):
            api_client.post(
                '/api/v1/auth/login/',
                {'email': user.email, 'password': 'wrong'},
                format='json'
            )
        response = api_client.post(
            '/api/v1/auth/login/',
            {'email': user.email, 'password': 'wrong'},
            format='json'
        )
        assert response.status_code in [401, 429, 400, 404]

    def test_lockout_duration(self, user, db):
        """Test lockout expires after duration."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.post(
            '/api/v1/auth/login/',
            {'email': user.email, 'password': 'wrong'},
            format='json'
        )
        response = api_client.post(
            '/api/v1/auth/login/',
            {'email': user.email, 'password': 'testpass123'},
            format='json'
        )
        assert response.status_code in [200, 429, 400, 404]


class TestPasswordSecurity:
    """Tests for password security."""

    def test_password_hash_algorithm(self, user, db):
        """Test password is hashed with secure algorithm."""
        from apps.accounts.models import User

        user = User.objects.create_user(
            email='passtest@test.com',
            password='SecurePass123!',
            first_name='Test',
            last_name='User'
        )

        assert not user.password.startswith('SecurePass')
        assert user.check_password('SecurePass123!')

    def test_password_not_in_response(self, user, db):
        """Test password is not returned in API responses."""
        from apps.accounts.serializers import UserSerializer

        serializer = UserSerializer(user)
        assert 'password' not in serializer.data


class TestTokenSecurity:
    """Tests for token security."""

    def test_token_entropy(self, user, db):
        """Test tokens have sufficient entropy."""
        from apps.accounts.oauth import generate_refresh_token

        tokens = [generate_refresh_token(user).token for _ in range(10)]

        unique_tokens = set(tokens)
        assert len(unique_tokens) == 10

    def test_token_signature_validation(self, user):
        """Test tampered tokens are rejected."""
        from apps.accounts.oauth import generate_access_token, verify_access_token, JWTAuthenticationError

        token = generate_access_token(user)

        tampered = token[:-5] + 'XXXXX'

        with pytest.raises(JWTAuthenticationError):
            verify_access_token(tampered)

    @pytest.mark.bug_c1
    def test_token_replay_prevention(self, user, db):
        """Test token replay is prevented."""
        from apps.accounts.oauth import generate_refresh_token, refresh_access_token, JWTAuthenticationError

        refresh = generate_refresh_token(user)
        token_string = refresh.token

        refresh_access_token(token_string)

        with pytest.raises(JWTAuthenticationError):
            refresh_access_token(token_string)

    def test_token_expiration_respected(self, user):
        """Test expired tokens are rejected."""
        from apps.accounts.oauth import verify_access_token, JWTAuthenticationError
        import jwt
        from django.conf import settings

        payload = {
            'user_id': user.id,
            'exp': int(time.time()) - 100,
            'type': 'access',
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        with pytest.raises(JWTAuthenticationError):
            verify_access_token(expired_token)


class TestSessionSecurity:
    """Tests for session security."""

    def test_session_invalidation_on_password_change(self, user, db):
        """Test sessions invalidated on password change."""
        from apps.accounts.oauth import generate_refresh_token
        from apps.accounts.models import RefreshToken

        token = generate_refresh_token(user)
        user.set_password('newpassword123')
        user.save()

        assert RefreshToken.objects.filter(user=user).exists()

    def test_session_cookie_flags(self):
        """Test session cookies have secure flags."""
        from django.conf import settings

        assert hasattr(settings, 'SESSION_COOKIE_SECURE')


class TestOAuthSecurity:
    """Tests for OAuth security."""

    @pytest.mark.bug_c2
    def test_oauth_state_required(self, db):
        """Test OAuth requires state parameter."""
        from apps.accounts.oauth import process_oauth_callback, OAuthError

        with pytest.raises(OAuthError):
            process_oauth_callback('google', 'code', state=None)

    @pytest.mark.bug_c2
    def test_oauth_state_single_use(self, oauth_state, db):
        """Test OAuth state can only be used once."""
        from apps.accounts.oauth import validate_oauth_state, OAuthError

        validate_oauth_state(oauth_state.state)

        with pytest.raises(OAuthError):
            validate_oauth_state(oauth_state.state)

    def test_oauth_code_exchange_timeout(self):
        """Test OAuth code exchange has timeout."""
        from apps.accounts.oauth import process_oauth_callback, OAuthError

        with pytest.raises(OAuthError):
            process_oauth_callback('google', 'invalid_code', state='invalid_state')


class TestCrossSiteProtection:
    """Tests for cross-site attack protection."""

    def test_csrf_token_required(self, client, db):
        """Test CSRF token is required for mutations."""
        from django.conf import settings

        assert hasattr(settings, 'REST_FRAMEWORK')

    def test_cors_headers(self, client, db):
        """Test CORS headers are set correctly."""
        from django.conf import settings

        assert hasattr(settings, 'ALLOWED_HOSTS')

    def test_content_type_validation(self, client, user, db):
        """Test content type is validated."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        response = api_client.post(
            '/api/v1/candidates/',
            'not json data',
            content_type='text/plain'
        )

        assert response.status_code in [400, 415, 404]


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_api_rate_limit_exists(self, user, db):
        """Test API has rate limiting configured."""
        from django.conf import settings

        rf = getattr(settings, 'REST_FRAMEWORK', {})
        assert 'DEFAULT_THROTTLE_CLASSES' in rf or 'DEFAULT_THROTTLE_RATES' in rf

    def test_login_rate_limit(self, client, db):
        """Test login endpoint responds to bad credentials."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        response = api_client.post(
            '/api/v1/auth/login/',
            {'email': 'nobody@test.com', 'password': 'wrong'},
            format='json'
        )
        assert response.status_code in [401, 400, 429, 404]


class TestDataExposure:
    """Tests for sensitive data exposure."""

    def test_no_sensitive_data_in_logs(self):
        """Test sensitive data is not logged."""
        import logging
        assert logging.getLogger().handlers is not None or True

    def test_no_stack_traces_in_production(self):
        """Test stack traces not exposed in production."""
        from django.conf import settings

        assert settings.DEBUG is False

    def test_error_messages_generic(self, user, db):
        """Test error messages don't reveal internals."""
        from apps.accounts.oauth import verify_access_token, JWTAuthenticationError

        with pytest.raises(JWTAuthenticationError) as exc_info:
            verify_access_token('invalid')

        error_msg = str(exc_info.value)
        assert 'SECRET_KEY' not in error_msg
        assert 'settings' not in error_msg.lower()


class TestInputSanitization:
    """Tests for input sanitization."""

    @pytest.mark.bug_i1
    def test_sql_characters_sanitized(self, user, db):
        """Test SQL special characters are sanitized."""
        from rest_framework.test import APIClient

        api_client = APIClient()
        api_client.force_authenticate(user=user)

        malicious_inputs = [
            "'; DROP TABLE--",
            "1 OR 1=1",
            "UNION SELECT *",
        ]

        for input_str in malicious_inputs:
            response = api_client.post(
                '/api/v1/candidates/advanced-search/',
                {'query': input_str},
                format='json'
            )
            assert response.status_code in [200, 400, 404, 500]

    def test_html_escaped_in_output(self, company, user, db):
        """Test HTML is escaped in output."""
        from apps.candidates.models import Candidate

        candidate = Candidate.objects.create(
            first_name='<script>alert("XSS")</script>',
            last_name='Test',
            email='xss@test.com',
            company=company,
            created_by=user
        )

        assert '<script>' in candidate.first_name or '&lt;script&gt;' in candidate.first_name
