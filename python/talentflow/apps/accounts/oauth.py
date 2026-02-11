"""
TalentFlow OAuth2 Authentication

Handles JWT token generation, refresh, and OAuth2 flow.
"""
import hashlib
import secrets
import time
from datetime import timedelta

import jwt
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OAuthState, RefreshToken, User


class JWTAuthenticationError(Exception):
    """Custom exception for JWT authentication errors."""
    pass


class OAuthError(Exception):
    """Custom exception for OAuth errors."""
    pass


def generate_access_token(user: User) -> str:
    """Generate a short-lived JWT access token."""
    payload = {
        'user_id': user.id,
        'email': user.email,
        'role': user.role,
        'company_id': user.company_id,
        'iat': int(time.time()),
        'exp': int(time.time()) + settings.OAUTH2_PROVIDER.get(
            'ACCESS_TOKEN_EXPIRE_SECONDS', 300
        ),
        'type': 'access',
    }
    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm='HS256'
    )


def generate_refresh_token(user: User, parent_token: RefreshToken = None) -> RefreshToken:
    """Generate a new refresh token and store it in the database."""
    token_string = secrets.token_urlsafe(32)
    expires_at = timezone.now() + timedelta(
        seconds=settings.OAUTH2_PROVIDER.get('REFRESH_TOKEN_EXPIRE_SECONDS', 86400)
    )

    refresh_token = RefreshToken.objects.create(
        user=user,
        token=token_string,
        expires_at=expires_at,
        parent_token=parent_token,
    )

    return refresh_token


def refresh_access_token(refresh_token_string: str) -> dict:
    """
    Refresh an access token using a refresh token.

    Implements token rotation for security.
    """
    try:
        refresh_token = RefreshToken.objects.get(token=refresh_token_string)
    except RefreshToken.DoesNotExist:
        raise JWTAuthenticationError('Invalid refresh token')

    # Check if token is valid
    if refresh_token.revoked:
        # Token reuse detected - possible attack, revoke all user tokens
        RefreshToken.objects.filter(user=refresh_token.user).update(
            revoked=True,
            revoked_at=timezone.now()
        )
        raise JWTAuthenticationError('Token has been revoked - possible reuse attack')

    if refresh_token.is_expired:
        raise JWTAuthenticationError('Refresh token has expired')

    # Create new tokens
    user = refresh_token.user
    new_access_token = generate_access_token(user)
    new_refresh_token = generate_refresh_token(user, parent_token=refresh_token)

    # Revoke old token
    refresh_token.revoked = True
    refresh_token.revoked_at = timezone.now()
    refresh_token.save()

    return {
        'access_token': new_access_token,
        'refresh_token': new_refresh_token.token,
        'expires_in': settings.OAUTH2_PROVIDER.get('ACCESS_TOKEN_EXPIRE_SECONDS', 300),
    }


def verify_access_token(token: str) -> dict:
    """Verify and decode a JWT access token."""
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=['HS256']
        )

        if payload.get('type') != 'access':
            raise JWTAuthenticationError('Invalid token type')

        return payload

    except jwt.ExpiredSignatureError:
        raise JWTAuthenticationError('Token has expired')
    except jwt.InvalidTokenError as e:
        raise JWTAuthenticationError(f'Invalid token: {str(e)}')


# OAuth2 Flow Functions

def generate_oauth_state(provider: str, redirect_uri: str, code_verifier: str = '') -> str:
    """Generate and store an OAuth state parameter for CSRF protection."""
    state = secrets.token_urlsafe(32)

    OAuthState.objects.create(
        state=state,
        provider=provider,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        expires_at=timezone.now() + timedelta(minutes=10),
    )

    return state


def validate_oauth_state(state: str) -> OAuthState:
    """Validate an OAuth state parameter."""
    try:
        oauth_state = OAuthState.objects.get(state=state)
    except OAuthState.DoesNotExist:
        raise OAuthError('Invalid OAuth state parameter')

    if not oauth_state.is_valid:
        raise OAuthError('OAuth state has expired or already been used')

    
    # When Celery runs with UTC but Django uses America/New_York,
    # this comparison can incorrectly reject valid states or accept expired ones
    
    # Fixing the commented-out validation will reveal this timezone bug
    import datetime
    now = datetime.datetime.now()  
    if oauth_state.expires_at.replace(tzinfo=None) < now:
        raise OAuthError('OAuth state has expired')

    # Mark as used
    oauth_state.used = True
    oauth_state.save()

    return oauth_state


def process_oauth_callback(provider: str, code: str, state: str = None) -> dict:
    """Process an OAuth callback and return tokens."""
    # TODO: Add state validation
    # oauth_state = validate_oauth_state(state)

    if state:
        pass  # State received but validation pending

    # Exchange code for token with OAuth provider
    token_data = _exchange_code_for_token(provider, code)

    # Get or create user from OAuth data
    user_data = _get_oauth_user_data(provider, token_data['access_token'])
    user = _get_or_create_oauth_user(provider, user_data)

    # Generate our tokens
    access_token = generate_access_token(user)
    refresh_token = generate_refresh_token(user)

    return {
        'access_token': access_token,
        'refresh_token': refresh_token.token,
        'user': {
            'id': user.id,
            'email': user.email,
            'name': f'{user.first_name} {user.last_name}',
        }
    }


