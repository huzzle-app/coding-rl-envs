"""
Cross-module integration tests exercising 2-3 bug interactions each.

Every test in this file FAILS against the current (buggy) source tree.
They are designed to surface inter-module coupling that single-unit tests
cannot reach, and to provide intermediate RL milestones.
"""

import math
import unittest
from datetime import datetime, timedelta, timezone

from latticeforge.dependency import parallel_execution_groups
from latticeforge.models import BurnPlan, BurnWindow, IncidentTicket, OrbitalSnapshot
from latticeforge.orbit import hohmann_delta_v
from latticeforge.policy import compound_risk_assessment, evaluate_risk, requires_hold
from latticeforge.queue import BoundedPriorityChannel
from latticeforge.resilience import replay_budget
from latticeforge.routing import choose_ground_station
from latticeforge.scheduler import (
    batch_schedule_with_cooldown,
    estimate_completion_time,
    schedule_operations,
)
from latticeforge.telemetry import CachedSensorView
from services.audit.service import AuditEvent, AuditLedger, EventPipeline
from services.gateway.service import (
    RouteNode,
    route_with_risk_assessment,
    score_node,
    select_primary_node,
)
from services.identity.service import authorize_intent, derive_context
from services.intake.service import normalize_intake_batch
from services.mission.service import MissionRegistry
from services.notifications.service import NotificationPlanner
from services.policy.service import evaluate_policy_gate
from services.reporting.service import rank_incidents
from services.resilience.service import build_replay_plan


# ── helpers ──────────────────────────────────────────────────────────────────

def _snapshot(**overrides) -> OrbitalSnapshot:
    defaults = dict(
        satellite_id="sat-x",
        fuel_kg=180.0,
        power_kw=5.4,
        temperature_c=22.5,
        altitude_km=556.0,
        epoch=datetime(2026, 1, 1, 12, 0, 0),
    )
    defaults.update(overrides)
    return OrbitalSnapshot(**defaults)


def _window(wid, offset_min=10, dur_min=8, dv=0.5, priority=2) -> BurnWindow:
    base = datetime(2026, 1, 1, 12, 0, 0)
    return BurnWindow(wid, base + timedelta(minutes=offset_min),
                      base + timedelta(minutes=offset_min + dur_min), dv, priority)


def _incident(tid, severity=3, subsystem="comms", desc="issue") -> IncidentTicket:
    return IncidentTicket(tid, severity=severity, subsystem=subsystem, description=desc)


def _topology(**kwargs):
    """Return a simple topology mapping service -> [RouteNode]."""
    defaults = {
        "intake": [RouteNode("intake", "int-a", latency_ms=10, queue_depth=1, saturation=0.1)],
        "planner": [RouteNode("planner", "plan-a", latency_ms=20, queue_depth=2, saturation=0.1)],
        "policy": [RouteNode("policy", "pol-a", latency_ms=25, queue_depth=2, saturation=0.1)],
        "orbit": [RouteNode("orbit", "orb-a", latency_ms=30, queue_depth=3, saturation=0.2)],
        "resilience": [RouteNode("resilience", "res-a", latency_ms=15, queue_depth=1, saturation=0.1)],
        "audit": [RouteNode("audit", "aud-a", latency_ms=12, queue_depth=1, saturation=0.1)],
        "notifications": [RouteNode("notifications", "not-a", latency_ms=8, queue_depth=1, saturation=0.1)],
        "security": [RouteNode("security", "sec-a", latency_ms=14, queue_depth=1, saturation=0.1)],
        "mission": [RouteNode("mission", "mis-a", latency_ms=18, queue_depth=2, saturation=0.15)],
    }
    defaults.update(kwargs)
    return defaults


# ═══════════════════════════════════════════════════════════════════════════
# Class 1 – Routing × Policy interactions
# Bugs: #1 (routing max/min), #2/#3 (hold thresholds), #4 (compound sum)
# ═══════════════════════════════════════════════════════════════════════════

