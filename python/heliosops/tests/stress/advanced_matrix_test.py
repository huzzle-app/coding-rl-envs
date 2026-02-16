"""
HeliosOps Advanced Stress Tests
================================

Exercises domain logic invariants, state machine correctness, distributed
protocol semantics, and cross-module integration consistency.
"""
import inspect as _inspect
import os as _os
import time
import unittest
from datetime import datetime, timedelta, timezone

from heliosops.models import (
    Incident, IncidentStatus, Location, Unit, UnitType, UnitStatus,
)
from heliosops.dispatch import plan_dispatch
from heliosops.policy import EventProjection
from heliosops.geo import nearest_units, haversine
from heliosops.routing import choose_route, optimize_multi_stop, clear_tsp_cache
from heliosops.workflow import (
    can_transition, execute_transition, classify_incident, auto_triage,
)
from heliosops.resilience import CircuitBreaker, CircuitState
from heliosops.scheduler import chord_callback_check
import heliosops.scheduler as _sched_mod


# =========================================================================
# Category 1  Latent: EventProjection reference integrity
# =========================================================================

def _make_latent_case(idx: int) -> None:
    proj = EventProjection()

    if idx % 3 == 0:
        # Update events must MERGE into existing entity, not replace it
        fields = {
            "name": f"entity-{idx}",
            "version": 1,
            "active": True,
            "priority": idx % 5,
        }
        proj.append_event({
            "type": "created", "entity_id": f"e-{idx}", "data": dict(fields),
        })
        proj.append_event({
            "type": "updated", "entity_id": f"e-{idx}",
            "data": {"version": 2},
        })
        proj.refresh()
        snap = proj.get_projection()
        entity = snap.get(f"e-{idx}", {})
        assert "name" in entity, (
            "Field 'name' lost after partial update — update replaced instead of merging"
        )
        assert entity.get("version") == 2
        assert entity.get("active") is True

    elif idx % 3 == 1:
        # Mutating the returned projection must not corrupt event source data
        original = {"score": 100 + idx, "tag": f"t-{idx}"}
        proj.append_event({
            "type": "created", "entity_id": f"e-{idx}", "data": original,
        })
        proj.refresh()
        snap = proj.get_projection()
        snap[f"e-{idx}"]["score"] = -999
        assert original["score"] == 100 + idx, (
            "Modifying projection dict corrupted the original event data"
        )

    else:
        # Events appended after first get_projection must be visible
        proj.append_event({
            "type": "created", "entity_id": f"a-{idx}", "data": {"v": 1},
        })
        proj.get_projection()
        proj.append_event({
            "type": "created", "entity_id": f"b-{idx}", "data": {"v": 2},
        })
        snap = proj.get_projection()
        assert f"b-{idx}" in snap, (
            "Events appended after caching are invisible in projection"
        )


# =========================================================================
# Category 2  Domain Logic: nearest_units distance must be in km
# =========================================================================

def _make_domain_case(idx: int) -> None:
    lat_offset = 0.05 + (idx % 10) * 0.02
    base_lat = 35.0 + (idx % 5) * 5.0

    origin = Location(latitude=base_lat, longitude=-74.0)
    unit_loc = Location(latitude=base_lat + lat_offset, longitude=-74.0)

    unit = Unit(
        id=f"u-{idx}", name=f"Unit-{idx}",
        unit_type=UnitType.FIRE, status=UnitStatus.AVAILABLE,
        location=unit_loc,
    )

    results = nearest_units(origin, [unit], radius_km=100.0)
    assert len(results) >= 1, "Unit within 100km should be found"

    reported = results[0]["distance_km"]
    expected = haversine(
        origin.latitude, origin.longitude,
        unit_loc.latitude, unit_loc.longitude,
    )
    ratio = reported / max(expected, 0.001)
    assert 0.9 < ratio < 1.1, (
        f"distance_km={reported} vs haversine={expected:.2f}km "
        f"(ratio={ratio:.4f}, should be ~1.0)"
    )


# =========================================================================
# Category 3  Multi-step: TSP cache key collision + reference aliasing
# =========================================================================

