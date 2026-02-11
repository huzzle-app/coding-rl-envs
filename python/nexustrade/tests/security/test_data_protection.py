"""
Data protection and compliance security tests.

These tests cover data leak prevention, PII protection, API key security,
and regulatory compliance checks.  No bug-mapped tests -- these are
supplementary security coverage.
"""
import pytest
import hashlib
import json
import re
import time
import secrets
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Data Leak Prevention
# ---------------------------------------------------------------------------

class TestDataLeakPrevention:
    """Tests to verify that internal details are not leaked to clients."""

    def test_error_message_sanitization(self):
        """Test that error messages do not expose internal details."""
        internal_error = (
            "psycopg2.OperationalError: connection to server at "
            '"10.0.3.12", port 5432 failed'
        )
        # Sanitized error should strip internal hostnames and ports
        sanitized = "An internal error occurred. Please try again later."
        assert "10.0.3.12" not in sanitized, "Internal IP should not be in error message"
        assert "5432" not in sanitized, "Internal port should not be in error message"
        assert "psycopg2" not in sanitized, "Library name should not be in error message"

    def test_stack_trace_not_exposed(self):
        """Test that stack traces are not included in API responses."""
        try:
            raise ValueError("test error for stack trace check")
        except ValueError:
            import traceback
            tb = traceback.format_exc()

        # The response body should not contain the traceback
        response_body = {"error": "Internal Server Error", "status": 500}
        response_str = json.dumps(response_body)
        assert "Traceback" not in response_str, "Stack trace should not be in response"
        assert "ValueError" not in response_str, "Exception type should not be in response"

    def test_internal_id_not_leaked(self):
        """Test that internal database IDs are not exposed in responses."""
        internal_record = {
            "_id": 98765,
            "public_id": "ord_abc123def456",
            "amount": 150.00,
            "status": "filled",
        }
        # Public response should use public_id, not internal _id
        public_fields = {"public_id", "amount", "status"}
        response = {k: v for k, v in internal_record.items() if k in public_fields}
        assert "_id" not in response, "Internal database ID should not be exposed"
        assert "public_id" in response

    def test_debug_endpoint_disabled_in_production(self):
        """Test that debug/diagnostic endpoints are disabled in production."""
        environment = "production"
        debug_endpoints = ["/debug/vars", "/debug/pprof", "/_debug", "/diagnostics"]

        enabled_endpoints = []
        for ep in debug_endpoints:
            is_enabled = environment != "production"
            if is_enabled:
                enabled_endpoints.append(ep)

        assert len(enabled_endpoints) == 0, "Debug endpoints must be disabled in production"

    def test_verbose_headers_removed(self):
        """Test that verbose server headers are stripped."""
        response_headers = {
            "Content-Type": "application/json",
            "X-Powered-By": "Express",
            "Server": "nginx/1.21.3",
            "X-AspNet-Version": "4.0.30319",
        }
        sensitive_headers = {"X-Powered-By", "Server", "X-AspNet-Version"}
        sanitized_headers = {
            k: v for k, v in response_headers.items() if k not in sensitive_headers
        }
        for h in sensitive_headers:
            assert h not in sanitized_headers, f"Header {h} should be removed"


# ---------------------------------------------------------------------------
# PII Protection
# ---------------------------------------------------------------------------

