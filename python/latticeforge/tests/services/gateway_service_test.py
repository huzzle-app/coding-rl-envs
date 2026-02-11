import unittest

from services.gateway.service import (
    RouteNode,
    admission_control,
    build_route_chain,
    select_primary_node,
)


class GatewayServiceTest(unittest.TestCase):
    def test_select_primary_prefers_lowest_score(self) -> None:
        nodes = [
            RouteNode("planner", "planner-a", latency_ms=40, queue_depth=2, saturation=0.2),
            RouteNode("planner", "planner-b", latency_ms=140, queue_depth=12, saturation=0.8),
        ]
        chosen = select_primary_node(nodes)
        self.assertEqual(chosen.endpoint, "planner-a")

    def test_build_route_chain(self) -> None:
        topology = {
            "intake": [RouteNode("intake", "intake-a", 20, 2, 0.1)],
            "planner": [RouteNode("planner", "planner-a", 60, 2, 0.2)],
            "policy": [RouteNode("policy", "policy-a", 45, 2, 0.1)],
            "orbit": [RouteNode("orbit", "orbit-a", 80, 3, 0.2)],
        }
        chain = build_route_chain("orbit-adjust", topology)
        self.assertEqual([node.service for node in chain], ["intake", "planner", "policy", "orbit"])

    def test_admission_control_hard_limit(self) -> None:
        out = admission_control(backlog=90, inflight=20, hard_limit=100)
        self.assertFalse(out["accepted"])
        self.assertEqual(out["reason"], "hard-limit")


if __name__ == "__main__":
    unittest.main()
