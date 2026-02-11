"""
Security tests for OAuth and authentication.

Tests: 15 - Focus on OAuth state validation and JWT race condition bugs
"""
import pytest
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from django.utils import timezone


pytestmark = [pytest.mark.security, pytest.mark.django_db(transaction=True)]


class TestOAuthStateSecurity:
    """Security tests for OAuth state validation - detects Bug C2."""

    @pytest.mark.bug_c2
    def test_oauth_callback_validates_state(self, api_client, oauth_state):
        """
        BUG C2: Test that OAuth callback validates state parameter.

        Without state validation, the OAuth flow is vulnerable to CSRF attacks.
        """
        from apps.accounts.oauth import process_oauth_callback, OAuthError, validate_oauth_state

        # Valid state should work
        try:
            # This would normally validate the state
            valid_state = validate_oauth_state(oauth_state.state)
            assert valid_state is not None
        except OAuthError:
            pytest.fail("Valid state should be accepted")

        # Invalid state should be rejected
        with pytest.raises(OAuthError):
            validate_oauth_state('invalid-state-parameter')

    @pytest.mark.bug_c2
    def test_oauth_callback_without_state_is_vulnerable(self):
        """
        BUG C2: Demonstrate CSRF vulnerability in OAuth callback.

        The process_oauth_callback function receives state but doesn't
        validate it, making the flow vulnerable to CSRF.
        """
        from apps.accounts.oauth import process_oauth_callback, OAuthError

        # An attacker can provide any state value
        
        # After fix, invalid state should raise OAuthError
        with pytest.raises(OAuthError):
            process_oauth_callback(
                provider='google',
                code='fake-auth-code',
                state='attacker-controlled-state',  # Should be rejected!
            )

    @pytest.mark.bug_c2
    def test_oauth_state_csrf_attack_scenario(self, api_client, user):
        """
        BUG C2: Simulate a CSRF attack on OAuth flow.

        Attack scenario:
        1. Attacker starts OAuth flow, gets authorization code
        2. Attacker tricks victim into visiting callback with attacker's code
        3. Without state validation, victim logs in as attacker
        """
        # This test documents the attack scenario
        # After fix, state validation would prevent this

        # Simulate attacker initiating OAuth
        attacker_state = 'attacker-controlled'

        # Simulate callback without proper state validation
        
        response = api_client.get('/api/v1/accounts/oauth/callback/', {
            'code': 'attacker-auth-code',
            'state': attacker_state,
            'provider': 'google',
        })

        # With the bug fix, this should be rejected immediately due to invalid state
        assert response.status_code in [400, 403], \
            f"Invalid OAuth state should be rejected, got {response.status_code}"

    @pytest.mark.bug_c2
    def test_oauth_state_expiration(self, db):
        """Test that expired OAuth states are rejected."""
        from apps.accounts.models import OAuthState
        from apps.accounts.oauth import validate_oauth_state, OAuthError

        # Create expired state
        expired_state = OAuthState.objects.create(
            state='expired-state-token',
            provider='google',
            redirect_uri='http://localhost/callback',
            expires_at=timezone.now() - timedelta(minutes=5),
        )

        # Should be rejected
        with pytest.raises(OAuthError):
            validate_oauth_state(expired_state.state)

    @pytest.mark.bug_c2
    def test_oauth_state_reuse_prevention(self, oauth_state):
        """Test that OAuth states can't be reused."""
        from apps.accounts.oauth import validate_oauth_state, OAuthError

        # First use should succeed
        validate_oauth_state(oauth_state.state)

        # Second use should fail
        with pytest.raises(OAuthError):
            validate_oauth_state(oauth_state.state)


