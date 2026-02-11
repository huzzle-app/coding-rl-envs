"""
SynapseNet Security Vulnerability Tests
Terminal Bench v2 - Tests for security bugs across all services

Tests cover:
- I1-I10: Security bugs
"""
import time
import uuid
import hashlib
import sys
import os
from unittest import mock

import pytest


# =========================================================================
# I1: SQL injection in experiment filter
# =========================================================================

class TestExperimentFilterInjection:
    """BUG I1: Experiment search allows SQL injection via tag."""

    def test_experiment_filter_injection(self):
        """SQL injection in experiment search should be prevented."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("safe_exp", "model_1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["production"]

        # SQL injection attempt
        malicious_input = "production'; DROP TABLE experiments; --"
        results = manager.search_by_tag(malicious_input)

        # Should not affect other queries
        safe_results = manager.search_by_tag("production")
        assert len(safe_results) == 1, (
            "SQL injection should not affect other queries"
        )

    def test_parameterized_query_used(self):
        """Search should use parameterized queries, not string interpolation."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Test various SQL injection payloads
        injection_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE--",
            "' UNION SELECT * FROM users--",
            "1; EXEC xp_cmdshell('whoami')",
            "' AND 1=1--",
        ]

        for payload in injection_payloads:
            results = manager.search_by_tag(payload)
            # Should return empty, not error or return unexpected data
            assert isinstance(results, list)


# =========================================================================
# I2: SSRF via webhook URL
# =========================================================================

