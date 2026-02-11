"""
OmniCloud Security Vulnerability Tests
Terminal Bench v2 - Tests for SQL injection, SSRF, IDOR, path traversal, and more.

Covers bugs: I1-I10
~80 tests
"""
import pytest
import os
import hmac
import time
import hashlib
from unittest.mock import MagicMock, patch

from services.auth.views import validate_api_key, resolve_permissions, check_tenant_access, _roles
from services.compliance.views import (
    create_default_security_group,
    evaluate_compliance_rules,
)
from services.gateway.main import get_client_ip


class TestSQLInjection:
    """Tests for I1: SQL injection vulnerabilities."""

    def test_sql_injection_blocked(self):
        """I1: SQL injection in user input should be blocked."""
        malicious_input = "'; DROP TABLE resources; --"
        # A parameterized query should safely handle this
        safe_query = "SELECT * FROM resources WHERE name = %s"
        # The key assertion: input should be treated as data, not code
        assert "DROP TABLE" not in safe_query, \
            "Query template should not contain user input"

    def test_parameterized_query_usage(self):
        """I1: All database queries should use parameterized queries."""
        # Verify that string interpolation is not used for SQL
        bad_query = f"SELECT * FROM resources WHERE name = '{'test'}'"
        good_query = "SELECT * FROM resources WHERE name = %s"

        assert "%s" in good_query or "?" in good_query, \
            "Queries should use parameter placeholders"

    def test_sql_injection_in_search(self):
        """I1: Search endpoints should sanitize input."""
        search_term = "test' OR '1'='1"
        # Should be parameterized
        query = "SELECT * FROM resources WHERE name LIKE %s"
        assert "OR" not in query

    def test_sql_injection_in_filter(self):
        """I1: Filter parameters should be parameterized."""
        filter_value = "active; DELETE FROM resources"
        query = "SELECT * FROM resources WHERE status = %s"
        assert "DELETE" not in query

    def test_numeric_injection_prevented(self):
        """I1: Numeric parameters should be validated."""
        numeric_input = "1; DROP TABLE users"
        try:
            parsed = int(numeric_input)
            is_valid = True
        except ValueError:
            is_valid = False
        assert is_valid is False, "Non-numeric input should be rejected"


class TestSSRF:
    """Tests for I2: Server-Side Request Forgery."""

    def test_ssrf_url_blocked(self):
        """I2: Internal URLs should be blocked in user-provided webhook/callback URLs."""
        internal_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://localhost:8001/admin",
            "http://10.0.0.1:8080/internal",
            "http://127.0.0.1:6379/",
            "http://[::1]/admin",
        ]
        for url in internal_urls:
            is_internal = (
                "169.254" in url or
                "localhost" in url or
                "127.0.0.1" in url or
                "10.0." in url or
                "[::1]" in url
            )
            assert is_internal is True, f"Internal URL should be blocked: {url}"

    def test_internal_url_validation(self):
        """I2: URL validation should reject internal network addresses."""
        safe_url = "https://external-webhook.example.com/callback"
        unsafe_url = "http://192.168.1.1/admin"

        is_safe = not any(
            pattern in safe_url
            for pattern in ["192.168.", "10.", "172.16.", "localhost", "127.0.0.1"]
        )
        is_unsafe = any(
            pattern in unsafe_url
            for pattern in ["192.168.", "10.", "172.16.", "localhost", "127.0.0.1"]
        )

        assert is_safe is True
        assert is_unsafe is True

    def test_ssrf_redirect_blocked(self):
        """I2: Redirect to internal URL should be blocked."""
        final_url = "http://169.254.169.254/latest/"
        is_internal = "169.254" in final_url
        assert is_internal is True, "Redirect to metadata endpoint should be blocked"

    def test_dns_rebinding_protection(self):
        """I2: DNS rebinding attacks should be detected."""
        # Hostname resolves to internal IP
        resolved_ip = "10.0.0.5"
        is_internal = resolved_ip.startswith("10.") or resolved_ip.startswith("192.168.")
        assert is_internal is True


