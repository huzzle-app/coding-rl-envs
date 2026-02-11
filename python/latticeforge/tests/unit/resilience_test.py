import unittest

from latticeforge.resilience import choose_failover_region, classify_outage, replay_budget, retry_backoff


class ResilienceTest(unittest.TestCase):
    def test_retry_backoff_caps(self) -> None:
        self.assertEqual(retry_backoff(1), 80)
        self.assertEqual(retry_backoff(8, cap_ms=1000), 1000)

    def test_choose_failover_region(self) -> None:
        region = choose_failover_region("us-east", ["us-east", "us-west", "eu-central"], ["us-west"])
        self.assertEqual(region, "eu-central")

    def test_replay_budget(self) -> None:
        self.assertEqual(replay_budget(100, 3), 32)
        self.assertEqual(replay_budget(0, 9), 0)

    def test_classify_outage(self) -> None:
        self.assertEqual(classify_outage(5, 1), "minor")
        self.assertEqual(classify_outage(50, 3), "major")


if __name__ == "__main__":
    unittest.main()
