"""
Auth service views.
"""
import time
import logging
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from django.conf import settings
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request
import jwt
from passlib.hash import bcrypt

from services.auth.models import User, RefreshToken, APIKey, OAuthState, UserPermission

logger = logging.getLogger(__name__)


def create_access_token(user: User) -> str:
    """Create a JWT access token."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "username": user.username,
        
        # Missing: "roles", "permissions", "tenant_id"
        "iat": now,
        "exp": now + timedelta(seconds=settings.JWT_ACCESS_TOKEN_LIFETIME),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user: User) -> str:
    """Create a refresh token."""
    token = secrets.token_urlsafe(32)
    
    expires_at = datetime.now() + timedelta(seconds=settings.JWT_REFRESH_TOKEN_LIFETIME)

    RefreshToken.objects.create(
        user=user,
        token=token,
        expires_at=expires_at,
    )
    return token


@api_view(["POST"])
def register(request: Request) -> Response:
    """
    Register a new user.

    BUG I7: Mass assignment vulnerability - can set is_admin
    """
    data = request.data

    
    email = data.get("email")
    username = data.get("username")
    password = data.get("password")

    if not all([email, username, password]):
        return Response(
            {"error": "Missing required fields"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email=email).exists():
        return Response(
            {"error": "Email already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    
    is_admin = data.get("is_admin", False)
    is_verified = data.get("is_verified", False)

    password_hash = bcrypt.hash(password)

    user = User.objects.create(
        email=email,
        username=username,
        password_hash=password_hash,
        is_admin=is_admin,  
        is_verified=is_verified,  
        account_type=data.get("account_type", "individual"),
    )

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    return Response({
        "user_id": str(user.id),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.JWT_ACCESS_TOKEN_LIFETIME,
    }, status=status.HTTP_201_CREATED)


@api_view(["POST"])
def login(request: Request) -> Response:
    """
    Login user.

    BUG I8: Timing attack vulnerability - response time varies
    """
    email = request.data.get("email")
    password = request.data.get("password")

    if not email or not password:
        return Response(
            {"error": "Missing credentials"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        
        # Timing difference between "user not found" and "wrong password"
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    
    if not bcrypt.verify(password, user.password_hash):
        
        return Response(
            {"error": "Invalid credentials"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Update last login
    user.last_login = datetime.now()  
    user.save()

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    return Response({
        "user_id": str(user.id),
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": settings.JWT_ACCESS_TOKEN_LIFETIME,
    })


@api_view(["POST"])
def refresh(request: Request) -> Response:
    """
    Refresh access token.

    BUG E2: Race condition on concurrent refresh
    """
    refresh_token = request.data.get("refresh_token")

    if not refresh_token:
        return Response(
            {"error": "Missing refresh token"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        
        # then both tokens become invalid
        token_obj = RefreshToken.objects.get(token=refresh_token, revoked=False)
    except RefreshToken.DoesNotExist:
        return Response(
            {"error": "Invalid refresh token"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    
    if token_obj.expires_at < datetime.now():
        return Response(
            {"error": "Refresh token expired"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Revoke old token
    
    token_obj.revoked = True
    token_obj.save()

    # Create new tokens
    user = token_obj.user
    access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(user)

    return Response({
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "expires_in": settings.JWT_ACCESS_TOKEN_LIFETIME,
    })


@api_view(["POST"])
def logout(request: Request) -> Response:
    """Logout user by revoking refresh token."""
    refresh_token = request.data.get("refresh_token")

    if refresh_token:
        RefreshToken.objects.filter(token=refresh_token).update(revoked=True)

    return Response({"status": "logged_out"})


@api_view(["POST"])
def service_auth(request: Request) -> Response:
    """
    Service-to-service authentication.

    BUG E3: Can be bypassed with empty header
    """
    
    internal_header = request.headers.get("X-Internal-Service")
    if internal_header is not None:  
        # Bypass normal auth for internal services
        service_name = request.data.get("service_name", "unknown")
        token = jwt.encode(
            {
                "service": service_name,
                "type": "service",
                "iat": datetime.utcnow(),
                "exp": datetime.utcnow() + timedelta(hours=1),
            },
            settings.JWT_SECRET,
            algorithm=settings.JWT_ALGORITHM,
        )
        return Response({"token": token})

    return Response(
        {"error": "Unauthorized"},
        status=status.HTTP_401_UNAUTHORIZED,
    )


@api_view(["GET"])
def check_permission(request: Request, user_id: str) -> Response:
    """
    Check if user has permission.

    BUG E4: Result cached without invalidation
    """
    resource = request.query_params.get("resource")
    action = request.query_params.get("action")

    if not resource or not action:
        return Response(
            {"error": "Missing resource or action"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    
    # when permissions change
    has_permission = UserPermission.objects.filter(
        user_id=user_id,
        permission__resource=resource,
        permission__action=action,
    ).exists()

    return Response({
        "user_id": user_id,
        "resource": resource,
        "action": action,
        "allowed": has_permission,
    })


@api_view(["POST"])
def rotate_api_key(request: Request, user_id: str) -> Response:
    """
    Rotate user's API key.

    BUG E5: No grace period - old key immediately invalid
    """
    old_key = request.data.get("old_key")

    if not old_key:
        return Response(
            {"error": "Missing old key"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Find existing key
        old_key_hash = bcrypt.hash(old_key)
        api_key = APIKey.objects.get(user_id=user_id, is_active=True)

        
        # No grace period for propagation
        api_key.is_active = False
        api_key.save()

        # Create new key
        new_key = secrets.token_urlsafe(32)
        new_key_hash = bcrypt.hash(new_key)

        APIKey.objects.create(
            user_id=user_id,
            key_hash=new_key_hash,
            name=api_key.name,
            is_active=True,
        )

        
        # Old key already invalid - window where no key works

        return Response({
            "new_key": new_key,
            "message": "API key rotated successfully",
        })

    except APIKey.DoesNotExist:
        return Response(
            {"error": "No active API key found"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["GET"])
def health(request: Request) -> Response:
    """Health check endpoint."""
    return Response({"status": "healthy", "service": "auth"})
