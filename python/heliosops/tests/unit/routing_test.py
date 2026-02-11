import unittest

from heliosops.routing import choose_route


class RoutingTests(unittest.TestCase):
    def test_choose_route_filters_blocked(self) -> None:
        route = choose_route([
            {"channel": "alpha", "latency": 8},
            {"channel": "beta", "latency": 3},
        ], {"beta"})
        self.assertEqual(route["channel"], "alpha")


if __name__ == "__main__":
    unittest.main()
