import unittest

from aetherops.routing import choose_ground_station


class RoutingPartitionChaosTest(unittest.TestCase):
    def test_blackout_fallback(self) -> None:
        chosen = choose_ground_station(
            ["sg-1", "sg-2", "sg-3"],
            latency_ms={"sg-1": 45, "sg-2": 90, "sg-3": 70},
            blackout=["sg-1"],
        )
        self.assertEqual(chosen, "sg-3")


if __name__ == "__main__":
    unittest.main()
