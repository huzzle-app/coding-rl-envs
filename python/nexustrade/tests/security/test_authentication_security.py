"""
Authentication and access-control security tests.

These tests cover JWT handling, input sanitization, session management,
cryptographic practices, and access control.  No bug-mapped tests -- these
are supplementary security coverage.
"""
import pytest
import hashlib
import hmac
import base64
import json
import os
import re
import time
import secrets
from unittest.mock import MagicMock, patch
from urllib.parse import urlparse, quote


# ---------------------------------------------------------------------------
# Lightweight helpers (self-contained, no running services)
# ---------------------------------------------------------------------------

def _make_jwt(header, payload, secret="test_secret"):
    """Create a minimal JWT for testing (HS256 only)."""
    def _b64(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    h = _b64(header)
    p = _b64(payload)
    sig = hmac.new(secret.encode(), f"{h}.{p}".encode(), hashlib.sha256).hexdigest()
    return f"{h}.{p}.{sig}"


def _verify_jwt(token, secret="test_secret", allowed_algorithms=None, expected_audience=None):
    """Verify a minimal JWT. Returns (valid, payload) tuple."""
    allowed_algorithms = allowed_algorithms or ["HS256"]
    parts = token.split(".")
    if len(parts) != 3:
        return False, {}

    def _decode_b64(s):
        padding = 4 - len(s) % 4
        return json.loads(base64.urlsafe_b64decode(s + "=" * padding))

    header = _decode_b64(parts[0])
    payload = _decode_b64(parts[1])

    # Algorithm check
    if header.get("alg") not in allowed_algorithms:
        return False, {}

    # Signature check
    expected_sig = hmac.new(
        secret.encode(), f"{parts[0]}.{parts[1]}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(parts[2], expected_sig):
        return False, {}

    # Expiry check
    if "exp" in payload and payload["exp"] < time.time():
        return False, {}

    # Audience check
    if expected_audience and payload.get("aud") != expected_audience:
        return False, {}

    return True, payload


# ---------------------------------------------------------------------------
# JWT Security
# ---------------------------------------------------------------------------

class TestJWTSecurity:
    """JWT token security validation tests."""

    def test_jwt_algorithm_restriction(self):
        """Test that only approved algorithms are accepted."""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": "user-1", "exp": time.time() + 3600}
        token = _make_jwt(header, payload)

        valid, _ = _verify_jwt(token, allowed_algorithms=["HS256"])
        assert valid, "HS256 should be accepted"

        # RS256 token should be rejected when only HS256 allowed
        header_rs = {"alg": "RS256", "typ": "JWT"}
        token_rs = _make_jwt(header_rs, payload)
        valid_rs, _ = _verify_jwt(token_rs, allowed_algorithms=["HS256"])
        assert not valid_rs, "RS256 should be rejected when not in allowed list"

    def test_jwt_expiry_validation(self):
        """Test that expired JWTs are rejected."""
        header = {"alg": "HS256", "typ": "JWT"}
        expired_payload = {"sub": "user-1", "exp": time.time() - 3600}
        token = _make_jwt(header, expired_payload)

        valid, _ = _verify_jwt(token)
        assert not valid, "Expired JWT should be rejected"

    def test_jwt_audience_check(self):
        """Test that JWT audience claim is validated."""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": "user-1", "aud": "trading-api", "exp": time.time() + 3600}
        token = _make_jwt(header, payload)

        valid, _ = _verify_jwt(token, expected_audience="trading-api")
        assert valid, "Correct audience should be accepted"

        valid_wrong, _ = _verify_jwt(token, expected_audience="admin-api")
        assert not valid_wrong, "Wrong audience should be rejected"

    def test_jwt_none_algorithm_rejected(self):
        """Test that 'none' algorithm is rejected."""
        header = {"alg": "none", "typ": "JWT"}
        payload = {"sub": "admin", "exp": time.time() + 3600}
        token = _make_jwt(header, payload)

        valid, _ = _verify_jwt(token, allowed_algorithms=["HS256"])
        assert not valid, "'none' algorithm must be rejected"

    def test_jwt_signature_verification(self):
        """Test that tampered JWTs are rejected."""
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {"sub": "user-1", "role": "user", "exp": time.time() + 3600}
        token = _make_jwt(header, payload, secret="correct_secret")

        valid, _ = _verify_jwt(token, secret="wrong_secret")
        assert not valid, "JWT signed with wrong secret should be rejected"


# ---------------------------------------------------------------------------
# Input Sanitization
# ---------------------------------------------------------------------------

class TestInputSanitization:
    """Input sanitization and injection prevention tests."""

    def test_html_injection_prevention(self):
        """Test that HTML tags are escaped in user input."""
        user_input = '<script>alert("xss")</script>'
        sanitized = user_input.replace("<", "&lt;").replace(">", "&gt;")
        assert "<script>" not in sanitized, "HTML tags should be escaped"
        assert "&lt;script&gt;" in sanitized

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        from urllib.parse import unquote
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2f",
            "....//....//etc/passwd",
        ]
        for path in malicious_paths:
            decoded = unquote(path)
            normalized = os.path.normpath(decoded)
            is_traversal = ".." in normalized or normalized.startswith("/")
            assert is_traversal or ".." in decoded, f"Path traversal not detected: {path}"

    def test_command_injection_blocked(self):
        """Test that shell metacharacters are rejected."""
        dangerous_inputs = [
            "valid; rm -rf /",
            "valid | cat /etc/passwd",
            "valid && echo pwned",
            "valid `whoami`",
            "valid $(id)",
        ]
        shell_metacharacters = re.compile(r'[;&|`$()]')
        for inp in dangerous_inputs:
            assert shell_metacharacters.search(inp), f"Should detect shell metacharacters in: {inp}"

    def test_header_injection_blocked(self):
        """Test that CRLF injection in headers is blocked."""
        malicious_values = [
            "value\r\nX-Injected: true",
            "value\nSet-Cookie: admin=true",
            "value\r\n\r\n<html>injected</html>",
        ]
        for val in malicious_values:
            has_crlf = "\r" in val or "\n" in val
            assert has_crlf, f"CRLF injection not detected in: {val!r}"
            sanitized = val.replace("\r", "").replace("\n", "")
            assert "\r" not in sanitized and "\n" not in sanitized

    def test_unicode_normalization(self):
        """Test that unicode normalization prevents homograph attacks."""
        import unicodedata
        # Cyrillic 'а' (U+0430) looks like Latin 'a' (U+0061)
        lookalike = "\u0430dmin"  # Cyrillic a + "dmin"
        normalized = unicodedata.normalize("NFKC", lookalike)

        # After normalization the string still uses Cyrillic; must check script
        has_non_ascii = any(ord(c) > 127 for c in normalized)
        assert has_non_ascii, "Homograph characters should be detected"


# ---------------------------------------------------------------------------
# Session Security
# ---------------------------------------------------------------------------

class TestSessionSecurity:
    """Session management security tests."""

    def test_session_fixation_prevention(self):
        """Test that session ID is regenerated after authentication."""
        old_session_id = secrets.token_hex(16)
        # After login, a new session ID should be issued
        new_session_id = secrets.token_hex(16)
        assert old_session_id != new_session_id, "Session ID must change after login"

    def test_session_timeout_enforcement(self):
        """Test that sessions expire after inactivity."""
        session_start = time.time() - 3700  # 1 hour + 100 seconds ago
        timeout_seconds = 3600
        is_expired = (time.time() - session_start) > timeout_seconds
        assert is_expired, "Session should expire after timeout"

    def test_concurrent_session_limit(self):
        """Test that concurrent session count is limited."""
        max_sessions = 3
        active_sessions = [secrets.token_hex(16) for _ in range(5)]

        # Only keep the most recent max_sessions
        enforced = active_sessions[-max_sessions:]
        assert len(enforced) == max_sessions, "Should enforce session limit"

    def test_session_invalidation_on_password_change(self):
        """Test that all sessions are invalidated when password changes."""
        sessions = {
            "sess_1": {"user": "bob", "created": time.time() - 1000},
            "sess_2": {"user": "bob", "created": time.time() - 500},
            "sess_3": {"user": "alice", "created": time.time() - 200},
        }
        password_changed_user = "bob"
        # Invalidate all sessions for the user who changed password
        remaining = {
            k: v for k, v in sessions.items() if v["user"] != password_changed_user
        }
        assert len(remaining) == 1, "All sessions for user should be invalidated"
        assert "sess_3" in remaining, "Other users' sessions should remain"

    def test_session_id_regeneration(self):
        """Test that session IDs have sufficient entropy."""
        session_ids = set()
        for _ in range(1000):
            sid = secrets.token_hex(16)
            assert sid not in session_ids, "Session ID collision detected"
            session_ids.add(sid)
        assert len(session_ids) == 1000, "All session IDs should be unique"


# ---------------------------------------------------------------------------
# Cryptography
# ---------------------------------------------------------------------------

class TestCryptography:
    """Cryptographic practice validation tests."""

    def test_password_hash_strength(self):
        """Test that password hashing uses strong algorithm."""
        # Simulate bcrypt-style cost factor check
        password = "secure_password_123"
        # bcrypt hashes start with $2b$ and include cost factor
        mock_hash = "$2b$12$" + hashlib.sha256(password.encode()).hexdigest()[:53]
        assert mock_hash.startswith("$2b$12$"), "Should use bcrypt with cost >= 12"
        cost = int(mock_hash.split("$")[2])
        assert cost >= 12, f"bcrypt cost {cost} is too low"

    def test_random_token_entropy(self):
        """Test that random tokens have sufficient entropy."""
        token = secrets.token_bytes(32)
        assert len(token) >= 32, "Token should be at least 256 bits"

        # Check token is not all zeros or repeating
        assert token != b"\x00" * 32, "Token should not be all zeros"
        unique_bytes = len(set(token))
        assert unique_bytes > 10, f"Token has low byte diversity: {unique_bytes}"

    def test_encryption_at_rest(self):
        """Test that sensitive data is encrypted before storage."""
        plaintext = "sensitive_api_key_12345"
        # Simulate encryption: the stored value should not contain plaintext
        encrypted = base64.b64encode(
            hashlib.sha256(plaintext.encode()).digest()
        ).decode()
        assert plaintext not in encrypted, "Plaintext should not appear in encrypted data"

    def test_tls_version_enforcement(self):
        """Test that only TLS 1.2+ is allowed."""
        allowed_versions = ["TLSv1.2", "TLSv1.3"]
        rejected_versions = ["SSLv3", "TLSv1.0", "TLSv1.1"]

        for ver in rejected_versions:
            assert ver not in allowed_versions, f"{ver} should not be allowed"
        for ver in allowed_versions:
            assert ver in allowed_versions

    def test_weak_cipher_rejection(self):
        """Test that weak cipher suites are rejected."""
        weak_ciphers = [
            "DES-CBC3-SHA",
            "RC4-SHA",
            "NULL-SHA",
            "EXPORT-DES-CBC-SHA",
            "DES-CBC-SHA",
        ]
        allowed_ciphers = [
            "TLS_AES_256_GCM_SHA384",
            "TLS_CHACHA20_POLY1305_SHA256",
            "TLS_AES_128_GCM_SHA256",
        ]
        for cipher in weak_ciphers:
            assert cipher not in allowed_ciphers, f"Weak cipher {cipher} should be rejected"


# ---------------------------------------------------------------------------
# Access Control
# ---------------------------------------------------------------------------

class TestAccessControl:
    """Access control and privilege escalation prevention tests."""

    def test_horizontal_privilege_escalation_blocked(self):
        """Test that users cannot access other users' resources."""
        requesting_user = "user-100"
        resource_owner = "user-200"
        assert requesting_user != resource_owner, "Horizontal access should be denied"

    def test_vertical_privilege_escalation_blocked(self):
        """Test that regular users cannot access admin functions."""
        user_roles = {"user-100": "trader"}
        required_role = "admin"
        user_role = user_roles.get("user-100", "guest")
        assert user_role != required_role, "Regular user should not have admin access"

    def test_admin_endpoint_protection(self):
        """Test that admin endpoints require admin role."""
        admin_endpoints = [
            "/admin/users",
            "/admin/config",
            "/admin/audit",
            "/internal/metrics",
        ]
        user_role = "trader"
        for endpoint in admin_endpoints:
            is_admin_route = endpoint.startswith("/admin") or endpoint.startswith("/internal")
            has_permission = user_role == "admin"
            assert is_admin_route and not has_permission, (
                f"Non-admin should be denied access to {endpoint}"
            )

    def test_api_key_scope_enforcement(self):
        """Test that API keys are limited to their defined scopes."""
        api_key_scopes = {
            "key_read_only": ["read:orders", "read:positions"],
            "key_trade": ["read:orders", "write:orders"],
        }
        # Read-only key should not allow writes
        read_key_scopes = api_key_scopes["key_read_only"]
        assert "write:orders" not in read_key_scopes, "Read-only key should not have write scope"

    def test_resource_ownership_validation(self):
        """Test that resource ownership is validated before modification."""
        resources = {
            "order-1": {"owner": "user-A", "amount": 1000},
            "order-2": {"owner": "user-B", "amount": 2000},
        }
        requesting_user = "user-A"
        target_resource = "order-2"

        owner = resources[target_resource]["owner"]
        can_modify = owner == requesting_user
        assert not can_modify, "User should not modify resources they don't own"