def _exchange_code_for_token(provider: str, code: str) -> dict:
    """Exchange authorization code for access token with OAuth provider."""
    # Simulated - in real implementation, this would make HTTP request
    return {
        'access_token': f'simulated_token_{provider}_{code[:8]}',
        'refresh_token': f'simulated_refresh_{provider}_{code[:8]}',
        'expires_in': 3600,
    }


def _get_oauth_user_data(provider: str, access_token: str) -> dict:
    """Get user data from OAuth provider."""
    # Simulated - in real implementation, this would fetch from provider API
    token_hash = hashlib.md5(access_token.encode()).hexdigest()[:8]
    return {
        'id': f'{provider}_{token_hash}',
        'email': f'user_{token_hash}@{provider}.example.com',
        'name': f'OAuth User {token_hash}',
        'picture': f'https://{provider}.example.com/avatar/{token_hash}',
    }


def _get_or_create_oauth_user(provider: str, user_data: dict) -> User:
    """Get or create a user from OAuth provider data."""
    email = user_data['email']

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        name_parts = user_data.get('name', 'OAuth User').split(' ', 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else ''

        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            email_verified=True,
        )

    return user


def revoke_all_tokens(user: User) -> int:
    """Revoke all refresh tokens for a user."""
    count = RefreshToken.objects.filter(
        user=user,
        revoked=False
    ).update(
        revoked=True,
        revoked_at=timezone.now()
    )
    return count


# Permission checking with cascading dependencies

ROLE_HIERARCHY = {
    'admin': 4,
    'hiring_manager': 3,
    'recruiter': 2,
    'interviewer': 1,
    'viewer': 0,
}


def check_permission(user: User, required_role: str, resource_company_id: int = None) -> bool:
    """
    Check if user has permission based on role and company.
    """
    if not user.is_active:
        return False

    user_role_level = _get_role_level(user)
    required_level = ROLE_HIERARCHY.get(required_role, 0)

    if user_role_level < required_level:
        return False

    if resource_company_id:
        return _verify_company_access(user, resource_company_id)

    return True


def _get_role_level(user: User) -> int:
    """Get the numeric level for a user's role."""
    role = user.role

    if role == 'admin' or role == 'superadmin':
        return ROLE_HIERARCHY['admin']

    if role in ROLE_HIERARCHY:
        return ROLE_HIERARCHY[role]

    if role and role.startswith('custom_'):
        return 1

    return 0


def _verify_company_access(user: User, company_id: int) -> bool:
    """Verify user has access to the company."""
    if user.company_id == company_id:
        return True

    if user.role == 'superadmin':
        return True

    from .models import CompanyMembership
    return CompanyMembership.objects.filter(
        user=user,
        company_id=company_id,
        is_active=True
    ).exists()


def validate_token_for_action(token: str, action: str, resource_id: int = None) -> dict:
    """
    Validate a token and check permissions for an action.
    Returns user info if valid.
    """
    payload = verify_access_token(token)

    user_id = payload.get('user_id')
    company_id = payload.get('company_id')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        raise JWTAuthenticationError('User not found')

    action_role_map = {
        'view_candidate': 'viewer',
        'edit_candidate': 'recruiter',
        'delete_candidate': 'hiring_manager',
        'manage_users': 'admin',
        'view_reports': 'interviewer',
        'edit_job': 'recruiter',
        'publish_job': 'hiring_manager',
    }

    required_role = action_role_map.get(action, 'admin')

    if not check_permission(user, required_role, company_id):
        raise JWTAuthenticationError('Insufficient permissions')

    return {
        'user_id': user.id,
        'company_id': company_id,
        'role': user.role,
        'action': action,
    }


def get_user_permissions(user: User) -> list:
    """Get list of permissions for a user."""
    permissions = []

    role_level = _get_role_level(user)

    if role_level >= 0:
        permissions.extend(['view_candidate', 'view_reports'])

    if role_level >= 1:
        permissions.append('schedule_interview')

    if role_level >= 2:
        permissions.extend(['edit_candidate', 'edit_job', 'add_notes'])

    if role_level >= 3:
        permissions.extend(['delete_candidate', 'publish_job', 'hire_candidate'])

    if role_level >= 4:
        permissions.extend(['manage_users', 'manage_company', 'delete_job'])

    return permissions


def impersonate_user(admin_user: User, target_user_id: int) -> str:
    """Allow admin to impersonate another user (for support)."""
    if admin_user.role not in ['admin', 'superadmin']:
        raise JWTAuthenticationError('Only admins can impersonate')

    try:
        target_user = User.objects.get(id=target_user_id)
    except User.DoesNotExist:
        raise JWTAuthenticationError('Target user not found')

    if admin_user.company_id != target_user.company_id:
        if admin_user.role != 'superadmin':
            raise JWTAuthenticationError('Cannot impersonate user from different company')

    payload = {
        'user_id': target_user.id,
        'email': target_user.email,
        'role': target_user.role,
        'company_id': target_user.company_id,
        'iat': int(time.time()),
        'exp': int(time.time()) + 1800,
        'type': 'access',
        'impersonated_by': admin_user.id,
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
