import hashlib
import unittest

from ionveil.models import (
    DispatchOrder, VesselManifest, merge_manifests,
    classify_severity, create_batch_orders, SLA_BY_SEVERITY,
)
from ionveil.dispatch import (
    plan_dispatch, dispatch_batch, has_conflict, BerthSlot,
    estimate_cost, estimate_turnaround, check_capacity,
    mutual_aid_required,
)
from ionveil.routing import (
    choose_route, channel_score, estimate_transit_time, plan_multi_leg, Waypoint,
    build_adjacency_costs, haversine_distance, find_cheapest_route,
)
from ionveil.policy import (
    next_policy, previous_policy, should_deescalate, check_sla_compliance,
    sla_percentage, all_policies, policy_index, escalation_chain,
)
from ionveil.queue import should_shed, queue_health, estimate_wait_time, PriorityQueue, drain_by_priority
from ionveil.resilience import (
    replay_events, deduplicate, replay_converges,
)
from ionveil.statistics import percentile, mean, moving_average, exponential_moving_average, compute_breach_rate
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

    # --- Sub-categories: each exercises a distinct source-code bug ---
    severity_a = (idx % 5) + 1
    severity_b = ((idx * 3) % 5) + 1
    sla_a = 20 + (idx % 90)
    sla_b = 20 + ((idx * 2) % 90)

    a = DispatchOrder(f"a-{idx}", severity_a, sla_a)
    b = DispatchOrder(f"b-{idx}", severity_b, sla_b)

    sub = (idx // 4) % 16

    if sub == 0:
        # Bug: urgency_score uses severity * 8 instead of * 10
        expected = severity_a * 10 + max(0, 120 - sla_a)
        assert a.urgency_score() == expected
        return

    if sub == 1:
        # Bug: choose_route picks highest latency instead of lowest
        routes_list = [
            {"channel": "alpha", "latency": 2 + (idx % 9)},
            {"channel": "beta", "latency": 1 + (idx % 3)},
            {"channel": "gamma", "latency": 4 + (idx % 4)},
        ]
        route = choose_route(routes_list, set())
        expected_latency = min(r["latency"] for r in routes_list)
        assert route["latency"] == expected_latency
        return

    if sub == 2:
        # Bug: replay_events keeps LOWER sequence instead of higher
        seq_high = 10 + (idx % 20)
        replayed = replay_events([
            {"id": f"ev-{idx}", "sequence": 1},
            {"id": f"ev-{idx}", "sequence": seq_high},
            {"id": f"other-{idx}", "sequence": 3},
        ])
        ev_entry = [e for e in replayed if e["id"] == f"ev-{idx}"][0]
        assert ev_entry["sequence"] == seq_high
        return

    if sub == 3:
        # Bug: should_shed uses > instead of >= (off-by-one)
        limit = 30 + (idx % 20)
        assert should_shed(limit, limit, False) is True
        return

    if sub == 4:
        # Bug: estimate_cost uses 0.45 instead of 0.5 per km
        urg = (idx % 5) + 1
        cost_near = estimate_cost(urg, 100.0)
        cost_far = estimate_cost(urg, 200.0)
        per_km = round((cost_far - cost_near) / 100.0, 2)
        assert per_km == 0.5
        return

    if sub == 5:
        # Bug: compute_breach_rate uses integer division (//)
        base = 50.0 + float(idx % 40)
        times = [base, 150.0, 200.0 + float(idx % 30)]
        rate = compute_breach_rate(times, 100.0)
        expected = round(2 / 3, 4)
        assert abs(rate - expected) < 0.001
        return

    if sub == 6:
        # Bug: EMA uses values[i-1] instead of values[i]
        step = 10.0 + float(idx % 20)
        vals = [1.0, step, step]
        ema = exponential_moving_average(vals, 0.5)
        expected_ema1 = 0.5 * vals[1] + 0.5 * vals[0]
        assert abs(ema[1] - expected_ema1) < 0.01
        return

    if sub == 7:
        # Bug: merge_manifests doesn't deduplicate shared orders
        shared = DispatchOrder(f"shared-{idx}", severity_a, sla_a)
        m_a = VesselManifest(f"A-{idx}", [shared, a])
        m_b = VesselManifest(f"B-{idx}", [shared, b])
        merged = merge_manifests(m_a, m_b)
        unique_ids = {o.id for o in merged.orders}
        assert merged.order_count() == len(unique_ids)
        return

    if sub == 8:
        # Bug: queue_health uses >= EMERGENCY_RATIO for "critical" (should be >)
        limit = 5 * (1 + (idx % 20))
        depth = limit * 4 // 5
        health = queue_health(depth, limit)
        assert health.status == "warning"
        return

    if sub == 9:
        # Bug: build_adjacency_costs only fills upper triangle (asymmetric)
        lat = float(idx % 50)
        lon = float(idx % 80)
        wps = [
            Waypoint("P", lat, lon),
            Waypoint("Q", lat + 2.0 + float(idx % 5), lon + 3.0),
        ]
        matrix = build_adjacency_costs(wps)
        assert abs(matrix[0][1] - matrix[1][0]) < 0.01
        return

    if sub == 10:
        # Bug: mutual_aid_required checks < 2 instead of < 3 for critical
        assert mutual_aid_required(5, 2) is True
        return

    if sub == 11:
        # Bug: drain_by_priority uses > instead of >= (off-by-one)
        q = PriorityQueue(capacity=100)
        threshold = 3 + (idx % 5)
        q.enqueue({"id": f"exact-{idx}", "priority": threshold})
        q.enqueue({"id": f"above-{idx}", "priority": threshold + 2})
        q.enqueue({"id": f"below-{idx}", "priority": threshold - 1})
        drained = drain_by_priority(q, threshold)
        drained_ids = {d["id"] for d in drained}
        assert f"exact-{idx}" in drained_ids
        assert f"above-{idx}" in drained_ids
        return

    if sub == 12:
        # Bug: haversine_distance uses cos(lat1)^2 instead of cos(lat1)*cos(lat2)
        import math
        lat1 = float(idx % 60)
        lon1 = float(idx % 90)
        lat2 = lat1 + 10.0 + float(idx % 20)
        lon2 = lon1 + 15.0
        dist = haversine_distance(lat1, lon1, lat2, lon2)
        R = 6371.0
        lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a_val = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
        c_val = 2 * math.atan2(math.sqrt(a_val), math.sqrt(1 - a_val))
        expected = round(R * c_val, 2)
        assert abs(dist - expected) < 1.0
        return

    if sub == 13:
        # Bug: should_deescalate uses >= instead of > at exact threshold
        policy_level = ["halted", "restricted", "watch"][idx % 3]
        thresholds = {"halted": 20, "restricted": 10, "watch": 5}
        threshold = thresholds[policy_level]
        assert should_deescalate(threshold, policy_level) is False
        return

    if sub == 14:
        # Bug: escalation_chain returns ascending for de-escalation (should be descending)
        pairs = [("halted", "normal"), ("restricted", "normal"), ("halted", "watch")]
        current, target = pairs[idx % 3]
        chain = escalation_chain(current, target)
        assert len(chain) >= 2
        assert chain[0] == current
        assert chain[-1] == target
        return

    if sub == 15:
        # Bug: find_cheapest_route treats missing cost as 0 (cheapest)
        cost = 10 + (idx % 50)
        routes = [
            {"channel": f"known-{idx}", "cost": cost},
            {"channel": f"unknown-{idx}"},
        ]
        cheapest = find_cheapest_route(routes)
        assert cheapest["channel"] == f"known-{idx}"
        return


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