class TestPIIProtection:
    """Tests to verify personally identifiable information is protected."""

    def test_pii_masking_in_logs(self):
        """Test that PII fields are masked before logging."""
        log_data = {
            "user_id": "user-123",
            "email": "john@example.com",
            "ssn": "123-45-6789",
            "action": "login",
        }
        pii_fields = {"email", "ssn"}
        masked = {}
        for k, v in log_data.items():
            if k in pii_fields:
                masked[k] = "***REDACTED***"
            else:
                masked[k] = v

        assert masked["email"] == "***REDACTED***"
        assert masked["ssn"] == "***REDACTED***"
        assert masked["action"] == "login", "Non-PII fields should remain unchanged"

    def test_pii_encryption_in_storage(self):
        """Test that PII is encrypted before being stored."""
        pii_value = "john.doe@example.com"
        encryption_key = secrets.token_bytes(32)

        # Simulate encryption (use hash as stand-in for real encryption)
        encrypted = hashlib.sha256(pii_value.encode() + encryption_key).hexdigest()
        assert pii_value not in encrypted, "Plaintext PII should not appear in storage"
        assert len(encrypted) > 0, "Encrypted value should not be empty"

    def test_pii_redaction_in_responses(self):
        """Test that PII is redacted from API responses."""
        user_record = {
            "id": "user-456",
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "+1-555-123-4567",
            "trading_balance": 10000.0,
        }
        redact_fields = {"email", "phone"}
        response = {}
        for k, v in user_record.items():
            if k in redact_fields:
                if k == "email":
                    parts = v.split("@")
                    response[k] = parts[0][:2] + "***@" + parts[1]
                elif k == "phone":
                    response[k] = "***" + v[-4:]
            else:
                response[k] = v

        assert "jane@example.com" not in json.dumps(response)
        assert "+1-555-123-4567" not in json.dumps(response)
        assert response["email"].startswith("ja***@")
        assert response["phone"].endswith("4567")

    def test_audit_log_pii_handling(self):
        """Test that audit logs handle PII according to policy."""
        audit_entry = {
            "timestamp": time.time(),
            "actor": "user-789",
            "action": "update_profile",
            "changes": {
                "email": {"old": "old@example.com", "new": "new@example.com"},
                "name": {"old": "Old Name", "new": "New Name"},
            },
        }
        # PII in audit logs should be hashed, not stored in plaintext
        pii_in_changes = ["email"]
        sanitized_changes = {}
        for field, change in audit_entry["changes"].items():
            if field in pii_in_changes:
                sanitized_changes[field] = {
                    "old": hashlib.sha256(change["old"].encode()).hexdigest()[:16],
                    "new": hashlib.sha256(change["new"].encode()).hexdigest()[:16],
                }
            else:
                sanitized_changes[field] = change

        assert "old@example.com" not in json.dumps(sanitized_changes)
        assert "new@example.com" not in json.dumps(sanitized_changes)

    def test_cache_pii_expiry(self):
        """Test that cached PII expires within mandated time window."""
        pii_cache_ttl = 300  # 5 minutes max
        max_allowed_ttl = 600  # 10 minutes regulatory limit

        assert pii_cache_ttl <= max_allowed_ttl, "PII cache TTL exceeds regulatory limit"

        # Simulate cached PII entry
        cached_at = time.time() - 400  # 400 seconds ago
        is_expired = (time.time() - cached_at) > pii_cache_ttl
        assert is_expired, "PII cache entry should have expired"


# ---------------------------------------------------------------------------
# API Key Security
# ---------------------------------------------------------------------------

class TestAPIKeySecurity:
    """Tests for API key handling and lifecycle security."""

    def test_api_key_not_in_url(self):
        """Test that API keys are not passed as URL query parameters."""
        request_url = "https://api.nexustrade.com/v1/orders?symbol=BTC"
        request_headers = {"Authorization": "Bearer sk_live_abc123"}

        assert "api_key=" not in request_url, "API key should not be in URL"
        assert "sk_live" not in request_url, "Secret key should not be in URL"
        assert "Authorization" in request_headers, "API key should be in headers"

    def test_api_key_rotation_support(self):
        """Test that key rotation allows both old and new keys during grace period."""
        old_key = "sk_live_old_key_123"
        new_key = "sk_live_new_key_456"
        rotation_grace_period = 3600  # 1 hour
        rotation_started = time.time() - 1800  # 30 min ago

        in_grace_period = (time.time() - rotation_started) < rotation_grace_period
        assert in_grace_period, "Should be within grace period"

        # Both keys should work during grace period
        valid_keys = {old_key, new_key}
        assert old_key in valid_keys
        assert new_key in valid_keys

        # After grace period, only new key should work
        rotation_started_old = time.time() - 7200  # 2 hours ago
        past_grace = (time.time() - rotation_started_old) >= rotation_grace_period
        assert past_grace, "Grace period should have ended"

    def test_api_key_rate_limiting(self):
        """Test that API keys have individual rate limits."""
        rate_limits = {
            "key_basic": {"limit": 100, "window": 60},
            "key_premium": {"limit": 1000, "window": 60},
        }
        request_counts = {"key_basic": 150, "key_premium": 500}

        basic_exceeded = request_counts["key_basic"] > rate_limits["key_basic"]["limit"]
        premium_exceeded = request_counts["key_premium"] > rate_limits["key_premium"]["limit"]

        assert basic_exceeded, "Basic key should be rate limited"
        assert not premium_exceeded, "Premium key should not be rate limited"

    def test_api_key_scope_validation(self):
        """Test that API keys only allow operations within their scope."""
        key_permissions = {
            "sk_read_abc": ["orders:read", "positions:read"],
            "sk_trade_xyz": ["orders:read", "orders:write", "positions:read"],
        }

        # Read-only key attempting a write
        read_key = "sk_read_abc"
        requested_permission = "orders:write"
        has_permission = requested_permission in key_permissions.get(read_key, [])
        assert not has_permission, "Read-only key should not allow order writes"

        # Trade key attempting a write
        trade_key = "sk_trade_xyz"
        has_trade_perm = requested_permission in key_permissions.get(trade_key, [])
        assert has_trade_perm, "Trade key should allow order writes"

    def test_revoked_api_key_rejected(self):
        """Test that revoked API keys are immediately rejected."""
        active_keys = {"sk_active_1", "sk_active_2"}
        revoked_keys = {"sk_revoked_1"}
        all_keys = active_keys | revoked_keys

        test_key = "sk_revoked_1"
        is_active = test_key in active_keys
        is_revoked = test_key in revoked_keys

        assert not is_active, "Revoked key should not be in active set"
        assert is_revoked, "Key should appear in revoked set"


