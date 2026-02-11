import hmac
import unittest
from hashlib import sha256

from aetherops.security import requires_mfa, validate_command_signature


class SecurityPipelineIntegrationTest(unittest.TestCase):
    def test_signature_and_mfa(self) -> None:
        secret = "s3cr3t"
        command = "deploy mission-alpha"
        signature = hmac.new(secret.encode(), command.encode(), sha256).hexdigest()
        self.assertTrue(validate_command_signature(command, signature, secret))
        self.assertTrue(requires_mfa("security", severity=2))


if __name__ == "__main__":
    unittest.main()
