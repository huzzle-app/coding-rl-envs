"""
Unit tests for authentication and permissions.

Tests: 30
"""
import pytest
from unittest.mock import patch, MagicMock


pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class TestJWTTokenGeneration:
    """Tests for JWT token generation."""

    def test_access_token_generation(self, user):
        """Test access token is generated correctly."""
        from apps.accounts.oauth import generate_access_token
        import jwt
        from django.conf import settings

        token = generate_access_token(user)

        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

        assert payload['user_id'] == user.id
        assert payload['email'] == user.email
        assert payload['type'] == 'access'

    def test_access_token_expiration(self, user):
        """Test access token has correct expiration."""
        from apps.accounts.oauth import generate_access_token
        import jwt
        import time
        from django.conf import settings

        token = generate_access_token(user)
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])

        exp = payload['exp']
        iat = payload['iat']

        expected_duration = settings.OAUTH2_PROVIDER.get('ACCESS_TOKEN_EXPIRE_SECONDS', 300)
        actual_duration = exp - iat

        assert actual_duration == expected_duration

    def test_refresh_token_generation(self, user, db):
        """Test refresh token is generated and stored."""
        from apps.accounts.oauth import generate_refresh_token
        from apps.accounts.models import RefreshToken

        refresh = generate_refresh_token(user)

        assert refresh.user == user
        assert refresh.token is not None
        assert not refresh.revoked

        stored = RefreshToken.objects.get(id=refresh.id)
        assert stored.token == refresh.token


class TestTokenVerification:
    """Tests for token verification."""

    def test_verify_valid_token(self, user):
        """Test verifying a valid token."""
        from apps.accounts.oauth import generate_access_token, verify_access_token

        token = generate_access_token(user)
        payload = verify_access_token(token)

        assert payload['user_id'] == user.id

    def test_verify_expired_token(self, user):
        """Test verifying an expired token raises error."""
        from apps.accounts.oauth import verify_access_token, JWTAuthenticationError
        import jwt
        import time
        from django.conf import settings

        payload = {
            'user_id': user.id,
            'email': user.email,
            'exp': int(time.time()) - 100,
            'type': 'access',
        }
        expired_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        with pytest.raises(JWTAuthenticationError) as exc_info:
            verify_access_token(expired_token)

        assert 'expired' in str(exc_info.value).lower()

    def test_verify_invalid_token(self, user):
        """Test verifying an invalid token raises error."""
        from apps.accounts.oauth import verify_access_token, JWTAuthenticationError

        with pytest.raises(JWTAuthenticationError):
            verify_access_token('invalid.token.here')

    def test_verify_wrong_token_type(self, user, db):
        """Test verifying a refresh token as access token fails."""
        from apps.accounts.oauth import verify_access_token, JWTAuthenticationError
        import jwt
        from django.conf import settings
        import time

        payload = {
            'user_id': user.id,
            'type': 'refresh',
            'exp': int(time.time()) + 3600,
        }
        wrong_type_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        with pytest.raises(JWTAuthenticationError) as exc_info:
            verify_access_token(wrong_type_token)

        assert 'type' in str(exc_info.value).lower()


