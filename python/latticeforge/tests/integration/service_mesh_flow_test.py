import unittest
from datetime import datetime, timedelta, timezone

from latticeforge.models import BurnWindow, IncidentTicket, OrbitalSnapshot
from services.audit.service import AuditEvent, AuditLedger
from services.gateway.service import RouteNode, build_route_chain
from services.identity.service import authorize_intent, derive_context
from services.intake.service import normalize_intake_batch
from services.orbit.service import build_orbit_plan
from services.policy.service import evaluate_policy_gate


class ServiceMeshFlowIntegrationTest(unittest.TestCase):
    def test_intake_to_policy_pipeline(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        batch = [
            {
                "command_id": "cmd-11",
                "satellite_id": "sat-1",
                "intent": "orbit-adjust",
                "issued_by": "planner",
                "signature": "sig",
                "deadline": (now + timedelta(minutes=20)).isoformat(),
                "trace_id": "trace-11",
                "payload": {"target_altitude": 542.0},
            }
        ]
        commands, errors = normalize_intake_batch(batch, now)
        self.assertEqual(errors, [])
        self.assertEqual(len(commands), 1)

        context = derive_context(
            {
                "operator_id": "op-1",
                "org_id": "orbital",
                "roles": ["planner"],
                "mfa_level": 2,
            }
        )
        self.assertTrue(authorize_intent(context, "orbit-adjust", severity=3))

        topology = {
            "intake": [RouteNode("intake", "intake-a", latency_ms=15, queue_depth=1, saturation=0.1)],
            "planner": [RouteNode("planner", "planner-a", latency_ms=25, queue_depth=2, saturation=0.1)],
            "policy": [RouteNode("policy", "policy-a", latency_ms=30, queue_depth=2, saturation=0.1)],
            "orbit": [RouteNode("orbit", "orbit-a", latency_ms=45, queue_depth=3, saturation=0.2)],
        }
        chain = build_route_chain("orbit-adjust", topology)
        self.assertEqual(chain[0].service, "intake")

        snapshot = OrbitalSnapshot(
            satellite_id="sat-1",
            fuel_kg=170.0,
            power_kw=5.2,
            temperature_c=20.0,
            altitude_km=548.0,
            epoch=datetime(2026, 1, 1, 12, 0, 0),
        )
        windows = [
            BurnWindow("w-1", datetime(2026, 1, 1, 12, 10, 0), datetime(2026, 1, 1, 12, 18, 0), 0.7, 2),
            BurnWindow("w-2", datetime(2026, 1, 1, 12, 25, 0), datetime(2026, 1, 1, 12, 35, 0), 0.8, 3),
        ]
        incidents = [IncidentTicket("i-1", severity=2, subsystem="comms", description="drift")]
        orbit_plan = build_orbit_plan(snapshot, windows, incidents)
        decision = evaluate_policy_gate(
            snapshot=snapshot,
            burns=orbit_plan.burns,
            incidents=incidents,
            context={
                "comms_degraded": False,
                "operator_clearance": context.clearance,
                "required_clearance": 3,
            },
        )
        self.assertGreaterEqual(decision.risk_score, 0.0)

        ledger = AuditLedger()
        accepted = ledger.append(
            AuditEvent(
                event_id="evt-1",
                trace_id="trace-11",
                mission_id="mission-1",
                service="policy",
                kind="decision",
                payload={"approved": decision.approved},
                timestamp=now,
            )
        )
        self.assertTrue(accepted)
        self.assertEqual(len(ledger.by_trace("trace-11")), 1)


if __name__ == "__main__":
    unittest.main()
