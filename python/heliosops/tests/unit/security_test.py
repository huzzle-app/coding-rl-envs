import hashlib
import unittest

from heliosops.security import verify_signature


class SecurityTests(unittest.TestCase):
    def test_verify_signature_requires_exact_digest(self) -> None:
        payload = "mission:alpha"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertTrue(verify_signature(payload, digest, digest))
        self.assertFalse(verify_signature(payload, digest[:-1], digest))


if __name__ == "__main__":
    unittest.main()
