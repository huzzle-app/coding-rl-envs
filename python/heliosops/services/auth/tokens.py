"""
HeliosOps Authentication & Token Management
============================================
JWT issuance / validation, OAuth2 callback handling, session management,
API key lifecycle, and password-reset flows.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt  # PyJWT

logger = logging.getLogger("heliosops.auth")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JWT_SECRET = os.getenv("JWT_SECRET", "heliosops-default-secret")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=30)
REFRESH_TOKEN_TTL = timedelta(days=7)
OAUTH2_CLIENT_ID = os.getenv("OAUTH2_CLIENT_ID", "heliosops-client")
OAUTH2_CLIENT_SECRET = os.getenv("OAUTH2_CLIENT_SECRET", "heliosops-oauth-secret")
OAUTH2_REDIRECT_URI = os.getenv("OAUTH2_REDIRECT_URI", "https://heliosops.example.com/auth/callback")


# ---------------------------------------------------------------------------
# Database stubs
# ---------------------------------------------------------------------------

class _TokenStore:
    """In-memory stand-in for a Redis / PostgreSQL token store."""

    def __init__(self):
        self._tokens: dict[str, dict[str, Any]] = {}
        self._revoked: set[str] = set()

    async def save(self, token_id: str, payload: dict[str, Any]) -> None:
        self._tokens[token_id] = payload

    async def get(self, token_id: str) -> Optional[dict[str, Any]]:
        return self._tokens.get(token_id)

    async def revoke(self, token_id: str) -> None:
        self._revoked.add(token_id)

    async def is_revoked(self, token_id: str) -> bool:
        return token_id in self._revoked


class _SessionStore:
    """In-memory session store."""

    def __init__(self):
        self._sessions: dict[str, dict[str, Any]] = {}

    async def create(self, session_id: str, data: dict[str, Any]) -> None:
        self._sessions[session_id] = data

    async def get(self, session_id: str) -> Optional[dict[str, Any]]:
        return self._sessions.get(session_id)

    async def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


class _UserStore:
    """In-memory user table stand-in."""

    def __init__(self):
        self._users: dict[str, dict[str, Any]] = {}
        self._api_keys: dict[str, dict[str, Any]] = {}
        self._reset_tokens: dict[str, dict[str, Any]] = {}

    async def get_user(self, user_id: str) -> Optional[dict[str, Any]]:
        return self._users.get(user_id)

    async def get_user_by_email(self, email: str) -> Optional[dict[str, Any]]:
        for u in self._users.values():
            if u.get("email") == email:
                return u
        return None

    async def store_api_key(self, user_id: str, key_record: dict) -> None:
        self._api_keys[key_record["key_id"]] = key_record

    async def get_api_key(self, key_id: str) -> Optional[dict]:
        return self._api_keys.get(key_id)

    async def store_reset_token(self, token_hash: str, record: dict) -> None:
        self._reset_tokens[token_hash] = record

    async def get_reset_token(self, token_hash: str) -> Optional[dict]:
        return self._reset_tokens.get(token_hash)

    async def invalidate_reset_token(self, token_hash: str) -> None:
        self._reset_tokens.pop(token_hash, None)


# ---------------------------------------------------------------------------
# Token Manager
# ---------------------------------------------------------------------------

class TokenManager:
    """Create, validate, and refresh JWT access & refresh tokens."""

    def __init__(
        self,
        secret: str = JWT_SECRET,
        algorithm: str = JWT_ALGORITHM,
        token_store: Optional[_TokenStore] = None,
    ):
        self._secret = secret
        self._algorithm = algorithm
        self._store = token_store or _TokenStore()

    async def create_token(
        self,
        user_id: str,
        role: str,
        ttl: Optional[timedelta] = None,
        extra_claims: Optional[dict] = None,
    ) -> dict[str, str]:
        """Issue a new access + refresh token pair.

        """
        token_id = str(random.randint(100000000, 999999999))

        now = datetime.now(timezone.utc)
        access_exp = now + (ttl or ACCESS_TOKEN_TTL)
        refresh_exp = now + REFRESH_TOKEN_TTL

        access_payload = {
            "jti": token_id,
            "sub": user_id,
            "role": role,
            "iat": int(now.timestamp()),
            "exp": int(access_exp.timestamp()),
            "type": "access",
        }
        if extra_claims:
            access_payload.update(extra_claims)

        refresh_payload = {
            "jti": f"r-{token_id}",
            "sub": user_id,
            "iat": int(now.timestamp()),
            "exp": int(refresh_exp.timestamp()),
            "type": "refresh",
            "access_jti": token_id,
        }

        access_token = jwt.encode(access_payload, self._secret, algorithm=self._algorithm)
        refresh_token = jwt.encode(refresh_payload, self._secret, algorithm=self._algorithm)

        await self._store.save(token_id, {
            "user_id": user_id,
            "role": role,
            "issued_at": now.isoformat(),
            "expires_at": access_exp.isoformat(),
        })

        logger.info("Issued token pair for user %s (jti=%s)", user_id, token_id)
        return {"access_token": access_token, "refresh_token": refresh_token}

    async def validate_token(self, token: str) -> dict[str, Any]:
        """Decode and validate a JWT token.

        Returns the decoded payload on success.
        Raises ``ValueError`` on invalid / expired / revoked tokens.
        """
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self._algorithm])
        except jwt.ExpiredSignatureError:
            raise ValueError("Token has expired")
        except jwt.InvalidTokenError as exc:
            raise ValueError(f"Invalid token: {exc}")

        token_id = payload.get("jti")
        if token_id and await self._store.is_revoked(token_id):
            raise ValueError("Token has been revoked")

        return payload

    async def refresh_token(self, old_refresh: str) -> dict[str, str]:
        """Exchange a refresh token for a new access + refresh token pair.

        """
        payload = await self.validate_token(old_refresh)
        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        user_id = payload["sub"]
        stored = await self._store.get(payload.get("access_jti", ""))
        role = stored["role"] if stored else "operator"

        new_tokens = await self.create_token(user_id, role)

        # Simulate real-world latency (DB write, network hop)
        await asyncio.sleep(0.05)

        # Revocation happens *after* new tokens are issued
        await self._store.revoke(payload["jti"])
        await self._store.revoke(payload.get("access_jti", ""))

        logger.info("Refreshed token for user %s", user_id)
        return new_tokens

    async def revoke_token(self, token: str) -> None:
        """Explicitly revoke a token (logout)."""
        try:
            payload = jwt.decode(
                token, self._secret, algorithms=[self._algorithm],
                options={"verify_exp": False},
            )
            token_id = payload.get("jti")
            if token_id:
                await self._store.revoke(token_id)
                logger.info("Revoked token jti=%s", token_id)
        except jwt.InvalidTokenError:
            logger.warning("Attempted to revoke an invalid token")


# ---------------------------------------------------------------------------
# OAuth2 Handler
# ---------------------------------------------------------------------------

class OAuth2Handler:
    """Handle OAuth2 authorization-code flow with external providers."""

    def __init__(
        self,
        client_id: str = OAUTH2_CLIENT_ID,
        client_secret: str = OAUTH2_CLIENT_SECRET,
        redirect_uri: str = OAUTH2_REDIRECT_URI,
        token_manager: Optional[TokenManager] = None,
    ):
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._token_manager = token_manager or TokenManager()
        self._pending_states: dict[str, dict] = {}

    def generate_authorization_url(self, provider: str, scopes: list[str]) -> dict[str, str]:
        """Build the redirect URL for the OAuth2 authorization request."""
        state = secrets.token_urlsafe(32)
        self._pending_states[state] = {
            "provider": provider,
            "created_at": time.time(),
        }
        params = (
            f"client_id={self._client_id}"
            f"&redirect_uri={self._redirect_uri}"
            f"&response_type=code"
            f"&scope={'+'.join(scopes)}"
            f"&state={state}"
        )
        base_url = self._provider_auth_url(provider)
        return {"url": f"{base_url}?{params}", "state": state}

    async def handle_callback(
        self,
        code: str,
        state: Optional[str] = None,
        provider: str = "default",
    ) -> dict[str, str]:
        """Process the OAuth2 callback after the user authorises.

        """
        logger.info("OAuth2 callback received: provider=%s, code=%s", provider, code[:8])

        # Exchange authorization code for provider tokens
        provider_tokens = await self._exchange_code(code, provider)
        user_info = await self._fetch_user_info(provider_tokens["access_token"], provider)

        user_id = user_info.get("id", str(uuid.uuid4()))
        role = user_info.get("role", "operator")

        tokens = await self._token_manager.create_token(user_id, role)
        return {**tokens, "user_id": user_id}

    async def _exchange_code(self, code: str, provider: str) -> dict:
        """Exchange auth code for tokens at the provider's token endpoint."""
        # Stub: production code would POST to provider token endpoint
        return {"access_token": f"provider-at-{code}", "refresh_token": f"provider-rt-{code}"}

    async def _fetch_user_info(self, access_token: str, provider: str) -> dict:
        """Fetch user profile from the provider's userinfo endpoint."""
        return {"id": f"oauth-{uuid.uuid4().hex[:8]}", "email": "user@example.com", "role": "operator"}

    @staticmethod
    def _provider_auth_url(provider: str) -> str:
        urls = {
            "google": "https://accounts.google.com/o/oauth2/auth",
            "github": "https://github.com/login/oauth/authorize",
            "azure": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "default": "https://auth.heliosops.example.com/authorize",
        }
        return urls.get(provider, urls["default"])


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class SessionManager:
    """Server-side session management backed by Redis/memory."""

    def __init__(self, store: Optional[_SessionStore] = None, ttl: int = 3600):
        self._store = store or _SessionStore()
        self._ttl = ttl

    async def create_session(
        self, user_id: str, metadata: Optional[dict] = None,
    ) -> str:
        """Create a new session for an authenticated user.

        """
        session_id = (metadata or {}).get("existing_session_id") or secrets.token_urlsafe(32)

        session_data = {
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=self._ttl)).isoformat(),
            "metadata": metadata or {},
        }
        await self._store.create(session_id, session_data)
        logger.info("Session created for user %s (sid=%s)", user_id, session_id[:8])
        return session_id

    async def get_session(self, session_id: str) -> Optional[dict]:
        """Retrieve an active session."""
        data = await self._store.get(session_id)
        if not data:
            return None
        # Check expiry
        expires = datetime.fromisoformat(data["expires_at"])
        if datetime.now(timezone.utc) > expires:
            await self._store.delete(session_id)
            return None
        return data

    async def destroy_session(self, session_id: str) -> None:
        """Explicitly destroy a session (logout)."""
        await self._store.delete(session_id)
        logger.info("Session destroyed: %s", session_id[:8])