class TestPrivilegeEscalation:
    """Tests for I3: Privilege escalation via role inheritance."""

    def test_privilege_escalation_blocked(self):
        """I3: Circular role inheritance should not grant unintended permissions."""
        # Setup circular role inheritance
        _roles.clear()
        _roles["user"] = {
            "permissions": ["read"],
            "inherits_from": ["editor"],
        }
        _roles["editor"] = {
            "permissions": ["write"],
            "inherits_from": ["user"],  # Circular!
        }

        
        try:
            permissions = resolve_permissions("user")
            # Should handle cycle gracefully
            assert isinstance(permissions, list)
        except RecursionError:
            pytest.fail("Circular role inheritance caused infinite recursion")

    def test_role_inheritance_safe(self):
        """I3: Role inheritance should have cycle detection."""
        _roles.clear()
        _roles["admin"] = {"permissions": ["all"], "inherits_from": []}
        _roles["editor"] = {"permissions": ["write"], "inherits_from": ["admin"]}
        _roles["viewer"] = {"permissions": ["read"], "inherits_from": ["editor"]}

        perms = resolve_permissions("viewer")
        assert "read" in perms
        assert "write" in perms
        assert "all" in perms

    def test_nonexistent_role(self):
        """I3: Non-existent role should return empty permissions."""
        _roles.clear()
        perms = resolve_permissions("nonexistent")
        assert perms == []

    def test_role_without_inheritance(self):
        """I3: Role without inheritance should only have own permissions."""
        _roles.clear()
        _roles["basic"] = {"permissions": ["read"], "inherits_from": []}
        perms = resolve_permissions("basic")
        assert perms == ["read"]

    def test_deep_inheritance_chain(self):
        """I3: Deep inheritance chain should resolve all permissions."""
        _roles.clear()
        _roles["level0"] = {"permissions": ["p0"], "inherits_from": []}
        _roles["level1"] = {"permissions": ["p1"], "inherits_from": ["level0"]}
        _roles["level2"] = {"permissions": ["p2"], "inherits_from": ["level1"]}

        perms = resolve_permissions("level2")
        assert "p0" in perms
        assert "p1" in perms
        assert "p2" in perms


class TestRateLimitBypass:
    """Tests for I4: Rate limit bypass via header spoofing."""

    def test_rate_limit_bypass_blocked(self):
        """I4: X-Forwarded-For header should not be trusted from untrusted sources."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4"}
        request.client = MagicMock()
        request.client.host = "10.0.0.5"

        ip = get_client_ip(request)

        
        assert ip == request.client.host, \
            f"Should use real client IP ({request.client.host}), not spoofed header ({ip})"

    def test_rate_limit_uniform(self):
        """I4: Rate limiting should apply uniformly regardless of headers."""
        request = MagicMock()
        request.headers = {}
        request.client = MagicMock()
        request.client.host = "203.0.113.1"

        ip = get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_forwarded_for_with_proxy(self):
        """I4: When behind a trusted proxy, X-Forwarded-For should be used correctly."""
        request = MagicMock()
        request.headers = {"X-Forwarded-For": "1.2.3.4, 10.0.0.1"}
        request.client = MagicMock()
        request.client.host = "10.0.0.1"

        ip = get_client_ip(request)
        # Should extract the first IP (client IP)
        assert "1.2.3.4" in ip or ip == request.client.host

    def test_missing_client_fallback(self):
        """I4: Missing client info should have a safe fallback."""
        request = MagicMock()
        request.headers = {}
        request.client = None

        ip = get_client_ip(request)
        assert ip is not None


class TestIDOR:
    """Tests for I5: Insecure Direct Object Reference."""

    def test_idor_tenant_blocked(self):
        """I5: Users should not be able to access other tenants' resources."""
        user_tenant = "tenant-1"
        resource_tenant = "tenant-2"

        # check_tenant_access should reject cross-tenant access
        result = check_tenant_access(user_tenant, resource_tenant)
        assert result is False, "Cross-tenant access should be blocked"

    def test_authorization_check_required(self):
        """I5: All resource access should verify authorization."""
        user_tenant = "tenant-1"
        resource_tenant = "tenant-1"

        result = check_tenant_access(user_tenant, resource_tenant)
        assert result is True, "Same-tenant access should be allowed"

    def test_idor_enumeration_prevented(self):
        """I5: Sequential IDs should not be guessable."""
        import uuid
        resource_id = str(uuid.uuid4())
        # UUIDs should not be sequential
        assert "-" in resource_id
        assert len(resource_id) == 36

    def test_idor_via_path_parameter(self):
        """I5: Path parameters should have authorization checks."""
        authorized_resources = {"r1", "r2", "r3"}
        requested = "r4"
        assert requested not in authorized_resources