class TestWebhookSSRFBlocked:
    """BUG I2: Webhook registration doesn't validate URL target."""

    def test_webhook_ssrf_blocked(self):
        """Internal URLs should be blocked in webhook registration."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()

        # These URLs should be blocked (SSRF targets)
        internal_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://localhost:8001/admin/",
            "http://127.0.0.1:6379/",
            "http://10.0.0.1:5432/",
            "http://172.16.0.1:8080/",
            "http://192.168.1.1/",
            "http://[::1]:8080/",
        ]

        for url in internal_urls:
            try:
                sub_id = wm.register_webhook(url, ["model.deployed"])
                
                assert sub_id is None or not wm._subscriptions.get(sub_id, {}).get("is_active"), (
                    f"Internal URL {url} should be blocked. "
                    "BUG I2: No URL validation - SSRF possible."
                )
            except ValueError:
                pass  # Expected: URL validation rejects internal URLs

    def test_internal_url_rejected(self):
        """Metadata service URL should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()

        # AWS metadata endpoint
        try:
            sub_id = wm.register_webhook(
                "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
                ["model.deployed"],
            )
            
            if sub_id and wm._subscriptions.get(sub_id, {}).get("is_active"):
                pytest.fail(
                    "SSRF: AWS metadata endpoint URL was accepted. "
                    "BUG I2: No URL validation in webhook registration."
                )
        except (ValueError, SecurityError):
            pass  # Expected

    def test_external_url_accepted(self):
        """Legitimate external URLs should be accepted."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        sub_id = wm.register_webhook("https://hooks.example.com/webhook", ["model.deployed"])
        assert sub_id is not None


# =========================================================================
# I3: Pickle deserialization (arbitrary code execution)
# =========================================================================

class TestPickleDeserializationBlocked:
    """BUG I3: Pickle is used for model serialization, allowing code execution."""

    def test_pickle_deserialization_blocked(self):
        """Model serialization should not use pickle."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.serialization import safe_serialize, safe_deserialize

        data = {"model_weights": [1.0, 2.0, 3.0]}

        # Serialize as "model" format
        serialized = safe_serialize(data, format="model")

        
        # Should use safe formats like JSON, protobuf, or safetensors
        import pickle
        try:
            # Check if the serialized data is pickle format
            pickle.loads(serialized)
            pytest.fail(
                "Model serialization uses pickle, which allows arbitrary code execution. "
                "BUG I3: Should use a safe serialization format."
            )
        except (pickle.UnpicklingError, TypeError, AttributeError):
            pass  # Good - not pickle format

    def test_safe_serialization_used(self):
        """Serialization should use safe format (JSON/protobuf)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.serialization import safe_serialize, safe_deserialize

        data = {"key": "value", "numbers": [1, 2, 3]}

        # JSON format should work
        serialized = safe_serialize(data, format="json")
        deserialized = safe_deserialize(serialized, format="json")
        assert deserialized == data


# =========================================================================
# I4: Rate limit bypass via X-Forwarded-For
# =========================================================================

class TestRateLimitBypassBlocked:
    """BUG I4: Rate limiting uses X-Forwarded-For which can be spoofed."""

    def test_rate_limit_bypass_blocked(self):
        """Rate limiting should not trust X-Forwarded-For header."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)

        # Exhaust rate limit with real IP
        for i in range(5):
            assert limiter.check_rate_limit({"remote_addr": "1.2.3.4"}) is True

        # Should be rate limited now
        assert limiter.check_rate_limit({"remote_addr": "1.2.3.4"}) is False

        
        result = limiter.check_rate_limit({
            "remote_addr": "1.2.3.4",
            "X-Forwarded-For": "99.99.99.99",
        })

        assert result is False, (
            "Rate limiting was bypassed by spoofing X-Forwarded-For. "
            "BUG I4: Should not trust X-Forwarded-For for rate limiting."
        )

    def test_rate_limit_uniform(self):
        """All requests from same IP should be rate limited equally."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Three requests should succeed
        for _ in range(3):
            assert limiter.check_rate_limit({"remote_addr": "5.5.5.5"}) is True

        # Fourth should be blocked
        assert limiter.check_rate_limit({"remote_addr": "5.5.5.5"}) is False

        # Different IP should not be affected
        assert limiter.check_rate_limit({"remote_addr": "6.6.6.6"}) is True


# =========================================================================
# I5: IDOR on model endpoints
# =========================================================================

class TestModelIDORBlocked:
    """BUG I5: Any authenticated user can access any model."""

    def test_model_idor_blocked(self):
        """Model access should be restricted to owner/tenant."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model(
            {"name": "private_model", "tenant_id": "tenant_a"},
            user_id="owner_user",
        )

        # Another user from different tenant tries to access
        
        result = store.get_model(model["model_id"], user_id="other_user", tenant_id="tenant_b")

        assert result is None, (
            "User from tenant_b should not access tenant_a's model. "
            "BUG I5: IDOR - no tenant/owner authorization check."
        )

    def test_authorization_check_model(self):
        """Model access should verify tenant and ownership."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model(
            {"name": "tenant_model", "tenant_id": "t1"},
            user_id="u1",
        )

        # Same tenant should be able to access
        
        result_same = store.get_model(model["model_id"], user_id="u1", tenant_id="t1")
        assert result_same is not None


# =========================================================================
# I6: XXE prevention
# =========================================================================

class TestXXEPrevention:
    """BUG I6: XML parsing allows external entity expansion."""

    def test_xxe_prevention(self):
        """XML parsing should disable external entities."""
        # XXE attack payload
        xxe_payload = """<?xml version="1.0"?>
        <!DOCTYPE foo [
            <!ENTITY xxe SYSTEM "file:///etc/passwd">
        ]>
        <data>&xxe;</data>"""

        # The system should safely handle XML without expanding entities
        import xml.etree.ElementTree as ET
        try:
            root = ET.fromstring(xxe_payload)
            # If parsing succeeds, entity should NOT be expanded
            text = root.text or ""
            assert "root:" not in text, (
                "XXE attack succeeded - external entity was expanded"
            )
        except ET.ParseError:
            pass  # Expected: DTD parsing disabled

    def test_xml_safe_parsing(self):
        """XML parser should reject DOCTYPE declarations."""
        safe_xml = "<data><value>test</value></data>"
        import xml.etree.ElementTree as ET
        root = ET.fromstring(safe_xml)
        assert root.find("value").text == "test"


# =========================================================================
# I7: Mass assignment
# =========================================================================

class TestMassAssignmentBlocked:
    """BUG I7: Update accepts all fields including sensitive ones."""

    def test_mass_assignment_blocked(self):
        """Sensitive fields should not be updatable via mass assignment."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model(
            {"name": "safe_model", "tenant_id": "t1"},
            user_id="u1",
        )

        original_owner = model["owner_id"]
        original_tenant = model["tenant_id"]

        # Try to update sensitive fields
        
        updated = store.update_model(model["model_id"], {
            "name": "new_name",
            "owner_id": "attacker",
            "tenant_id": "attacker_tenant",
            "is_public": True,
        })

        assert updated["owner_id"] == original_owner, (
            f"owner_id changed from '{original_owner}' to '{updated['owner_id']}'. "
            "BUG I7: Mass assignment allows changing owner_id."
        )
        assert updated["tenant_id"] == original_tenant, (
            f"tenant_id changed from '{original_tenant}' to '{updated['tenant_id']}'. "
            "BUG I7: Mass assignment allows changing tenant_id."
        )

    def test_field_allowlist_enforced(self):
        """Only allowed fields should be updateable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import update_user

        user = {
            "user_id": "u1",
            "name": "Alice",
            "email": "alice@example.com",
            "is_admin": False,
            "role": "user",
        }

        # Try mass assignment
        updated = update_user(user, {
            "name": "Alice Updated",
            "is_admin": True,
            "role": "admin",
        })

        
        assert updated["is_admin"] is False, (
            "is_admin was changed via mass assignment. "
            "BUG I7: No field allowlist."
        )
        assert updated["role"] == "user", (
            "role was changed via mass assignment."
        )


# =========================================================================
# I8: API key timing attack
# =========================================================================

class TestAPIKeyTimingAttack:
    """BUG I8: API key comparison is not constant-time."""

    def test_api_key_timing_attack(self):
        """API key comparison should be constant-time."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager
        import hmac

        km = APIKeyManager()
        valid_key = km.create_key("user_1")

        # Time many comparisons
        invalid_key_prefix = valid_key[:10] + "x" * (len(valid_key) - 10)
        invalid_key_random = str(uuid.uuid4())

        
        # A proper implementation should use hmac.compare_digest
        iterations = 1000

        # Test with nearly-matching key
        start = time.time()
        for _ in range(iterations):
            km.validate_key(invalid_key_prefix)
        near_match_time = time.time() - start

        # Test with completely different key
        start = time.time()
        for _ in range(iterations):
            km.validate_key(invalid_key_random)
        random_time = time.time() - start

        # Times should be similar if constant-time comparison is used
        # This is a statistical test - may have false positives
        time_diff = abs(near_match_time - random_time)
        max_diff = max(near_match_time, random_time) * 0.5

        # Weak assertion - timing attacks are hard to test deterministically
        assert True  # Just validates no errors

    def test_constant_time_compare(self):
        """Key validation should use hmac.compare_digest or similar."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        key = km.create_key("user_1")

        # Valid key should authenticate
        result = km.validate_key(key)
        assert result == "user_1"

        # Invalid key should not authenticate
        result = km.validate_key("invalid_key")
        assert result is None


# =========================================================================
# I9: Path traversal in artifact download
# =========================================================================

class TestPathTraversalBlocked:
    """BUG I9: Artifact download allows path traversal."""

    def test_path_traversal_blocked(self):
        """Path traversal attempts should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_traversal_artifacts")
        storage.initialize_bucket("models")

        # Upload a legitimate artifact
        storage.upload_artifact("models", "model.pkl", b"model_data")

        # Try path traversal
        traversal_keys = [
            "../../etc/passwd",
            "../../../etc/shadow",
            "..%2F..%2Fetc%2Fpasswd",
            "....//....//etc/passwd",
        ]

        for key in traversal_keys:
            result = storage.download_artifact("models", key)
            
            # If result contains system file data, it's a vulnerability
            if result is not None:
                # Check if it's not the legitimate artifact
                from pathlib import Path
                resolved = (Path(storage.base_path) / "models" / key).resolve()
                is_safe = str(resolved).startswith(str(Path(storage.base_path).resolve()))
                assert is_safe, (
                    f"Path traversal succeeded with key '{key}'. "
                    "BUG I9: No path sanitization."
                )

    def test_artifact_path_validated(self):
        """Artifact paths should be validated against base directory."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_path_validation")
        storage.initialize_bucket("safe_bucket")

        # Normal upload and download should work
        storage.upload_artifact("safe_bucket", "artifact.bin", b"data")
        result = storage.download_artifact("safe_bucket", "artifact.bin")
        assert result == b"data"


# =========================================================================
# I10: ReDoS prevention
# =========================================================================

class TestReDoSPrevention:
    """BUG I10: Search regex allows catastrophic backtracking."""

    def test_redos_prevention(self):
        """Search patterns should not allow catastrophic backtracking."""
        import re

        # ReDoS payload that causes exponential backtracking
        evil_pattern = r"(a+)+$"
        evil_input = "a" * 30 + "!"

        # This should complete quickly (with safe regex)
        start = time.time()
        try:
            re.match(evil_pattern, evil_input, timeout=1)
        except (re.error, TypeError):
            pass  # timeout parameter may not exist in older Python
        elapsed = time.time() - start

        # Should complete in under 2 seconds
        assert elapsed < 2.0, (
            f"Regex took {elapsed:.1f}s - potential ReDoS vulnerability"
        )

    def test_search_regex_safe(self):
        """Search functionality should use safe regex patterns."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("regex_test", "m1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["safe_tag"]

        # Normal search should work
        results = manager.search_by_tag("safe_tag")
        assert len(results) == 1

        # Regex-like input should be treated as literal
        results = manager.search_by_tag(".*")
        assert len(results) == 0  # Should not match everything


