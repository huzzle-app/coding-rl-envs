import unittest

from latticeforge.routing import capacity_headroom, choose_ground_station, route_bundle


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


if __name__ == "__main__":
    unittest.main()