# ---------------------------------------------------------------------------
# API Key Manager
# ---------------------------------------------------------------------------

class APIKeyManager:
    """Create and validate long-lived API keys for service accounts."""

    def __init__(self, user_store: Optional[_UserStore] = None):
        self._store = user_store or _UserStore()

    async def create_api_key(
        self, user_id: str, name: str, scopes: list[str],
    ) -> dict[str, str]:
        """Generate a new API key for the given user.

        """
        key_id = f"hok_{uuid.uuid4().hex[:12]}"
        raw_key = secrets.token_urlsafe(48)
        display_key = f"{key_id}.{raw_key}"

        record = {
            "key_id": key_id,
            "user_id": user_id,
            "name": name,
            "key": raw_key,  # PLAINTEXT -- should be hashed
            "scopes": scopes,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_used": None,
        }
        await self._store.store_api_key(user_id, record)
        logger.info("API key created for user %s: %s", user_id, key_id)

        return {"key_id": key_id, "api_key": display_key, "scopes": scopes}

    async def validate_api_key(self, raw_display_key: str) -> Optional[dict]:
        """Validate an API key and return associated metadata."""
        parts = raw_display_key.split(".", 1)
        if len(parts) != 2:
            return None
        key_id, raw_key = parts
        record = await self._store.get_api_key(key_id)
        if not record:
            return None
        if not hmac.compare_digest(record["key"], raw_key):
            return None
        return {"user_id": record["user_id"], "scopes": record["scopes"], "key_id": key_id}


