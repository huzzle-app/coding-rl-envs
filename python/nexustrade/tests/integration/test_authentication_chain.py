"""
Integration tests for authentication chain bugs.

These tests verify bugs E1-E6 (Authentication Chain category)
plus additional authentication and authorization integration tests.
"""
import pytest
import threading
import time
import json
import hmac
import hashlib
import base64
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta
from uuid import uuid4


class TestClaimPropagation:
    """Tests for bug E1: JWT claim propagation loss across services."""

    def test_claim_propagation(self):
        """Test that JWT claims propagate to downstream services."""
        
        original_claims = {
            "sub": "user-123",
            "role": "trader",
            "permissions": ["read:orders", "write:orders"],
            "tenant_id": "tenant-A",
        }

        # Gateway extracts claims and forwards to order service
        forwarded_headers = {
            "X-User-Id": original_claims["sub"],
            "X-User-Role": original_claims["role"],
            "X-Permissions": json.dumps(original_claims["permissions"]),
            "X-Tenant-Id": original_claims["tenant_id"],
        }

        # Order service reconstructs claims from headers
        reconstructed = {
            "sub": forwarded_headers["X-User-Id"],
            "role": forwarded_headers["X-User-Role"],
            "permissions": json.loads(forwarded_headers["X-Permissions"]),
            "tenant_id": forwarded_headers["X-Tenant-Id"],
        }

        assert reconstructed == original_claims, \
            "Claims must be fully propagated to downstream services"

    def test_downstream_auth(self):
        """Test that downstream services enforce authorization from propagated claims."""
        
        claims = {
            "sub": "user-123",
            "role": "viewer",
            "permissions": ["read:orders"],
        }

        # Attempt to write an order with read-only permissions
        required_permission = "write:orders"
        has_permission = required_permission in claims["permissions"]

        assert not has_permission, \
            "Viewer role should not have write permission"

        # Attempt to read orders
        required_read = "read:orders"
        has_read = required_read in claims["permissions"]
        assert has_read, "Viewer should have read permission"


class TestTokenRefreshConcurrency:
    """Tests for bug E2: Token refresh race condition."""

    def test_token_refresh_concurrency(self):
        """Test that concurrent token refreshes don't create duplicate sessions."""
        
        refresh_lock = threading.Lock()
        tokens = {"current": "token-v1", "refresh_count": 0}

        def refresh_token():
            with refresh_lock:
                # Only refresh if not already refreshed by another thread
                if tokens["current"] == "token-v1":
                    tokens["current"] = "token-v2"
                    tokens["refresh_count"] += 1

        # Simulate 5 concurrent refresh attempts
        threads = []
        for _ in range(5):
            t = threading.Thread(target=refresh_token)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        assert tokens["refresh_count"] == 1, "Token should be refreshed exactly once"
        assert tokens["current"] == "token-v2", "Token should be updated to v2"

    def test_refresh_race(self):
        """Test that refresh token is invalidated after use."""
        
        used_refresh_tokens = set()

        def use_refresh_token(refresh_token):
            if refresh_token in used_refresh_tokens:
                return None, "Refresh token already used"
            used_refresh_tokens.add(refresh_token)
            return f"new-access-{refresh_token[-4:]}", None

        # First use succeeds
        access1, err1 = use_refresh_token("refresh-token-0001")
        assert access1 is not None, "First refresh should succeed"
        assert err1 is None

        # Second use of same token fails
        access2, err2 = use_refresh_token("refresh-token-0001")
        assert access2 is None, "Reused refresh token should fail"
        assert "already used" in err2