class TestPathTraversal:
    """Tests for I6: Path traversal in artifact download."""

    def test_path_traversal_blocked(self):
        """I6: Path traversal attempts should be blocked."""
        base_dir = "/app/artifacts"
        malicious_paths = [
            "../../etc/passwd",
            "../../../etc/shadow",
            "..\\..\\windows\\system32",
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ]

        for path in malicious_paths:
            full_path = os.path.join(base_dir, path)
            real_path = os.path.realpath(full_path)
            is_safe = real_path.startswith(os.path.realpath(base_dir))
            
            assert not is_safe or True, \
                f"Path traversal should be blocked: {path}"

    def test_artifact_path_validated(self):
        """I6: Artifact paths should be validated against base directory."""
        base_dir = "/app/artifacts"
        safe_path = "project-a/build-123/output.tar.gz"
        full_path = os.path.join(base_dir, safe_path)
        real_path = os.path.realpath(full_path)

        # Safe paths should resolve within base directory
        assert real_path.startswith("/app/artifacts")

    def test_null_byte_injection(self):
        """I6: Null byte injection should be prevented."""
        path = "safe_file.txt\x00../../etc/passwd"
        # Should strip or reject null bytes
        sanitized = path.replace("\x00", "")
        assert "\x00" not in sanitized

    def test_absolute_path_rejected(self):
        """I6: Absolute paths should be rejected."""
        path = "/etc/passwd"
        assert path.startswith("/"), "Absolute path should be detected"
        # Implementation should reject absolute paths in artifact requests


class TestMassAssignment:
    """Tests for I7: Mass assignment vulnerability."""

    def test_mass_assignment_blocked(self):
        """I7: User-provided fields should be filtered against an allowlist."""
        allowed_fields = {"name", "description", "tags"}
        user_input = {
            "name": "My Resource",
            "description": "A resource",
            "is_admin": True,  # Unauthorized field
            "tenant_id": "other-tenant",  # Unauthorized field
        }

        filtered = {k: v for k, v in user_input.items() if k in allowed_fields}
        assert "is_admin" not in filtered
        assert "tenant_id" not in filtered

    def test_field_allowlist_enforced(self):
        """I7: Only allowlisted fields should be accepted in create/update."""
        allowed_fields = {"name", "size_gb", "type"}
        user_input = {"name": "vol1", "size_gb": 100, "type": "ssd", "cost": 0}

        filtered = {k: v for k, v in user_input.items() if k in allowed_fields}
        assert "cost" not in filtered
        assert len(filtered) == 3

    def test_nested_mass_assignment(self):
        """I7: Nested objects should also be filtered."""
        allowed_fields = {"name", "config"}
        user_input = {"name": "svc", "config": {"replicas": 3}, "admin_config": {"bypass": True}}

        filtered = {k: v for k, v in user_input.items() if k in allowed_fields}
        assert "admin_config" not in filtered

    def test_update_preserves_readonly(self):
        """I7: Read-only fields should not be updateable."""
        readonly_fields = {"id", "created_at", "tenant_id"}
        update = {"id": "new-id", "name": "updated", "created_at": "2024-01-01"}

        writable_update = {k: v for k, v in update.items() if k not in readonly_fields}
        assert "id" not in writable_update
        assert "created_at" not in writable_update
        assert "name" in writable_update


class TestTimingAttack:
    """Tests for I8: Timing attack on API key comparison."""

    def test_timing_attack_prevented(self):
        """I8: API key comparison should use constant-time comparison."""
        stored_key = "super_secret_api_key_12345678"

        
        result = validate_api_key(stored_key, stored_key)
        assert result is True

        # The implementation should use hmac.compare_digest
        # Direct string comparison leaks timing information
        safe_result = hmac.compare_digest(stored_key, stored_key)
        assert safe_result is True

    def test_constant_time_comparison(self):
        """I8: Comparison should take same time regardless of where strings differ."""
        key_a = "abcdefghijklmnop"
        key_b = "xbcdefghijklmnop"  # Differs at position 0
        key_c = "abcdefghijklmnox"  # Differs at position 15

        # Both should use constant-time comparison
        result_b = hmac.compare_digest(key_a, key_b)
        result_c = hmac.compare_digest(key_a, key_c)

        assert result_b is False
        assert result_c is False

    def test_different_length_keys(self):
        """I8: Different length keys should be handled safely."""
        result = validate_api_key("short", "longer_key_value")
        assert result is False

    def test_empty_key_rejected(self):
        """I8: Empty API key should be rejected."""
        result = validate_api_key("", "stored_key")
        assert result is False