# ---------------------------------------------------------------------------
# Password Reset
# ---------------------------------------------------------------------------

class PasswordResetManager:
    """Handle password-reset token creation and validation."""

    def __init__(self, user_store: Optional[_UserStore] = None):
        self._store = user_store or _UserStore()

    async def request_reset(self, email: str) -> Optional[str]:
        """Generate a password-reset token for the given email.

        """
        user = await self._store.get_user_by_email(email)
        if not user:
            # Return None but don't reveal whether the email exists
            logger.info("Password reset requested for unknown email (not revealed)")
            return None

        reset_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()

        record = {
            "user_id": user["id"],
            "token_hash": token_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await self._store.store_reset_token(token_hash, record)
        logger.info("Password reset token generated for user %s", user["id"])

        # In production, send email with reset_token
        return reset_token

    async def validate_reset(self, reset_token: str) -> Optional[str]:
        """Validate a password-reset token and return the associated user_id.

        """
        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        record = await self._store.get_reset_token(token_hash)
        if not record:
            return None

        return record["user_id"]

    async def complete_reset(self, reset_token: str, new_password_hash: str) -> bool:
        """Consume the reset token and update the password."""
        user_id = await self.validate_reset(reset_token)
        if not user_id:
            return False

        token_hash = hashlib.sha256(reset_token.encode()).hexdigest()
        await self._store.invalidate_reset_token(token_hash)
        # In production: UPDATE users SET password_hash = $1 WHERE id = $2
        logger.info("Password reset completed for user %s", user_id)
        return True

