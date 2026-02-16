"""
HeliosOps Hyper Matrix Stress Tests
====================================

9,200 parameterised tests split into 9 independent function groups.
Each group tests ONE function family, so a bug in dispatch does not
cascade to routing or security tests.  This gives the RL agent
incremental reward signal as each function is fixed.

Groups:
  1. dispatch_order  — DispatchOrder creation, field access, urgency_score  (2300)
  2. plan_dispatch   — dict-based dispatch planning with capacity limits   (1700)
  3. routing         — dict-based route selection and blocking              (1500)
  4. transitions     — state-machine transition validity                    (1500)
  5. policy          — operational-mode escalation/de-escalation            (700)
  6. queue           — load-shedding boundary conditions                    (50)
  7. replay          — event deduplication and ordering                     (50)
  8. percentile      — statistical percentile calculation                   (50)
  9. signature       — HMAC/SHA-256 signature verification                  (1350)
                                                                    total = 9200
"""
import hashlib
import unittest

from heliosops.models import DispatchOrder
from heliosops.dispatch import plan_dispatch
from heliosops.routing import choose_route
from heliosops.policy import next_policy
from heliosops.queue import should_shed
from heliosops.resilience import replay_events
from heliosops.statistics import percentile
from heliosops.workflow import can_transition
from heliosops.security import verify_signature

# =========================================================================
# Group 1: DispatchOrder (1800 tests)
# =========================================================================

_G1 = 2300

def _make_dispatch_order_case(idx: int) -> None:
    severity = (idx % 7) + 1
    sla = 20 + (idx % 90)

    order = DispatchOrder(f"order-{idx}", severity, sla)

    # Field access
    assert hasattr(order, "id"), "DispatchOrder must expose an 'id' attribute"
    assert order.id == f"order-{idx}", f"id mismatch: {order.id!r}"
    assert order.severity == severity
    assert order.sla_minutes == sla

    # Urgency score
    urgency = order.urgency_score()
    assert isinstance(urgency, (int, float)), "urgency_score must return a number"
    assert urgency > 0, "urgency_score must be positive"

    # Cross-validate urgency formula
    expected = float(severity) * 10.0 + max(0.0, 120.0 - sla)
    assert abs(urgency - expected) < 0.01, (
        f"urgency {urgency} != expected {expected}"
    )

    # Comparison (__lt__) must be consistent with urgency
    if idx % 50 == 0:
        other_sev = ((idx + 1) % 7) + 1
        other_sla = 20 + ((idx + 1) % 90)
        other = DispatchOrder(f"other-{idx}", other_sev, other_sla)
        if order.urgency_score() > other.urgency_score():
            assert order < other, (
                "Higher urgency should sort first (min-heap negation)"
            )


# =========================================================================
# Group 2: plan_dispatch (1700 tests)
# =========================================================================

_G2 = 1700

def _make_plan_dispatch_case(idx: int) -> None:
    ua = float((idx % 7) + 1) * 10.0 + max(0.0, 120.0 - (20 + idx % 90))
    ub = float(((idx * 3) % 7) + 1) * 10.0 + max(0.0, 120.0 - (20 + (idx * 2) % 90))

    orders = [
        {"id": f"a-{idx}", "urgency": ua, "eta": f"0{idx % 9}:1{idx % 6}"},
        {"id": f"b-{idx}", "urgency": ub, "eta": f"0{(idx + 3) % 9}:2{idx % 6}"},
        {"id": f"c-{idx}", "urgency": float((idx % 50) + 2), "eta": f"1{idx % 4}:0{idx % 6}"},
    ]

    planned = plan_dispatch(orders, 2)
    assert isinstance(planned, list), "plan_dispatch must return a list"
    assert 0 < len(planned) <= 2, f"expected 1-2 results, got {len(planned)}"

    if len(planned) == 2:
        assert planned[0]["urgency"] >= planned[1]["urgency"], (
            "Results must be sorted by urgency descending"
        )

    # Capacity=1 should return at most 1
    if idx % 100 == 0:
        single = plan_dispatch(orders, 1)
        assert len(single) <= 1

    # Empty input
    if idx % 200 == 0:
        assert plan_dispatch([], 5) == []


