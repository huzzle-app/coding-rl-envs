"""
HeliosOps Advanced Stress Tests
================================

Exercises domain logic invariants, state machine correctness, distributed
protocol semantics, and cross-module integration consistency.
"""
import time
import unittest
from datetime import datetime, timedelta, timezone

from heliosops.models import (
    Incident, IncidentStatus, Location, Unit, UnitType, UnitStatus,
)
from heliosops.policy import EventProjection
from heliosops.geo import nearest_units, haversine
from heliosops.routing import optimize_multi_stop, clear_tsp_cache
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
