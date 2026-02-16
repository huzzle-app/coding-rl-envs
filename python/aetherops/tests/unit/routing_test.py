import unittest

from aetherops.routing import (
    RouteTable,
    capacity_headroom,
    channel_score,
    choose_ground_station,
    compute_link_budget,
    estimate_transit_time,
    route_bundle,
    weighted_route_score,
)


class RoutingTest(unittest.TestCase):
    def test_choose_ground_station(self) -> None:
        station = choose_ground_station(["sg-1", "sg-2"], {"sg-1": 90, "sg-2": 60}, blackout=[])
        self.assertEqual(station, "sg-2")

    def test_choose_ground_station_none_available(self) -> None:
        with self.assertRaises(ValueError):
            choose_ground_station(["sg-1"], {"sg-1": 50}, blackout=["sg-1"])

    def test_route_bundle_congestion_order(self) -> None:
        routed = route_bundle({"f": ["a", "b", "c"]}, {"b": 0.9, "c": 0.2, "a": 0.3})
        self.assertEqual(routed["f"], ["c", "a", "b"])

    def test_capacity_headroom(self) -> None:
        headroom = capacity_headroom({"a": 10, "b": 5}, {"a": 7, "b": 5})
        self.assertEqual(headroom, {"a": 3, "b": 0})


class RoutingBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in routing.py."""

    def test_channel_score_drop_weight_complement(self) -> None:
        score = channel_score(latency_ms=100, drop_rate=0.05)
        expected = round(0.7 * 0.1 + 0.3 * 0.05, 4)
        self.assertAlmostEqual(score, expected, places=3)

    def test_route_table_sorted_destinations(self) -> None:
        rt = RouteTable()
        rt.add_route("zebra", ["h1"])
        rt.add_route("alpha", ["h2"])
        dests = rt.all_destinations()
        self.assertEqual(dests, sorted(dests))

    def test_weighted_route_score_bandwidth_lowers(self) -> None:
        low_bw = weighted_route_score(100, 10.0, 0.99)
        high_bw = weighted_route_score(100, 90.0, 0.99)
        self.assertLess(high_bw, low_bw)

    def test_estimate_transit_time_per_hop_overhead(self) -> None:
        result = estimate_transit_time(hops=3, latency_per_hop_ms=10, overhead_ms=5)
        self.assertEqual(result, 45)

    def test_compute_link_budget_snr_rounds_not_truncates(self) -> None:
        result = compute_link_budget(10.0, 5.0, 111.5, noise_floor_dbm=-100.0)
        self.assertTrue(result["link_viable"])


if __name__ == "__main__":
    unittest.main()