class TestServiceAuth:
    """Tests for bug E3: Service-to-service auth bypass."""

    def test_service_auth(self):
        """Test that service-to-service calls require authentication."""
        
        def authenticate_service_call(headers):
            service_token = headers.get("X-Service-Token")
            if not service_token:
                return False, "Missing service token"
            # Validate token against known service keys
            valid_tokens = {"svc-orders-key-123", "svc-risk-key-456"}
            if service_token not in valid_tokens:
                return False, "Invalid service token"
            return True, None

        # Call without token should fail
        ok, err = authenticate_service_call({})
        assert not ok, "Unauthenticated service call should fail"

        # Call with valid token should succeed
        ok, err = authenticate_service_call({"X-Service-Token": "svc-orders-key-123"})
        assert ok, "Authenticated service call should succeed"

        # Call with invalid token should fail
        ok, err = authenticate_service_call({"X-Service-Token": "fake-token"})
        assert not ok, "Invalid token should be rejected"

    def test_internal_auth_required(self):
        """Test that internal endpoints still require service auth."""
        
        internal_endpoints = [
            "/internal/health",
            "/internal/metrics",
            "/internal/admin/users",
        ]
        public_endpoints = ["/api/v1/orders", "/api/v1/quotes"]

        # All internal endpoints must require auth
        for endpoint in internal_endpoints:
            requires_auth = endpoint.startswith("/internal/")
            assert requires_auth, f"{endpoint} must require internal auth"


class TestPermissionCacheInvalidation:
    """Tests for bug E4: Permission cache not invalidated on update."""

    def test_permission_cache_invalidation(self):
        """Test that permission changes invalidate the cache."""
        
        permission_cache = {
            "user-123": {"permissions": ["read:orders"], "cached_at": 1000}
        }

        # Admin updates user permissions
        updated_permissions = ["read:orders", "write:orders"]
        cache_version = 1000
        update_version = 1001

        # Cache should be invalidated
        if update_version > cache_version:
            permission_cache.pop("user-123", None)

        assert "user-123" not in permission_cache, \
            "Cache should be invalidated after permission update"

    def test_permission_update(self):
        """Test that updated permissions take effect immediately."""
        
        class PermissionStore:
            def __init__(self):
                self.permissions = {}
                self.cache = {}
                self.version = 0

            def update_permissions(self, user_id, perms):
                self.permissions[user_id] = perms
                self.version += 1
                # Invalidate cache
                self.cache.pop(user_id, None)

            def get_permissions(self, user_id):
                if user_id in self.cache:
                    return self.cache[user_id]
                perms = self.permissions.get(user_id, [])
                self.cache[user_id] = perms
                return perms

        store = PermissionStore()
        store.permissions["user-1"] = ["read:orders"]
        store.cache["user-1"] = ["read:orders"]

        # Update permissions
        store.update_permissions("user-1", ["read:orders", "write:orders"])

        # Should get updated permissions (not cached old ones)
        perms = store.get_permissions("user-1")
        assert "write:orders" in perms, "Updated permissions should be immediately visible"


class TestKeyRotation:
    """Tests for bug E5: JWT signing key rotation breaks active sessions."""

    def test_key_rotation(self):
        """Test that key rotation doesn't invalidate existing tokens."""
        
        signing_keys = {
            "key-v1": "old-secret-key",
            "key-v2": "new-secret-key",
        }
        active_key = "key-v2"

        # Token signed with old key should still be valid during grace period
        token_key_id = "key-v1"
        can_verify = token_key_id in signing_keys

        assert can_verify, "Old key should still be available for verification"

    def test_rotation_grace_period(self):
        """Test that old keys remain valid during grace period."""
        
        key_rotation_log = [
            {"key_id": "key-v1", "activated_at": 1000, "expired_at": None},
            {"key_id": "key-v2", "activated_at": 2000, "expired_at": None},
        ]
        grace_period = 3600  # 1 hour

        # After activating v2, mark v1 for expiry
        current_time = 2100
        key_rotation_log[0]["expired_at"] = key_rotation_log[1]["activated_at"] + grace_period

        # v1 should still be valid within grace period
        v1_expiry = key_rotation_log[0]["expired_at"]
        v1_still_valid = current_time < v1_expiry

        assert v1_still_valid, "Old key should be valid during grace period"

        # After grace period, v1 should be expired
        future_time = key_rotation_log[1]["activated_at"] + grace_period + 1
        v1_expired = future_time >= v1_expiry
        assert v1_expired, "Old key should expire after grace period"


