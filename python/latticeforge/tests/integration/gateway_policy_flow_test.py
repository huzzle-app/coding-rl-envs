import unittest

from services.gateway.service import RouteNode, route_with_risk_assessment


class GatewayRiskRoutingTest(unittest.TestCase):
    def _topology(self) -> dict[str, list[RouteNode]]:
        return {
            "intake": [
                RouteNode("intake", "intake-a", latency_ms=30, queue_depth=1, saturation=0.1),
                RouteNode("intake", "intake-b", latency_ms=50, queue_depth=5, saturation=0.8),
            ],
            "policy": [
                RouteNode("policy", "policy-a", latency_ms=40, queue_depth=2, saturation=0.2),
            ],
            "resilience": [
                RouteNode("resilience", "res-a", latency_ms=60, queue_depth=3, saturation=0.7),
                RouteNode("resilience", "res-b", latency_ms=35, queue_depth=1, saturation=0.1),
            ],
            "audit": [
                RouteNode("audit", "audit-a", latency_ms=25, queue_depth=1, saturation=0.1),
            ],
        }

    def test_degraded_comms_blocks_saturated(self) -> None:
        result = route_with_risk_assessment(
            intent="replay-window",
            topology=self._topology(),
            risk_score=60.0,
            comms_degraded=True,
        )
        self.assertGreater(result["blocked_count"], 0)

    def test_normal_comms_moderate_risk(self) -> None:
        result = route_with_risk_assessment(
            intent="replay-window",
            topology=self._topology(),
            risk_score=60.0,
            comms_degraded=False,
        )
        self.assertEqual(result["blocked_count"], 0)

    def test_high_risk_triggers_blocking(self) -> None:
        result = route_with_risk_assessment(
            intent="replay-window",
            topology=self._topology(),
            risk_score=75.0,
            comms_degraded=False,
        )
        self.assertGreater(result["blocked_count"], 0)

    def test_degraded_more_protective(self) -> None:
        normal = route_with_risk_assessment(
            intent="replay-window",
            topology=self._topology(),
            risk_score=60.0,
            comms_degraded=False,
        )
        degraded = route_with_risk_assessment(
            intent="replay-window",
            topology=self._topology(),
            risk_score=60.0,
            comms_degraded=True,
        )
        self.assertGreater(degraded["blocked_count"], normal["blocked_count"])

    def test_route_chain_complete(self) -> None:
        result = route_with_risk_assessment(
            intent="replay-window",
            topology=self._topology(),
            risk_score=30.0,
            comms_degraded=False,
        )
        self.assertEqual(result["services"], ["intake", "policy", "resilience", "audit"])
        self.assertTrue(result["routed"])


if __name__ == "__main__":
    unittest.main()
