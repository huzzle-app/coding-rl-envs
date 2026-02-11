from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from latticeforge.models import IncidentTicket, OrbitalSnapshot
from services.audit.service import AuditEvent, AuditLedger
from services.gateway.service import RouteNode, select_primary_node
from services.identity.service import authorize_intent, derive_context
from services.intake.service import normalize_intake_batch
from services.notifications.service import NotificationPlanner
from services.policy.service import evaluate_policy_gate
from services.reporting.service import rank_incidents
from services.resilience.service import build_replay_plan

TOTAL_CASES = 5400


def _case(idx: int) -> None:
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    bucket = idx % 8

    if bucket == 0:
        batch = [
            {
                "command_id": f"cmd-a-{idx}",
                "satellite_id": f"sat-{idx % 11}",
                "intent": "orbit-adjust",
                "issued_by": "planner",
                "signature": "sig-a",
                "deadline": (now + timedelta(minutes=30)).isoformat(),
                "trace_id": f"trace-{idx}",
                "payload": {"target_altitude": 542.0},
            },
            {
                "command_id": f"cmd-b-{idx}",
                "satellite_id": f"sat-{idx % 11}",
                "intent": "orbit-adjust",
                "issued_by": "planner",
                "signature": "sig-b",
                "deadline": (now + timedelta(minutes=35)).isoformat(),
                "trace_id": f"trace-{idx}",
                "payload": {"target_altitude": 543.0},
            },
        ]
        normalized, errors = normalize_intake_batch(batch, now)
        assert errors == []
        assert len(normalized) == 2
        return

    if bucket == 1:
        context = derive_context(
            {
                "operator_id": f"op-{idx}",
                "org_id": "orbital",
                "roles": ["planner"],
                "mfa_level": 2,
            }
        )
        assert authorize_intent(context, "orbit-adjust", severity=3) is True
        return

    if bucket == 2:
        nodes = [
            RouteNode("planner", f"planner-a-{idx}", latency_ms=30, queue_depth=1, saturation=0.1),
            RouteNode("planner", f"planner-b-{idx}", latency_ms=160, queue_depth=10, saturation=0.8),
        ]
        selected = select_primary_node(nodes)
        assert selected.latency_ms == 30
        return

    if bucket == 3:
        snapshot = OrbitalSnapshot(
            satellite_id=f"sat-{idx % 17}",
            fuel_kg=100.0,
            power_kw=5.0,
            temperature_c=20.0,
            altitude_km=543.0,
            epoch=datetime(2026, 1, 1, 12, 0, 0),
        )
        incidents = [
            IncidentTicket(f"i-a-{idx}", severity=4, subsystem="comms", description="loss"),
            IncidentTicket(f"i-b-{idx}", severity=4, subsystem="power", description="drift"),
            IncidentTicket(f"i-c-{idx}", severity=4, subsystem="payload", description="lag"),
        ]
        decision = evaluate_policy_gate(
            snapshot=snapshot,
            burns=(),
            incidents=incidents,
            context={"comms_degraded": True, "operator_clearance": 5, "required_clearance": 3},
        )
        assert decision.hold is True
        return

    if bucket == 4:
        plan = build_replay_plan(
            events=140 + (idx % 20),
            timeout_s=35,
            primary_region="us-east",
            candidate_regions=["us-east", "us-west", "eu-central"],
            degraded_regions=["us-west"],
        )
        assert plan.region == "eu-central"
        return

    if bucket == 5:
        ledger = AuditLedger()
        event = AuditEvent(
            event_id=f"evt-{idx}",
            trace_id=f"trace-{idx}",
            mission_id=f"m-{idx % 13}",
            service="gateway",
            kind="dispatch",
            payload={},
            timestamp=now,
        )
        assert ledger.append(event) is True
        assert ledger.append(event) is False
        assert len(ledger.by_trace(f"trace-{idx}")) == 1
        return

    if bucket == 6:
        planner = NotificationPlanner(throttle_minutes=5)
        incident = IncidentTicket(f"i-{idx}", severity=5, subsystem="orbit", description="critical")
        messages = planner.plan_incident_notifications([incident], [{"id": "oncall"}], now)
        channels = sorted(message.channel for message in messages)
        assert channels == ["email", "pager", "sms"]
        return

    ranked = rank_incidents(
        [
            IncidentTicket(f"i-low-{idx}", severity=2, subsystem="power", description="warn"),
            IncidentTicket(f"i-high-{idx}", severity=5, subsystem="orbit", description="critical"),
            IncidentTicket(f"i-mid-{idx}", severity=4, subsystem="payload", description="elevated"),
        ]
    )
    assert ranked[0]["severity"] == 5


class ServiceMeshMatrixTest(unittest.TestCase):
    pass


def _add_case(i: int) -> None:
    def test_fn(self: unittest.TestCase) -> None:
        _case(i)

    setattr(ServiceMeshMatrixTest, f"test_service_mesh_matrix_{i:05d}", test_fn)


for _i in range(TOTAL_CASES):
    _add_case(_i)


if __name__ == "__main__":
    unittest.main()