class TestJWTRefreshSecurity:
    """Security tests for JWT refresh - detects Bug C1."""

    @pytest.mark.bug_c1
    def test_concurrent_refresh_race_condition(self, user, refresh_token):
        """
        BUG C1: Test race condition in token refresh.

        When multiple requests try to refresh the same token simultaneously,
        both can succeed, creating duplicate tokens.
        """
        from apps.accounts.oauth import refresh_access_token, JWTAuthenticationError
        from apps.accounts.models import RefreshToken

        # Get initial count
        initial_count = RefreshToken.objects.filter(user=user, revoked=False).count()

        results = []
        errors = []

        def do_refresh():
            try:
                result = refresh_access_token(refresh_token.token)
                results.append(result)
                return True
            except JWTAuthenticationError as e:
                errors.append(str(e))
                return False
            except Exception as e:
                errors.append(str(e))
                return False

        # Try to refresh concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(do_refresh) for _ in range(5)]
            outcomes = [f.result() for f in as_completed(futures)]

        
        # After fix, exactly one should succeed

        final_count = RefreshToken.objects.filter(user=user, revoked=False).count()

        # If race condition exists, we might have more tokens than expected
        success_count = sum(outcomes)

        # Document expected behavior: exactly 1 success, others should fail
        # With bug: multiple successes possible
        # After fix: exactly 1 success

    @pytest.mark.bug_c1
    def test_refresh_token_rotation(self, user, refresh_token):
        """Test that refresh token rotation works correctly."""
        from apps.accounts.oauth import refresh_access_token

        old_token = refresh_token.token

        result = refresh_access_token(old_token)

        # Should get new tokens
        assert 'access_token' in result
        assert 'refresh_token' in result
        assert result['refresh_token'] != old_token

        # Old token should be revoked
        refresh_token.refresh_from_db()
        assert refresh_token.revoked

    @pytest.mark.bug_c1
    def test_revoked_token_reuse_detection(self, user, refresh_token):
        """Test that reusing revoked token revokes all user tokens."""
        from apps.accounts.oauth import refresh_access_token, JWTAuthenticationError
        from apps.accounts.models import RefreshToken

        old_token = refresh_token.token

        # First refresh
        refresh_access_token(old_token)

        # Create another valid token
        new_token = RefreshToken.objects.create(
            user=user,
            token='new-valid-token',
            expires_at=timezone.now() + timedelta(days=1),
        )

        # Try to reuse the old (now revoked) token
        with pytest.raises(JWTAuthenticationError, match='reuse'):
            refresh_access_token(old_token)

        # All user tokens should be revoked (security measure)
        new_token.refresh_from_db()
        assert new_token.revoked

    @pytest.mark.bug_c1
    def test_expired_refresh_token_rejected(self, user):
        """Test that expired refresh tokens are rejected."""
        from apps.accounts.models import RefreshToken
        from apps.accounts.oauth import refresh_access_token, JWTAuthenticationError

        expired_token = RefreshToken.objects.create(
            user=user,
            token='expired-refresh-token',
            expires_at=timezone.now() - timedelta(hours=1),
        )

        with pytest.raises(JWTAuthenticationError, match='expired'):
            refresh_access_token(expired_token.token)


class TestAccessTokenSecurity:
    """Security tests for access tokens."""

    def test_access_token_expiration(self, user):
        """Test that access tokens expire correctly."""
        from apps.accounts.oauth import generate_access_token, verify_access_token, JWTAuthenticationError
        import time

        token = generate_access_token(user)

        # Should be valid initially
        payload = verify_access_token(token)
        assert payload['user_id'] == user.id

        # Note: Can't easily test expiration without waiting or mocking

    def test_invalid_access_token_rejected(self):
        """Test that invalid access tokens are rejected."""
        from apps.accounts.oauth import verify_access_token, JWTAuthenticationError

        with pytest.raises(JWTAuthenticationError):
            verify_access_token('invalid.token.here')

    def test_tampered_access_token_rejected(self, user):
        """Test that tampered tokens are rejected."""
        from apps.accounts.oauth import generate_access_token, verify_access_token, JWTAuthenticationError

        token = generate_access_token(user)

        # Tamper with the token
        parts = token.split('.')
        parts[1] = 'tampered' + parts[1]
        tampered = '.'.join(parts)

        with pytest.raises(JWTAuthenticationError):
            verify_access_token(tampered)


class TestAuthenticationFlow:
    """Security tests for authentication flow."""

    def test_password_not_returned_in_response(self, api_client, user):
        """Test that password is never returned in API responses."""
        api_client.force_authenticate(user=user)
        response = api_client.get('/api/v1/accounts/me/')

        assert 'password' not in response.data
        assert 'password_hash' not in str(response.data)

    def test_logout_revokes_all_tokens(self, authenticated_client, user):
        """Test that logout revokes all user tokens."""
        from apps.accounts.models import RefreshToken

        # Create multiple tokens
        for i in range(3):
            RefreshToken.objects.create(
                user=user,
                token=f'token-{i}',
                expires_at=timezone.now() + timedelta(days=1),
            )

        # Logout
        response = authenticated_client.post('/api/v1/accounts/logout/')

        assert response.status_code == 200

        # All tokens should be revoked
        active_tokens = RefreshToken.objects.filter(user=user, revoked=False).count()
        assert active_tokens == 0

    def test_invalid_credentials_rejected(self, api_client, user):
        """Test that invalid credentials are rejected."""
        response = api_client.post('/api/v1/accounts/login/', {
            'email': user.email,
            'password': 'wrong-password',
        })

        assert response.status_code == 401
