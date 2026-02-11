import unittest

from ionveil.models import (
    DispatchOrder, VesselManifest, classify_severity, create_batch_orders,
    validate_dispatch_order, SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_MODERATE,
    SEVERITY_LOW, SEVERITY_INFO, SLA_BY_SEVERITY,
)
from ionveil.dispatch import (
    dispatch_batch, has_conflict, find_available_slots, BerthSlot,
    estimate_cost, allocate_costs, estimate_turnaround, check_capacity,
    validate_order, validate_batch, compare_by_urgency_then_eta,
    RollingWindowScheduler,
)
from ionveil.routing import (
    channel_score, estimate_transit_time, estimate_route_cost, compare_routes,
    plan_multi_leg, Waypoint, RouteTable,
)
from ionveil.policy import (
    previous_policy, should_deescalate, policy_index, all_policies,
    get_metadata, check_sla_compliance, sla_percentage, PolicyEngine,
)
from ionveil.queue import (
    queue_health, estimate_wait_time, PriorityQueue, RateLimiter,
)
from ionveil.security import (
    sign_manifest, verify_manifest, sanitise_path, is_allowed_origin, TokenStore,
)
from ionveil.resilience import (
    deduplicate, replay_converges, CheckpointManager, CircuitBreaker,
    CB_CLOSED, CB_OPEN,
)
from ionveil.statistics import (
    mean, variance, stddev, median, moving_average,
    ResponseTimeTracker, generate_heatmap,
)
from ionveil.workflow import (
    is_terminal_state, is_valid_state, allowed_transitions, shortest_path,
    WorkflowEngine, TERMINAL_STATES,
)
from shared.contracts.contracts import (
    get_service_url, validate_contract, topological_order, SERVICE_DEFS,
)


class ExtModelsTest(unittest.TestCase):
    def test_severity_constants(self):
        self.assertEqual(SEVERITY_CRITICAL, 5)
        self.assertEqual(SEVERITY_INFO, 1)

    def test_sla_by_severity(self):
        self.assertEqual(SLA_BY_SEVERITY[SEVERITY_CRITICAL], 15)
        self.assertGreater(SLA_BY_SEVERITY[SEVERITY_INFO], SLA_BY_SEVERITY[SEVERITY_CRITICAL])

    def test_classify_severity(self):
        self.assertEqual(classify_severity("massive explosion downtown"), SEVERITY_CRITICAL)
        self.assertEqual(classify_severity("building fire reported"), SEVERITY_HIGH)
        self.assertEqual(classify_severity("traffic accident"), SEVERITY_MODERATE)
        self.assertEqual(classify_severity("false alarm"), SEVERITY_LOW)
        self.assertEqual(classify_severity("routine check"), SEVERITY_INFO)

    def test_create_batch_orders(self):
        items = [{"id": "a", "severity": 3}, {"id": "b", "severity": 5, "sla_minutes": 10}]
        orders = create_batch_orders(items)
        self.assertEqual(len(orders), 2)
        self.assertEqual(orders[1].sla_minutes, 10)

    def test_validate_dispatch_order(self):
        self.assertEqual(validate_dispatch_order({"id": "x", "severity": 3}), [])
        errs = validate_dispatch_order({})
        self.assertIn("missing id", errs)
        self.assertIn("missing severity", errs)

    def test_vessel_manifest(self):
        m = VesselManifest("M1", [DispatchOrder("a", 3, 60), DispatchOrder("b", 5, 15)])
        self.assertEqual(m.order_count(), 2)
        self.assertEqual(m.highest_severity(), 5)


class ExtDispatchTest(unittest.TestCase):
    def test_dispatch_batch(self):
        orders = [{"id": "a", "urgency": 5, "eta": "09:00"}, {"id": "b", "urgency": 3, "eta": "10:00"}, {"id": "c", "urgency": 4, "eta": "08:00"}]
        result = dispatch_batch(orders, 2)
        self.assertEqual(len(result.planned), 2)
        self.assertEqual(len(result.rejected), 1)
        self.assertGreater(result.total_cost, 0)

    def test_has_conflict(self):
        a = BerthSlot("s1", 8, 12)
        b = BerthSlot("s2", 10, 14)
        c = BerthSlot("s3", 14, 18)
        self.assertTrue(has_conflict(a, b))
        self.assertFalse(has_conflict(a, c))

    def test_find_available_slots(self):
        slots = [BerthSlot("s1", 8, 12), BerthSlot("s2", 10, 14, locked=True), BerthSlot("s3", 6, 10)]
        available = find_available_slots(slots, 7, 13)
        self.assertEqual(len(available), 1)

    def test_estimate_cost(self):
        cost = estimate_cost(5, 100.0)
        self.assertGreater(cost, 0)

    def test_estimate_turnaround(self):
        self.assertEqual(estimate_turnaround(5), 30)
        self.assertEqual(estimate_turnaround(1), 120)

    def test_check_capacity(self):
        self.assertTrue(check_capacity(5, 10))
        self.assertFalse(check_capacity(10, 10))

    def test_validate_batch(self):
        errors = validate_batch([{"id": "a", "urgency": 5}, {"id": "", "urgency": 0}])
        self.assertTrue(any("missing id" in e for e in errors))

    def test_rolling_window_scheduler(self):
        sched = RollingWindowScheduler(window_seconds=60.0)
        sched.submit()
        sched.submit()
        self.assertEqual(sched.count(), 2)
        sched.reset()
        self.assertEqual(sched.count(), 0)