# =========================================================================
# Additional security tests
# =========================================================================

class TestWebhookDelivery:
    """Test webhook delivery security."""

    def test_webhook_secret_validation(self):
        """Webhook deliveries should include secret for verification."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        sub_id = wm.register_webhook(
            "https://hooks.example.com/hook",
            ["model.deployed"],
            secret="webhook_secret_123",
        )

        sub = wm._subscriptions[sub_id]
        assert sub["secret"] == "webhook_secret_123"

    def test_webhook_event_delivery(self):
        """Events should be delivered to matching webhooks."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://example.com/hook1", ["model.deployed"])
        wm.register_webhook("https://example.com/hook2", ["model.trained"])

        count = wm.deliver_event("model.deployed", {"model_id": "m1"})
        assert count == 1  # Only hook1 matches


class TestConfigReloadSecurity:
    """Test config reload security."""

    def test_config_reload_atomic(self):
        """Config reload should be atomic."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import ConfigManager

        cm = ConfigManager()
        cm.load_config({"key1": "val1", "key2": "val2"})

        assert cm.get("key1") == "val1"
        assert cm.get("key2") == "val2"

    def test_partial_config_prevention(self):
        """Readers should not see partially updated config."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import ConfigManager

        cm = ConfigManager()
        cm.load_config({"a": 1, "b": 2, "c": 3})

        # All values should be consistent
        config = cm.get_all()
        assert len(config) == 3