def _make_multistep_case(idx: int) -> None:
    clear_tsp_cache()

    if idx % 2 == 0:
        # Different intermediates sharing endpoints must produce different routes
        A = Location(0.0, 0.0)
        C = Location(1.0, 1.0)
        B1 = Location(0.5 + idx * 0.01, 0.0)
        B2 = Location(0.0, 0.5 + idx * 0.01)

        r1 = optimize_multi_stop([A, B1, C])
        r2 = optimize_multi_stop([A, B2, C])

        coords1 = [(s.latitude, s.longitude) for s in r1]
        coords2 = [(s.latitude, s.longitude) for s in r2]
        assert coords1 != coords2, (
            "Routes with different intermediates returned identical results — "
            "cache key is too coarse"
        )
    else:
        # Caller modifications must not corrupt the cache
        A = Location(idx * 0.1, 0.0)
        B = Location(idx * 0.1 + 0.5, 0.0)
        C = Location(idx * 0.1 + 1.0, 0.0)

        r1 = optimize_multi_stop([A, B, C])
        expected_len = len(r1)
        r1.pop()

        r2 = optimize_multi_stop([A, B, C])
        assert len(r2) == expected_len, (
            f"Cache corrupted by caller: expected {expected_len} stops, got {len(r2)}"
        )


# =========================================================================
# Category 4  State Machine: invalid shortcuts + timestamp overwrite
# =========================================================================

def _make_statemachine_case(idx: int) -> None:
    if idx % 4 == 0:
        # ON_HOLD must not shortcut directly to RESOLVED
        assert can_transition("on_hold", "resolved") is False, (
            "on_hold -> resolved should be invalid; work must resume first"
        )

    elif idx % 4 == 1:
        # resolved_at must be preserved when an incident is reopened and re-resolved
        inc = Incident(
            id=f"sm-{idx}", title="ts-test", description="d",
            severity=3, status=IncidentStatus.IN_PROGRESS,
        )
        execute_transition(inc, "resolved")
        first_resolved = inc.resolved_at
        assert first_resolved is not None

        time.sleep(0.01)
        execute_transition(inc, "in_progress")
        execute_transition(inc, "resolved")
        assert inc.resolved_at == first_resolved, (
            "resolved_at was overwritten on re-resolution; "
            "first resolution timestamp should be preserved"
        )

    elif idx % 4 == 2:
        # Valid path: on_hold -> in_progress -> resolved (not on_hold -> resolved)
        inc = Incident(
            id=f"sm-{idx}", title="path-test", description="d",
            severity=4, status=IncidentStatus.ACKNOWLEDGED,
        )
        execute_transition(inc, "on_hold")
        assert inc.status == IncidentStatus.ON_HOLD

        # Must go through IN_PROGRESS before resolving
        assert can_transition("on_hold", "in_progress") is True
        execute_transition(inc, "in_progress")
        execute_transition(inc, "resolved")
        assert inc.resolved_at is not None

    else:
        # acknowledged_at must be set only once
        inc = Incident(
            id=f"sm-{idx}", title="ack-once", description="d",
            severity=2, status=IncidentStatus.NEW,
        )
        execute_transition(inc, "acknowledged")
        first_ack = inc.acknowledged_at
        assert first_ack is not None

        # Move forward and create a new incident to re-test ack idempotency
        inc2 = Incident(
            id=f"sm2-{idx}", title="ack-twice", description="d",
            severity=2, status=IncidentStatus.NEW,
        )
        execute_transition(inc2, "acknowledged")
        ack1 = inc2.acknowledged_at
        time.sleep(0.01)
        # Force re-ack by manipulating status (to test the guard)
        inc2.status = IncidentStatus.NEW
        execute_transition(inc2, "acknowledged")
        assert inc2.acknowledged_at == ack1, (
            "acknowledged_at was overwritten on re-acknowledgment"
        )


# =========================================================================
# Category 5  Concurrency: CircuitBreaker must fully recover after success
# =========================================================================

def _make_concurrency1_case(idx: int) -> None:
    threshold = 2 + (idx % 4)
    cb = CircuitBreaker(
        failure_threshold=threshold,
        cooldown_seconds=0.0,
    )

    # Trip the circuit
    for _ in range(threshold):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN

    # Cooldown -> HALF_OPEN
    time.sleep(0.01)
    assert cb.state == CircuitState.HALF_OPEN

    # Successful probe -> CLOSED
    cb.record_success()
    assert cb.state == CircuitState.CLOSED

    # After recovery, failure count must be zero.
    # A single failure should NOT re-trip (threshold > 1).
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED, (
        f"Single failure after recovery tripped circuit "
        f"(threshold={threshold}); failure count was not reset"
    )