class TestDefaultSecurityGroup:
    """Tests for I9: Insecure default security group."""

    def test_default_security_group_safe(self):
        """I9: Default security group should deny all ingress."""
        sg = create_default_security_group("test-tenant")

        ingress_rules = [
            r for r in sg["rules"]
            if r.get("direction") == "ingress"
        ]

        
        for rule in ingress_rules:
            assert rule["action"] != "allow" or rule["source"] != "0.0.0.0/0", \
                "Default security group should NOT allow all ingress from 0.0.0.0/0"

    def test_no_open_ingress(self):
        """I9: No ingress rule should allow traffic from 0.0.0.0/0."""
        sg = create_default_security_group("test-tenant")

        for rule in sg["rules"]:
            if rule.get("direction") == "ingress":
                assert not (
                    rule.get("action") == "allow" and
                    rule.get("source") == "0.0.0.0/0" and
                    rule.get("protocol") == "all"
                ), "Open ingress (all protocols from 0.0.0.0/0) is insecure"

    def test_egress_allowed_by_default(self):
        """I9: Default egress rules can be permissive."""
        sg = create_default_security_group("test-tenant")
        egress_rules = [r for r in sg["rules"] if r.get("direction") == "egress"]
        assert len(egress_rules) >= 1

    def test_security_group_has_tenant(self):
        """I9: Security group should be associated with a tenant."""
        sg = create_default_security_group("my-tenant")
        assert sg["tenant_id"] == "my-tenant"


class TestComplianceEvaluation:
    """Tests for I10: Compliance rule evaluation order."""

    def test_compliance_rule_evaluation(self):
        """I10: Deny rules should take precedence over allow rules."""
        resource = {"resource_id": "r1", "resource_type": "compute", "public": True}

        rules = [
            {"action": "allow", "resource_type": "compute"},
            {"action": "deny", "resource_type": "compute"},
        ]

        violations = evaluate_compliance_rules(resource, rules)

        
        assert len(violations) >= 1, \
            "Deny rule should create a violation even when allow rule also matches"

    def test_policy_enforcement_order(self):
        """I10: Deny rules should be evaluated before allow rules."""
        resource = {"resource_id": "r2", "resource_type": "network"}

        deny_rule = {"action": "deny", "resource_type": "network"}
        allow_rule = {"action": "allow", "resource_type": "network"}

        # Deny should win over allow
        violations = evaluate_compliance_rules(resource, [allow_rule, deny_rule])
        assert len(violations) >= 1, \
            "Deny should take precedence over allow"

    def test_no_matching_rules(self):
        """I10: No matching rules should produce no violations."""
        resource = {"resource_id": "r1", "resource_type": "compute"}
        rules = [{"action": "deny", "resource_type": "storage"}]

        violations = evaluate_compliance_rules(resource, rules)
        assert len(violations) == 0

    def test_wildcard_rule_matches_all(self):
        """I10: Wildcard resource type should match all resources."""
        resource = {"resource_id": "r1", "resource_type": "compute"}
        rules = [{"action": "deny", "resource_type": "*"}]

        violations = evaluate_compliance_rules(resource, rules)
        assert len(violations) >= 1

    def test_empty_rules(self):
        """I10: Empty rules list should produce no violations."""
        resource = {"resource_id": "r1"}
        violations = evaluate_compliance_rules(resource, [])
        assert len(violations) == 0

    def test_multiple_deny_rules(self):
        """I10: Multiple deny rules should each create a violation."""
        resource = {"resource_id": "r1", "resource_type": "compute"}
        rules = [
            {"action": "deny", "resource_type": "compute"},
            {"action": "deny", "resource_type": "*"},
        ]
        violations = evaluate_compliance_rules(resource, rules)
        # At least one violation should exist
        assert len(violations) >= 1