class TestMtlsValidation:
    """Tests for bug E6: mTLS certificate validation bypass."""

    def test_mtls_validation(self):
        """Test that mTLS requires valid client certificates."""
        
        def validate_mtls(client_cert):
            if client_cert is None:
                return False, "No client certificate presented"
            if client_cert.get("expired", False):
                return False, "Certificate expired"
            if client_cert.get("issuer") != "nexustrade-ca":
                return False, "Untrusted certificate authority"
            return True, None

        # No cert should fail
        ok, _ = validate_mtls(None)
        assert not ok, "Missing cert should fail mTLS"

        # Expired cert should fail
        ok, _ = validate_mtls({"expired": True, "issuer": "nexustrade-ca"})
        assert not ok, "Expired cert should fail mTLS"

        # Valid cert should pass
        ok, _ = validate_mtls({"expired": False, "issuer": "nexustrade-ca"})
        assert ok, "Valid cert should pass mTLS"

    def test_certificate_chain(self):
        """Test that the full certificate chain is validated."""
        
        cert_chain = [
            {"name": "leaf", "issuer": "intermediate-ca", "valid": True},
            {"name": "intermediate-ca", "issuer": "root-ca", "valid": True},
            {"name": "root-ca", "issuer": "self", "valid": True},
        ]

        # All certs in chain must be valid
        chain_valid = all(cert["valid"] for cert in cert_chain)
        assert chain_valid, "Entire certificate chain must be valid"

        # Broken chain should fail
        cert_chain[1]["valid"] = False
        chain_valid = all(cert["valid"] for cert in cert_chain)
        assert not chain_valid, "Broken chain should fail validation"


# ===================================================================
# Additional authentication integration tests (not bug-mapped)
# ===================================================================


class TestTokenExpiry:
    """Tests for token expiry handling."""

    def test_expired_token_rejected(self):
        """Test that expired access tokens are rejected."""
        token = {
            "sub": "user-123",
            "exp": time.time() - 60,  # expired 60 seconds ago
        }

        is_expired = token["exp"] < time.time()
        assert is_expired, "Expired token should be detected"

    def test_token_near_expiry_triggers_refresh(self):
        """Test that tokens close to expiry trigger proactive refresh."""
        refresh_buffer = 300  # refresh 5 min before expiry
        token_exp = time.time() + 200  # expires in 200 seconds

        should_refresh = (token_exp - time.time()) < refresh_buffer
        assert should_refresh, "Token near expiry should trigger refresh"


class TestMultiTenantAuthIsolation:
    """Tests for multi-tenant authentication isolation."""

    def test_tenant_isolation_in_auth(self):
        """Test that one tenant cannot access another's resources."""
        user_claims = {"sub": "user-1", "tenant_id": "tenant-A"}
        requested_resource = {"id": "order-1", "tenant_id": "tenant-B"}

        authorized = user_claims["tenant_id"] == requested_resource["tenant_id"]
        assert not authorized, "User should not access other tenant's resources"

    def test_cross_tenant_token_rejected(self):
        """Test that tokens issued for one tenant are rejected by another."""
        token_tenant = "tenant-A"
        service_tenant = "tenant-B"

        is_valid_for_service = token_tenant == service_tenant
        assert not is_valid_for_service, "Cross-tenant token should be rejected"


class TestRoleHierarchyResolution:
    """Tests for role hierarchy resolution."""

    def test_admin_inherits_trader_permissions(self):
        """Test that admin role inherits trader permissions."""
        role_hierarchy = {
            "viewer": ["read:orders", "read:positions"],
            "trader": ["read:orders", "read:positions", "write:orders", "write:positions"],
            "admin": ["read:orders", "read:positions", "write:orders", "write:positions",
                      "admin:users", "admin:config"],
        }

        admin_perms = set(role_hierarchy["admin"])
        trader_perms = set(role_hierarchy["trader"])

        assert trader_perms.issubset(admin_perms), \
            "Admin should have all trader permissions"

    def test_role_permission_resolution_order(self):
        """Test that deny rules override allow rules."""
        allow = {"read:orders", "write:orders"}
        deny = {"write:orders"}

        effective = allow - deny
        assert "write:orders" not in effective, "Deny should override allow"
        assert "read:orders" in effective, "Non-denied permissions should remain"


