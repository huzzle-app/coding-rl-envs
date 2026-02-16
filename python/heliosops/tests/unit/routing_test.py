import unittest

from heliosops.routing import choose_route


class RoutingTests(unittest.TestCase):
    def test_choose_route_filters_blocked(self) -> None:
        route = choose_route([
            {"channel": "alpha", "latency": 8},
            {"channel": "beta", "latency": 3},
        ], {"beta"})
        self.assertEqual(route["channel"], "alpha")

    def test_choose_route_picks_lowest_latency(self) -> None:
        route = choose_route([
            {"channel": "slow", "latency": 20},
            {"channel": "fast", "latency": 1},
            {"channel": "mid", "latency": 10},
        ], set())
        self.assertEqual(route["channel"], "fast")

    def test_choose_route_all_blocked_returns_none(self) -> None:
        result = choose_route(
            [{"channel": "x", "latency": 1}],
            {"x"},
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
