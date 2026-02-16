import hmac
import inspect
import unittest
from hashlib import sha256

from aetherops.security import (
    PermissionMatrix,
    TokenStore,
    is_allowed_origin,
    requires_mfa,
    sanitize_target_path,
    validate_command_signature,
    verify_manifest,
)


class SecurityTest(unittest.TestCase):
    def test_requires_mfa(self) -> None:
        self.assertTrue(requires_mfa("flight-director", 1))
        self.assertTrue(requires_mfa("operator", 5))
        self.assertFalse(requires_mfa("operator", 2))

    def test_validate_signature(self) -> None:
        secret = "top-secret"
        cmd = "deploy burn"
        sig = hmac.new(secret.encode(), cmd.encode(), sha256).hexdigest()
        self.assertTrue(validate_command_signature(cmd, sig, secret))

    def test_sanitize_path(self) -> None:
        self.assertEqual(sanitize_target_path("logs/../logs/out.txt"), "logs/out.txt")
        with self.assertRaises(ValueError):
            sanitize_target_path("../../etc/passwd")


class SecurityBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in security.py."""

    def test_verify_manifest_uses_compare_digest(self) -> None:
        src = inspect.getsource(verify_manifest)
        self.assertIn("compare_digest", src)

    def test_is_allowed_origin_case_insensitive(self) -> None:
        allowed = {"https://example.com"}
        self.assertTrue(is_allowed_origin("HTTPS://EXAMPLE.COM", allowed))

    def test_token_store_valid_immediately(self) -> None:
        store = TokenStore()
        token = store.issue("user1", "operator", ttl_s=3600)
        result = store.validate(token)
        self.assertIsNotNone(result)

    def test_permission_matrix_check_all_requires_all(self) -> None:
        pm = PermissionMatrix()
        pm.grant("op-1", "read")
        pm.grant("op-1", "write")
        self.assertFalse(pm.check_all("op-1", {"read", "write", "delete"}))


if __name__ == "__main__":
    unittest.main()