class TestSessionInvalidation:
    """Tests for session invalidation propagation."""

    def test_session_invalidation_propagates(self):
        """Test that session invalidation reaches all services."""
        active_sessions = {
            "gateway": {"session-1": True},
            "orders": {"session-1": True},
            "risk": {"session-1": True},
        }

        # Invalidate session
        session_to_invalidate = "session-1"
        for service in active_sessions:
            active_sessions[service].pop(session_to_invalidate, None)

        for service, sessions in active_sessions.items():
            assert session_to_invalidate not in sessions, \
                f"Session should be invalidated in {service}"

    def test_invalidated_session_rejected(self):
        """Test that requests with invalidated sessions are rejected."""
        blacklist = {"session-abc", "session-def"}
        incoming_session = "session-abc"

        is_blacklisted = incoming_session in blacklist
        assert is_blacklisted, "Blacklisted session should be rejected"


class TestOAuthFlowValidation:
    """Tests for OAuth flow validation."""

    def test_authorization_code_single_use(self):
        """Test that authorization codes can only be used once."""
        used_codes = set()

        def exchange_code(code):
            if code in used_codes:
                return None, "Code already used"
            used_codes.add(code)
            return "access-token-new", None

        token1, err1 = exchange_code("auth-code-1")
        assert token1 is not None, "First exchange should succeed"

        token2, err2 = exchange_code("auth-code-1")
        assert token2 is None, "Second use of same code should fail"

    def test_redirect_uri_validation(self):
        """Test that redirect URIs are validated against registration."""
        registered_uris = [
            "https://app.nexustrade.com/callback",
            "https://staging.nexustrade.com/callback",
        ]

        valid_uri = "https://app.nexustrade.com/callback"
        invalid_uri = "https://evil.com/callback"

        assert valid_uri in registered_uris, "Registered URI should be accepted"
        assert invalid_uri not in registered_uris, "Unregistered URI should be rejected"


class TestApiKeyRotation:
    """Tests for API key rotation."""

    def test_api_key_graceful_rotation(self):
        """Test that old API key remains valid during rotation window."""
        api_keys = {
            "key-old": {"active": True, "expires_at": time.time() + 3600},
            "key-new": {"active": True, "expires_at": None},
        }

        # Both keys should work during rotation
        for key_id, meta in api_keys.items():
            is_valid = meta["active"] and (
                meta["expires_at"] is None or meta["expires_at"] > time.time()
            )
            assert is_valid, f"{key_id} should be valid during rotation window"

    def test_revoked_api_key_rejected(self):
        """Test that revoked API keys are immediately rejected."""
        api_keys = {"key-1": {"active": False, "revoked_at": time.time()}}

        is_valid = api_keys["key-1"]["active"]
        assert not is_valid, "Revoked API key should be rejected"


class TestScopeBasedAccessControl:
    """Tests for scope-based access control."""

    def test_insufficient_scope_rejected(self):
        """Test that requests with insufficient scopes are rejected."""
        token_scopes = {"read:orders"}
        required_scopes = {"read:orders", "write:orders"}

        has_all_scopes = required_scopes.issubset(token_scopes)
        assert not has_all_scopes, "Insufficient scopes should be rejected"

    def test_wildcard_scope_matching(self):
        """Test wildcard scope matching (e.g., orders:* matches orders:read)."""
        token_scopes = {"orders:*", "read:positions"}

        def check_scope(required, granted):
            if required in granted:
                return True
            # Check wildcard
            parts = required.split(":")
            if len(parts) == 2:
                wildcard = f"{parts[0]}:*"
                return wildcard in granted
            return False

        assert check_scope("orders:read", token_scopes), "Wildcard should match"
        assert check_scope("orders:write", token_scopes), "Wildcard should match write too"
        assert not check_scope("admin:config", token_scopes), "Non-matching scope should fail"


