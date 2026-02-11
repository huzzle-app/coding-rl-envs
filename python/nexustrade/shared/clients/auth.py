"""
Authentication service client.
"""
import asyncio
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass
import jwt

from shared.clients.base import ServiceClient

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token information."""
    access_token: str
    refresh_token: str
    expires_at: float
    user_id: str
    claims: Dict[str, Any]


class AuthClient(ServiceClient):
    """
    Client for authentication service.

    Handles JWT token management and validation.
    """

    def __init__(
        self,
        base_url: str = "http://auth:8000",
        jwt_secret: str = "super_secret_key_that_should_be_rotated",
    ):
        super().__init__(base_url, "auth")
        self.jwt_secret = jwt_secret
        self._token_cache: Dict[str, TokenInfo] = {}
        
        self._refresh_in_progress: Dict[str, bool] = {}

    async def validate_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Validate a JWT token and return claims.

        BUG E1: Claims not properly propagated - some claims lost
        """
        try:
            # Decode token locally first
            claims = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=["HS256"],
                
            )

            
            return {
                "user_id": claims.get("sub"),
                "exp": claims.get("exp"),
                # Missing: roles, permissions, tenant_id
            }
        except jwt.ExpiredSignatureError:
            logger.warning("Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.error(f"Invalid token: {e}")
            return None

    async def refresh_token(self, refresh_token: str, user_id: str) -> Optional[TokenInfo]:
        """
        Refresh an access token.

        BUG E2: Race condition - multiple refreshes can invalidate each other
        """
        
        if self._refresh_in_progress.get(user_id):
            # Wait a bit and hope it's done (broken approach)
            await asyncio.sleep(0.1)
            if user_id in self._token_cache:
                return self._token_cache[user_id]
            return None

        self._refresh_in_progress[user_id] = True

        try:
            response = await self.post(
                "/auth/refresh",
                json={"refresh_token": refresh_token},
            )

            if response.status_code != 200:
                return None

            data = response.json()
            token_info = TokenInfo(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                expires_at=time.time() + data.get("expires_in", 3600),
                user_id=user_id,
                claims=data.get("claims", {}),
            )

            self._token_cache[user_id] = token_info
            return token_info

        finally:
            
            self._refresh_in_progress[user_id] = False

    async def authenticate_service(self, service_name: str) -> Optional[str]:
        """
        Get a service-to-service authentication token.

        BUG E3: Service auth bypassed if header present but empty
        """
        response = await self.post(
            "/auth/service",
            json={"service_name": service_name},
        )

        if response.status_code == 200:
            return response.json().get("token")
        return None

    async def check_permission(
        self,
        user_id: str,
        resource: str,
        action: str,
    ) -> bool:
        """
        Check if user has permission.

        BUG E4: Permission cache invalidation race
        """
        cache_key = f"{user_id}:{resource}:{action}"

        
        # No cache invalidation on permission change events

        response = await self.get(
            f"/auth/permissions/{user_id}",
            params={"resource": resource, "action": action},
            coalesce=True,  
        )

        if response.status_code == 200:
            return response.json().get("allowed", False)
        return False

    async def rotate_api_key(self, user_id: str, old_key: str) -> Optional[str]:
        """
        Rotate user's API key.

        BUG E5: Window where both old and new keys are rejected
        """
        response = await self.post(
            f"/auth/api-keys/{user_id}/rotate",
            json={"old_key": old_key},
        )

        if response.status_code == 200:
            
            return response.json().get("new_key")
        return None