# =========================================================================
# Category 6  Concurrency: chord callback must not re-fire on late arrivals
# =========================================================================

def _make_concurrency2_case(idx: int) -> None:
    chord_id = f"chord-adv2-{idx}"
    _sched_mod._chord_completed.pop(chord_id, None)

    total = 3 + (idx % 4)
    fire_count = [0]

    def cb():
        fire_count[0] += 1

    # Complete all tasks -> callback fires once
    for _ in range(total):
        chord_callback_check(chord_id, total, cb)
    assert fire_count[0] == 1, (
        f"Callback should fire once after {total} completions, "
        f"fired {fire_count[0]} times"
    )

    # Late-arriving duplicate completions must NOT re-trigger
    for _ in range(total):
        chord_callback_check(chord_id, total, cb)
    assert fire_count[0] == 1, (
        f"Late arrivals re-triggered callback: fired {fire_count[0]} times"
    )

    _sched_mod._chord_completed.pop(chord_id, None)


# =========================================================================
# Category 7  Integration: classify_incident + auto_triage consistency
# =========================================================================

_TRIAGE_CASES = [
    ("Large fire with smoke and flames burning nearby buildings", "structure_fire", 4),
    ("Medical emergency: injury requiring ambulance, difficulty breathing", "medical_emergency", 4),
    ("Traffic collision involving multiple vehicles, crash on highway", "traffic_accident", 4),
    ("Chemical hazmat spill of toxic gas at industrial plant", "hazmat_spill", 4),
    ("Riot and looting, large crowd gathering", "civil_disturbance", 4),
]


def _make_integration_case(idx: int) -> None:
    desc, expected_cat, min_severity = _TRIAGE_CASES[idx % len(_TRIAGE_CASES)]

    probs = classify_incident(desc)
    total_prob = sum(probs.values())

    # Probabilities should be properly normalized (sum near 1.0 is ideal,
    # but at minimum the top score should be meaningful)
    top_cat = max(probs, key=lambda k: probs[k])
    top_score = probs[top_cat]

    assert top_cat == expected_cat, (
        f"Expected '{expected_cat}' for '{desc[:40]}...', got '{top_cat}'"
    )

    # Top score with many keyword matches should be significant
    assert top_score >= 0.15, (
        f"Top score {top_score} is too low for a description with "
        f"multiple matching keywords — normalization may be broken"
    )

    # auto_triage should assign severity >= min_severity for strong matches
    inc = Incident(
        id=f"int-{idx}", title="triage-test",
        description=desc, severity=3,
        status=IncidentStatus.NEW,
    )
    triage = auto_triage(inc)
    assert triage["suggested_severity"] >= min_severity, (
        f"auto_triage suggested severity {triage['suggested_severity']} "
        f"for a clear {expected_cat} (expected >= {min_severity})"
    )


# =========================================================================
# Category 8  Anti-tamper: source integrity and non-hardcoding checks
# =========================================================================

_HELIOSOPS_ROOT = _os.path.dirname(
    _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
)
_SRC_DIR = _os.path.join(_HELIOSOPS_ROOT, "heliosops")

_SOURCE_MODULES = [
    ("models.py", 300),
    ("dispatch.py", 300),
    ("routing.py", 200),
    ("policy.py", 200),
    ("queue.py", 250),
    ("security.py", 250),
    ("resilience.py", 250),
    ("workflow.py", 250),
    ("scheduler.py", 200),
    ("statistics.py", 200),
    ("geo.py", 200),
]