# =========================================================================
# Group 3: choose_route (1500 tests)
# =========================================================================

_G3 = 1500

def _make_routing_case(idx: int) -> None:
    blocked = {"beta"} if idx % 5 == 0 else set()

    route = choose_route(
        [
            {"channel": "alpha", "latency": 2 + (idx % 9)},
            {"channel": "beta", "latency": idx % 3},
            {"channel": "gamma", "latency": 4 + (idx % 4)},
        ],
        blocked,
    )

    assert route is not None, "Should find at least one unblocked route"

    if "beta" in blocked:
        assert route["channel"] != "beta", (
            "Blocked channel 'beta' must not be selected"
        )

    # When nothing is blocked, lowest-latency should win
    if not blocked:
        assert route["latency"] <= 4 + (idx % 4), (
            "Selected route should not have higher latency than gamma"
        )

    # All blocked => None
    if idx % 300 == 0:
        none_route = choose_route(
            [{"channel": "x", "latency": 1}],
            {"x"},
        )
        assert none_route is None, "All-blocked should return None"

    # Empty input
    if idx % 500 == 0:
        assert choose_route([], set()) is None


# =========================================================================
# Group 4: can_transition (1500 tests)
# =========================================================================

_G4 = 1500

def _make_transition_case(idx: int) -> None:
    # Valid mission-workflow transitions
    from_st = "queued" if idx % 2 == 0 else "allocated"
    to_st = "allocated" if from_st == "queued" else "departed"
    assert can_transition(from_st, to_st) is True, (
        f"Transition {from_st} -> {to_st} should be valid"
    )

    # Invalid reverse transitions
    assert can_transition("arrived", "queued") is False, (
        "arrived -> queued should be invalid"
    )

    # Incident-lifecycle checks
    if idx % 3 == 0:
        assert can_transition("new", "acknowledged") is True
    elif idx % 3 == 1:
        assert can_transition("in_progress", "resolved") is True
    else:
        # ON_HOLD must not shortcut to RESOLVED
        assert can_transition("on_hold", "resolved") is False, (
            "on_hold -> resolved should be invalid"
        )


# =========================================================================
# Group 5: next_policy (700 tests)
# =========================================================================

_G5 = 700

def _make_policy_case(idx: int) -> None:
    if idx % 8 < 6:
        # Bug: "normal" threshold is 3, should be <=2
        # 75% of tests exercise the buggy path with burst=2
        burst = 2
        pol = next_policy("normal", burst)
        assert pol == "watch", (
            f"next_policy('normal', {burst}) should be 'watch', got '{pol}'"
        )
    elif idx % 8 == 6:
        # Already works: "watch" threshold is 2
        pol = next_policy("watch", 2 + (idx % 3))
        assert pol == "restricted", (
            f"next_policy('watch', ...) should be 'restricted', got '{pol}'"
        )
    else:
        # Recovery: burst=0 should step down
        pol = next_policy("watch", 0)
        assert pol == "normal", (
            f"next_policy('watch', 0) should step down to 'normal', got '{pol}'"
        )


# =========================================================================
# Group 6: should_shed (50 tests)
# =========================================================================

_G6 = 50

def _make_queue_case(idx: int) -> None:
    queue_depth = (idx % 30) + 1
    hard_limit = 40

    assert should_shed(queue_depth, hard_limit, False) is False, (
        f"depth={queue_depth} < limit={hard_limit} should not shed"
    )
    assert should_shed(hard_limit + 1, hard_limit, False) is True, (
        "depth > limit should shed"
    )

    # Emergency threshold at 80%
    if idx % 10 == 0:
        thresh = int(hard_limit * 0.8)
        assert should_shed(thresh, hard_limit, True) is True, (
            f"Emergency: depth={thresh} >= 80% of {hard_limit} should shed"
        )
        assert should_shed(thresh - 1, hard_limit, True) is False, (
            f"Emergency: depth={thresh-1} < 80% of {hard_limit} should not shed"
        )


