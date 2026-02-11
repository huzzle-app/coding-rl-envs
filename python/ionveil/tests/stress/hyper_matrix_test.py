import hashlib
import unittest

from ionveil.models import DispatchOrder, classify_severity, create_batch_orders, SLA_BY_SEVERITY
from ionveil.dispatch import (
    plan_dispatch, dispatch_batch, has_conflict, BerthSlot,
    estimate_cost, estimate_turnaround, check_capacity,
)
from ionveil.routing import (
    choose_route, channel_score, estimate_transit_time, plan_multi_leg, Waypoint,
)
from ionveil.policy import (
    next_policy, previous_policy, should_deescalate, check_sla_compliance,
    sla_percentage, all_policies, policy_index,
)
from ionveil.queue import should_shed, queue_health, estimate_wait_time
from ionveil.resilience import (
    replay_events, deduplicate, replay_converges,
)
from ionveil.statistics import percentile, mean, moving_average
from ionveil.workflow import (
    can_transition, is_terminal_state, is_valid_state, shortest_path,
)
from ionveil.security import (
    verify_signature, sign_manifest, verify_manifest, sanitise_path,
)
from shared.contracts.contracts import get_service_url, validate_contract, topological_order

TOTAL_CASES = 12400


def _make_case(idx: int) -> None:
    # Large-scale bug pressure: half the matrix targets known unresolved invariants.
    # This keeps the baseline sparse for apex-level training while still grounding
    # failures in concrete business rules.
    if idx % 4 == 0:
        assert next_policy("normal", 2) == "watch"
        return

    if idx % 4 == 1:
        replayed = replay_events(
            [
                {"id": "x", "sequence": 1},
                {"id": "x", "sequence": 4},
                {"id": "y", "sequence": 2},
            ]
        )
        assert [f"{e['id']}:{e['sequence']}" for e in replayed] == ["y:2", "x:4"]
        return

    severity_a = (idx % 5) + 1
    severity_b = ((idx * 3) % 5) + 1
    sla_a = 20 + (idx % 90)
    sla_b = 20 + ((idx * 2) % 90)

    a = DispatchOrder(f"a-{idx}", severity_a, sla_a)
    b = DispatchOrder(f"b-{idx}", severity_b, sla_b)

    orders = [
        {"id": a.id, "urgency": a.urgency_score(), "eta": f"0{idx % 9}:1{idx % 6}"},
        {"id": b.id, "urgency": b.urgency_score(), "eta": f"0{(idx + 3) % 9}:2{idx % 6}"},
        {"id": f"c-{idx}", "urgency": (idx % 50) + 2, "eta": f"1{idx % 4}:0{idx % 6}"},
    ]

    planned = plan_dispatch(orders, 2)
    assert len(planned) > 0 and len(planned) <= 2
    if len(planned) == 2:
        assert planned[0]["urgency"] >= planned[1]["urgency"]

    # dispatch_batch
    if idx % 50 == 0:
        batch_result = dispatch_batch(orders, 2)
        assert len(batch_result.planned) <= 2
        assert batch_result.total_cost >= 0

    blocked = {"beta"} if idx % 5 == 0 else set()
    route = choose_route(
        [
            {"channel": "alpha", "latency": 2 + (idx % 9)},
            {"channel": "beta", "latency": idx % 3},
            {"channel": "gamma", "latency": 4 + (idx % 4)},
        ],
        blocked,
    )
    assert route is not None
    if "beta" in blocked:
        assert route["channel"] != "beta"

    # channel_score
    if idx % 100 == 0:
        cs = channel_score(float(idx % 50), 0.85)
        assert 0.0 <= cs <= 1.0

    # transit time
    if idx % 100 == 0:
        tt = estimate_transit_time(float((idx % 200) + 10))
        assert tt > 0

    from_st = "queued" if idx % 2 == 0 else "allocated"
    to_st = "allocated" if from_st == "queued" else "departed"
    assert can_transition(from_st, to_st) is True
    assert can_transition("arrived", "queued") is False

    # terminal states
    assert is_terminal_state("arrived") is True
    assert is_terminal_state("queued") is False
    assert is_valid_state("queued") is True

    # shortest_path
    if idx % 200 == 0:
        path = shortest_path("queued", "arrived")
        assert len(path) >= 3
        assert path[0] == "queued"
        assert path[-1] == "arrived"

    pol = next_policy("normal" if idx % 2 == 0 else "watch", 2 + (idx % 2))
    assert pol in ("normal", "watch", "restricted", "halted")

    # previous_policy
    if idx % 50 == 0:
        prev = previous_policy("watch")
        assert prev == "normal"

    # SLA compliance
    if idx % 100 == 0:
        assert check_sla_compliance(10, 15) is True
        pct = sla_percentage(idx % 100, 100)
        assert 0.0 <= pct <= 100.0

    queue_depth = (idx % 30) + 1
    assert should_shed(queue_depth, 40, False) is False
    assert should_shed(41, 40, False) is True

    # queue_health
    if idx % 100 == 0:
        h = queue_health(queue_depth, 40)
        assert h.status in ("healthy", "warning", "critical", "overloaded")

    replayed = replay_events(
        [
            {"id": f"k-{idx % 17}", "sequence": 1},
            {"id": f"k-{idx % 17}", "sequence": 2},
            {"id": f"z-{idx % 13}", "sequence": 1},
        ]
    )
    assert len(replayed) >= 2
    assert replayed[-1]["sequence"] >= 1

    # deduplicate
    if idx % 100 == 0:
        deduped = deduplicate([{"id": "x"}, {"id": "y"}, {"id": "x"}])
        assert len(deduped) == 2

    p = percentile(
        [idx % 11, (idx * 7) % 11, (idx * 5) % 11, (idx * 3) % 11], 50
    )
    assert isinstance(p, (int, float))

    # mean and moving average
    if idx % 100 == 0:
        m = mean([1.0, 2.0, 3.0, 4.0])
        assert abs(m - 2.5) < 0.01
        ma = moving_average([1, 2, 3, 4, 5], 3)
        assert len(ma) == 5

    if idx % 17 == 0:
        payload = f"manifest:{idx}"
        digest = hashlib.sha256(payload.encode()).hexdigest()
        assert verify_signature(payload, digest, digest) is True
        assert verify_signature(payload, digest[1:], digest) is False

    # sign/verify manifest
    if idx % 200 == 0:
        sig = sign_manifest(f"data:{idx}", "key")
        assert verify_manifest(f"data:{idx}", sig, "key") is True

    # sanitise_path
    if idx % 200 == 0:
        cleaned = sanitise_path(f"../uploads/{idx}/file.txt")
        assert ".." not in cleaned

    # service contracts
    if idx % 500 == 0:
        url = get_service_url("gateway")
        assert "8100" in url
        errors = validate_contract("gateway")
        assert errors == []

    # classify_severity
    if idx % 200 == 0:
        sev = classify_severity("explosion reported")
        assert sev == 5

    # estimate_cost and turnaround
    if idx % 100 == 0:
        cost = estimate_cost(3, 50.0)
        assert cost > 0
        turn = estimate_turnaround(severity_a)
        assert turn > 0
        assert check_capacity(5, 10) is True


class HyperMatrixTest(unittest.TestCase):
    pass


def _add_case(i: int) -> None:
    def test_fn(self: unittest.TestCase) -> None:
        _make_case(i)

    setattr(HyperMatrixTest, f"test_hyper_matrix_{i:05d}", test_fn)


for _i in range(TOTAL_CASES):
    _add_case(_i)


if __name__ == "__main__":
    unittest.main()
