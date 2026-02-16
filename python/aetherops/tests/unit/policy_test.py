import unittest
from datetime import datetime

from aetherops.models import BurnPlan, IncidentTicket, OrbitalSnapshot
from aetherops.orbit import allocate_burns
from aetherops.policy import (
    PolicyEngine,
    compliance_tags,
    compound_risk,
    escalation_band,
    evaluate_risk,
    requires_hold,
    sla_percentage,
)
from tests.test_helper import sample_incidents, sample_snapshot, sample_windows


class PolicyTest(unittest.TestCase):
    def test_risk_score_increases_with_load(self) -> None:
        snapshot = sample_snapshot()
        low = evaluate_risk(snapshot, allocate_burns(sample_windows(), 0.3), [])
        high = evaluate_risk(snapshot, allocate_burns(sample_windows(), 1.5), sample_incidents())
        self.assertAlmostEqual(low, 2.25, places=2)
        self.assertAlmostEqual(high, 23.25, places=2)

    def test_requires_hold(self) -> None:
        self.assertTrue(requires_hold(70.0, False))
        self.assertTrue(requires_hold(50.0, True))
        self.assertFalse(requires_hold(40.0, False))

    def test_compliance_tags(self) -> None:
        self.assertEqual(compliance_tags(72.0), ("review-required", "board-notify"))
        self.assertEqual(compliance_tags(10.0), ("routine", "auto-approved"))


class PolicyBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in policy.py."""

    def test_escalate_advances_one_level(self) -> None:
        engine = PolicyEngine()
        engine.escalate()
        self.assertEqual(engine.current_level, "yellow")

    def test_sla_percentage_full_compliance(self) -> None:
        incidents = [{"severity": 1, "elapsed": 100}]
        self.assertEqual(sla_percentage(incidents), 100.0)

    def test_escalation_band_eighty_five_is_high(self) -> None:
        self.assertEqual(escalation_band(85), "high")

    def test_compound_risk_uses_max_for_hold(self) -> None:
        snap_risky = OrbitalSnapshot("s1", 50.0, 5.0, 80.0, 500.0, datetime.now())
        snap_safe = OrbitalSnapshot("s2", 300.0, 5.0, 20.0, 500.0, datetime.now())
        incidents = [
            IncidentTicket("i1", 5, "nav", "critical"),
            IncidentTicket("i2", 5, "comms", "critical"),
        ]
        result = compound_risk([snap_risky, snap_safe], [], incidents)
        self.assertTrue(result["hold_required"])


if __name__ == "__main__":
    unittest.main()
