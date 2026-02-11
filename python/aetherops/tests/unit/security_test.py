import hmac
import unittest
from hashlib import sha256

from aetherops.security import requires_mfa, sanitize_target_path, validate_command_signature


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


if __name__ == "__main__":
    unittest.main()
