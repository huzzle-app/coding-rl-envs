import unittest
import threading
import time

from ionveil.models import (
    DispatchOrder, VesselManifest, merge_manifests, triage_priority,
    compute_aggregate_sla, SEVERITY_CRITICAL, SEVERITY_HIGH,
    SEVERITY_MODERATE, SEVERITY_LOW, SEVERITY_INFO,
)
from ionveil.dispatch import (
    estimate_fleet_cost, mutual_aid_required, rebalance_dispatch,
    dispatch_with_routing, AllocationResult, dispatch_batch,
    estimate_cost, plan_dispatch,
)
from ionveil.routing import (
    haversine_distance, find_cheapest_route, build_adjacency_costs,
    Waypoint, RouteTable, channel_score, plan_multi_leg,
)
from ionveil.policy import (
    incident_command_level, escalation_chain, PolicyEngine, ORDER,
    next_policy, should_deescalate,
)
from ionveil.queue import (
    PriorityQueue, drain_by_priority, queue_health, RateLimiter,
)
from ionveil.resilience import (
    merge_checkpoints, event_stream_diff, CheckpointManager,
    CircuitBreaker, CB_CLOSED, CB_OPEN, CB_HALF_OPEN,
)
from ionveil.workflow import (
    WorkflowEngine, validate_state_path, can_transition,
    is_terminal_state, shortest_path, TERMINAL_STATES,
)
from ionveil.statistics import (
    exponential_moving_average, compute_breach_rate,
    ResponseTimeTracker, mean, variance, percentile,
)
from ionveil.security import TokenStore


# =========================================================================
# Latent bug tests — bugs that corrupt state silently or only manifest
# under specific conditions
# =========================================================================

class LatentMergeManifestTest(unittest.TestCase):
    def test_merge_deduplicates_shared_orders(self):
        shared = DispatchOrder("shared-1", 5, 15)
        a = VesselManifest("M1", [shared, DispatchOrder("a1", 3, 60)])
        b = VesselManifest("M2", [shared, DispatchOrder("b1", 1, 480)])
        merged = merge_manifests(a, b)
        unique_ids = {o.id for o in merged.orders}
        self.assertEqual(merged.order_count(), len(unique_ids))

    def test_merge_preserves_all_unique_orders(self):
        a = VesselManifest("M1", [DispatchOrder("a1", 5, 15)])
        b = VesselManifest("M2", [DispatchOrder("b1", 3, 60), DispatchOrder("b2", 1, 480)])
        merged = merge_manifests(a, b)
        self.assertEqual(merged.order_count(), 3)
        self.assertEqual(merged.highest_severity(), 5)

    def test_merge_takes_higher_priority(self):
        a = VesselManifest("M1", priority=3)
        b = VesselManifest("M2", priority=7)
        merged = merge_manifests(a, b)
        self.assertEqual(merged.priority, 7)


class LatentTriagePriorityTest(unittest.TestCase):
    def test_moderate_in_dense_area_upgrades_once(self):
        result = triage_priority(SEVERITY_MODERATE, 6000.0, 1.0)
        self.assertEqual(result, SEVERITY_HIGH)

    def test_critical_stays_critical_in_dense_area(self):
        result = triage_priority(SEVERITY_CRITICAL, 8000.0, 1.0)
        self.assertEqual(result, SEVERITY_CRITICAL)

    def test_low_density_no_upgrade(self):
        result = triage_priority(SEVERITY_LOW, 100.0, 1.0)
        self.assertEqual(result, SEVERITY_LOW)


class LatentAggregateSLATest(unittest.TestCase):
    def test_duplicate_severity_weights_correctly(self):
        orders = [DispatchOrder("a", 3, 60), DispatchOrder("b", 3, 90)]
        result = compute_aggregate_sla(orders)
        expected = round((3 * 60 + 3 * 90) / (3 + 3), 2)
        self.assertAlmostEqual(result, expected, places=1)

    def test_mixed_severity_weighted_average(self):
        orders = [DispatchOrder("a", 5, 15), DispatchOrder("b", 1, 480)]
        result = compute_aggregate_sla(orders)
        expected = round((5 * 15 + 1 * 480) / (5 + 1), 2)
        self.assertAlmostEqual(result, expected, places=1)

    def test_empty_orders(self):
        self.assertEqual(compute_aggregate_sla([]), 0.0)


