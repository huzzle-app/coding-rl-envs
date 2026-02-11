import unittest

from ionveil.policy import next_policy
from ionveil.queue import should_shed


class SecurityPipelineTests(unittest.TestCase):
    def test_policy_queue_alignment(self) -> None:
        self.assertEqual(next_policy("normal", 2), "watch")
        self.assertTrue(should_shed(15, 10, False))


if __name__ == "__main__":
    unittest.main()
