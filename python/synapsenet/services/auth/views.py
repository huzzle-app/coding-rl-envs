"""
SynapseNet Auth Service Views
Terminal Bench v2 - Authentication & RBAC

Contains bugs:
- G1: JWT propagation loses claims (via shared.clients.base)
- G2: Token refresh race condition
- G3: Service-to-service auth bypass (via shared.clients.base)
- G4: RBAC permission cache stale
- G5: API key rotation window - both old and new rejected
- I7: Mass assignment on user update
- I8: Timing attack on API key comparison
"""
import os
import time
import uuid
import hashlib
import hmac
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


class TokenManager:
    """
    JWT token management.

    BUG G2: Token refresh is not atomic. If two requests try to refresh
    the same token simultaneously, both may succeed, creating two valid
    tokens and invalidating the refresh token prematurely.
    """

    def __init__(self, secret: str = "super_secret_key_that_should_be_rotated"):
        self.secret = secret
        self._refresh_tokens: Dict[str, Dict[str, Any]] = {}
        self._revoked_tokens: set = set()

    def create_token(self, user_id: str, claims: Dict[str, Any]) -> Dict[str, str]:
        """Create access and refresh tokens."""
        access_token = str(uuid.uuid4())
        refresh_token = str(uuid.uuid4())

        self._refresh_tokens[refresh_token] = {
            "user_id": user_id,
            "claims": claims,
            "created_at": time.time(),
            "access_token": access_token,
        }

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": 3600,
        }

    def refresh(self, refresh_token: str) -> Optional[Dict[str, str]]:
        """
        Refresh an access token.

        BUG G2: Not atomic - race condition if called concurrently.

        
          1. services/auth/views.py (this file): Add lock around refresh_tokens access
          2. services/auth/views.py - PermissionCache: When G2 is fixed with proper locking,
             the PermissionCache (BUG G4) must also be invalidated on token refresh, or
             the new token will have stale permissions from the cache
          3. shared/clients/base.py: The service client (BUG G1 - JWT propagation) passes
             the old token to downstream services during the refresh window - fixing G2
             alone will create a brief period where old tokens are rejected but still
             propagated to downstream services
        Fixing only G2 will cause permission desync and intermittent auth failures.
        """
        if refresh_token not in self._refresh_tokens:
            return None

        
        token_data = self._refresh_tokens[refresh_token]
        
        del self._refresh_tokens[refresh_token]

        return self.create_token(token_data["user_id"], token_data["claims"])


class PermissionCache:
    """
    RBAC permission cache.

    BUG G4: Cache is not invalidated when permissions change.
    A user's permissions are cached and used even after role changes.
    """

    def __init__(self, ttl: float = 300.0):
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}

    def get_permissions(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached permissions.

        BUG G4: Does not check if permissions have been updated since caching.
        """
        if user_id in self._cache:
            cached = self._cache[user_id]
            
            if time.time() - cached["cached_at"] < self.ttl:
                return cached["permissions"]
        return None

    def set_permissions(self, user_id: str, permissions: Dict[str, Any]):
        """Cache user permissions."""
        self._cache[user_id] = {
            "permissions": permissions,
            "cached_at": time.time(),
        }

    def invalidate(self, user_id: str):
        """
        Invalidate cached permissions.

        BUG G4: This method exists but is never called after permission changes.
        """
        self._cache.pop(user_id, None)


class APIKeyManager:
    """
    API key management.

    BUG G5: During key rotation, both old and new keys are rejected.
    BUG I8: Key comparison is not constant-time, vulnerable to timing attacks.
    """

    def __init__(self):
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._rotation_window: Dict[str, str] = {}

    def create_key(self, user_id: str) -> str:
        """Create a new API key."""
        key = str(uuid.uuid4())
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        self._keys[key_hash] = {
            "user_id": user_id,
            "created_at": time.time(),
            "is_active": True,
        }
        return key

    def rotate_key(self, old_key: str) -> Optional[str]:
        """
        Rotate an API key.

        BUG G5: Deactivates old key before new key is fully activated.
        During the gap, both keys are invalid.
        """
        old_hash = hashlib.sha256(old_key.encode()).hexdigest()
        if old_hash not in self._keys:
            return None

        
        self._keys[old_hash]["is_active"] = False

        
        new_key = str(uuid.uuid4())
        new_hash = hashlib.sha256(new_key.encode()).hexdigest()
        self._keys[new_hash] = {
            "user_id": self._keys[old_hash]["user_id"],
            "created_at": time.time(),
            "is_active": True,
        }

        return new_key

    def validate_key(self, key: str) -> Optional[str]:
        """
        Validate an API key.

        BUG I8: Uses non-constant-time comparison, vulnerable to timing attacks.
        """
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        
        for stored_hash, data in self._keys.items():
            if stored_hash == key_hash and data["is_active"]:  
                return data["user_id"]

        return None


def update_user(user_data: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user data.

    BUG I7: Mass assignment - accepts all fields including roles, tenant_id,
    and is_admin, allowing privilege escalation.
    """
    
    for key, value in updates.items():
        user_data[key] = value
    return user_data