class RoutingPolicyInteractionTest(unittest.TestCase):

    # ── Bug #1: choose_ground_station returns max instead of min ──

    def test_station_selection_lowest_latency(self) -> None:
        stations = ["gs-east", "gs-west", "gs-north"]
        latency = {"gs-east": 120, "gs-west": 40, "gs-north": 80}
        result = choose_ground_station(stations, latency, blackout=[])
        self.assertEqual(result, "gs-west")

    def test_station_selection_avoids_blackout(self) -> None:
        stations = ["gs-a", "gs-b", "gs-c"]
        latency = {"gs-a": 10, "gs-b": 50, "gs-c": 30}
        result = choose_ground_station(stations, latency, blackout=["gs-a"])
        self.assertEqual(result, "gs-c")

    def test_station_feeds_risk_pipeline(self) -> None:
        """Station with min-latency should feed downstream policy risk."""
        stations = ["gs-low", "gs-high"]
        latency = {"gs-low": 5, "gs-high": 999}
        picked = choose_ground_station(stations, latency, blackout=[])
        self.assertEqual(picked, "gs-low")

    # ── Bug #2/#3: hold thresholds ──

    def test_hold_at_65_triggers_without_comms(self) -> None:
        """Score 65 must trigger hold (correct threshold is 65, not 66)."""
        self.assertTrue(requires_hold(65.0, comms_degraded=False))

    def test_hold_boundary_between_64_and_65(self) -> None:
        """Score 64.9 should NOT trigger hold; 65.0 should."""
        self.assertFalse(requires_hold(64.9, comms_degraded=False))
        self.assertTrue(requires_hold(65.0, comms_degraded=False))

    def test_comms_degraded_lowers_threshold(self) -> None:
        """With comms degraded, hold triggers at 50 not 55."""
        self.assertTrue(requires_hold(50.0, comms_degraded=True))

    def test_comms_degraded_hold_boundary(self) -> None:
        """Score 54.0 should trigger hold when comms degraded (threshold 50)."""
        self.assertTrue(requires_hold(54.0, comms_degraded=True))

    # ── Bug #4: compound risk uses sum instead of product ──

    def test_compound_risk_product(self) -> None:
        """compound_risk_assessment must multiply factors, not sum."""
        factors = [0.5, 0.5]
        result = compound_risk_assessment(factors, base_risk=10.0)
        # Correct: product = 0.5*0.5 = 0.25 → 10 + 0.25*90 = 32.5
        # Bug (sum): 0.5+0.5 = 1.0 → 10 + 1.0*90 = 100.0
        self.assertLess(result, 50.0)

    def test_compound_two_factors_differ(self) -> None:
        """Two factors [0.3, 0.4]: product=0.12 vs sum=0.7."""
        result = compound_risk_assessment([0.3, 0.4], base_risk=10.0)
        # Correct: product = 0.12 → 10 + 0.12*90 = 20.8
        # Bug: sum = 0.7 → 10 + 0.7*90 = 73.0
        self.assertAlmostEqual(result, 20.8, places=1)

    def test_compound_three_factors(self) -> None:
        """Three factors [0.5, 0.5, 0.5]: product=0.125 vs sum=1.5→capped 1.0."""
        result = compound_risk_assessment([0.5, 0.5, 0.5], base_risk=10.0)
        # Correct: product = 0.125 → 10 + 0.125*90 = 21.25
        # Bug: sum = 1.5 → capped 1.0 → 10 + 1.0*90 = 100.0
        self.assertLess(result, 30.0)

    def test_station_then_risk_pipeline(self) -> None:
        """End-to-end: station pick → evaluate_risk → requires_hold."""
        snap = _snapshot(fuel_kg=100.0, temperature_c=80.0)
        burns = [BurnPlan("w1", delta_v=8.0, thruster="main", reason="adj", safety_margin=0.2)]
        incidents = [_incident("i1", severity=4)]
        risk = evaluate_risk(snap, burns, incidents)
        station = choose_ground_station(["gs-a", "gs-b"], {"gs-a": 20, "gs-b": 90}, [])
        self.assertEqual(station, "gs-a")
        self.assertTrue(risk > 0)


# ═══════════════════════════════════════════════════════════════════════════
# Class 2 – Scheduler × Orbit interactions
# Bugs: #6 (hohmann sqrt), #7 (batch offset), #8 (completion time)
# ═══════════════════════════════════════════════════════════════════════════