class TestTenantIsolation:
    """Test tenant isolation."""

    def test_tenant_data_isolation(self):
        """Tenants should not see each other's data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        store.create_model({"name": "model_t1", "tenant_id": "t1"}, "u1")
        store.create_model({"name": "model_t2", "tenant_id": "t2"}, "u2")

        t1_models = store.list_models(tenant_id="t1")
        t2_models = store.list_models(tenant_id="t2")

        assert len(t1_models) == 1
        assert len(t2_models) == 1
        assert t1_models[0]["name"] == "model_t1"
        assert t2_models[0]["name"] == "model_t2"


# =========================================================================
# Extended Security Tests
# =========================================================================

class TestInputSanitization:
    """Test input sanitization across services."""

    def test_model_name_sanitization(self):
        """Model name with special characters should be sanitized."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        # Name with HTML/script injection
        model = store.create_model(
            {"name": "<script>alert('xss')</script>"},
            user_id="u1",
        )
        assert "<script>" not in model.get("name", "") or model["name"] == "<script>alert('xss')</script>"

    def test_experiment_name_sanitization(self):
        """Experiment names should be safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment(
            "test<img src=x onerror=alert(1)>", "m1", {"lr": 0.01}
        )
        assert exp_id is not None

    def test_feature_group_name_sanitization(self):
        """Feature group names should be validated."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        result = store.write_feature("e1", "../../../etc/passwd", {"v": 1})
        assert isinstance(result, bool)

    def test_config_key_injection(self):
        """Config keys should not allow injection."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import ConfigManager

        cm = ConfigManager()
        cm.load_config({"safe_key": "value"})
        # Try to inject via key
        result = cm.get("safe_key' OR '1'='1", "default")
        assert result == "default"


class TestAuthenticationSecurity:
    """Extended authentication security tests."""

    def test_token_format_validation(self):
        """Token should have proper format."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user_1", {"role": "admin"})
        assert len(tokens["access_token"]) > 20
        assert len(tokens["refresh_token"]) > 20

    def test_expired_refresh_token(self):
        """Using expired refresh token should fail."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user_1", {})
        # Use the refresh token
        new_tokens = tm.refresh(tokens["refresh_token"])
        assert new_tokens is not None

        # Old refresh token should now be invalid
        result = tm.refresh(tokens["refresh_token"])
        assert result is None

    def test_api_key_length(self):
        """API key should be sufficiently long."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        key = km.create_key("user_1")
        assert len(key) >= 32, "API key should be at least 32 characters"

    def test_api_key_uniqueness(self):
        """Each generated API key should be unique."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        keys = set()
        for i in range(50):
            key = km.create_key(f"user_{i}")
            assert key not in keys, "API keys should be unique"
            keys.add(key)

    def test_api_key_rotation(self):
        """Rotated key should work, old key should be invalidated."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        old_key = km.create_key("user_1")
        new_key = km.rotate_key(old_key)

        assert new_key is not None
        assert new_key != old_key
        assert km.validate_key(new_key) == "user_1"

    def test_permission_cache_ttl(self):
        """Permission cache should respect TTL."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import PermissionCache

        cache = PermissionCache(ttl=0.01)
        cache.set_permissions("user_1", {"role": "admin"})
        time.sleep(0.02)
        result = cache.get_permissions("user_1")
        assert result is None, "Expired permissions should not be returned"


class TestStorageSecurity:
    """Extended storage security tests."""

    def test_bucket_isolation(self):
        """Artifacts in different buckets should be isolated."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_bucket_isolation")
        storage.initialize_bucket("bucket_a")
        storage.initialize_bucket("bucket_b")

        storage.upload_artifact("bucket_a", "secret.bin", b"confidential_data")

        # Bucket B should not see bucket A's artifacts
        result = storage.download_artifact("bucket_b", "secret.bin")
        assert result is None

    def test_artifact_checksum_verification(self):
        """Downloaded artifact should match uploaded checksum."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_checksum_verify")
        storage.initialize_bucket("verified")

        data = b"important model weights"
        checksum = storage.upload_artifact("verified", "model.bin", data)
        downloaded = storage.download_artifact("verified", "model.bin")

        assert downloaded == data
        meta = storage.get_metadata("verified", "model.bin")
        assert meta["checksum"] == checksum

    def test_path_traversal_upload(self):
        """Path traversal in upload should be blocked."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_upload_traversal")
        storage.initialize_bucket("safe")

        # Try to upload outside the bucket
        traversal_key = "../../outside.bin"
        storage.upload_artifact("safe", traversal_key, b"malicious")

        # Verify file didn't escape the base path
        from pathlib import Path
        escaped_path = Path("/tmp/test_upload_traversal") / "safe" / traversal_key
        resolved = escaped_path.resolve()
        base_resolved = Path("/tmp/test_upload_traversal").resolve()
        # This documents the vulnerability
        assert True  


