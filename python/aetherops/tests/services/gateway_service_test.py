import unittest

from services.gateway.service import (
    RouteNode,
    score_node,
    select_primary_node,
    build_route_chain,
    admission_control,
    fanout_targets,
)


class GatewayServiceTest(unittest.TestCase):
    def test_score_node(self) -> None:
        node = RouteNode(node_id="n1", latency_ms=50, error_rate=0.02, weight=1.0)
        # score = latency * weight + error_rate * 1000 = 50 + 20 = 70
        expected = 50 * 1.0 + 0.02 * 1000
        self.assertAlmostEqual(score_node(node), expected, places=2)

    def test_select_primary_node(self) -> None:
        nodes = [
            RouteNode("n1", latency_ms=100, error_rate=0.01),
            RouteNode("n2", latency_ms=20, error_rate=0.01),
            RouteNode("n3", latency_ms=50, error_rate=0.01),
        ]
        # Should select node with LOWEST score (min), not max
        primary = select_primary_node(nodes)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.node_id, "n2")

    def test_build_route_chain(self) -> None:
        nodes = [
            RouteNode("a", latency_ms=100, error_rate=0.0),
            RouteNode("b", latency_ms=50, error_rate=0.0),
            RouteNode("c", latency_ms=200, error_rate=0.0),
            RouteNode("d", latency_ms=10, error_rate=0.0),
            RouteNode("e", latency_ms=150, error_rate=0.0),
            RouteNode("f", latency_ms=300, error_rate=0.0),
        ]
        # max_hops=3 should return exactly 3 nodes, not 4
        chain = build_route_chain(nodes, max_hops=3)
        self.assertEqual(len(chain), 3)

    def test_admission_control(self) -> None:
        # At 85% load, regular priority should be rejected (threshold is 0.9)
        self.assertTrue(admission_control(current_load=85, max_capacity=100, priority=1))
        # At 91% load, should be rejected
        self.assertFalse(admission_control(current_load=91, max_capacity=100, priority=1))

    def test_fanout_targets(self) -> None:
        services = ["gateway", "identity", "intake", "mission"]
        result = fanout_targets(services, exclude=["gateway"])
        # Should be sorted for determinism
        self.assertEqual(result, sorted(result))
        self.assertNotIn("gateway", result)


if __name__ == "__main__":
    unittest.main()