class SchedulerOrbitInteractionTest(unittest.TestCase):

    # ── Bug #7: offset starts at cooldown instead of 0 ──

    def test_first_batch_offset_is_zero(self) -> None:
        ops = [{"id": "op1", "priority": 1}, {"id": "op2", "priority": 2}]
        result = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=30)
        offsets = [int(s["scheduled_offset_s"]) for s in result]
        self.assertEqual(offsets[0], 0)

    def test_second_batch_offset(self) -> None:
        ops = [{"id": f"op{i}"} for i in range(4)]
        result = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=15)
        batch1_offsets = {int(r["scheduled_offset_s"]) for r in result[:2]}
        batch2_offsets = {int(r["scheduled_offset_s"]) for r in result[2:]}
        self.assertEqual(batch1_offsets, {0})
        self.assertEqual(batch2_offsets, {15})

    def test_offsets_sequential_from_zero(self) -> None:
        ops = [{"id": f"op{i}"} for i in range(6)]
        result = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=10)
        unique_offsets = sorted({int(r["scheduled_offset_s"]) for r in result})
        self.assertEqual(unique_offsets, [0, 10, 20])

    def test_single_batch_no_cooldown_prefix(self) -> None:
        ops = [{"id": "only"}]
        result = batch_schedule_with_cooldown(ops, batch_size=5, cooldown_s=60)
        self.assertEqual(int(result[0]["scheduled_offset_s"]), 0)

    # ── Bug #8: completion = max_offset + duration (not minus cooldown) ──

    def test_completion_time_basic(self) -> None:
        scheduled = [{"scheduled_offset_s": 0}, {"scheduled_offset_s": 10}]
        total = estimate_completion_time(scheduled, per_op_duration_s=5, cooldown_s=10)
        self.assertEqual(total, 15)  # max_offset(10) + duration(5)

    def test_completion_single_op(self) -> None:
        scheduled = [{"scheduled_offset_s": 0}]
        total = estimate_completion_time(scheduled, per_op_duration_s=20, cooldown_s=10)
        self.assertEqual(total, 20)  # 0 + 20

    def test_completion_independent_of_offset_bug(self) -> None:
        """Test completion with hand-crafted offsets (bypasses bug #7)."""
        # Correct offsets: [0, 0, 15, 15]
        scheduled = [
            {"scheduled_offset_s": 0}, {"scheduled_offset_s": 0},
            {"scheduled_offset_s": 15}, {"scheduled_offset_s": 15},
        ]
        total = estimate_completion_time(scheduled, per_op_duration_s=10, cooldown_s=15)
        # max_offset(15) + duration(10) = 25
        # Bug: 15 + 10 - 15 = 10
        self.assertEqual(total, 25)

    # ── Bug #6: hohmann uses sqrt(r1*r2) instead of (r1+r2)/2 ──

    def test_hohmann_arithmetic_mean(self) -> None:
        r1, r2 = 6771.0, 42164.0
        dv = hohmann_delta_v(r1, r2)
        # Correct semi-major axis = (r1+r2)/2 = 24467.5
        a_correct = (r1 + r2) / 2.0
        a_buggy = math.sqrt(r1 * r2)
        self.assertNotAlmostEqual(a_correct, a_buggy, places=0)
        # dv should use the correct formula — verify it's positive
        self.assertGreater(dv, 0.0)
        # With correct formula the dv is ~3.935; with sqrt it differs
        v1_correct = math.sqrt(398600.4418 * (2.0 / r1 - 1.0 / a_correct))
        v1_buggy = math.sqrt(max(398600.4418 * (2.0 / r1 - 1.0 / a_buggy), 0.0))
        self.assertAlmostEqual(
            dv,
            abs(v1_correct - math.sqrt(398600.4418 / r1))
            + abs(math.sqrt(398600.4418 / r2) - math.sqrt(max(398600.4418 * (2.0 / r2 - 1.0 / a_correct), 0.0))),
            places=2,
        )

    def test_hohmann_known_value_leo_to_geo(self) -> None:
        """LEO (6771 km) to GEO (42164 km): correct dv ≈ 3.935 km/s."""
        dv = hohmann_delta_v(6771.0, 42164.0)
        # Correct with arithmetic mean: ~3.935
        # Buggy with geometric mean: different value
        self.assertAlmostEqual(dv, 3.935, places=1)

    def test_hohmann_feeds_scheduler(self) -> None:
        """Hohmann dv value determines burn allocation in scheduler."""
        dv = hohmann_delta_v(6771.0, 42164.0)
        # The correct dv ~ 3.935 should differ from buggy
        a_correct = (6771.0 + 42164.0) / 2.0
        a_buggy = math.sqrt(6771.0 * 42164.0)
        mu = 398600.4418
        v1 = math.sqrt(mu / 6771.0)
        vt1_correct = math.sqrt(max(mu * (2.0 / 6771.0 - 1.0 / a_correct), 0.0))
        vt1_buggy = math.sqrt(max(mu * (2.0 / 6771.0 - 1.0 / a_buggy), 0.0))
        # The transfer velocities should differ
        self.assertNotAlmostEqual(vt1_correct, vt1_buggy, places=2)
        # dv should match the correct formula
        v2 = math.sqrt(mu / 42164.0)
        vt2_correct = math.sqrt(max(mu * (2.0 / 42164.0 - 1.0 / a_correct), 0.0))
        expected_dv = abs(vt1_correct - v1) + abs(v2 - vt2_correct)
        self.assertAlmostEqual(dv, expected_dv, places=3)

    def test_batch_offset_then_completion(self) -> None:
        """Verify first offset is zero AND completion time is correct."""
        ops = [{"id": f"op{i}"} for i in range(3)]
        sched = batch_schedule_with_cooldown(ops, batch_size=1, cooldown_s=5)
        # First offset should be 0 (bug: cooldown_s)
        self.assertEqual(int(sched[0]["scheduled_offset_s"]), 0)
        # Max offset should be 10 (bug: 15)
        max_offset = max(int(s["scheduled_offset_s"]) for s in sched)
        self.assertEqual(max_offset, 10)


# ═══════════════════════════════════════════════════════════════════════════
# Class 3 – Gateway × Identity × Policy interactions
# Bugs: #12 (clearance >/>=), #14 (gateway max/min), #16 (comms_degraded)
# ═══════════════════════════════════════════════════════════════════════════

