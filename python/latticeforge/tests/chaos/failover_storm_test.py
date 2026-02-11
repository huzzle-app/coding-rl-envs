import unittest

from latticeforge.resilience import choose_failover_region


class FailoverStormChaosTest(unittest.TestCase):
    def test_failover_avoids_degraded_regions(self) -> None:
        region = choose_failover_region("us-east", ["us-east", "us-west", "eu-central"], degraded=["us-west"])
        self.assertEqual(region, "eu-central")


if __name__ == "__main__":
    unittest.main()
