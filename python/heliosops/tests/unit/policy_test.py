import unittest

from heliosops.policy import next_policy


class PolicyTests(unittest.TestCase):
    def test_next_policy_escalates(self) -> None:
        self.assertEqual(next_policy("watch", 3), "restricted")

    def test_normal_to_watch_escalation(self) -> None:
        self.assertEqual(next_policy("normal", 2), "watch",
                         "normal with burst=2 should escalate to watch")

    def test_watch_stepdown_on_zero_burst(self) -> None:
        self.assertEqual(next_policy("watch", 0), "normal",
                         "watch with burst=0 should step down to normal")


if __name__ == "__main__":
    unittest.main()