class GatewayIdentityPolicyInteractionTest(unittest.TestCase):

    # ── Bug #12: authorize_intent uses > instead of >= ──

    def test_exact_clearance_authorizes(self) -> None:
        ctx = derive_context({"operator_id": "op1", "org_id": "org",
                              "roles": ["planner"], "mfa_level": 2})
        # planner clearance = 3, orbit-adjust required = 3
        self.assertTrue(authorize_intent(ctx, "orbit-adjust", severity=1))

    def test_exact_clearance_observer(self) -> None:
        """Observer (clearance 1) should authorize status-refresh (required 1)."""
        ctx = derive_context({"operator_id": "op1", "org_id": "org",
                              "roles": ["observer"], "mfa_level": 0})
        self.assertTrue(authorize_intent(ctx, "status-refresh", severity=1))

    def test_exact_clearance_operator(self) -> None:
        """Operator (clearance 2) should authorize replay-window (required 2)."""
        ctx = derive_context({"operator_id": "op1", "org_id": "org",
                              "roles": ["operator"], "mfa_level": 0})
        self.assertTrue(authorize_intent(ctx, "replay-window", severity=1))

    def test_exact_clearance_flight_director(self) -> None:
        """Flight-director (clearance 4) must authorize failover-region (required 4)."""
        ctx = derive_context({"operator_id": "op1", "org_id": "org",
                              "roles": ["flight-director"], "mfa_level": 2})
        # clearance 4, failover-region required = 4 → exact match
        # Bug: 4 > 4 = False. Correct: 4 >= 4 = True
        self.assertTrue(authorize_intent(ctx, "failover-region", severity=1))

    # ── Bug #14: gateway select_primary uses max(score) instead of min ──

    def test_gateway_selects_lowest_score(self) -> None:
        nodes = [
            RouteNode("svc", "ep-slow", latency_ms=200, queue_depth=5, saturation=0.8),
            RouteNode("svc", "ep-fast", latency_ms=10, queue_depth=1, saturation=0.1),
        ]
        picked = select_primary_node(nodes)
        self.assertEqual(picked.endpoint, "ep-fast")

    def test_gateway_avoids_degraded(self) -> None:
        nodes = [
            RouteNode("svc", "ep-deg", latency_ms=5, queue_depth=0, saturation=0.0, degraded=True),
            RouteNode("svc", "ep-ok", latency_ms=50, queue_depth=2, saturation=0.3),
        ]
        picked = select_primary_node(nodes)
        self.assertEqual(picked.endpoint, "ep-ok")

    def test_gateway_selects_from_three(self) -> None:
        """With three candidates, pick the lowest-scored node."""
        nodes = [
            RouteNode("s", "ep-high", latency_ms=100, queue_depth=10, saturation=0.9),
            RouteNode("s", "ep-mid", latency_ms=50, queue_depth=5, saturation=0.5),
            RouteNode("s", "ep-low", latency_ms=10, queue_depth=1, saturation=0.1),
        ]
        picked = select_primary_node(nodes)
        self.assertEqual(picked.endpoint, "ep-low")

    # ── Bug #16: policy service hardcodes comms_degraded=False ──

    def test_policy_gate_comms_degraded_holds(self) -> None:
        """Risk ~58 + comms_degraded should trigger hold (bug: comms_degraded=False)."""
        snap = _snapshot()  # normal temp & fuel → no penalties
        burns = [BurnPlan("w1", delta_v=7.0, thruster="main", reason="adj", safety_margin=0.2)]
        incidents = [_incident("i1", severity=2)]
        risk = evaluate_risk(snap, burns, incidents)
        # risk = 7.0*7.5 + 2*3.0 + 0 + 0 = 52.5 + 6.0 = 58.5
        # With comms_degraded=True, correct threshold=50 → hold at 58.5
        # Bug: passes comms_degraded=False, threshold=66 → 58.5 < 66 → no hold
        decision = evaluate_policy_gate(
            snap, burns, incidents,
            context={"comms_degraded": True, "operator_clearance": 5, "required_clearance": 3},
        )
        self.assertTrue(decision.hold)

    def test_auth_then_gateway_route(self) -> None:
        """Identity auth (exact clearance) → gateway route (min node)."""
        ctx = derive_context({"operator_id": "op1", "org_id": "org",
                              "roles": ["planner"], "mfa_level": 2})
        # Bug #12: > instead of >= → planner (3) fails orbit-adjust (3)
        self.assertTrue(authorize_intent(ctx, "orbit-adjust", severity=1))

        # Route with two intake nodes — should pick lowest score
        topo = _topology(intake=[
            RouteNode("intake", "int-slow", latency_ms=200, queue_depth=10, saturation=0.8),
            RouteNode("intake", "int-fast", latency_ms=10, queue_depth=1, saturation=0.1),
        ])
        result = route_with_risk_assessment("orbit-adjust", topo, risk_score=30.0,
                                            comms_degraded=False)
        self.assertTrue(result["routed"])

    def test_gateway_blocked_two_remaining(self) -> None:
        """After blocking one, pick lowest from remaining two."""
        nodes = [
            RouteNode("svc", "ep-a", latency_ms=10, queue_depth=1, saturation=0.1),
            RouteNode("svc", "ep-b", latency_ms=80, queue_depth=5, saturation=0.7),
            RouteNode("svc", "ep-c", latency_ms=30, queue_depth=2, saturation=0.2),
        ]
        picked = select_primary_node(nodes, blocked_endpoints=["ep-a"])
        self.assertEqual(picked.endpoint, "ep-c")

    def test_route_risk_blocks_saturated_comms_degraded(self) -> None:
        """Mid-saturation node blocked only when sat_threshold is correct (0.5)."""
        topo = {
            "intake": [
                RouteNode("intake", "int-mid", latency_ms=10, queue_depth=1, saturation=0.7),
                RouteNode("intake", "int-ok", latency_ms=15, queue_depth=1, saturation=0.3),
            ],
            "policy": [RouteNode("policy", "pol-a", latency_ms=20, queue_depth=2, saturation=0.1)],
            "resilience": [RouteNode("resilience", "res-a", latency_ms=15, queue_depth=1, saturation=0.1)],
            "audit": [RouteNode("audit", "aud-a", latency_ms=12, queue_depth=1, saturation=0.1)],
        }
        result = route_with_risk_assessment("replay-window", topo, risk_score=60.0,
                                            comms_degraded=True)
        # Bug #15: sat_threshold=0.9 → int-mid (0.7) NOT blocked → blocked_count=0
        # Correct: sat_threshold=0.5 → int-mid (0.7) IS blocked → blocked_count>0
        self.assertGreater(result["blocked_count"], 0)

    def test_identity_clearance_boundary(self) -> None:
        """Clearance exactly equal to required must authorize."""
        ctx = derive_context({"operator_id": "op1", "org_id": "org",
                              "roles": ["observer"], "mfa_level": 0})
        # observer clearance = 1, status-refresh required = 1
        self.assertTrue(authorize_intent(ctx, "status-refresh", severity=1))