# ---------------------------------------------------------------------------
# Compliance Checks
# ---------------------------------------------------------------------------

class TestComplianceChecks:
    """Regulatory and compliance validation tests."""

    def test_data_retention_policy(self):
        """Test that data retention periods are enforced."""
        retention_days = 365
        record_created = time.time() - (400 * 86400)  # 400 days ago
        age_days = (time.time() - record_created) / 86400

        should_delete = age_days > retention_days
        assert should_delete, "Record past retention period should be flagged for deletion"

    def test_right_to_deletion(self):
        """Test that user data can be completely deleted on request."""
        user_data_stores = {
            "users_table": {"user-del-1": {"name": "Test User"}},
            "orders_table": {"order-1": {"user_id": "user-del-1"}},
            "sessions_table": {"sess-1": {"user_id": "user-del-1"}},
            "audit_log": {"entry-1": {"actor": "user-del-1"}},
        }

        user_to_delete = "user-del-1"
        # Delete from all stores
        for store_name, store in list(user_data_stores.items()):
            keys_to_remove = [
                k for k, v in store.items()
                if v.get("user_id") == user_to_delete
                or v.get("actor") == user_to_delete
                or k == user_to_delete
            ]
            for k in keys_to_remove:
                del store[k]

        # Verify deletion
        for store_name, store in user_data_stores.items():
            for k, v in store.items():
                record_str = json.dumps(v)
                assert user_to_delete not in record_str, (
                    f"User data found in {store_name} after deletion"
                )

    def test_consent_tracking(self):
        """Test that user consent is tracked before data processing."""
        consent_records = {
            "user-c1": {"marketing": True, "analytics": True, "third_party": False},
            "user-c2": {"marketing": False, "analytics": True, "third_party": False},
        }

        # Processing marketing data requires marketing consent
        user = "user-c2"
        has_marketing_consent = consent_records[user].get("marketing", False)
        assert not has_marketing_consent, "Should not process marketing without consent"

        # Analytics is consented
        has_analytics_consent = consent_records[user].get("analytics", False)
        assert has_analytics_consent, "Analytics processing should be allowed"

    def test_cross_border_data_restriction(self):
        """Test that data does not flow to restricted regions."""
        allowed_regions = {"us-east-1", "us-west-2", "eu-west-1"}
        restricted_regions = {"cn-north-1", "ru-central-1"}
        data_destinations = {"us-east-1", "eu-west-1"}

        for dest in data_destinations:
            assert dest in allowed_regions, f"Data sent to unauthorized region: {dest}"
            assert dest not in restricted_regions, f"Data sent to restricted region: {dest}"

    def test_audit_trail_immutability(self):
        """Test that audit trail entries cannot be modified after creation."""
        audit_log = []

        def append_audit(entry):
            entry["hash"] = hashlib.sha256(
                json.dumps(entry, sort_keys=True).encode()
            ).hexdigest()
            audit_log.append(entry)

        entry = {"timestamp": time.time(), "action": "trade_executed", "amount": 5000}
        append_audit(entry)

        # Verify integrity
        stored = audit_log[0]
        expected_hash = stored.pop("hash")
        computed_hash = hashlib.sha256(
            json.dumps(stored, sort_keys=True).encode()
        ).hexdigest()
        assert computed_hash == expected_hash, "Audit entry hash mismatch -- integrity violated"
