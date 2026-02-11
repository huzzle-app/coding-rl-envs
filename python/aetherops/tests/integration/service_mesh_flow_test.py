import unittest
from datetime import datetime, timezone

from services.intake.service import validate_command_shape, normalize_intake_batch
from services.policy.service import evaluate_policy_gate
from services.audit.service import AuditEvent, AuditLedger, is_compliant_audit_trail
from services.gateway.service import RouteNode, score_node, select_primary_node


class IntakeToPolicyPipelineTest(unittest.TestCase):
    def test_intake_to_policy_pipeline(self) -> None:
        """Validate a command through intake, then run it through policy gate."""
        raw = {
            "command_id": "c1",
            "satellite_id": "sat-1",
            "intent": "maneuver",
            "issued_by": "op1",
            "signature": "sig123",
            "deadline": "2026-06-01T00:00:00Z",
            "trace_id": "t1",
        }
        errors = validate_command_shape(raw)
        # With trace_id present and all required fields, no errors expected
        self.assertEqual(len(errors), 0)

        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        commands, batch_errors = normalize_intake_batch([raw], now)
        self.assertEqual(len(commands), 1)
        self.assertEqual(len(batch_errors), 0)

        # Run through policy gate with moderate risk
        decision = evaluate_policy_gate(
            risk_score=50.0, comms_degraded=False, has_mfa=True, priority=3,
        )
        self.assertTrue(decision.approved)


class AuditComplianceFlowTest(unittest.TestCase):
    def test_audit_compliance_flow(self) -> None:
        """Create audit trail and verify compliance check."""
        ledger = AuditLedger()
        ledger.append(AuditEvent(
            event_id="e1", timestamp=datetime(2026, 1, 1),
            service="gateway", action="route", operator_id="op1",
        ))
        ledger.append(AuditEvent(
            event_id="e2", timestamp=datetime(2026, 1, 1),
            service="identity", action="auth", operator_id="op1",
        ))
        ledger.append(AuditEvent(
            event_id="e3", timestamp=datetime(2026, 1, 1),
            service="policy", action="evaluate", operator_id="op1",
        ))

        required = {"gateway", "identity", "policy"}
        # All required services have events in the ledger
        self.assertTrue(is_compliant_audit_trail(ledger, required))

        # If we require a service not in the ledger, should fail
        required_extended = {"gateway", "identity", "policy", "security"}
        self.assertFalse(is_compliant_audit_trail(ledger, required_extended))


class GatewayRoutingFlowTest(unittest.TestCase):
    def test_gateway_routing_flow(self) -> None:
        """Score nodes and select primary, verifying correct selection."""
        nodes = [
            RouteNode("node-us-east", latency_ms=30, error_rate=0.01),
            RouteNode("node-eu-west", latency_ms=80, error_rate=0.005),
            RouteNode("node-ap-south", latency_ms=120, error_rate=0.02),
        ]

        # Score each node: lower score is better
        scores = {n.node_id: score_node(n) for n in nodes}
        # node-us-east: 30*1 + 0.01*1000 = 40
        # node-eu-west: 80*1 + 0.005*1000 = 85
        # node-ap-south: 120*1 + 0.02*1000 = 140
        self.assertAlmostEqual(scores["node-us-east"], 40.0, places=1)

        # Primary should be the node with lowest score
        primary = select_primary_node(nodes)
        self.assertIsNotNone(primary)
        self.assertEqual(primary.node_id, "node-us-east")


if __name__ == "__main__":
    unittest.main()