class TestTokenRefresh:
    """Tests for token refresh functionality."""

    @pytest.mark.bug_c1
    def test_refresh_token_rotation(self, user, db):
        """Test refresh token rotation creates new token."""
        from apps.accounts.oauth import generate_refresh_token, refresh_access_token

        original = generate_refresh_token(user)
        original_string = original.token

        result = refresh_access_token(original_string)

        assert result['refresh_token'] != original_string
        original.refresh_from_db()
        assert original.revoked

    @pytest.mark.bug_c1
    def test_refresh_revoked_token_fails(self, user, db):
        """Test refreshing a revoked token fails."""
        from apps.accounts.oauth import (
            generate_refresh_token,
            refresh_access_token,
            JWTAuthenticationError
        )
        from django.utils import timezone

        refresh = generate_refresh_token(user)
        refresh.revoked = True
        refresh.revoked_at = timezone.now()
        refresh.save()

        with pytest.raises(JWTAuthenticationError) as exc_info:
            refresh_access_token(refresh.token)

        assert 'revoked' in str(exc_info.value).lower()

    @pytest.mark.bug_c1
    def test_refresh_expired_token_fails(self, user, db):
        """Test refreshing an expired token fails."""
        from apps.accounts.oauth import generate_refresh_token, refresh_access_token, JWTAuthenticationError
        from django.utils import timezone
        from datetime import timedelta

        refresh = generate_refresh_token(user)
        refresh.expires_at = timezone.now() - timedelta(hours=1)
        refresh.save()

        with pytest.raises(JWTAuthenticationError) as exc_info:
            refresh_access_token(refresh.token)

        assert 'expired' in str(exc_info.value).lower()


class TestRoleHierarchy:
    """Tests for role-based access control."""

    @pytest.mark.bug_f4
    def test_role_levels(self):
        """Test role hierarchy levels are correct."""
        from apps.accounts.oauth import ROLE_HIERARCHY

        assert ROLE_HIERARCHY['admin'] > ROLE_HIERARCHY['hiring_manager']
        assert ROLE_HIERARCHY['hiring_manager'] > ROLE_HIERARCHY['recruiter']
        assert ROLE_HIERARCHY['recruiter'] > ROLE_HIERARCHY['interviewer']
        assert ROLE_HIERARCHY['interviewer'] > ROLE_HIERARCHY['viewer']

    @pytest.mark.bug_f4
    def test_get_role_level_admin(self, user, db):
        """Test admin role level."""
        from apps.accounts.oauth import _get_role_level, ROLE_HIERARCHY

        user.role = 'admin'
        level = _get_role_level(user)

        assert level == ROLE_HIERARCHY['admin']

    @pytest.mark.bug_f4
    def test_get_role_level_superadmin(self, user, db):
        """Test superadmin gets admin level."""
        from apps.accounts.oauth import _get_role_level, ROLE_HIERARCHY

        user.role = 'superadmin'
        level = _get_role_level(user)

        assert level == ROLE_HIERARCHY['admin']

    @pytest.mark.bug_f4
    def test_get_role_level_custom(self, user, db):
        """Test custom role gets level 1."""
        from apps.accounts.oauth import _get_role_level

        user.role = 'custom_role'
        level = _get_role_level(user)

        assert level == 1

    @pytest.mark.bug_f4
    def test_get_role_level_unknown(self, user, db):
        """Test unknown role gets level 0."""
        from apps.accounts.oauth import _get_role_level

        user.role = 'unknown_role'
        level = _get_role_level(user)

        assert level == 0


class TestPermissionChecking:
    """Tests for permission checking."""

    @pytest.mark.bug_f4
    def test_check_permission_inactive_user(self, user, db):
        """Test inactive user has no permissions."""
        from apps.accounts.oauth import check_permission

        user.is_active = False
        result = check_permission(user, 'viewer')

        assert result is False

    @pytest.mark.bug_f4
    def test_check_permission_sufficient_role(self, user, db):
        """Test user with sufficient role has permission."""
        from apps.accounts.oauth import check_permission

        user.role = 'admin'
        user.is_active = True

        assert check_permission(user, 'viewer') is True
        assert check_permission(user, 'recruiter') is True
        assert check_permission(user, 'admin') is True

    @pytest.mark.bug_f4
    def test_check_permission_insufficient_role(self, user, db):
        """Test user with insufficient role lacks permission."""
        from apps.accounts.oauth import check_permission

        user.role = 'viewer'
        user.is_active = True

        assert check_permission(user, 'recruiter') is False
        assert check_permission(user, 'admin') is False

    @pytest.mark.bug_f4
    def test_check_permission_with_company(self, user, company, db):
        """Test permission check includes company access."""
        from apps.accounts.oauth import check_permission

        user.role = 'recruiter'
        user.is_active = True
        user.company = company

        assert check_permission(user, 'viewer', company.id) is True


