import unittest
from datetime import datetime, timedelta

from aetherops import (
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SLA_BY_SEVERITY,
    BurnPlan,
    BurnWindow,
    OrbitalSnapshot,
    classify_severity,
    validate_snapshot,
    create_burn_manifest,
    transfer_orbit_cost,
    estimate_burn_cost,
    optimal_window,
    merge_burn_plans,
    critical_path_nodes,
    transitive_deps,
    depth_map,
    rolling_schedule,
    merge_schedules,
    validate_schedule,
    detect_drift,
    zscore_outliers,
    downsample,
    CircuitBreaker,
    deduplicate,
    replay_converges,
    sign_manifest,
    verify_manifest,
    is_allowed_origin,
    TokenStore,
    PolicyEngine,
    check_sla_compliance,
    sla_percentage,
    escalation_band,
    channel_score,
    estimate_transit_time,
    RouteTable,
    PriorityQueue,
    queue_health,
    estimate_wait_time,
    RateLimiter,
    mean,
    variance,
    stddev,
    median,
    ResponseTimeTracker,
    generate_heatmap,
    STATES,
    TRANSITIONS,
    TERMINAL_STATES,
    can_transition,
    is_terminal_state,
    shortest_path,
    WorkflowEngine,
)
from shared.contracts.contracts import (
    SERVICE_DEFS,
    get_service_url,
    validate_contract,
    topological_order,
)


class ExtModelsTest(unittest.TestCase):
    def test_severity_constants(self) -> None:
        # SEVERITY_CRITICAL should be 5, distinct from SEVERITY_HIGH (4)
        self.assertEqual(SEVERITY_CRITICAL, 5)
        self.assertNotEqual(SEVERITY_CRITICAL, SEVERITY_HIGH)

    def test_sla_by_severity(self) -> None:
        # SLA for severity 5 should be 15 minutes
        self.assertEqual(SLA_BY_SEVERITY[5], 15)

    def test_classify_severity(self) -> None:
        # Temperature extreme + low fuel (<100 kg) should contribute 4 points -> severity 5
        result = classify_severity(temperature_c=-25.0, fuel_kg=90.0, altitude_km=500.0)
        self.assertEqual(result, 5)

    def test_validate_snapshot(self) -> None:
        # Altitude 1500 km is within valid range (100-2000) so no error expected
        snap = OrbitalSnapshot(
            satellite_id="s1", fuel_kg=100.0, power_kw=5.0,
            temperature_c=20.0, altitude_km=1500.0,
            epoch=datetime(2026, 1, 1),
        )
        errors = validate_snapshot(snap)
        self.assertEqual(errors, [])

    def test_create_burn_manifest(self) -> None:
        snap = OrbitalSnapshot(
            satellite_id="s1", fuel_kg=200.0, power_kw=5.0,
            temperature_c=20.0, altitude_km=500.0,
            epoch=datetime(2026, 1, 1),
        )
        burns = [
            BurnPlan(window_id="w1", delta_v=1.0, thruster="main",
                     reason="correction", safety_margin=0.1),
        ]
        manifest = create_burn_manifest(burns, snap)
        # fuel cost factor should be 1.9, so fuel_cost = 1.0 * 1.9 = 1.9
        self.assertAlmostEqual(manifest["estimated_fuel_cost"], 1.9, places=2)


class ExtOrbitTest(unittest.TestCase):
    def test_transfer_orbit_cost(self) -> None:
        # Transfer cost should be dv1 + dv2 (sum), not max
        cost = transfer_orbit_cost(400.0, 800.0)
        # We can verify it's the sum by checking that the result is > max(dv1, dv2)
        # For 400->800km Hohmann transfer, total dv should be sum of two burns
        self.assertGreater(cost, 0)
        # The key test: cost should equal dv1 + dv2
        from math import sqrt
        mu = 398600.4418
        r1 = 6371.0 + 400.0
        r2 = 6371.0 + 800.0
        a_t = (r1 + r2) / 2.0
        v1 = sqrt(mu / r1)
        vt1 = sqrt(mu * (2.0 / r1 - 1.0 / a_t))
        dv1 = abs(vt1 - v1)
        v2 = sqrt(mu / r2)
        vt2 = sqrt(mu * (2.0 / r2 - 1.0 / a_t))
        dv2 = abs(v2 - vt2)
        expected = round(dv1 + dv2, 4)
        self.assertAlmostEqual(cost, expected, places=3)

    def test_estimate_burn_cost(self) -> None:
        # Tsiolkovsky: fuel = mass * (exp(dv/ve) - 1)
        from math import exp
        dv = 100.0
        mass = 1000.0
        isp = 300.0
        ve = isp * 9.80665
        expected = round(mass * (exp(dv / ve) - 1), 4)
        result = estimate_burn_cost(dv, mass, isp)
        self.assertAlmostEqual(result, expected, places=2)

    def test_optimal_window(self) -> None:
        base = datetime(2026, 1, 1, 12, 0, 0)
        w_low = BurnWindow("w-low", base, base + timedelta(minutes=10), 0.5, 1)
        w_high = BurnWindow("w-high", base, base + timedelta(minutes=10), 2.0, 1)
        # Should return window with highest delta_v_budget per second (max, not min)
        result = optimal_window([w_low, w_high])
        self.assertEqual(result.window_id, "w-high")

    def test_merge_burn_plans(self) -> None:
        b1 = BurnPlan("w1", 0.5, "main", "correction", 0.1)
        b2 = BurnPlan("w2", 0.3, "rcs", "correction", 0.05)
        b3 = BurnPlan("w1", 0.6, "main", "override", 0.2)
        merged = merge_burn_plans([b1], [b2, b3])
        self.assertEqual(len(merged), 2)
        self.assertEqual(merged[0].window_id, "w1")
        self.assertEqual(merged[1].window_id, "w2")