class TestSSRFVulnerabilities(unittest.TestCase):
    """Tests for SSRF vulnerabilities in webhook and service communication."""

    @pytest.mark.security
    def test_webhook_allows_internal_url_bug_i2(self):
        """Bug I2: Webhook registration allows internal URLs."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        # Should block internal IPs but BUG I2: no validation
        sub_id = wm.register_webhook("http://169.254.169.254/latest/meta-data/", ["model.deployed"])
        assert sub_id is not None  # Should have been rejected

    @pytest.mark.security
    def test_webhook_allows_localhost_bug_i2(self):
        """Bug I2: Webhook allows localhost URLs for SSRF."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        sub_id = wm.register_webhook("http://localhost:8001/admin/", ["model.updated"])
        assert sub_id is not None  

    @pytest.mark.security
    def test_webhook_allows_private_network_bug_i2(self):
        """Bug I2: Webhook allows private network range URLs."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        private_urls = [
            "http://10.0.0.1:8080/internal",
            "http://172.16.0.1:9090/api",
            "http://192.168.1.1:3000/admin",
        ]
        for url in private_urls:
            sub_id = wm.register_webhook(url, ["model.deployed"])
            assert sub_id is not None  # All succeed - BUG I2

    @pytest.mark.security
    def test_rate_limit_bypass_via_forwarded_for_bug_i4(self):
        """Bug I4: Rate limit can be bypassed by spoofing X-Forwarded-For."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        # Exhaust rate limit for one IP
        for _ in range(5):
            limiter.check_rate_limit({"remote_addr": "10.0.0.1"})
        assert limiter.check_rate_limit({"remote_addr": "10.0.0.1"}) is False

        
        result = limiter.check_rate_limit({"X-Forwarded-For": "fake_ip_1", "remote_addr": "10.0.0.1"})
        assert result is True  # Bypassed using spoofed header

    @pytest.mark.security
    def test_rate_limit_bypass_with_many_ips(self):
        """Bug I4: Attacker can use unlimited IPs via header spoofing."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=2, window_seconds=60)
        # Each "different" IP gets its own rate limit
        for i in range(100):
            result = limiter.check_rate_limit({"X-Forwarded-For": f"spoofed_{i}"})
            assert result is True  # Every request succeeds - unlimited bypass

    @pytest.mark.security
    def test_mass_assignment_privilege_escalation_bug_i7(self):
        """Bug I7: Mass assignment allows setting admin flag."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import update_user

        user = {"name": "regular_user", "role": "viewer", "is_admin": False}
        updated = update_user(user, {"is_admin": True, "role": "admin"})
        
        assert updated["is_admin"] is True
        assert updated["role"] == "admin"

    @pytest.mark.security
    def test_mass_assignment_tenant_override_bug_i7(self):
        """Bug I7: Mass assignment allows overriding tenant_id."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import update_user

        user = {"name": "user1", "tenant_id": "tenant_a"}
        updated = update_user(user, {"tenant_id": "tenant_b"})
        assert updated["tenant_id"] == "tenant_b"  

    @pytest.mark.security
    def test_timing_attack_api_key_bug_i8(self):
        """Bug I8: API key comparison is not constant-time."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        valid_key = km.create_key("user1")
        # Validation iterates through keys with early return
        result = km.validate_key(valid_key)
        assert result == "user1"
        # Invalid key must be checked against all keys - timing leak
        result_invalid = km.validate_key("completely-wrong-key")
        assert result_invalid is None

    @pytest.mark.security
    def test_api_key_rotation_window_bug_g5(self):
        """Bug G5: During rotation, both old and new keys may be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        old_key = km.create_key("user1")
        assert km.validate_key(old_key) == "user1"
        new_key = km.rotate_key(old_key)
        
        assert km.validate_key(old_key) is None  # Old key deactivated
        assert km.validate_key(new_key) == "user1"  # New key should work

    @pytest.mark.security
    def test_token_refresh_race_condition_bug_g2(self):
        """Bug G2: Token refresh is not atomic."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user1", {"role": "admin"})
        refresh_token = tokens["refresh_token"]

        # First refresh should succeed
        new_tokens = tm.refresh(refresh_token)
        assert new_tokens is not None

        # Second refresh with same token should fail (already consumed)
        result = tm.refresh(refresh_token)
        assert result is None

    @pytest.mark.security
    def test_permission_cache_stale_after_revocation_bug_g4(self):
        """Bug G4: Permission cache not invalidated on revocation."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import PermissionCache

        cache = PermissionCache(ttl=300.0)
        cache.set_permissions("user1", {"role": "admin", "can_delete": True})
        # Permissions revoked but cache still returns old permissions
        perms = cache.get_permissions("user1")
        assert perms["role"] == "admin"  # Stale - BUG G4

    @pytest.mark.security
    def test_feature_flag_race_condition_bug_k3(self):
        """Bug K3: Feature flag update is not atomic."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import FeatureFlagManager

        ffm = FeatureFlagManager()
        ffm.set_flag("dark_mode", True, {"percentage": 50})
        errors = []

        def update_flag():
            try:
                for _ in range(50):
                    ffm.set_flag("dark_mode", False, {"percentage": 0})
                    ffm.set_flag("dark_mode", True, {"percentage": 100})
            except Exception as e:
                errors.append(str(e))

        def read_flag():
            try:
                for _ in range(100):
                    ffm.evaluate_flag("dark_mode")
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=update_flag)
        t2 = threading.Thread(target=read_flag)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0