class ExtRoutingTest(unittest.TestCase):
    def test_channel_score(self):
        score = channel_score(10.0, 0.95)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 1.0)

    def test_estimate_transit_time(self):
        t = estimate_transit_time(100.0, 12.0)
        self.assertGreater(t, 0)

    def test_plan_multi_leg(self):
        wps = [Waypoint("A", 40.0, -74.0), Waypoint("B", 41.0, -73.0, dwell_minutes=10)]
        plan = plan_multi_leg(wps)
        self.assertEqual(plan.leg_count(), 1)
        self.assertGreater(plan.total_distance_km, 0)

    def test_route_table(self):
        rt = RouteTable()
        rt.add("alpha", {"channel": "alpha", "latency": 5})
        self.assertEqual(rt.count(), 1)
        self.assertIsNotNone(rt.get("alpha"))
        self.assertTrue(rt.remove("alpha"))
        self.assertEqual(rt.count(), 0)


class ExtPolicyTest(unittest.TestCase):
    def test_previous_policy(self):
        self.assertEqual(previous_policy("watch"), "normal")
        self.assertEqual(previous_policy("normal"), "normal")

    def test_should_deescalate(self):
        self.assertTrue(should_deescalate(20, "halted"))
        self.assertFalse(should_deescalate(3, "halted"))

    def test_policy_engine(self):
        eng = PolicyEngine()
        self.assertEqual(eng.current, "normal")
        eng.escalate("test")
        self.assertEqual(eng.current, "watch")
        eng.deescalate("recovery")
        self.assertEqual(eng.current, "normal")
        self.assertEqual(len(eng.history()), 2)

    def test_sla_percentage(self):
        self.assertEqual(sla_percentage(90, 100), 90.0)
        self.assertEqual(sla_percentage(0, 0), 0.0)

    def test_check_sla_compliance(self):
        self.assertTrue(check_sla_compliance(10, 15))
        self.assertFalse(check_sla_compliance(20, 15))


class ExtQueueTest(unittest.TestCase):
    def test_queue_health(self):
        h = queue_health(50, 100)
        self.assertEqual(h.status, "healthy")
        h2 = queue_health(85, 100)
        self.assertEqual(h2.status, "critical")

    def test_priority_queue(self):
        pq = PriorityQueue(capacity=3)
        self.assertTrue(pq.enqueue({"id": "a", "priority": 1}))
        self.assertTrue(pq.enqueue({"id": "b", "priority": 5}))
        self.assertTrue(pq.enqueue({"id": "c", "priority": 3}))
        self.assertFalse(pq.enqueue({"id": "d", "priority": 2}))
        top = pq.dequeue()
        self.assertEqual(top["id"], "b")
        self.assertEqual(pq.size(), 2)

    def test_estimate_wait_time(self):
        self.assertEqual(estimate_wait_time(100, 10.0), 10.0)
        self.assertEqual(estimate_wait_time(5, 0), float("inf"))


class ExtSecurityTest(unittest.TestCase):
    def test_sign_verify_manifest(self):
        sig = sign_manifest("payload", "secret")
        self.assertTrue(verify_manifest("payload", sig, "secret"))
        self.assertFalse(verify_manifest("payload", "wrong", "secret"))

    def test_sanitise_path(self):
        self.assertEqual(sanitise_path("../etc/passwd"), "etc/passwd")
        self.assertEqual(sanitise_path("a/./b/../c"), "a/b/c")

    def test_is_allowed_origin(self):
        self.assertTrue(is_allowed_origin("https://ionveil.internal"))
        self.assertFalse(is_allowed_origin("https://evil.com"))

    def test_token_store(self):
        ts = TokenStore(default_ttl=3600.0)
        ts.store("tok1", {"user": "admin"})
        self.assertTrue(ts.validate("tok1"))
        self.assertFalse(ts.validate("nonexistent"))
        self.assertTrue(ts.revoke("tok1"))
        self.assertEqual(ts.count(), 0)


