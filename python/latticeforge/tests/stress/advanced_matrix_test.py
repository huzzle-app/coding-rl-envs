from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta, timezone

from latticeforge.dependency import parallel_execution_groups
from latticeforge.orbit import hohmann_delta_v
from latticeforge.policy import compound_risk_assessment
from latticeforge.queue import BoundedPriorityChannel
from latticeforge.scheduler import batch_schedule_with_cooldown, estimate_completion_time
from latticeforge.telemetry import CachedSensorView
from services.audit.service import EventPipeline
from services.gateway.service import RouteNode, route_with_risk_assessment

TOTAL_CASES = 1400


def _make_advanced_case(idx: int) -> None:
    bucket = idx % 8

    if bucket == 0:
        nodes = ["A", "B", "C", "D"]
        depth_offset = idx % 3
        if depth_offset == 0:
            edges = [("A", "B"), ("A", "C"), ("B", "C"), ("C", "D")]
        elif depth_offset == 1:
            edges = [("A", "B"), ("B", "C"), ("A", "D"), ("C", "D"), ("B", "D")]
        else:
            nodes = ["A", "B", "C", "D", "E"]
            edges = [("A", "B"), ("B", "C"), ("A", "D"), ("C", "E"), ("D", "E")]

        groups = parallel_execution_groups(nodes, edges)
        edge_set = set(edges)
        for group in groups:
            items = list(group)
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    assert (items[i], items[j]) not in edge_set and (items[j], items[i]) not in edge_set, (
                        f"idx={idx}: dependent nodes {items[i]},{items[j]} in same group"
                    )
        return

    if bucket == 1:
        r1 = 6371.0 + float(idx % 300) * 4
        r2 = r1 + 80.0 + float(idx % 150) * 5
        dv = hohmann_delta_v(r1, r2)
        mu = 398600.4418
        a_t = (r1 + r2) / 2.0
        v1 = math.sqrt(mu / r1)
        v2 = math.sqrt(mu / r2)
        vt1 = math.sqrt(mu * (2.0 / r1 - 1.0 / a_t))
        vt2 = math.sqrt(mu * (2.0 / r2 - 1.0 / a_t))
        expected = round(abs(vt1 - v1) + abs(v2 - vt2), 4)
        assert abs(dv - expected) < 0.02, f"idx={idx}: hohmann got {dv}, expected {expected}"
        return

    if bucket == 2:
        n_factors = 2 + (idx % 4)
        factors = [0.15 + 0.1 * ((idx + j) % 6) for j in range(n_factors)]
        risk = compound_risk_assessment(factors, base_risk=10.0)
        survival = 1.0
        for f in factors:
            survival *= (1.0 - min(max(f, 0.0), 1.0))
        expected = round(min(10.0 + (1.0 - survival) * 90.0, 100.0), 4)
        assert abs(risk - expected) < 0.5, f"idx={idx}: compound risk got {risk}, expected {expected}"
        return

    if bucket == 3:
        n_ops = 4 + (idx % 5)
        cooldown = 8 + (idx % 12)
        ops = [{"id": f"op-{i}"} for i in range(n_ops)]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=cooldown)
        assert scheduled[0]["scheduled_offset_s"] == 0, (
            f"idx={idx}: first batch should start at 0, got {scheduled[0]['scheduled_offset_s']}"
        )
        return

    if bucket == 4:
        p = EventPipeline()
        eid = f"evt-{idx}"
        p.receive(eid, {"trace_id": f"t-{idx}", "service": "gw", "version": "1"})
        p.validate(eid)
        p.enrich(eid, {"region": "us-east", "env": "prod", "source_version": "1"})
        p.retry(eid, {"trace_id": f"t-{idx}", "service": "gw-v2", "version": "2"})
        enrichment = p.get_enrichment(eid)
        assert enrichment == {}, f"idx={idx}: enrichment should be empty after retry, got {enrichment}"
        return

    if bucket == 5:
        view = CachedSensorView()
        base_a = float(idx % 50)
        base_b = float(100 + idx % 30)
        view.record("sensor_a", base_a)
        view.record("sensor_b", base_b)
        view.get_average("sensor_a")
        view.record("sensor_a", base_a + 20.0)
        view.get_average("sensor_b")
        avg_a = view.get_average("sensor_a")
        expected_a = round((base_a + base_a + 20.0) / 2.0, 4)
        assert abs(avg_a - expected_a) < 0.01, (
            f"idx={idx}: sensor_a avg got {avg_a}, expected {expected_a}"
        )
        return

    if bucket == 6:
        cap = 3 + (idx % 4)
        ch = BoundedPriorityChannel(capacity=cap)
        for j in range(cap):
            ch.send(f"t-{j}", severity=j + 1, wait_seconds=(j + 1) * 30)
        drain_count = max(cap // 2, 1)
        ch.drain(drain_count)
        extra = drain_count
        for j in range(extra):
            ch.send(f"t-extra-{j}", severity=1, wait_seconds=10)
        assert ch.pending_count <= ch.capacity, (
            f"idx={idx}: pending {ch.pending_count} exceeds capacity {ch.capacity}"
        )
        return

    if bucket == 7:
        topology = {
            "intake": [
                RouteNode("intake", f"in-a-{idx}", 30, 1, 0.1),
                RouteNode("intake", f"in-b-{idx}", 50, 5, 0.8),
            ],
            "policy": [
                RouteNode("policy", f"pol-{idx}", 40, 2, 0.2),
            ],
            "resilience": [
                RouteNode("resilience", f"res-a-{idx}", 60, 3, 0.7),
                RouteNode("resilience", f"res-b-{idx}", 35, 1, 0.1),
            ],
            "audit": [
                RouteNode("audit", f"aud-{idx}", 25, 1, 0.1),
            ],
        }
        risk = 55.0 + float(idx % 10)
        result = route_with_risk_assessment(
            intent="replay-window",
            topology=topology,
            risk_score=risk,
            comms_degraded=True,
        )
        assert result["blocked_count"] > 0, (
            f"idx={idx}: should block saturated nodes when comms degraded, risk={risk}"
        )
        return


class AdvancedMatrixTest(unittest.TestCase):
    pass


def _add_case(i: int) -> None:
    def test_fn(self: unittest.TestCase) -> None:
        _make_advanced_case(i)

    setattr(AdvancedMatrixTest, f"test_advanced_matrix_{i:05d}", test_fn)


for _i in range(TOTAL_CASES):
    _add_case(_i)


if __name__ == "__main__":
    unittest.main()