# =========================================================================
# Domain logic bug tests — require understanding emergency dispatch
# =========================================================================

class DomainFleetCostTest(unittest.TestCase):
    def test_volume_discount_for_large_fleet(self):
        orders = [{"id": str(i), "urgency": 5} for i in range(12)]
        cost = estimate_fleet_cost(orders)
        base = 12 * 5 * 12.0
        self.assertLess(cost, base)

    def test_no_discount_for_small_fleet(self):
        orders = [{"id": str(i), "urgency": 5} for i in range(5)]
        cost = estimate_fleet_cost(orders)
        self.assertEqual(cost, 5 * 5 * 12.0)


class DomainMutualAidTest(unittest.TestCase):
    def test_critical_needs_three_units(self):
        self.assertTrue(mutual_aid_required(5, 2))

    def test_critical_with_three_units_no_aid(self):
        self.assertFalse(mutual_aid_required(5, 3))

    def test_high_severity_one_unit(self):
        self.assertTrue(mutual_aid_required(4, 0))

    def test_moderate_no_mutual_aid(self):
        self.assertFalse(mutual_aid_required(3, 1))


class DomainIncidentCommandTest(unittest.TestCase):
    def test_mass_casualty_always_level_3(self):
        result = incident_command_level(SEVERITY_MODERATE, 150)
        self.assertEqual(result, 3)

    def test_critical_severity_level_3(self):
        self.assertEqual(incident_command_level(SEVERITY_CRITICAL, 5), 3)

    def test_high_severity_level_2(self):
        self.assertEqual(incident_command_level(SEVERITY_HIGH, 10), 2)

    def test_low_severity_few_affected(self):
        self.assertEqual(incident_command_level(SEVERITY_LOW, 3), 0)


class DomainHaversineTest(unittest.TestCase):
    def test_known_distance_nyc_london(self):
        dist = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
        self.assertGreater(dist, 5500)
        self.assertLess(dist, 5700)

    def test_same_point_zero_distance(self):
        self.assertAlmostEqual(haversine_distance(0, 0, 0, 0), 0.0)

    def test_different_hemispheres_accuracy(self):
        dist = haversine_distance(60.0, 25.0, -33.9, 18.4)
        correct_approx = 10530
        self.assertAlmostEqual(dist, correct_approx, delta=100)

    def test_equator_90_degrees(self):
        dist = haversine_distance(0, 0, 0, 90)
        self.assertGreater(dist, 9900)
        self.assertLess(dist, 10100)


# =========================================================================
# Multi-step bug tests — fixing one reveals another
# =========================================================================

class MultiStepRebalanceTest(unittest.TestCase):
    def test_rebalance_selects_highest_urgency(self):
        planned = [{"id": "a", "urgency": 2}]
        rejected = [{"id": "b", "urgency": 10}, {"id": "c", "urgency": 5}]
        result = rebalance_dispatch(planned, rejected, 2)
        ids = [str(o["id"]) for o in result.planned]
        self.assertIn("b", ids)
        urgencies = [int(o["urgency"]) for o in result.planned]
        self.assertEqual(urgencies[0], max(urgencies))


class MultiStepEscalationChainTest(unittest.TestCase):
    def test_deescalation_path_correct_order(self):
        chain = escalation_chain("halted", "normal")
        self.assertEqual(len(chain), 4)
        self.assertEqual(chain[0], "halted")
        self.assertEqual(chain[-1], "normal")

    def test_escalation_path(self):
        chain = escalation_chain("normal", "restricted")
        self.assertEqual(chain, ["normal", "watch", "restricted"])

    def test_same_level(self):
        chain = escalation_chain("watch", "watch")
        self.assertEqual(chain, ["watch"])


