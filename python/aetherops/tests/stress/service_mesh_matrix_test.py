from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from tests.test_helper import sample_snapshot, sample_windows, sample_incidents

from services.gateway.service import (
    RouteNode,
    score_node,
    select_primary_node,
    build_route_chain,
    admission_control,
    fanout_targets,
)
from services.identity.service import (
    OperatorContext,
    derive_context,
    authorize_intent,
    has_role,
    validate_session,
    list_permissions,
)
from services.intake.service import (
    validate_command_shape,
    batch_summary,
)
from services.mission.service import (
    MissionRegistry,
    MissionState,
    validate_phase_transition,
    compute_mission_health,
    phase_index,
    VALID_PHASES,
)
from services.orbit.service import (
    compute_orbital_period,
    orbital_decay_rate,
    predict_conjunction_risk,
    altitude_band,
)
from services.planner.service import (
    PlannerConfig,
    build_burn_sequence,
    validate_fuel_budget,
    estimate_timeline_hours,
    plan_summary,
)
from services.resilience.service import (
    ReplayPlan,
    build_replay_plan,
    classify_replay_mode,
    estimate_replay_coverage,
    failover_priority,
)
from services.policy.service import (
    PolicyDecision,
    evaluate_policy_gate,
    enforce_dual_control,
    risk_band,
    compute_compliance_score,
)
from services.security.service import (
    validate_command_auth,
    check_path_traversal,
    rate_limit_check,
    sanitize_input,
    compute_risk_score,
)
from services.audit.service import (
    AuditEvent,
    AuditLedger,
    validate_audit_event,
    summarize_ledger,
    is_compliant_audit_trail,
)
from services.analytics.service import (
    compute_fleet_health,
    trend_analysis,
    anomaly_report,
    satellite_ranking,
)
from services.notifications.service import (
    NotificationPlanner,
    should_throttle,
    format_notification,
    notification_summary,
    batch_notify,
)
from services.reporting.service import (
    rank_incidents,
    compliance_report,
    format_incident_row,
    generate_executive_summary,
    mission_report,
)

TOTAL_CASES = 2200