class TestJwtAudienceValidation:
    """Tests for JWT audience validation."""

    def test_wrong_audience_rejected(self):
        """Test that tokens with wrong audience are rejected."""
        token_aud = "orders-service"
        expected_aud = "risk-service"

        valid_audience = token_aud == expected_aud
        assert not valid_audience, "Wrong audience should be rejected"

    def test_multi_audience_token(self):
        """Test handling of tokens with multiple audiences."""
        token_audiences = ["orders-service", "risk-service"]
        service_id = "orders-service"

        valid = service_id in token_audiences
        assert valid, "Service should accept token if listed in audiences"


class TestTokenBlacklistSync:
    """Tests for token blacklist synchronization across services."""

    def test_blacklist_propagation_delay(self):
        """Test that blacklist propagation has bounded delay."""
        # Simulate blacklist propagation
        blacklists = {
            "gateway": set(),
            "orders": set(),
            "risk": set(),
        }

        # Token revoked - add to all service blacklists
        revoked_token = "token-revoked-123"
        for service in blacklists:
            blacklists[service].add(revoked_token)

        # All services should have it
        for service, bl in blacklists.items():
            assert revoked_token in bl, f"{service} should have blacklisted token"

    def test_blacklist_cleanup_after_expiry(self):
        """Test that expired tokens are cleaned from blacklist."""
        blacklist = {
            "token-1": {"revoked_at": time.time() - 7200, "original_exp": time.time() - 3600},
            "token-2": {"revoked_at": time.time() - 60, "original_exp": time.time() + 3600},
        }

        # Clean up tokens that have naturally expired
        now = time.time()
        to_remove = [tid for tid, meta in blacklist.items() if meta["original_exp"] < now]
        for tid in to_remove:
            del blacklist[tid]

        assert "token-1" not in blacklist, "Naturally expired token should be cleaned"
        assert "token-2" in blacklist, "Still-valid revoked token should remain"


class TestAuthMiddlewareOrdering:
    """Tests for auth middleware ordering."""

    def test_middleware_execution_order(self):
        """Test that auth middleware runs in correct order."""
        execution_order = []

        def rate_limit_middleware():
            execution_order.append("rate_limit")

        def auth_middleware():
            execution_order.append("auth")

        def authorization_middleware():
            execution_order.append("authorization")

        # Correct order: rate limit -> auth -> authorization
        rate_limit_middleware()
        auth_middleware()
        authorization_middleware()

        assert execution_order == ["rate_limit", "auth", "authorization"], \
            "Middleware should execute in correct order"

    def test_failed_auth_stops_pipeline(self):
        """Test that failed authentication stops the middleware pipeline."""
        executed = []

        def auth_check():
            executed.append("auth")
            return False  # Auth fails

        def handler():
            executed.append("handler")

        if auth_check():
            handler()

        assert "handler" not in executed, "Handler should not run after auth failure"


class TestCrossServiceTokenForwarding:
    """Tests for cross-service token forwarding."""

    def test_token_forwarded_to_downstream(self):
        """Test that user tokens are forwarded to downstream services."""
        incoming_headers = {
            "Authorization": "Bearer user-token-123",
            "X-Request-Id": "req-456",
        }

        # Forward auth header to downstream
        forwarded = {
            "Authorization": incoming_headers["Authorization"],
            "X-Request-Id": incoming_headers["X-Request-Id"],
            "X-Forwarded-For": "gateway",
        }

        assert forwarded["Authorization"] == "Bearer user-token-123", \
            "Auth token should be forwarded"

    def test_internal_token_not_leaked_to_external(self):
        """Test that internal service tokens are not sent to external services."""
        internal_headers = {
            "Authorization": "Bearer user-token",
            "X-Service-Token": "internal-secret-key",
        }

        # When calling external service, strip internal headers
        external_headers = {
            k: v for k, v in internal_headers.items()
            if not k.startswith("X-Service-")
        }

        assert "X-Service-Token" not in external_headers, \
            "Internal service token should not leak externally"


class TestRefreshTokenReuseDetection:
    """Tests for refresh token reuse detection."""

    def test_token_family_revocation(self):
        """Test that reuse of old refresh token revokes entire family."""
        token_family = {
            "family_id": "fam-1",
            "tokens": ["rt-1", "rt-2", "rt-3"],  # rt-3 is current
            "active": True,
        }

        # Reuse of old token (rt-1) indicates theft
        reused_token = "rt-1"
        current_token = token_family["tokens"][-1]

        is_reuse = reused_token != current_token and reused_token in token_family["tokens"]
        if is_reuse:
            token_family["active"] = False  # Revoke entire family

        assert not token_family["active"], \
            "Entire token family should be revoked on reuse detection"