def _make_antitamper_case(idx: int) -> None:
    if idx < len(_SOURCE_MODULES):
        # Check source file existence and minimum line count
        mod_name, min_lines = _SOURCE_MODULES[idx]
        mod_path = _os.path.join(_SRC_DIR, mod_name)
        assert _os.path.isfile(mod_path), (
            f"Source module {mod_name} is missing — cannot be deleted"
        )
        with open(mod_path) as f:
            lines = f.readlines()
        assert len(lines) >= min_lines, (
            f"{mod_name} has {len(lines)} lines (min {min_lines}) — "
            f"file appears stubbed or truncated"
        )
    elif idx == 11:
        # plan_dispatch must produce different results for different inputs
        r1 = plan_dispatch(
            [{"id": "a", "urgency": 10, "eta": "09:00"}], 1,
        )
        r2 = plan_dispatch(
            [{"id": "b", "urgency": 5, "eta": "10:00"}], 1,
        )
        assert r1[0]["id"] != r2[0]["id"], (
            "plan_dispatch returned same result for different inputs — hardcoded"
        )
    elif idx == 12:
        # choose_route must vary with latency values
        r1 = choose_route(
            [{"channel": "x", "latency": 1}, {"channel": "y", "latency": 9}],
            set(),
        )
        r2 = choose_route(
            [{"channel": "x", "latency": 9}, {"channel": "y", "latency": 1}],
            set(),
        )
        assert r1["channel"] != r2["channel"], (
            "choose_route returned same channel regardless of latency — hardcoded"
        )
    elif idx == 13:
        # percentile must vary with data
        from heliosops.statistics import percentile
        p1 = percentile([1, 2, 3, 4, 5], 50)
        p2 = percentile([10, 20, 30, 40, 50], 50)
        assert p1 != p2, (
            "percentile returned same value for different data — hardcoded"
        )
    elif idx == 14:
        # replay_events must respect sequence numbers
        from heliosops.resilience import replay_events
        r = replay_events([
            {"id": "k", "sequence": 1}, {"id": "k", "sequence": 5},
        ])
        assert any(e["sequence"] == 5 for e in r), (
            "replay_events did not keep highest sequence — may be hardcoded"
        )
    elif idx == 15:
        # can_transition must have distinct True/False results
        valid = can_transition("queued", "allocated")
        invalid = can_transition("arrived", "queued")
        assert valid is True and invalid is False, (
            "can_transition returned same value for valid and invalid — hardcoded"
        )
    elif idx == 16:
        # Cross-module: dispatch + routing don't share mutable state
        plan_dispatch(
            [{"id": "z", "urgency": 99, "eta": "00:01"}], 1,
        )
        route = choose_route(
            [{"channel": "only", "latency": 1}], set(),
        )
        assert route is not None, (
            "choose_route returned None after plan_dispatch — shared state corruption"
        )
    elif idx == 17:
        # Cross-module: policy + queue independence
        from heliosops.policy import next_policy
        from heliosops.queue import should_shed
        next_policy("watch", 3)
        result = should_shed(5, 10, False)
        assert result is False, (
            "should_shed returned wrong result after next_policy call — shared state"
        )
    elif idx == 18:
        # Verify test files aren't truncated
        test_dir = _os.path.join(_HELIOSOPS_ROOT, "tests", "stress")
        hyper_path = _os.path.join(test_dir, "hyper_matrix_test.py")
        assert _os.path.isfile(hyper_path), "hyper_matrix_test.py missing"
        with open(hyper_path) as f:
            content = f.read()
        assert "HyperMatrixTest" in content, (
            "hyper_matrix_test.py does not contain HyperMatrixTest class — truncated"
        )
        assert len(content) > 5000, (
            "hyper_matrix_test.py is too small — likely truncated"
        )
    elif idx == 19:
        # Verify DispatchOrder is a proper class with expected attributes
        from heliosops.models import DispatchOrder
        assert _inspect.isclass(DispatchOrder), "DispatchOrder must be a class"
        sig = _inspect.signature(DispatchOrder)
        assert len(sig.parameters) >= 2, (
            f"DispatchOrder has {len(sig.parameters)} params, expected >= 2"
        )


# =========================================================================
# Category 9  Cross-module: dispatch → routing → workflow chains
# =========================================================================