class ExtResilienceTest(unittest.TestCase):
    def test_deduplicate(self):
        items = [{"id": "a"}, {"id": "b"}, {"id": "a"}]
        result = deduplicate(items)
        self.assertEqual(len(result), 2)

    def test_replay_converges(self):
        events = [{"id": "x", "sequence": 1}, {"id": "x", "sequence": 2}]
        self.assertTrue(replay_converges(events, list(reversed(events))))

    def test_checkpoint_manager(self):
        cm = CheckpointManager(interval=5)
        for i in range(5):
            cm.record(f"cp-{i}", i)
        self.assertTrue(cm.should_checkpoint())
        self.assertEqual(cm.count(), 5)
        cm.reset()
        self.assertEqual(cm.count(), 0)

    def test_circuit_breaker(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        self.assertEqual(cb.state, CB_CLOSED)
        for _ in range(3):
            cb.record_failure()
        self.assertEqual(cb.state, CB_OPEN)
        cb.record_success()
        self.assertEqual(cb.state, CB_CLOSED)


class ExtStatisticsTest(unittest.TestCase):
    def test_mean(self):
        self.assertAlmostEqual(mean([2, 4, 6]), 4.0)
        self.assertEqual(mean([]), 0.0)

    def test_variance_and_stddev(self):
        self.assertGreater(variance([1, 2, 3, 4, 5]), 0)
        self.assertGreater(stddev([1, 2, 3, 4, 5]), 0)

    def test_median(self):
        self.assertEqual(median([1, 3, 5]), 3.0)
        self.assertEqual(median([1, 2, 3, 4]), 2.5)

    def test_moving_average(self):
        result = moving_average([1, 2, 3, 4, 5], 3)
        self.assertEqual(len(result), 5)
        self.assertAlmostEqual(result[-1], 4.0, places=2)

    def test_response_time_tracker(self):
        tracker = ResponseTimeTracker(max_window=100)
        for i in range(50):
            tracker.record(float(i))
        self.assertEqual(tracker.count(), 50)
        self.assertGreater(tracker.p50(), 0)

    def test_generate_heatmap(self):
        events = [{"row": 0, "col": 1, "value": 3.0}, {"row": 0, "col": 1, "value": 2.0}]
        cells = generate_heatmap(events, 5, 5)
        self.assertEqual(len(cells), 1)
        self.assertAlmostEqual(cells[0].value, 5.0)


class ExtWorkflowTest(unittest.TestCase):
    def test_terminal_states(self):
        self.assertTrue(is_terminal_state("arrived"))
        self.assertTrue(is_terminal_state("cancelled"))
        self.assertFalse(is_terminal_state("queued"))

    def test_is_valid_state(self):
        self.assertTrue(is_valid_state("queued"))
        self.assertFalse(is_valid_state("unknown"))

    def test_allowed_transitions(self):
        trans = allowed_transitions("queued")
        self.assertIn("allocated", trans)
        self.assertIn("cancelled", trans)

    def test_shortest_path(self):
        path = shortest_path("queued", "arrived")
        self.assertGreater(len(path), 0)
        self.assertEqual(path[0], "queued")
        self.assertEqual(path[-1], "arrived")

    def test_workflow_engine(self):
        eng = WorkflowEngine()
        self.assertTrue(eng.register("e1"))
        self.assertEqual(eng.get_state("e1"), "queued")
        result = eng.transition("e1", "allocated", "dispatched")
        self.assertTrue(result.success)
        result2 = eng.transition("e1", "queued")
        self.assertFalse(result2.success)
        self.assertEqual(eng.active_count(), 1)
        eng.transition("e1", "departed")
        eng.transition("e1", "arrived")
        self.assertTrue(eng.is_terminal("e1"))
        self.assertEqual(eng.active_count(), 0)
        self.assertGreater(len(eng.audit_log()), 0)


class ExtContractsTest(unittest.TestCase):
    def test_get_service_url(self):
        url = get_service_url("gateway")
        self.assertIn("8100", url)

    def test_validate_contract(self):
        errors = validate_contract("gateway")
        self.assertEqual(errors, [])
        errors2 = validate_contract("nonexistent")
        self.assertGreater(len(errors2), 0)

    def test_topological_order(self):
        order = topological_order()
        self.assertEqual(order[0], "gateway")
        self.assertEqual(len(order), 10)

    def test_service_defs(self):
        self.assertIn("gateway", SERVICE_DEFS)
        self.assertEqual(SERVICE_DEFS["gateway"].port, 8100)


if __name__ == "__main__":
    unittest.main()
