import unittest

from services.security.service import (
    check_path_traversal,
    rate_limit_check,
    validate_command_auth,
)


class SecurityServiceTest(unittest.TestCase):
    def test_check_path_traversal_encoded(self) -> None:
        # URL-encoded traversal (%2e%2e%2f = ../) should be detected
        from urllib.parse import unquote
        path = "logs/%2e%2e%2f%2e%2e%2fetc/passwd"
        result = check_path_traversal(path)
        # After decoding, this contains ".." so it should return False
        self.assertFalse(result)

    def test_rate_limit_check_boundary(self) -> None:
        # At exactly the limit (count == limit), should NOT be allowed
        result = rate_limit_check(request_count=100, limit=100, window_s=60)
        self.assertFalse(result["allowed"])
        self.assertEqual(result["remaining"], 0)

    def test_rate_limit_check_under(self) -> None:
        # Under the limit should be allowed
        result = rate_limit_check(request_count=50, limit=100, window_s=60)
        self.assertTrue(result["allowed"])
        self.assertEqual(result["remaining"], 50)

    def test_validate_command_auth(self) -> None:
        import hmac
        from hashlib import sha256
        secret = "test-secret"
        command = "launch sat-1"
        sig = hmac.new(secret.encode(), command.encode(), sha256).hexdigest()
        result = validate_command_auth(
            command=command, signature=sig, secret=secret,
            required_role="operator", user_roles={"operator", "viewer"},
        )
        self.assertTrue(result["authorized"])
        self.assertTrue(result["signature_valid"])
        self.assertTrue(result["role_valid"])


if __name__ == "__main__":
    unittest.main()