class MultiStepAdjacencyMatrixTest(unittest.TestCase):
    def test_matrix_symmetric(self):
        wps = [Waypoint("A", 0.0, 0.0), Waypoint("B", 1.0, 0.0), Waypoint("C", 0.0, 1.0)]
        matrix = build_adjacency_costs(wps)
        for i in range(3):
            for j in range(3):
                self.assertAlmostEqual(matrix[i][j], matrix[j][i], places=2,
                    msg=f"matrix[{i}][{j}]={matrix[i][j]} != matrix[{j}][{i}]={matrix[j][i]}")

    def test_matrix_diagonal_zero(self):
        wps = [Waypoint("A", 10.0, 20.0), Waypoint("B", 11.0, 21.0)]
        matrix = build_adjacency_costs(wps)
        self.assertAlmostEqual(matrix[0][0], 0.0)
        self.assertAlmostEqual(matrix[1][1], 0.0)
        self.assertGreater(matrix[0][1], 0)
        self.assertGreater(matrix[1][0], 0)


class MultiStepDispatchCostTest(unittest.TestCase):
    def test_dispatch_routing_cost_formula(self):
        orders = [{"id": "a", "urgency": 5}, {"id": "b", "urgency": 3}]
        routes = [{"channel": "alpha", "latency": 10}]
        result = dispatch_with_routing(orders, routes, [], 2)
        expected_cost = sum(float(o["urgency"]) * 1.5 for o in orders)
        self.assertAlmostEqual(result.total_cost, expected_cost)


# =========================================================================
# State machine bug tests
# =========================================================================

class StateMachineRollbackTest(unittest.TestCase):
    def test_rollback_to_previous_state(self):
        eng = WorkflowEngine()
        eng.register("e1")
        eng.transition("e1", "allocated")
        eng.transition("e1", "departed")
        result = eng.rollback("e1")
        self.assertTrue(result.success)
        self.assertEqual(eng.get_state("e1"), "allocated")

    def test_rollback_from_terminal_fails(self):
        eng = WorkflowEngine()
        eng.register("e1")
        eng.transition("e1", "allocated")
        eng.transition("e1", "departed")
        eng.transition("e1", "arrived")
        result = eng.rollback("e1")
        self.assertFalse(result.success)

    def test_rollback_no_history(self):
        eng = WorkflowEngine()
        eng.register("e1")
        result = eng.rollback("e1")
        self.assertFalse(result.success)


class StateMachineCloneTest(unittest.TestCase):
    def test_clone_nonexistent_source_fails(self):
        eng = WorkflowEngine()
        result = eng.clone_entity("nonexistent", "new")
        self.assertFalse(result)

    def test_clone_nonexistent_no_none_state(self):
        eng = WorkflowEngine()
        eng.clone_entity("nonexistent", "new")
        state = eng.get_state("new")
        self.assertIsNotNone(state)

    def test_clone_copies_state(self):
        eng = WorkflowEngine()
        eng.register("src")
        eng.transition("src", "allocated")
        eng.clone_entity("src", "dst")
        self.assertEqual(eng.get_state("dst"), "allocated")


class StateMachineValidatePathTest(unittest.TestCase):
    def test_reports_all_unknown_states(self):
        errors = validate_state_path(["queued", "bogus", "unknown", "arrived"])
        unknown_errors = [e for e in errors if "unknown" in e.lower()]
        self.assertGreaterEqual(len(unknown_errors), 2)

    def test_valid_path_no_errors(self):
        errors = validate_state_path(["queued", "allocated", "departed", "arrived"])
        self.assertEqual(errors, [])


# =========================================================================
# Concurrency bug tests
# =========================================================================

class ConcurrencyTransferTest(unittest.TestCase):
    def test_transfer_respects_target_capacity(self):
        src = PriorityQueue(capacity=10)
        for i in range(5):
            src.enqueue({"id": str(i), "priority": i})
        target = PriorityQueue(capacity=2)
        transferred = src.transfer(target, 5)
        self.assertEqual(target.size(), 2)
        self.assertEqual(transferred, 2)

    def test_transfer_preserves_source_items(self):
        src = PriorityQueue(capacity=10)
        for i in range(5):
            src.enqueue({"id": str(i), "priority": i})
        target = PriorityQueue(capacity=2)
        src.transfer(target, 5)
        self.assertEqual(src.size(), 3)


