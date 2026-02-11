import unittest

from ionveil.policy import next_policy


class PolicyTests(unittest.TestCase):
    def test_next_policy_escalates(self) -> None:
        self.assertEqual(next_policy("watch", 3), "restricted")


if __name__ == "__main__":
    unittest.main()
