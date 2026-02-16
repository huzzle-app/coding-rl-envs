import hashlib
import unittest

from heliosops.security import verify_signature


class SecurityTests(unittest.TestCase):
    def test_verify_signature_requires_exact_digest(self) -> None:
        payload = "mission:alpha"
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        self.assertTrue(verify_signature(payload, digest, digest))
        self.assertFalse(verify_signature(payload, digest[:-1], digest))

    def test_verify_signature_mismatched_payload(self) -> None:
        payload = "data:123"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        other_digest = hashlib.sha256(b"other").hexdigest()
        self.assertFalse(verify_signature(payload, other_digest, digest),
                         "Mismatched payload/signature must not verify")

    def test_verify_signature_truncated_fails(self) -> None:
        payload = "manifest:test"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        self.assertFalse(verify_signature(payload, digest[1:], digest),
                         "Truncated signature must not verify")


if __name__ == "__main__":
    unittest.main()