class ConcurrencyMergeTest(unittest.TestCase):
    def test_merge_maintains_sort_order(self):
        q1 = PriorityQueue(capacity=100)
        q1.enqueue({"id": "a", "priority": 5})
        q1.enqueue({"id": "b", "priority": 1})
        q2 = PriorityQueue(capacity=100)
        q2.enqueue({"id": "c", "priority": 3})
        q1.merge(q2)
        items = q1.drain()
        priorities = [int(i["priority"]) for i in items]
        self.assertEqual(priorities, sorted(priorities, reverse=True))

    def test_merge_preserves_all_items(self):
        q1 = PriorityQueue(capacity=100)
        q1.enqueue({"id": "a", "priority": 5})
        q2 = PriorityQueue(capacity=100)
        q2.enqueue({"id": "b", "priority": 3})
        q2.enqueue({"id": "c", "priority": 1})
        q1.merge(q2)
        self.assertEqual(q1.size(), 3)


class ConcurrencyCircuitBreakerExecuteTest(unittest.TestCase):
    def test_success_resets_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(4):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError()))
        for _ in range(10):
            cb.execute(lambda: "ok")
        cb.execute(lambda: (_ for _ in ()).throw(ValueError()))
        self.assertEqual(cb.state, CB_CLOSED)

    def test_exception_records_failure(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        cb.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        self.assertEqual(cb.state, CB_OPEN)

    def test_successful_execution_returns_result(self):
        cb = CircuitBreaker(failure_threshold=3)
        result = cb.execute(lambda: 42)
        self.assertEqual(result, 42)
        self.assertEqual(cb.state, CB_CLOSED)


# =========================================================================
# Integration bug tests
# =========================================================================

class IntegrationDispatchRoutingTest(unittest.TestCase):
    def test_rejected_orders_counted(self):
        orders = [
            {"id": "a", "urgency": 5},
            {"id": "b", "urgency": 3},
            {"id": "c", "urgency": 1},
        ]
        routes = [{"channel": "alpha", "latency": 10}]
        result = dispatch_with_routing(orders, routes, [], 2)
        self.assertEqual(len(result.planned), 2)
        self.assertEqual(len(result.rejected), 1)

    def test_no_routes_all_rejected(self):
        orders = [{"id": "a", "urgency": 5}]
        result = dispatch_with_routing(orders, [], [], 1)
        self.assertEqual(len(result.planned), 0)
        self.assertEqual(len(result.rejected), 1)


class IntegrationEventStreamDiffTest(unittest.TestCase):
    def test_diff_finds_items_in_a_not_in_b(self):
        a = [{"id": "x"}, {"id": "y"}, {"id": "z"}]
        b = [{"id": "y"}, {"id": "w"}]
        diff = event_stream_diff(a, b)
        diff_ids = {d["id"] for d in diff}
        self.assertEqual(diff_ids, {"x", "z"})

    def test_diff_considers_sequence_not_just_id(self):
        a = [{"id": "x", "sequence": 3}, {"id": "y", "sequence": 1}]
        b = [{"id": "x", "sequence": 1}, {"id": "y", "sequence": 1}]
        diff = event_stream_diff(a, b)
        self.assertGreater(len(diff), 0)

    def test_identical_streams_empty_diff(self):
        a = [{"id": "x"}, {"id": "y"}]
        b = [{"id": "x"}, {"id": "y"}]
        self.assertEqual(event_stream_diff(a, b), [])


class IntegrationMergeCheckpointsTest(unittest.TestCase):
    def test_merge_keeps_higher_sequence_when_a_is_newer(self):
        a = CheckpointManager(interval=100)
        a.record("cp1", 10, {"data": "new"})
        time.sleep(0.01)
        b = CheckpointManager(interval=100)
        b.record("cp1", 5, {"data": "old"})
        merged = merge_checkpoints(a, b)
        cp = merged.get("cp1")
        self.assertIsNotNone(cp)
        self.assertEqual(cp.sequence, 10)

    def test_merge_combines_unique_checkpoints(self):
        a = CheckpointManager(interval=100)
        a.record("cp1", 1)
        b = CheckpointManager(interval=100)
        b.record("cp2", 2)
        merged = merge_checkpoints(a, b)
        self.assertEqual(merged.count(), 2)


class IntegrationPolicyAutoEscalateTest(unittest.TestCase):
    def test_auto_escalate_at_threshold(self):
        eng = PolicyEngine()
        result = eng.auto_escalate(3, 3)
        self.assertTrue(result)
        self.assertEqual(eng.current, "watch")

    def test_auto_escalate_no_change_at_max(self):
        eng = PolicyEngine("halted")
        result = eng.auto_escalate(5, 3)
        self.assertFalse(result)

    def test_auto_escalate_below_threshold(self):
        eng = PolicyEngine()
        result = eng.auto_escalate(2, 3)
        self.assertFalse(result)
        self.assertEqual(eng.current, "normal")


class IntegrationProcessEventsTest(unittest.TestCase):
    def test_process_failure_burst_escalates(self):
        eng = PolicyEngine()
        events = [
            {"type": "failure", "burst": 3},
            {"type": "failure", "burst": 3},
            {"type": "failure", "burst": 3},
        ]
        escalations = eng.process_events(events)
        self.assertGreater(escalations, 0)
        self.assertNotEqual(eng.current, "normal")


# =========================================================================
# Statistics bug tests
# =========================================================================

class StatisticsEMATest(unittest.TestCase):
    def test_ema_responds_to_step_change(self):
        values = [0.0, 0.0, 0.0, 100.0, 100.0]
        ema = exponential_moving_average(values, 0.5)
        self.assertGreater(ema[3], 0)

    def test_ema_weights_new_values_more(self):
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        ema = exponential_moving_average(values, 0.3)
        self.assertEqual(len(ema), 5)
        self.assertGreater(ema[-1], ema[0])

    def test_ema_alpha_near_one_tracks_closely(self):
        values = [0.0, 100.0]
        ema = exponential_moving_average(values, 0.9)
        self.assertGreater(ema[-1], 80.0)


class StatisticsBreachRateTest(unittest.TestCase):
    def test_partial_breach_rate(self):
        times = [100.0, 100.0, 50.0, 50.0]
        rate = compute_breach_rate(times, 100.0)
        self.assertAlmostEqual(rate, 0.5)

    def test_all_below_threshold(self):
        times = [10.0, 20.0, 30.0]
        rate = compute_breach_rate(times, 100.0)
        self.assertEqual(rate, 0.0)


# =========================================================================
# Route / drain / token tests
# =========================================================================

class CheapestRouteTest(unittest.TestCase):
    def test_unknown_cost_treated_conservatively(self):
        routes = [
            {"channel": "a", "cost": 50},
            {"channel": "b"},
            {"channel": "c", "cost": 30},
        ]
        cheapest = find_cheapest_route(routes)
        self.assertEqual(cheapest["channel"], "c")


class DrainByPriorityTest(unittest.TestCase):
    def test_drains_at_exact_threshold(self):
        q = PriorityQueue(capacity=100)
        q.enqueue({"id": "a", "priority": 5})
        q.enqueue({"id": "b", "priority": 3})
        q.enqueue({"id": "c", "priority": 1})
        drained = drain_by_priority(q, 3)
        drained_ids = {d["id"] for d in drained}
        self.assertIn("a", drained_ids)
        self.assertIn("b", drained_ids)
        self.assertEqual(q.size(), 1)


class TokenStoreTransferTest(unittest.TestCase):
    def test_transfer_preserves_remaining_ttl(self):
        store_long = TokenStore(default_ttl=10000.0)
        store_long.store("tok", {"user": "admin"}, ttl=10000.0)
        store_short = TokenStore(default_ttl=0.001)
        result = store_long.transfer("tok", store_short)
        self.assertTrue(result)
        time.sleep(0.01)
        self.assertTrue(store_short.validate("tok"))

    def test_transfer_expired_token_fails(self):
        store1 = TokenStore(default_ttl=1000.0)
        store1.store("tok", {"user": "admin"}, ttl=0.001)
        time.sleep(0.01)
        store2 = TokenStore(default_ttl=1000.0)
        result = store1.transfer("tok", store2)
        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