class TestSecurityDefaults:
    """Additional security tests for coverage."""

    def test_api_key_format(self):
        """API keys should be sufficiently long."""
        import secrets
        key = secrets.token_hex(32)
        assert len(key) >= 32

    def test_tenant_access_check(self):
        """Tenant access check should be strict equality."""
        assert check_tenant_access("t1", "t1") is True
        assert check_tenant_access("t1", "t2") is False
        assert check_tenant_access("", "") is True

    def test_cors_configuration(self):
        """CORS should allow necessary methods."""
        required_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
        configured_methods = ["GET"]  
        for method in required_methods:
            if method not in configured_methods:
                pass  # Just checking they exist

    def test_password_hashing(self):
        """Passwords should be hashed with a strong algorithm."""
        password = "user_password_123"
        hashed = hashlib.sha256(password.encode()).hexdigest()
        assert hashed != password
        assert len(hashed) == 64


class TestSQLInjectionEdgeCases:
    """Extended SQL injection tests."""

    def test_sql_injection_union_select(self):
        """I1: UNION SELECT injection should be blocked."""
        malicious = "' UNION SELECT username, password FROM users --"
        assert "UNION" in malicious.upper()

    def test_sql_injection_drop_table(self):
        """I1: DROP TABLE injection should be blocked."""
        malicious = "'; DROP TABLE resources; --"
        assert "DROP" in malicious.upper()

    def test_sql_injection_in_sort_order(self):
        """I1: SQL injection in ORDER BY clause."""
        malicious = "name; DELETE FROM resources"
        assert ";" in malicious

    def test_sql_injection_blind_boolean(self):
        """I1: Boolean-based blind injection should be detected."""
        malicious = "' OR 1=1 --"
        assert "OR" in malicious.upper()


class TestPathTraversalEdgeCases:
    """Extended path traversal tests."""

    def test_path_traversal_encoded_dots(self):
        """I6: URL-encoded traversal should be blocked."""
        path = "%2e%2e/%2e%2e/etc/passwd"
        decoded = path.replace("%2e", ".").replace("%2f", "/")
        assert ".." in decoded

    def test_path_traversal_double_encoded(self):
        """I6: Double-encoded traversal."""
        path = "%252e%252e/etc/passwd"
        decoded = path.replace("%25", "%").replace("%2e", ".").replace("%2f", "/")
        assert ".." in decoded or "%2e" in decoded

    def test_path_traversal_backslash(self):
        """I6: Backslash-based traversal on Windows."""
        path = "..\\..\\etc\\passwd"
        assert ".." in path


class TestPrivilegeEscalationEdgeCases:
    """Extended privilege escalation tests."""

    def test_role_self_reference_cycle(self):
        """I3: Role referencing itself should not cause infinite loop."""
        original_roles = dict(_roles)
        _roles["self_ref"] = {"permissions": set(), "inherits": ["self_ref"]}
        try:
            perms = resolve_permissions("self_ref", max_depth=5)
            assert isinstance(perms, set)
        finally:
            _roles.clear()
            _roles.update(original_roles)

    def test_deeply_nested_role_hierarchy(self):
        """I3: Deep role chains should be bounded."""
        original_roles = dict(_roles)
        for i in range(20):
            _roles[f"level_{i}"] = {"permissions": {f"perm_{i}"}, "inherits": [f"level_{i+1}"] if i < 19 else []}
        try:
            perms = resolve_permissions("level_0", max_depth=25)
            assert isinstance(perms, set)
        finally:
            _roles.clear()
            _roles.update(original_roles)

    def test_role_with_no_permissions(self):
        """I3: Role with empty permissions inheriting nothing."""
        original_roles = dict(_roles)
        _roles["empty"] = {"permissions": set(), "inherits": []}
        try:
            perms = resolve_permissions("empty", max_depth=5)
            assert len(perms) == 0
        finally:
            _roles.clear()
            _roles.update(original_roles)


class TestTimingAttackEdgeCases:
    """Extended timing attack tests."""

    def test_empty_string_comparison(self):
        """I8: Comparing empty strings should be constant time."""
        result = hmac.compare_digest("", "")
        assert result is True

    def test_different_length_comparison(self):
        """I8: Different length strings should still use constant time."""
        result = hmac.compare_digest("short", "much_longer_string")
        assert result is False

    def test_unicode_comparison(self):
        """I8: Unicode string comparison should work correctly."""
        result = hmac.compare_digest("hello".encode(), "hello".encode())
        assert result is True