def _case(idx):
    """Generate test context and run assertions modulated by idx."""
    now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc) + timedelta(minutes=idx % 60)
    snapshot = sample_snapshot()
    windows = sample_windows()
    incidents = sample_incidents()
    bucket = idx % 8

    if bucket == 0:
        # gateway + identity services
        nodes = [
            RouteNode(
                node_id=f"node-{idx}-{k}",
                latency_ms=(idx * 7 + k * 31) % 200 + 5,
                error_rate=float(k % 10) / 100.0,
                weight=1.0 + float(k % 3) * 0.1,
            )
            for k in range(idx % 4 + 2)
        ]
        for node in nodes:
            s = score_node(node)
            assert isinstance(s, float)
        primary = select_primary_node(nodes)
        assert primary is not None
        assert isinstance(primary, RouteNode)
        chain = build_route_chain(nodes, max_hops=3)
        assert isinstance(chain, list)
        assert len(chain) <= len(nodes)
        admitted = admission_control(
            current_load=idx % 80, max_capacity=100, priority=idx % 6
        )
        assert isinstance(admitted, bool)
        targets = fanout_targets(
            ["svc-a", "svc-b", "svc-c"], exclude=["svc-b"]
        )
        assert isinstance(targets, list)
        assert "svc-b" not in targets

        ctx = derive_context(
            operator_id=f"op-{idx}",
            name=f"Operator {idx}",
            roles=["operator", "engineer"] if idx % 2 == 0 else ["viewer"],
            clearance=idx % 5 + 1,
            mfa_done=idx % 3 == 0,
        )
        assert isinstance(ctx, OperatorContext)
        auth = authorize_intent(ctx, required_clearance=3)
        assert isinstance(auth, bool)
        hr = has_role(ctx, "operator")
        assert isinstance(hr, bool)
        vs = validate_session(ctx, max_idle_s=300, idle_s=idx % 400)
        assert isinstance(vs, bool)
        perms = list_permissions(ctx)
        assert isinstance(perms, list)
        assert len(perms) > 0

    elif bucket == 1:
        # intake + mission services
        raw_cmd = {
            "command_id": f"cmd-{idx}",
            "satellite_id": f"sat-{idx % 10}",
            "intent": "orbit-adjust",
            "issued_by": "planner",
            "signature": f"sig-{idx}",
            "deadline": (now + timedelta(minutes=30)).isoformat(),
        }
        shape_errors = validate_command_shape(raw_cmd)
        assert isinstance(shape_errors, list)
        summary = batch_summary([])
        assert isinstance(summary, dict)

        registry = MissionRegistry()
        ms = registry.register(f"mission-{idx}")
        assert isinstance(ms, MissionState)
        assert ms.phase == "planning"
        retrieved = registry.get(f"mission-{idx}")
        assert retrieved is not None
        assert registry.count() == 1
        ids = registry.all_ids()
        assert isinstance(ids, list)
        assert len(ids) == 1
        valid_trans = validate_phase_transition("planning", "fueling")
        assert valid_trans
        invalid_trans = validate_phase_transition("planning", "orbit")
        assert not invalid_trans
        health = compute_mission_health(ms)
        assert isinstance(health, float)
        pi_val = phase_index("planning")
        assert pi_val == 0
        assert isinstance(VALID_PHASES, list)

    elif bucket == 2:
        # orbit service + planner service
        period = compute_orbital_period(float(idx % 800 + 200))
        assert isinstance(period, float)
        assert period > 0.0
        decay = orbital_decay_rate(
            float(idx % 600 + 200),
            area_m2=float(idx % 10 + 1),
            mass_kg=float(idx % 500 + 100),
        )
        assert isinstance(decay, float)
        assert decay >= 0.0
        risk = predict_conjunction_risk(
            float(idx % 100 + 1), float(idx % 20 + 1)
        )
        assert isinstance(risk, float)
        assert risk >= 0.0
        assert risk <= 1.0
        band = altitude_band(float(idx % 40000 + 100))
        assert band in ("LEO", "MEO", "GEO")

        cfg = PlannerConfig(
            max_burns=idx % 8 + 2,
            safety_factor=1.15,
            fuel_reserve_pct=0.10,
        )
        burns = build_burn_sequence(
            delta_v_required=float(idx % 10 + 1) * 0.1,
            available_fuel_kg=float(idx % 150 + 50),
            config=cfg,
        )
        assert isinstance(burns, list)
        valid_budget = validate_fuel_budget(
            total_delta_v=float(idx % 5 + 1) * 0.2,
            fuel_kg=float(idx % 100 + 50),
        )
        assert isinstance(valid_budget, bool)
        hours = estimate_timeline_hours(len(burns), spacing_minutes=90)
        assert isinstance(hours, float)
        assert hours >= 0.0
        ps = plan_summary(burns)
        assert isinstance(ps, dict)
        assert "num_burns" in ps
        assert "total_delta_v" in ps
        assert "total_fuel_cost" in ps

    elif bucket == 3:
        # resilience service + policy service
        plan = build_replay_plan(
            event_count=idx % 200 + 10,
            timeout_s=idx % 30 + 5,
            parallel=idx % 2 == 0,
        )
        assert isinstance(plan, ReplayPlan)
        assert plan.budget >= 0
        assert plan.mode in ("skip", "full", "partial", "sampled")
        mode = classify_replay_mode(100, idx % 100 + 1)
        assert mode in ("full", "partial", "sampled")
        coverage = estimate_replay_coverage(plan)
        assert isinstance(coverage, float)
        assert coverage >= 0.0
        fp = failover_priority(
            region=f"region-{idx % 3}",
            is_degraded=idx % 4 == 0,
            latency_ms=idx % 300 + 20,
        )
        assert isinstance(fp, float)

        decision = evaluate_policy_gate(
            risk_score=float(idx % 100),
            comms_degraded=idx % 3 == 0,
            has_mfa=idx % 2 == 0,
            priority=idx % 6,
        )
        assert isinstance(decision, PolicyDecision)
        assert isinstance(decision.approved, bool)
        assert isinstance(decision.reason, str)
        dual = enforce_dual_control(
            f"op-{idx}", f"op-{idx + 1}", "launch"
        )
        assert isinstance(dual, bool)
        rb = risk_band(float(idx % 100))
        assert rb in ("low", "medium", "high", "critical")
        cs = compute_compliance_score(
            incidents_resolved=idx % 50,
            incidents_total=max(idx % 60, 1),
            sla_met_pct=float(idx % 100),
        )
        assert isinstance(cs, float)

    elif bucket == 4:
        # security service + audit service
        secret = f"key-{idx % 15}"
        command = f"execute-burn-{idx}"
        import hmac as _hmac
        from hashlib import sha256 as _sha256
        sig = _hmac.new(
            secret.encode(), command.encode(), _sha256
        ).hexdigest()
        auth_result = validate_command_auth(
            command=command,
            signature=sig,
            secret=secret,
            required_role="operator",
            user_roles={"operator", "engineer"},
        )
        assert isinstance(auth_result, dict)
        assert "authorized" in auth_result
        assert "signature_valid" in auth_result
        assert "role_valid" in auth_result
        path_ok = check_path_traversal(f"data/sat-{idx % 5}/log.txt")
        assert isinstance(path_ok, bool)
        rl = rate_limit_check(
            request_count=idx % 20,
            limit=15,
            window_s=60,
        )
        assert isinstance(rl, dict)
        assert "allowed" in rl
        assert "remaining" in rl
        sanitized = sanitize_input(f"  command-{idx}  ", max_length=100)
        assert isinstance(sanitized, str)
        rs = compute_risk_score(
            failed_attempts=idx % 8,
            geo_anomaly=idx % 5 == 0,
            time_anomaly=idx % 7 == 0,
        )
        assert isinstance(rs, float)
        assert rs >= 0.0
        assert rs <= 100.0

        ledger = AuditLedger()
        evt = AuditEvent(
            event_id=f"evt-{idx}",
            timestamp=now,
            service="gateway",
            action="dispatch",
            operator_id=f"op-{idx % 10}",
            payload={"target": f"sat-{idx % 5}"},
        )
        appended = ledger.append(evt)
        assert appended
        assert ledger.count() == 1
        events = ledger.get_events()
        assert len(events) == 1
        by_svc = ledger.events_by_service("gateway")
        assert len(by_svc) == 1
        by_op = ledger.events_by_operator(f"op-{idx % 10}")
        assert len(by_op) == 1
        ve = validate_audit_event(evt)
        assert isinstance(ve, list)
        summary = summarize_ledger(ledger)
        assert isinstance(summary, dict)
        compliant = is_compliant_audit_trail(
            ledger, required_services={"gateway", "identity"}
        )
        assert isinstance(compliant, bool)

    elif bucket == 5:
        # analytics + notifications services
        satellites = [
            {
                "satellite_id": f"sat-{idx}-{k}",
                "fuel_kg": float((idx + k * 17) % 200 + 10),
                "power_kw": float((idx + k * 3) % 10 + 1),
                "temperature_c": float((idx + k * 7) % 100 - 20),
            }
            for k in range(idx % 5 + 2)
        ]
        health = compute_fleet_health(satellites)
        assert isinstance(health, float)
        assert health > 0.0
        values = [float((idx * 3 + j) % 50 + 1) for j in range(idx % 8 + 10)]
        trend = trend_analysis(values, window=5)
        assert trend in (
            "insufficient_data", "improving", "degrading", "stable",
        )
        anomalies = anomaly_report(values, threshold_z=2.0)
        assert isinstance(anomalies, list)
        ranking = satellite_ranking(satellites)
        assert isinstance(ranking, list)
        assert len(ranking) == len(satellites)

        planner = NotificationPlanner(
            severity=idx % 5 + 1, operator_id=f"op-{idx % 10}"
        )
        channels = planner.plan_channels()
        assert isinstance(channels, list)
        assert len(channels) > 0
        throttled = should_throttle(
            recent_count=idx % 15,
            max_per_window=10,
            severity=idx % 5 + 1,
        )
        assert isinstance(throttled, bool)
        notif = format_notification(
            operator_id=f"op-{idx % 10}",
            severity=idx % 5 + 1,
            message=f"Alert for case {idx}",
        )
        assert isinstance(notif, dict)
        assert "operator_id" in notif
        assert "severity" in notif
        assert "message" in notif
        assert "channels" in notif

    elif bucket == 6:
        # reporting service
        inc_list = [
            {"ticket_id": f"t-{idx}-{j}", "severity": (idx + j) % 5 + 1,
             "subsystem": "comms", "description": f"issue-{j}"}
            for j in range(idx % 6 + 2)
        ]
        ranked = rank_incidents(inc_list)
        assert isinstance(ranked, list)
        assert len(ranked) == len(inc_list)
        cr = compliance_report(
            resolved=idx % 40 + 1,
            total=max(idx % 50 + 1, idx % 40 + 1),
            sla_met_pct=float(idx % 100),
        )
        assert isinstance(cr, dict)
        assert "resolution_rate" in cr
        assert "sla_met_pct" in cr
        assert "compliant" in cr
        for inc in inc_list[:3]:
            row = format_incident_row(inc)
            assert isinstance(row, str)
            assert len(row) > 0
        exec_summary = generate_executive_summary(
            incidents=inc_list,
            fleet_health=float(idx % 100) / 100.0,
        )
        assert isinstance(exec_summary, dict)
        assert "total_incidents" in exec_summary
        assert "critical_incidents" in exec_summary
        assert "fleet_health" in exec_summary
        assert "health_status" in exec_summary
        mr = mission_report(
            mission_id=f"m-{idx}",
            burns_executed=idx % 10,
            fuel_remaining_kg=float(idx % 150 + 20),
            incidents=idx % 8,
        )
        assert isinstance(mr, dict)
        assert "mission_id" in mr
        assert "burns_executed" in mr
        assert "fuel_remaining_kg" in mr
        assert "efficiency" in mr

    elif bucket == 7:
        # cross-service: notifications batch + analytics + reporting
        operators = [f"op-{idx % 10 + k}" for k in range(idx % 3 + 2)]
        batch = batch_notify(
            operators=operators,
            severity=idx % 5 + 1,
            message=f"Cross-service alert {idx}",
        )
        assert isinstance(batch, list)
        assert len(batch) == len(operators)
        ns = notification_summary(batch)
        assert isinstance(ns, dict)
        assert len(ns) > 0
        satellites = [
            {
                "satellite_id": f"sat-{idx}-{k}",
                "fuel_kg": float(idx % 180 + 20),
                "power_kw": float(idx % 8 + 2),
                "temperature_c": 22.0,
            }
            for k in range(3)
        ]
        fleet_h = compute_fleet_health(satellites)
        assert isinstance(fleet_h, float)
        ranking = satellite_ranking(satellites)
        assert isinstance(ranking, list)
        assert len(ranking) == 3
        exec_summary = generate_executive_summary(
            incidents=[
                {"severity": idx % 5 + 1},
                {"severity": (idx + 2) % 5 + 1},
            ],
            fleet_health=fleet_h,
        )
        assert isinstance(exec_summary, dict)
        assert exec_summary["total_incidents"] == 2


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
