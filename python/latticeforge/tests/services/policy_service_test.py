import unittest
from datetime import datetime

from latticeforge.models import IncidentTicket, OrbitalSnapshot
from services.policy.service import evaluate_policy_gate


class PolicyServiceTest(unittest.TestCase):
    def test_degraded_comms_triggers_hold_at_lower_threshold(self) -> None:
        snapshot = OrbitalSnapshot(
            satellite_id="sat-2",
            fuel_kg=100.0,
            power_kw=5.2,
            temperature_c=18.0,
            altitude_km=545.0,
            epoch=datetime(2026, 1, 1, 12, 0, 0),
        )
        incidents = [
            IncidentTicket("i-1", severity=4, subsystem="comms", description="loss"),
            IncidentTicket("i-2", severity=4, subsystem="power", description="drift"),
            IncidentTicket("i-3", severity=4, subsystem="payload", description="lag"),
        ]
        decision = evaluate_policy_gate(
            snapshot=snapshot,
            burns=(),
            incidents=incidents,
            context={
                "comms_degraded": True,
                "operator_clearance": 5,
                "required_clearance": 3,
            },
        )
        self.assertTrue(decision.hold)

    def test_dual_control_not_needed_when_not_approved(self) -> None:
        snapshot = OrbitalSnapshot(
            satellite_id="sat-3",
            fuel_kg=180.0,
            power_kw=5.2,
            temperature_c=18.0,
            altitude_km=540.0,
            epoch=datetime(2026, 1, 1, 12, 0, 0),
        )
        decision = evaluate_policy_gate(
            snapshot=snapshot,
            burns=(),
            incidents=(),
            context={
                "comms_degraded": False,
                "operator_clearance": 1,
                "required_clearance": 3,
            },
        )
        self.assertFalse(decision.approved)


if __name__ == "__main__":
    unittest.main()