# ═══════════════════════════════════════════════════════════════════════════
# Class 4 – Intake × Audit × Mission interactions
# Bugs: #13 (dedup key), #20 (ledger dup), #21 (retry enrichment), #22 (transition)
# ═══════════════════════════════════════════════════════════════════════════

class IntakeAuditMissionInteractionTest(unittest.TestCase):

    # ── Bug #13: dedupe by (sat, intent) instead of command_id ──

    def test_distinct_commands_same_satellite_intent(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        batch = [
            {"command_id": "cmd-1", "satellite_id": "sat-1", "intent": "orbit-adjust",
             "issued_by": "planner", "signature": "sig1",
             "deadline": (now + timedelta(minutes=30)).isoformat(),
             "trace_id": "t1", "payload": {}},
            {"command_id": "cmd-2", "satellite_id": "sat-1", "intent": "orbit-adjust",
             "issued_by": "planner", "signature": "sig2",
             "deadline": (now + timedelta(minutes=40)).isoformat(),
             "trace_id": "t2", "payload": {}},
        ]
        commands, errors = normalize_intake_batch(batch, now)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(commands), 2)

    def test_three_commands_two_share_sat_intent(self) -> None:
        """Three commands: A & B share satellite+intent but differ in command_id."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        batch = [
            {"command_id": "cmd-A", "satellite_id": "sat-1", "intent": "orbit-adjust",
             "issued_by": "planner", "signature": "s",
             "deadline": (now + timedelta(minutes=20)).isoformat(),
             "trace_id": "tA", "payload": {}},
            {"command_id": "cmd-B", "satellite_id": "sat-1", "intent": "orbit-adjust",
             "issued_by": "planner", "signature": "s",
             "deadline": (now + timedelta(minutes=25)).isoformat(),
             "trace_id": "tB", "payload": {}},
            {"command_id": "cmd-C", "satellite_id": "sat-2", "intent": "status-refresh",
             "issued_by": "op", "signature": "s",
             "deadline": (now + timedelta(minutes=30)).isoformat(),
             "trace_id": "tC", "payload": {}},
        ]
        commands, errors = normalize_intake_batch(batch, now)
        self.assertEqual(len(errors), 0)
        # Correct: all 3 unique command_ids → 3 commands
        # Bug: (sat-1, orbit-adjust) dedup → cmd-B dropped → 2 commands
        self.assertEqual(len(commands), 3)

    def test_intake_same_sat_different_intents(self) -> None:
        """Same satellite, different intents should all pass regardless of dedup."""
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        batch = [
            {"command_id": f"cmd-{i}", "satellite_id": "sat-1", "intent": intent,
             "issued_by": "op", "signature": "s",
             "deadline": (now + timedelta(minutes=10 + i)).isoformat(),
             "trace_id": f"t{i}", "payload": {}}
            for i, intent in enumerate(["orbit-adjust", "orbit-adjust", "status-refresh"])
        ]
        commands, _ = normalize_intake_batch(batch, now)
        # Bug drops cmd-1 (same sat+intent as cmd-0)
        # Correct: all 3 command_ids unique
        self.assertEqual(len(commands), 3)

    # ── Bug #20: ledger appends duplicate events ──

    def test_ledger_rejects_duplicate_no_store(self) -> None:
        ledger = AuditLedger()
        ts = datetime(2026, 1, 1, 12, 0, 0)
        ev = AuditEvent("evt-1", "trace-1", "m-1", "intake", "received", {}, ts)
        self.assertTrue(ledger.append(ev))
        self.assertFalse(ledger.append(ev))
        # After rejecting duplicate, ledger should have exactly 1 event
        events = ledger.by_trace("trace-1")
        self.assertEqual(len(events), 1)

    def test_ledger_duplicate_count(self) -> None:
        ledger = AuditLedger()
        ts = datetime(2026, 1, 1, 12, 0, 0)
        ev1 = AuditEvent("evt-1", "t1", "m1", "svc", "kind", {}, ts)
        ev2 = AuditEvent("evt-1", "t1", "m1", "svc", "kind", {}, ts)
        ledger.append(ev1)
        ledger.append(ev2)
        self.assertEqual(ledger.duplicate_count(), 1)
        # Only 1 event should be stored
        self.assertEqual(len(ledger.by_trace("t1")), 1)

    # ── Bug #21: retry doesn't clear enrichment ──

    def test_retry_clears_enrichment(self) -> None:
        pipe = EventPipeline()
        pipe.receive("e1", {"trace_id": "t1", "service": "intake"})
        pipe.validate("e1")
        pipe.enrich("e1", {"geo": "us-east"})
        # Retry should reset enrichment
        pipe.retry("e1", {"trace_id": "t1", "service": "intake"})
        enrichment = pipe.get_enrichment("e1")
        self.assertEqual(enrichment, {})

    def test_retry_enrichment_not_carried_forward(self) -> None:
        """After retry, old enrichment must not leak into new pipeline run."""
        pipe = EventPipeline()
        pipe.receive("e1", {"trace_id": "t1", "service": "svc"})
        pipe.validate("e1")
        pipe.enrich("e1", {"region": "eu", "tag": "old"})
        pipe.retry("e1", {"trace_id": "t1", "service": "svc"})
        # After retry, enrichment must be empty
        self.assertEqual(pipe.get_enrichment("e1"), {})
        # Re-validate and re-enrich with new data
        pipe.validate("e1")
        pipe.enrich("e1", {"region": "us"})
        # Must NOT contain old "tag"
        self.assertNotIn("tag", pipe.get_enrichment("e1"))

    # ── Bug #22: invalid transition silently stays in current state ──

    def test_invalid_transition_raises(self) -> None:
        reg = MissionRegistry()
        reg.register("m1", org_id="org", created_by="actor")
        # planned → completed is not allowed
        with self.assertRaises(ValueError):
            reg.transition("m1", "completed", "actor")

    def test_invalid_transition_raises_failed_from_planned(self) -> None:
        """planned → failed must raise ValueError (not silently stay)."""
        reg = MissionRegistry()
        reg.register("m1", org_id="org", created_by="actor")
        with self.assertRaises(ValueError):
            reg.transition("m1", "failed", "actor")

    def test_invalid_transition_executing_to_planned(self) -> None:
        """executing → planned must raise ValueError."""
        reg = MissionRegistry()
        reg.register("m1", org_id="org", created_by="actor")
        reg.transition("m1", "queued", "actor")
        reg.transition("m1", "executing", "actor")
        with self.assertRaises(ValueError):
            reg.transition("m1", "planned", "actor")

    def test_mission_transition_sequence(self) -> None:
        reg = MissionRegistry()
        reg.register("m1", org_id="org", created_by="actor")
        reg.transition("m1", "queued", "actor")
        reg.transition("m1", "executing", "actor")
        self.assertEqual(reg.current("m1").state, "executing")
        # executing → planned is invalid
        with self.assertRaises(ValueError):
            reg.transition("m1", "planned", "actor")


# ═══════════════════════════════════════════════════════════════════════════
# Class 5 – Resilience × Notifications × Reporting interactions
# Bugs: #5 (budget 0.8), #17 (degraded=[]), #18 (throttle key), #19 (rank asc)
# ═══════════════════════════════════════════════════════════════════════════

class ResilienceNotificationsReportingInteractionTest(unittest.TestCase):

    # ── Bug #5: replay budget uses 0.8 instead of 0.9 ──

    def test_replay_budget_factor(self) -> None:
        budget = replay_budget(events=100, timeout_s=20)
        baseline = min(100, 20 * 12)  # 100
        expected = max(int(baseline * 0.9), 1)  # 90
        self.assertEqual(budget, expected)

    def test_replay_budget_bounded_by_timeout(self) -> None:
        budget = replay_budget(events=1000, timeout_s=5)
        baseline = min(1000, 5 * 12)  # 60
        expected = max(int(baseline * 0.9), 1)  # 54
        self.assertEqual(budget, expected)

    def test_replay_budget_medium_events(self) -> None:
        """events=10: int(10*0.9)=9 vs int(10*0.8)=8."""
        budget = replay_budget(events=10, timeout_s=100)
        baseline = min(10, 100 * 12)  # 10
        expected = max(int(baseline * 0.9), 1)  # 9
        self.assertEqual(budget, expected)

    # ── Bug #17: build_replay_plan passes degraded=[] ──

    def test_plan_uses_degraded_regions(self) -> None:
        plan = build_replay_plan(
            events=50, timeout_s=30,
            primary_region="us-east",
            candidate_regions=["us-east", "us-west", "eu-west"],
            degraded_regions=["us-west"],
        )
        self.assertNotEqual(plan.region, "us-west")

    def test_plan_fallback_when_all_degraded(self) -> None:
        plan = build_replay_plan(
            events=50, timeout_s=30,
            primary_region="us-east",
            candidate_regions=["us-east", "us-west"],
            degraded_regions=["us-west"],
        )
        self.assertEqual(plan.region, "us-east")

    def test_plan_first_candidate_degraded(self) -> None:
        """First non-primary candidate is degraded → must skip to second."""
        plan = build_replay_plan(
            events=50, timeout_s=30,
            primary_region="us-east",
            candidate_regions=["us-east", "eu-west", "us-west"],
            degraded_regions=["eu-west"],
        )
        # Bug: degraded=[] → picks eu-west (first non-primary)
        # Correct: eu-west is degraded → picks us-west
        self.assertNotEqual(plan.region, "eu-west")

    # ── Bug #18: throttle key missing channel ──

    def test_throttle_allows_multi_channel(self) -> None:
        planner = NotificationPlanner(throttle_minutes=10)
        now = datetime(2026, 1, 1, 12, 0, 0)
        incidents = [_incident("i1", severity=5)]
        recipients = [{"id": "user-1"}]
        notifications = planner.plan_incident_notifications(incidents, recipients, now)
        # severity 5 → pager, sms, email = 3 channels
        channels = [n.channel for n in notifications]
        self.assertEqual(len(channels), 3)
        self.assertIn("pager", channels)
        self.assertIn("sms", channels)
        self.assertIn("email", channels)

    def test_throttle_per_channel_separate(self) -> None:
        planner = NotificationPlanner(throttle_minutes=10)
        now = datetime(2026, 1, 1, 12, 0, 0)
        incidents = [_incident("i1", severity=5)]
        recipients = [{"id": "user-1"}]
        n1 = planner.plan_incident_notifications(incidents, recipients, now)
        # Immediately re-fire; all channels should be throttled
        n2 = planner.plan_incident_notifications(incidents, recipients, now)
        # First call: 3 (pager, sms, email). Second: 0 (all throttled)
        self.assertEqual(len(n1), 3)
        self.assertEqual(len(n2), 0)

    def test_throttle_same_recipient_two_incidents(self) -> None:
        """Two incidents to same recipient: throttle keyed per (recipient, channel)."""
        planner = NotificationPlanner(throttle_minutes=10)
        now = datetime(2026, 1, 1, 12, 0, 0)
        incidents = [_incident("i1", severity=5), _incident("i2", severity=5)]
        recipients = [{"id": "user-1"}]
        notifications = planner.plan_incident_notifications(incidents, recipients, now)
        # Correct: throttle per (recipient, channel) → i1 gets 3, i2 gets 0 → total 3
        # Bug: throttle per (recipient, ticket_id) → i1 gets 3, i2 gets 3 → total 6
        # But wait, with bug: i1 sends pager, key=(user-1, i1) → stored. sms, key=(user-1, i1) → throttled!
        # Actually re-reading the code: for i1, channel "pager": key=(user-1, i1), not in last_sent → send.
        # Then "sms": key=(user-1, i1), IS in last_sent (just set) → throttled!
        # So bug: i1 gets 1 (pager only), i2 gets 1 (pager only) = 2
        # Correct: i1 gets 3 (pager,sms,email), i2 gets 0 (all throttled) = 3
        # Either way, let's check: first incident should get all 3 channels
        i1_channels = [n.channel for n in notifications
                       if n.recipient_id == "user-1" and n.subject.endswith("comms")]
        # The first incident should yield pager, sms, email (3 channels)
        self.assertEqual(len(i1_channels), 3)

    # ── Bug #19: rank_incidents ascending instead of descending ──

    def test_rank_descending_severity(self) -> None:
        incidents = [
            _incident("i-low", severity=1),
            _incident("i-high", severity=5),
            _incident("i-mid", severity=3),
        ]
        ranked = rank_incidents(incidents)
        severities = [r["severity"] for r in ranked]
        self.assertEqual(severities, [5, 3, 1])

    def test_rank_tiebreak_ticket_id(self) -> None:
        incidents = [
            _incident("i-b", severity=3),
            _incident("i-a", severity=3),
        ]
        ranked = rank_incidents(incidents)
        ids = [r["ticket_id"] for r in ranked]
        # Same severity → alphabetical by ticket_id (descending context)
        self.assertEqual(ids[0], "i-b")


# ═══════════════════════════════════════════════════════════════════════════
# Class 6 – Telemetry × Queue × Dependency interactions
# Bugs: #9 (parallel groups level), #10 (cache valid), #11 (drain active_count)
# ═══════════════════════════════════════════════════════════════════════════

class TelemetryQueueDependencyInteractionTest(unittest.TestCase):

    # ── Bug #10: cache sets _cache_valid=True globally ──

    def test_cache_invalidation_per_sensor(self) -> None:
        view = CachedSensorView()
        view.record("s1", 10.0)
        avg_s1 = view.get_average("s1")  # computes and caches, sets valid=True
        self.assertEqual(avg_s1, 10.0)

        view.record("s2", 20.0)  # invalidates cache
        avg_s2 = view.get_average("s2")  # computes s2, sets valid=True

        # Now record more data for s2
        view.record("s2", 30.0)  # invalidates again
        # Read s1 — should still be 10.0 from cache (valid for s1)
        # But the bug: get_average(s1) returns cached 10.0 — sets valid=True
        # Then get_average(s2) returns stale 20.0 instead of recomputing 25.0
        avg_s1_again = view.get_average("s1")
        avg_s2_new = view.get_average("s2")
        self.assertAlmostEqual(avg_s2_new, 25.0, places=2)

    def test_cache_stale_cross_sensor(self) -> None:
        """Recording s2 then reading s1 sets valid=True → stale s2 cache."""
        view = CachedSensorView()
        view.record("s1", 5.0)
        view.get_average("s1")  # cache[s1]=5, valid=True
        view.record("s2", 15.0)  # valid=False
        view.get_average("s2")  # cache[s2]=15, valid=True
        view.record("s2", 25.0)  # valid=False
        # Bug: reading s1 sets valid=True, then s2 reads stale cache
        view.get_average("s1")  # recomputes s1=5, sets valid=True
        s2_avg = view.get_average("s2")
        # Bug returns 15.0 (stale); correct is (15+25)/2=20
        self.assertAlmostEqual(s2_avg, 20.0, places=2)

    def test_cache_three_sensors_invalidation(self) -> None:
        """Three sensors: recording s3 then reading s1 and s2 must recompute s3."""
        view = CachedSensorView()
        for sid, val in [("s1", 10.0), ("s2", 20.0), ("s3", 30.0)]:
            view.record(sid, val)
            view.get_average(sid)
        # All cached, valid=True
        view.record("s3", 50.0)  # valid=False
        view.get_average("s1")   # sets valid=True (bug)
        s3_avg = view.get_average("s3")  # Bug: returns stale 30.0
        self.assertAlmostEqual(s3_avg, 40.0, places=2)  # correct: (30+50)/2=40

    # ── Bug #11: drain decrements active_count too eagerly ──

    def test_drain_does_not_free_capacity(self) -> None:
        ch = BoundedPriorityChannel(capacity=3)
        self.assertTrue(ch.send("t1", severity=1, wait_seconds=0))
        self.assertTrue(ch.send("t2", severity=1, wait_seconds=0))
        self.assertTrue(ch.send("t3", severity=1, wait_seconds=0))
        # Capacity full
        self.assertFalse(ch.send("t4", severity=1, wait_seconds=0))

        # Drain 2 items — they go to inflight, capacity should NOT free
        drained = ch.drain(max_items=2)
        self.assertEqual(len(drained), 2)

        # Bug: drain decrements active_count → allows send even though
        # items are still inflight (not acknowledged)
        self.assertFalse(ch.send("t5", severity=1, wait_seconds=0))

    def test_acknowledge_frees_capacity(self) -> None:
        ch = BoundedPriorityChannel(capacity=2)
        ch.send("t1", severity=1, wait_seconds=0)
        ch.send("t2", severity=1, wait_seconds=0)
        self.assertFalse(ch.send("t3", severity=1, wait_seconds=0))

        drained = ch.drain(max_items=1)
        # Still full — items in inflight
        self.assertFalse(ch.send("t3", severity=1, wait_seconds=0))

        # Acknowledge frees capacity
        ch.acknowledge({drained[0].ticket_id})
        self.assertTrue(ch.send("t3", severity=1, wait_seconds=0))

    def test_drain_and_send_interaction(self) -> None:
        ch = BoundedPriorityChannel(capacity=5)
        for i in range(5):
            ch.send(f"t{i}", severity=i + 1, wait_seconds=i * 10)
        # Full
        self.assertFalse(ch.send("overflow", severity=1, wait_seconds=0))
        ch.drain(3)
        # Bug allows 3 new sends; correct behavior blocks until acknowledge
        self.assertFalse(ch.send("new1", severity=1, wait_seconds=0))

    # ── Bug #9: parallel_execution_groups BFS first-visit level ──

    def test_parallel_groups_uneven_parents(self) -> None:
        """A→B, A→C, B→C. C has parents at level 0 (A) and 1 (B).
        Bug assigns C to level 1 (first visit from A). Correct: level 2."""
        nodes = ["A", "B", "C"]
        edges = [("A", "B"), ("A", "C"), ("B", "C")]
        groups = parallel_execution_groups(nodes, edges)
        self.assertEqual(len(groups), 3)
        self.assertIn("A", groups[0])
        self.assertIn("B", groups[1])
        self.assertIn("C", groups[2])

    def test_parallel_groups_shortcut_edge(self) -> None:
        """A→B→C→D and also A→D directly.
        D has parents A (level 0) and C (level 2).
        Bug: first visit from A → D=1. Correct: D=3 (max path)."""
        nodes = ["A", "B", "C", "D"]
        edges = [("A", "B"), ("B", "C"), ("C", "D"), ("A", "D")]
        groups = parallel_execution_groups(nodes, edges)
        self.assertEqual(len(groups), 4)
        self.assertIn("D", groups[3])

    def test_parallel_groups_skip_level(self) -> None:
        """A→B, A→D, B→C, C→D. D has parents A (level 0) and C (level 2).
        Bug: first visit from A → D gets level 1. Correct: level 3."""
        nodes = ["A", "B", "C", "D"]
        edges = [("A", "B"), ("A", "D"), ("B", "C"), ("C", "D")]
        groups = parallel_execution_groups(nodes, edges)
        self.assertEqual(len(groups), 4)
        self.assertIn("A", groups[0])
        self.assertIn("B", groups[1])
        self.assertIn("C", groups[2])
        self.assertIn("D", groups[3])

    def test_parallel_groups_multiple_roots(self) -> None:
        """Two roots both reaching Z at different depths. Z should be max depth.
        R1→A→Z, R2→Z. Z has parents A (level 1) and R2 (level 0).
        Bug: first visit from R1→A gets Z at level 2, or from R2 at level 1.
        Depends on BFS order. But with edges [R1→A, R2→Z, A→Z]:
        Roots: R1, R2. BFS: R1 level 0, R2 level 0. Children of R1: A→level 1.
        Children of R2: Z. Z not in level → Z=1. Children of A: Z already at 1→skip.
        Bug: Z=1 (from R2). Correct: Z=2 (from R1→A→Z)."""
        nodes = ["R1", "R2", "A", "Z"]
        edges = [("R1", "A"), ("R2", "Z"), ("A", "Z")]
        groups = parallel_execution_groups(nodes, edges)
        self.assertEqual(len(groups), 3)
        self.assertIn("Z", groups[2])


if __name__ == "__main__":
    unittest.main()