class ExtDependencyTest(unittest.TestCase):
    def test_critical_path_nodes(self) -> None:
        nodes = ["a", "b", "c", "d"]
        edges = [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")]
        result = critical_path_nodes(nodes, edges)
        # All nodes are on a critical path of length 3 (a->b->d or a->c->d)
        self.assertIn("d", result)
        self.assertIn("a", result)

    def test_transitive_deps(self) -> None:
        edges = [("a", "b"), ("b", "c"), ("a", "c")]
        result = transitive_deps("c", edges)
        self.assertIn("a", result)
        self.assertIn("b", result)

    def test_depth_map(self) -> None:
        nodes = ["a", "b", "c"]
        edges = [("a", "b"), ("b", "c")]
        result = depth_map(nodes, edges)
        # Root node "a" should have depth 0
        self.assertEqual(result["a"], 0)
        self.assertEqual(result["b"], 1)
        self.assertEqual(result["c"], 2)


class ExtSchedulerTest(unittest.TestCase):
    def test_rolling_schedule(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0)
        cutoff_time = now + timedelta(minutes=60)
        w_at_cutoff = BurnWindow(
            "w-edge", cutoff_time, cutoff_time + timedelta(minutes=10), 1.0, 1
        )
        w_before = BurnWindow(
            "w-before", now + timedelta(minutes=10), now + timedelta(minutes=20), 1.0, 1
        )
        # Window starting exactly at cutoff should be included (<= not <)
        result = rolling_schedule([w_at_cutoff, w_before], 60, now)
        ids = [s["window_id"] for s in result]
        self.assertIn("w-edge", ids)

    def test_merge_schedules(self) -> None:
        s_a = [{"window_id": "w2", "start": 2, "priority": 1}]
        s_b = [{"window_id": "w1", "start": 1, "priority": 2}]
        merged = merge_schedules(s_a, s_b)
        # Should be sorted by (start, priority), not just priority
        self.assertEqual(merged[0]["window_id"], "w1")

    def test_validate_schedule(self) -> None:
        slots = [{"window_id": "w1", "priority": 0}]
        # Priority of 0 should be flagged as an error (priority must be > 0)
        errors = validate_schedule(slots)
        self.assertTrue(any("priority" in e.lower() or "w1" in e for e in errors))


class ExtTelemetryTest(unittest.TestCase):
    def test_detect_drift(self) -> None:
        # Values with a clear outlier; using >= instead of > changes detection
        values = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        # All same values - no drift expected
        result = detect_drift(values, threshold=2.0)
        self.assertEqual(result, [])

    def test_zscore_outliers(self) -> None:
        # Should return outlier values (|zscore| > z_limit), not non-outliers
        values = [10.0, 10.0, 10.0, 10.0, 100.0]
        outliers = zscore_outliers(values, z_limit=2.0)
        # 100.0 is a clear outlier and should be in the result
        self.assertIn(100.0, outliers)
        # Non-outlier values should NOT be in the result
        self.assertTrue(all(v != 10.0 for v in outliers))

    def test_downsample(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        # Factor 2: should average buckets [1,2], [3,4], [5,6] -> [1.5, 3.5, 5.5]
        result = downsample(values, 2)
        self.assertAlmostEqual(result[0], 1.5, places=3)
        self.assertAlmostEqual(result[1], 3.5, places=3)
        self.assertAlmostEqual(result[2], 5.5, places=3)


class ExtResilienceTest(unittest.TestCase):
    def test_circuit_breaker(self) -> None:
        cb = CircuitBreaker(failure_threshold=5)
        # Record exactly 5 failures; should open at >= 5 (threshold reached)
        for _ in range(4):
            state = cb.record_failure()
            self.assertEqual(state, "closed")
        state = cb.record_failure()  # 5th failure
        self.assertEqual(state, "open")

    def test_deduplicate(self) -> None:
        events = [
            {"event_id": "e1", "data": "a"},
            {"event_id": "e1", "data": "b"},
            {"event_id": "e2", "data": "c"},
        ]
        result = deduplicate(events)
        self.assertEqual(len(result), 2)

    def test_replay_converges(self) -> None:
        orig = [{"event_id": "e1", "payload": "A"}, {"event_id": "e2", "payload": "B"}]
        repl = [{"event_id": "e1", "payload": "X"}, {"event_id": "e2", "payload": "B"}]
        # Different payloads should mean convergence is False
        result = replay_converges(orig, repl)
        self.assertFalse(result)


class ExtSecurityTest(unittest.TestCase):
    def test_sign_verify_manifest(self) -> None:
        payload = "test-payload"
        secret = "test-secret"
        sig = sign_manifest(payload, secret)
        # verify_manifest should use constant-time comparison
        self.assertTrue(verify_manifest(payload, sig, secret))

    def test_is_allowed_origin(self) -> None:
        allowed = {"https://example.com", "https://ops.example.com"}
        # Case-insensitive: HTTPS://EXAMPLE.COM should match
        self.assertTrue(is_allowed_origin("HTTPS://EXAMPLE.COM", allowed))

    def test_token_store(self) -> None:
        store = TokenStore()
        token = store.issue("user1", "operator", ttl_s=3600)
        # Token should be valid immediately after issuance
        result = store.validate(token)
        self.assertIsNotNone(result)
        self.assertEqual(result["user_id"], "user1")


class ExtPolicyTest(unittest.TestCase):
    def test_policy_engine(self) -> None:
        engine = PolicyEngine()
        self.assertEqual(engine.current_level, "green")
        # Single escalation from green should go to yellow (one step), not orange
        level = engine.escalate()
        self.assertEqual(level, "yellow")

    def test_check_sla_compliance(self) -> None:
        # Severity 5 with SLA=15 min; 16 minutes should be non-compliant
        self.assertFalse(check_sla_compliance(5, 16))

    def test_sla_percentage(self) -> None:
        incidents = [
            {"severity": 1, "elapsed": 100},
            {"severity": 1, "elapsed": 100},
        ]
        # Both are compliant (sev 1 SLA is 1440 min), so 100%
        result = sla_percentage(incidents)
        self.assertAlmostEqual(result, 100.0, places=1)

    def test_escalation_band(self) -> None:
        # 80 should be "high", not "critical" (critical is >= 90)
        self.assertEqual(escalation_band(80), "high")
        self.assertEqual(escalation_band(90), "critical")


class ExtRoutingTest(unittest.TestCase):
    def test_channel_score(self) -> None:
        # weight_latency=0.7, weight_drop should be 0.3
        # score = 0.7 * (100/1000) + 0.3 * 0.05 = 0.07 + 0.015 = 0.085
        score = channel_score(latency_ms=100, drop_rate=0.05)
        expected = round(0.7 * 0.1 + 0.3 * 0.05, 4)
        self.assertAlmostEqual(score, expected, places=3)

    def test_estimate_transit_time(self) -> None:
        # Overhead should be per hop: 3 hops * (10ms + 5ms) = 45ms
        result = estimate_transit_time(hops=3, latency_per_hop_ms=10, overhead_ms=5)
        expected = 3 * (10 + 5)
        self.assertEqual(result, expected)

    def test_route_table(self) -> None:
        rt = RouteTable()
        rt.add_route("alpha", ["hop1", "hop2"])
        rt.add_route("beta", ["hop3"])
        # all_destinations should return sorted list for determinism
        dests = rt.all_destinations()
        self.assertEqual(dests, sorted(dests))


class ExtQueueTest(unittest.TestCase):
    def test_priority_queue(self) -> None:
        pq = PriorityQueue()
        pq.enqueue("low", priority=1)
        pq.enqueue("high", priority=10)
        # Should dequeue highest priority first
        item = pq.dequeue()
        self.assertEqual(item["id"], "high")

    def test_queue_health(self) -> None:
        # utilization should be size/max_size = 50/100 = 0.5
        result = queue_health(queue_size=50, max_size=100, avg_wait_s=100)
        self.assertAlmostEqual(result["utilization"], 0.5, places=2)

    def test_estimate_wait_time(self) -> None:
        # wait_time = queue_size / processing_rate = 100 / 10 = 10.0
        result = estimate_wait_time(queue_size=100, processing_rate_per_s=10.0)
        self.assertAlmostEqual(result, 10.0, places=1)

    def test_rate_limiter(self) -> None:
        rl = RateLimiter(max_requests=3)
        self.assertTrue(rl.allow("c1"))
        self.assertTrue(rl.allow("c1"))
        self.assertTrue(rl.allow("c1"))
        # 4th request should be denied (>= max)
        self.assertFalse(rl.allow("c1"))


class ExtStatisticsTest(unittest.TestCase):
    def test_mean(self) -> None:
        result = mean([2.0, 4.0, 6.0])
        self.assertAlmostEqual(result, 4.0, places=3)

    def test_variance_and_stddev(self) -> None:
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        # Sample variance (n-1): sum of squared deviations / (n-1)
        avg = sum(values) / len(values)
        expected_var = sum((x - avg) ** 2 for x in values) / (len(values) - 1)
        result = variance(values)
        self.assertAlmostEqual(result, round(expected_var, 4), places=3)

    def test_median(self) -> None:
        # Even-length list: average of middle two elements
        values = [1.0, 3.0, 5.0, 7.0]
        # median = (3 + 5) / 2 = 4.0
        result = median(values)
        self.assertAlmostEqual(result, 4.0, places=3)

    def test_response_time_tracker(self) -> None:
        tracker = ResponseTimeTracker()
        for v in [10.0, 20.0, 30.0, 40.0, 50.0]:
            tracker.record(v)
        self.assertEqual(tracker.count(), 5)
        self.assertAlmostEqual(tracker.average(), 30.0, places=2)

    def test_generate_heatmap(self) -> None:
        values = [1.0, 2.0, 3.0]
        grid = generate_heatmap(2, 3, values)
        # Missing values should be filled with 0.0, not -1.0
        self.assertEqual(grid[1][0], 0.0)
        self.assertEqual(grid[1][1], 0.0)
        self.assertEqual(grid[1][2], 0.0)


class ExtWorkflowTest(unittest.TestCase):
    def test_states_defined(self) -> None:
        self.assertIn("created", STATES)
        self.assertIn("completed", STATES)
        self.assertEqual(len(STATES), 10)

    def test_can_transition(self) -> None:
        # "approved" should be able to transition to "cancelled"
        self.assertTrue(can_transition("approved", "cancelled"))
        self.assertTrue(can_transition("approved", "executing"))

    def test_is_terminal(self) -> None:
        self.assertTrue(is_terminal_state("completed"))
        self.assertTrue(is_terminal_state("failed"))
        self.assertTrue(is_terminal_state("cancelled"))
        self.assertFalse(is_terminal_state("created"))

    def test_shortest_path(self) -> None:
        path = shortest_path("created", "completed")
        self.assertIsNotNone(path)
        self.assertEqual(path[0], "created")
        self.assertEqual(path[-1], "completed")

    def test_workflow_engine(self) -> None:
        engine = WorkflowEngine()
        engine.advance("validated")
        # step_count should return number of transitions (len(history) - 1)
        self.assertEqual(engine.step_count(), 1)


class ExtContractsTest(unittest.TestCase):
    def test_service_defs(self) -> None:
        self.assertEqual(len(SERVICE_DEFS), 13)
        self.assertTrue(SERVICE_DEFS["gateway"].critical)
        self.assertTrue(SERVICE_DEFS["security"].critical)

    def test_get_service_url(self) -> None:
        # Should use http://, not https://
        url = get_service_url("gateway")
        self.assertTrue(url.startswith("http://"))
        self.assertIn("8080", url)

    def test_validate_contract(self) -> None:
        event = {
            "event_id": "e1", "trace_id": "t1", "mission_id": "m1",
            "timestamp": "2026-01-01", "service": "gateway",
            "kind": "command", "payload": {},
        }
        errors = validate_contract(event, kind="event")
        self.assertEqual(errors, [])

    def test_topological_order(self) -> None:
        order = topological_order()
        # gateway has no dependencies, should come first
        self.assertEqual(order[0], "gateway")
        # reporting depends on audit and analytics, so should come after both
        self.assertGreater(order.index("reporting"), order.index("audit"))
        self.assertGreater(order.index("reporting"), order.index("analytics"))


if __name__ == "__main__":
    unittest.main()