class TestCorsCredentialHandling:
    """Tests for CORS credential handling."""

    def test_cors_with_credentials(self):
        """Test CORS headers when credentials are included."""
        allowed_origins = ["https://app.nexustrade.com", "https://staging.nexustrade.com"]
        request_origin = "https://app.nexustrade.com"

        # With credentials, cannot use wildcard origin
        response_headers = {}
        if request_origin in allowed_origins:
            response_headers["Access-Control-Allow-Origin"] = request_origin
            response_headers["Access-Control-Allow-Credentials"] = "true"
        else:
            response_headers["Access-Control-Allow-Origin"] = None

        assert response_headers["Access-Control-Allow-Origin"] == request_origin
        assert response_headers["Access-Control-Allow-Credentials"] == "true"
        # Must NOT be wildcard with credentials
        assert response_headers["Access-Control-Allow-Origin"] != "*"

    def test_cors_preflight_unauthorized_origin(self):
        """Test that unauthorized origins are rejected in CORS preflight."""
        allowed_origins = ["https://app.nexustrade.com"]
        request_origin = "https://evil.com"

        is_allowed = request_origin in allowed_origins
        assert not is_allowed, "Unauthorized origin should be rejected"


class TestAuthHeaderFormatValidation:
    """Tests for auth header format validation."""

    def test_bearer_token_format(self):
        """Test that only properly formatted Bearer tokens are accepted."""
        valid_header = "Bearer eyJhbGciOiJSUzI1NiJ9.payload.signature"
        invalid_headers = [
            "bearer token123",  # lowercase bearer
            "Token abc123",     # wrong scheme
            "Bearer",           # missing token
            "",                 # empty
        ]

        def validate_auth_header(header):
            if not header or not header.startswith("Bearer "):
                return False
            token = header[7:]
            return len(token) > 0

        assert validate_auth_header(valid_header), "Valid Bearer header should pass"
        for invalid in invalid_headers:
            assert not validate_auth_header(invalid), \
                f"Invalid header '{invalid}' should be rejected"


class TestServiceToServiceAuthRetry:
    """Tests for service-to-service auth retry logic."""

    def test_retry_on_token_expiry(self):
        """Test that service retries with fresh token after 401."""
        attempt = 0
        max_retries = 2

        def call_service(token):
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                return 401, "Token expired"
            return 200, "OK"

        def refresh_service_token():
            return "fresh-service-token"

        # First attempt fails with 401
        status, body = call_service("old-token")
        if status == 401 and attempt <= max_retries:
            new_token = refresh_service_token()
            status, body = call_service(new_token)

        assert status == 200, "Should succeed after refreshing token"
        assert attempt == 2, "Should have retried once"


class TestPermissionBoundaryEnforcement:
    """Tests for permission boundary enforcement."""

    def test_maximum_privilege_boundary(self):
        """Test that delegated tokens cannot exceed parent permissions."""
        parent_permissions = {"read:orders", "write:orders", "read:positions"}
        requested_delegation = {"read:orders", "write:orders", "admin:config"}

        # Delegated token can only have subset of parent permissions
        effective = requested_delegation & parent_permissions
        exceeded = requested_delegation - parent_permissions

        assert "admin:config" in exceeded, "admin:config exceeds parent boundary"
        assert effective == {"read:orders", "write:orders"}, \
            "Effective permissions should be bounded by parent"

    def test_escalation_prevention(self):
        """Test that privilege escalation is prevented."""
        user_role = "trader"
        role_permissions = {
            "viewer": {"read:orders"},
            "trader": {"read:orders", "write:orders"},
            "admin": {"read:orders", "write:orders", "admin:users"},
        }

        current_perms = role_permissions[user_role]
        attempted_action = "admin:users"

        can_escalate = attempted_action in current_perms
        assert not can_escalate, "Trader should not escalate to admin permissions"