def _make_crossmodule_case(idx: int) -> None:
    from heliosops.models import DispatchOrder
    from heliosops.queue import should_shed
    from heliosops.resilience import replay_events
    from heliosops.statistics import percentile
    from heliosops.policy import next_policy

    if idx % 6 == 0:
        # Full chain: dispatch → route → transition
        orders = plan_dispatch([
            {"id": f"cm-a-{idx}", "urgency": 10 + idx, "eta": "09:00"},
            {"id": f"cm-b-{idx}", "urgency": 5 + idx, "eta": "10:00"},
        ], 2)
        assert len(orders) >= 1, "plan_dispatch must return at least 1 order"

        route = choose_route([
            {"channel": "primary", "latency": 2},
            {"channel": "backup", "latency": 8},
        ], set())
        assert route["channel"] == "primary", (
            "Unblocked lowest-latency route should be 'primary'"
        )

        assert can_transition("queued", "allocated") is True
        assert can_transition("allocated", "departed") is True

    elif idx % 6 == 1:
        # DispatchOrder urgency → plan_dispatch sorting consistency
        sev_a, sla_a = 7, 25
        sev_b, sla_b = 2, 100
        ua = float(sev_a) * 10.0 + max(0.0, 120.0 - sla_a)
        ub = float(sev_b) * 10.0 + max(0.0, 120.0 - sla_b)

        orders = plan_dispatch([
            {"id": "high", "urgency": ua, "eta": "08:00"},
            {"id": "low", "urgency": ub, "eta": "12:00"},
        ], 2)
        assert len(orders) == 2
        assert orders[0]["urgency"] >= orders[1]["urgency"], (
            "plan_dispatch must sort by urgency descending"
        )

        # Cross-validate with DispatchOrder model
        do = DispatchOrder(f"cm-{idx}", sev_a, sla_a)
        assert hasattr(do, "id"), "DispatchOrder must have id field"
        model_urgency = do.urgency_score()
        assert abs(model_urgency - ua) < 0.01, (
            f"DispatchOrder.urgency_score()={model_urgency} != "
            f"manual formula={ua}"
        )

    elif idx % 6 == 2:
        # Policy escalation → queue shedding chain
        pol = next_policy("normal", 2)
        assert pol == "watch", (
            "normal + burst=2 should escalate to watch"
        )
        # Under watch policy, queue at 85% should shed in emergency
        assert should_shed(85, 100, True) is True, (
            "Emergency at 85% should trigger shedding"
        )

    elif idx % 6 == 3:
        # Replay → percentile pipeline
        events = [
            {"id": f"ev-{idx}", "sequence": i}
            for i in range(1, 6)
        ]
        events.append({"id": f"ev-{idx}", "sequence": 3})  # duplicate
        replayed = replay_events(events)

        # Should dedup to 1 entry with highest sequence
        ev_count = sum(1 for e in replayed if e["id"] == f"ev-{idx}")
        assert ev_count == 1, (
            f"Expected 1 deduped entry, got {ev_count}"
        )
        seq = next(e["sequence"] for e in replayed if e["id"] == f"ev-{idx}")
        assert seq == 5, f"Should keep sequence=5, got {seq}"

        # Use sequences as data for percentile
        seqs = [e["sequence"] for e in replayed]
        p50 = percentile(seqs, 50)
        assert isinstance(p50, (int, float))

    elif idx % 6 == 4:
        # State machine + security chain
        from heliosops.security import verify_signature
        import hashlib

        # Verify a mission can progress through states
        assert can_transition("new", "acknowledged") is True
        assert can_transition("acknowledged", "in_progress") is True
        assert can_transition("on_hold", "resolved") is False, (
            "on_hold → resolved must be invalid"
        )

        # Verify a dispatch manifest signature
        payload = f"dispatch-manifest-{idx}"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        assert verify_signature(payload, digest, digest) is True, (
            "Valid SHA-256 signature must verify"
        )

    else:
        # Routing + workflow + queue combined
        route = choose_route([
            {"channel": "east", "latency": 3 + idx % 5},
            {"channel": "west", "latency": 1 + idx % 3},
        ], set())
        assert route is not None

        # After routing, check workflow allows forward progress only
        assert can_transition("queued", "allocated") is True
        assert can_transition("departed", "queued") is False, (
            "Cannot go backward in mission lifecycle"
        )

        # Queue should not shed below limit
        assert should_shed(idx % 10, 100, False) is False


# =========================================================================
# Generate test methods using setattr pattern
# =========================================================================

class AdvancedMatrixTest(unittest.TestCase):
    pass


_CATS = [
    ("latent", _make_latent_case, 30),
    ("domain", _make_domain_case, 30),
    ("multistep", _make_multistep_case, 25),
    ("statemachine", _make_statemachine_case, 24),
    ("circuitbreaker", _make_concurrency1_case, 25),
    ("chord", _make_concurrency2_case, 25),
    ("integration", _make_integration_case, 25),
    ("antitamper", _make_antitamper_case, 20),
    ("crossmodule", _make_crossmodule_case, 30),
]

for _cat, _fn, _n in _CATS:
    for _i in range(_n):
        def _mk(fn=_fn, idx=_i):
            def method(self):
                fn(idx)
            return method
        setattr(AdvancedMatrixTest, f"test_{_cat}_{_i:04d}", _mk())


if __name__ == "__main__":
    unittest.main()
