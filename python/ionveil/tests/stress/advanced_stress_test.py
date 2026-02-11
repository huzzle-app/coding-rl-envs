import unittest

from ionveil.models import (
    DispatchOrder, VesselManifest, merge_manifests, triage_priority,
    compute_aggregate_sla, SEVERITY_CRITICAL, SEVERITY_HIGH,
    SEVERITY_MODERATE, SEVERITY_LOW, SEVERITY_INFO, SLA_BY_SEVERITY,
)
from ionveil.dispatch import (
    estimate_fleet_cost, mutual_aid_required, rebalance_dispatch,
    dispatch_with_routing,
)
from ionveil.routing import (
    build_adjacency_costs, Waypoint,
)
from ionveil.policy import (
    escalation_chain, PolicyEngine,
)
from ionveil.queue import PriorityQueue
from ionveil.resilience import CircuitBreaker, CB_CLOSED, CB_OPEN

TOTAL_CASES = 600


def _make_case(idx: int) -> None:
    category = idx % 12

    if category == 0:
        shared = DispatchOrder(f"shared-{idx}", 3 + (idx % 3), 60)
        a = VesselManifest(f"M-{idx}", [shared, DispatchOrder(f"a-{idx}", 2, 120)])
        b = VesselManifest(f"N-{idx}", [shared, DispatchOrder(f"b-{idx}", 1, 480)])
        merged = merge_manifests(a, b)
        unique_ids = {o.id for o in merged.orders}
        assert merged.order_count() == len(unique_ids)
        return

    if category == 1:
        density = 5500.0 + (idx % 3000)
        result = triage_priority(SEVERITY_MODERATE, density, 1.0)
        assert result == SEVERITY_HIGH
        return

    if category == 2:
        sev = (idx % 4) + 1
        sla_a = 30 + (idx % 60)
        sla_b = 60 + (idx % 120)
        orders = [DispatchOrder(f"a-{idx}", sev, sla_a), DispatchOrder(f"b-{idx}", sev, sla_b)]
        result = compute_aggregate_sla(orders)
        expected = round((sev * sla_a + sev * sla_b) / (sev + sev), 2)
        assert abs(result - expected) < 0.1
        return

    if category == 3:
        count = 10 + (idx % 10)
        urg = (idx % 5) + 1
        orders = [{"id": str(i), "urgency": urg} for i in range(count)]
        cost = estimate_fleet_cost(orders)
        base = count * urg * 12.0
        assert cost < base
        return

    if category == 4:
        assert mutual_aid_required(5, 2) is True
        return

    if category == 5:
        planned = [{"id": "lo", "urgency": 1 + (idx % 2)}]
        rejected = [
            {"id": "hi", "urgency": 8 + (idx % 3)},
            {"id": "mid", "urgency": 4 + (idx % 3)},
        ]
        result = rebalance_dispatch(planned, rejected, 2)
        urgencies = [int(o["urgency"]) for o in result.planned]
        assert urgencies == sorted(urgencies, reverse=True)
        return

    if category == 6:
        chain = escalation_chain("halted", "normal")
        assert len(chain) == 4
        assert chain[0] == "halted"
        assert chain[-1] == "normal"
        return

    if category == 7:
        lat_base = float(idx % 50)
        lon_base = float(idx % 80)
        wps = [
            Waypoint("A", lat_base, lon_base),
            Waypoint("B", lat_base + 1.0 + (idx % 5), lon_base),
            Waypoint("C", lat_base, lon_base + 1.0 + (idx % 5)),
        ]
        matrix = build_adjacency_costs(wps)
        for i in range(3):
            for j in range(3):
                if i != j:
                    assert matrix[i][j] > 0
                    assert abs(matrix[i][j] - matrix[j][i]) < 0.01
        return

    if category == 8:
        eng = PolicyEngine("halted")
        result = eng.auto_escalate(5, 3)
        assert result is False
        return

    if category == 9:
        q1 = PriorityQueue(capacity=100)
        q1.enqueue({"id": f"a-{idx}", "priority": 10})
        q1.enqueue({"id": f"b-{idx}", "priority": 1})
        q2 = PriorityQueue(capacity=100)
        q2.enqueue({"id": f"c-{idx}", "priority": 5 + (idx % 3)})
        q1.merge(q2)
        items = q1.drain()
        priorities = [int(it["priority"]) for it in items]
        assert priorities == sorted(priorities, reverse=True)
        return

    if category == 10:
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError()))
        for _ in range(10):
            cb.execute(lambda: "ok")
        cb.execute(lambda: (_ for _ in ()).throw(ValueError()))
        assert cb.state == CB_CLOSED
        return

    if category == 11:
        orders = [
            {"id": f"a-{idx}", "urgency": 5 + (idx % 3)},
            {"id": f"b-{idx}", "urgency": 3},
        ]
        routes = [{"channel": "alpha", "latency": 10}]
        result = dispatch_with_routing(orders, routes, [], 2)
        expected_cost = sum(float(o["urgency"]) * 1.5 for o in orders)
        assert abs(result.total_cost - expected_cost) < 0.01
        return


class AdvancedStressTest(unittest.TestCase):
    pass


def _add_case(i: int) -> None:
    def test_fn(self: unittest.TestCase) -> None:
        _make_case(i)

    setattr(AdvancedStressTest, f"test_advanced_{i:05d}", test_fn)


for _i in range(TOTAL_CASES):
    _add_case(_i)


if __name__ == "__main__":
    unittest.main()
