import unittest

from services.policy.service import (
    PolicyDecision,
    evaluate_policy_gate,
    enforce_dual_control,
    risk_band,
    compute_compliance_score,
)


class PolicyServiceTest(unittest.TestCase):
    def test_evaluate_policy_gate_comms_degraded(self) -> None:
        # With comms_degraded=True and risk >= 60, should be rejected
        decision = evaluate_policy_gate(
            risk_score=65.0, comms_degraded=True, has_mfa=True, priority=1,
        )
        self.assertFalse(decision.approved)

    def test_enforce_dual_control_case(self) -> None:
        # Same operator with different case should be rejected
        result = enforce_dual_control("Alice", "alice", "launch")
        self.assertFalse(result)

    def test_risk_band(self) -> None:
        # 75 should be "high", not "critical"
        self.assertEqual(risk_band(75), "high")
        # 85 should be "critical"
        self.assertEqual(risk_band(85), "critical")

    def test_compute_compliance_score(self) -> None:
        # resolution_rate = 8/10 = 0.8, sla_met_pct = 90
        # score = 0.8 * 60 + 90 * 40 / 100 = 48 + 36 = 84
        score = compute_compliance_score(8, 10, 90.0)
        expected = round(0.8 * 60 + 90.0 * 40 / 100, 2)
        self.assertAlmostEqual(score, expected, places=1)


if __name__ == "__main__":
    unittest.main()
