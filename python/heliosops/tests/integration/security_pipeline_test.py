import unittest

from heliosops.policy import next_policy
from heliosops.queue import should_shed


class SecurityPipelineTests(unittest.TestCase):
    def test_policy_queue_alignment(self) -> None:
        self.assertEqual(next_policy("normal", 2), "watch")
        self.assertTrue(should_shed(15, 10, False))

    def test_escalation_does_not_skip_levels(self) -> None:
        # Policy should step through levels, not skip
        pol = next_policy("normal", 3)
        self.assertEqual(pol, "watch", "normal should go to watch, not skip to restricted")


if __name__ == "__main__":
    unittest.main()