class TestCompanyAccess:
    """Tests for company access verification."""

    @pytest.mark.bug_f4
    def test_verify_own_company_access(self, user, company, db):
        """Test user has access to own company."""
        from apps.accounts.oauth import _verify_company_access

        user.company = company

        assert _verify_company_access(user, company.id) is True

    @pytest.mark.bug_f4
    def test_verify_other_company_access_denied(self, user, company, db):
        """Test user denied access to other company."""
        from apps.accounts.oauth import _verify_company_access

        user.company = company
        other_company_id = company.id + 9999

        assert _verify_company_access(user, other_company_id) is False

    @pytest.mark.bug_f4
    def test_superadmin_cross_company_access(self, user, company, db):
        """Test superadmin has cross-company access."""
        from apps.accounts.oauth import _verify_company_access

        user.role = 'superadmin'
        user.company = company
        other_company_id = company.id + 9999

        assert _verify_company_access(user, other_company_id) is True


class TestUserPermissions:
    """Tests for user permission lists."""

    @pytest.mark.bug_f4
    def test_get_viewer_permissions(self, user, db):
        """Test viewer gets view permissions."""
        from apps.accounts.oauth import get_user_permissions

        user.role = 'viewer'
        perms = get_user_permissions(user)

        assert 'view_candidate' in perms
        assert 'view_reports' in perms
        assert 'edit_candidate' not in perms

    @pytest.mark.bug_f4
    def test_get_recruiter_permissions(self, user, db):
        """Test recruiter gets edit permissions."""
        from apps.accounts.oauth import get_user_permissions

        user.role = 'recruiter'
        perms = get_user_permissions(user)

        assert 'view_candidate' in perms
        assert 'edit_candidate' in perms
        assert 'edit_job' in perms
        assert 'delete_candidate' not in perms

    @pytest.mark.bug_f4
    def test_get_admin_permissions(self, user, db):
        """Test admin gets all permissions."""
        from apps.accounts.oauth import get_user_permissions

        user.role = 'admin'
        perms = get_user_permissions(user)

        assert 'manage_users' in perms
        assert 'manage_company' in perms
        assert 'delete_job' in perms


class TestImpersonation:
    """Tests for user impersonation."""

    @pytest.mark.bug_f4
    def test_admin_can_impersonate(self, user, db):
        """Test admin can impersonate users."""
        from apps.accounts.oauth import impersonate_user
        from apps.accounts.models import User

        admin = user
        admin.role = 'admin'
        admin.save()

        target = User.objects.create_user(
            email='target@example.com',
            first_name='Target',
            last_name='User',
            company=admin.company
        )

        token = impersonate_user(admin, target.id)

        assert token is not None

    @pytest.mark.bug_f4
    def test_non_admin_cannot_impersonate(self, user, db):
        """Test non-admin cannot impersonate."""
        from apps.accounts.oauth import impersonate_user, JWTAuthenticationError
        from apps.accounts.models import User

        user.role = 'recruiter'
        user.save()

        with pytest.raises(JWTAuthenticationError):
            impersonate_user(user, 999)

    @pytest.mark.bug_f4
    def test_impersonate_cross_company_requires_superadmin(self, user, company, db):
        """Test cross-company impersonation requires superadmin."""
        from apps.accounts.oauth import impersonate_user, JWTAuthenticationError
        from apps.accounts.models import User, Company

        other_company = Company.objects.create(name='Other Co')

        admin = user
        admin.role = 'admin'
        admin.company = company
        admin.save()

        target = User.objects.create_user(
            email='other@example.com',
            first_name='Other',
            last_name='User',
            company=other_company
        )

        with pytest.raises(JWTAuthenticationError):
            impersonate_user(admin, target.id)