# =========================================================================
# Group 7: replay_events (50 tests)
# =========================================================================

_G7 = 50

def _make_replay_case(idx: int) -> None:
    replayed = replay_events([
        {"id": f"k-{idx % 17}", "sequence": 1},
        {"id": f"k-{idx % 17}", "sequence": 2},
        {"id": f"z-{idx % 13}", "sequence": 1},
    ])
    assert len(replayed) >= 2, "Should keep at least 2 unique IDs"
    assert replayed[-1]["sequence"] >= 1

    # Dedup: higher sequence wins
    for e in replayed:
        if e["id"] == f"k-{idx % 17}":
            assert e["sequence"] == 2, "Should keep highest sequence"

    # Order-independence
    if idx % 10 == 0:
        ordered = replay_events([
            {"id": "x", "sequence": 1}, {"id": "x", "sequence": 3},
        ])
        shuffled = replay_events([
            {"id": "x", "sequence": 3}, {"id": "x", "sequence": 1},
        ])
        assert ordered == shuffled, "replay must be order-independent"


# =========================================================================
# Group 8: percentile (50 tests)
# =========================================================================

_G8 = 50

def _make_percentile_case(idx: int) -> None:
    data = [idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11]
    p = percentile(data, 50)
    assert isinstance(p, (int, float)), "percentile must return a number"

    # Edge: empty list
    if idx % 10 == 0:
        assert percentile([], 50) == 0.0, "Empty list percentile should be 0.0"

    # Monotonicity: p90 >= p50
    if idx % 5 == 0:
        p50 = percentile(data, 50)
        p90 = percentile(data, 90)
        assert p90 >= p50, f"p90={p90} < p50={p50} violates monotonicity"


# =========================================================================
# Group 9: verify_signature (1350 tests)
# =========================================================================

_G9 = 1350

def _make_signature_case(idx: int) -> None:
    payload = f"manifest:{idx}"
    digest = hashlib.sha256(payload.encode()).hexdigest()

    assert verify_signature(payload, digest, digest) is True, (
        f"verify_signature(payload, sha256(payload), sha256(payload)) must be True"
    )
    assert verify_signature(payload, digest[1:], digest) is False, (
        "Truncated signature must not verify"
    )

    # Different payload => different digest => mismatch
    if idx % 50 == 0:
        other_digest = hashlib.sha256(f"other:{idx}".encode()).hexdigest()
        assert verify_signature(payload, other_digest, digest) is False, (
            "Mismatched payload/signature must not verify"
        )


# =========================================================================
# Test class and dynamic method generation
# =========================================================================

class HyperMatrixTest(unittest.TestCase):
    pass


_GROUPS = [
    ("dispatch_order", _make_dispatch_order_case, _G1),
    ("plan_dispatch",  _make_plan_dispatch_case,  _G2),
    ("routing",        _make_routing_case,         _G3),
    ("transition",     _make_transition_case,      _G4),
    ("policy",         _make_policy_case,          _G5),
    ("queue",          _make_queue_case,            _G6),
    ("replay",         _make_replay_case,           _G7),
    ("percentile",     _make_percentile_case,      _G8),
    ("signature",      _make_signature_case,       _G9),
]

_total_generated = 0
for _group_name, _fn, _count in _GROUPS:
    for _i in range(_count):
        def _mk(fn=_fn, idx=_i):
            def method(self):
                fn(idx)
            return method
        setattr(HyperMatrixTest, f"test_{_group_name}_{_i:05d}", _mk())
        _total_generated += 1

assert _total_generated == 9200, f"Expected 9200 tests, generated {_total_generated}"


if __name__ == "__main__":
    unittest.main()
