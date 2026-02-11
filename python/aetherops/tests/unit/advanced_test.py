"""Advanced bug tests covering latent, domain logic, multi-step, state machine,
concurrency, and integration bug categories."""

import unittest
from datetime import datetime, timedelta
from math import sqrt, log, exp

from aetherops.orbit import (
    fuel_reserve_after_burns,
    circularization_dv,
    plan_fuel_budget,
)
from aetherops.models import (
    build_incident_response_map,
    FleetMetricsCache,
    IncidentTicket,
    BurnPlan,
    OrbitalSnapshot,
)
from aetherops.scheduler import compact_schedule
from aetherops.resilience import ReplayBuffer, FailoverCoordinator
from aetherops.security import PermissionMatrix
from aetherops.workflow import (
    MissionPipeline,
    safe_advance,
    full_mission_pipeline,
    WorkflowEngine,
)
from aetherops.policy import (
    compound_risk,
    assess_orbit_safety,
    PolicyEngine,
)
from aetherops.routing import weighted_route_score, compute_link_budget
from aetherops.queue import (
    EventBuffer,
    BatchAccumulator,
    rebalance_with_history,
)
from aetherops.telemetry import (
    align_telemetry_timestamps,
    telemetry_health_check,
)
from aetherops.statistics import exponential_decay_mean, confidence_interval
from tests.test_helper import sample_snapshot, sample_windows, sample_incidents


# ---------------------------------------------------------------------------
# 1. Latent Bugs — corrupt state silently, visible only under specific inputs
# ---------------------------------------------------------------------------

class LatentBugTest(unittest.TestCase):

    def test_fuel_reserve_single_burn(self):
        remaining = fuel_reserve_after_burns(200.0, [0.5])
        self.assertGreater(remaining, 0.0)
        self.assertLess(remaining, 200.0)

    def test_fuel_reserve_multi_burn_accumulation(self):
        """Multiple burns should use remaining mass, not initial mass each time.
        With large burns each successive burn starts from less mass, so iterative
        burns must consume strictly less total fuel than a single equivalent burn."""
        burns = [500.0, 500.0, 500.0]
        remaining_multi = fuel_reserve_after_burns(100.0, burns, isp=300.0)
        remaining_single = fuel_reserve_after_burns(100.0, [1500.0], isp=300.0)
        multi_consumed = 100.0 - remaining_multi
        single_consumed = 100.0 - remaining_single
        self.assertLess(multi_consumed, single_consumed - 0.01)

    def test_response_map_each_handler_unique(self):
        """Each response handler should capture its own incident."""
        incidents = [
            IncidentTicket("t-001", 3, "comms", "link degraded"),
            IncidentTicket("t-002", 5, "power", "battery failure"),
            IncidentTicket("t-003", 2, "thermal", "temp warning"),
        ]
        handlers = build_incident_response_map(incidents)
        ts = datetime(2026, 6, 1, 12, 0, 0)
        results = [h(ts) for h in handlers]
        ticket_ids = [r["ticket_id"] for r in results]
        self.assertEqual(ticket_ids, ["t-001", "t-002", "t-003"])

    def test_response_map_severity_preserved(self):
        """Handler severity should match its corresponding incident."""
        incidents = [
            IncidentTicket("a", 1, "sys", "info"),
            IncidentTicket("b", 5, "sys", "critical"),
        ]
        handlers = build_incident_response_map(incidents)
        ts = datetime.now()
        self.assertEqual(handlers[0](ts)["severity"], 1)

    def test_response_map_single_incident(self):
        """Single incident should be captured correctly."""
        incidents = [IncidentTicket("only", 3, "nav", "drift")]
        handlers = build_incident_response_map(incidents)
        result = handlers[0](datetime.now())
        self.assertEqual(result["ticket_id"], "only")

    def test_fleet_cache_mutation_independence(self):
        """Modifying returned dict must not corrupt cache."""
        cache = FleetMetricsCache()
        result = cache.compute("fleet-1", [100.0, 200.0, 150.0])
        result["alerts"].append("low_fuel_warning")
        cached = cache.get_cached("fleet-1")
        self.assertEqual(len(cached["alerts"]), 0)

    def test_fleet_cache_separate_computes(self):
        """Two computes for same fleet should be independent."""
        cache = FleetMetricsCache()
        r1 = cache.compute("fleet-1", [100.0])
        r1["extra"] = "injected"
        r2 = cache.compute("fleet-1", [200.0])
        self.assertNotIn("extra", r2)

    def test_fleet_cache_get_uncached(self):
        cache = FleetMetricsCache()
        self.assertIsNone(cache.get_cached("nonexistent"))


# ---------------------------------------------------------------------------
# 2. Domain Logic Bugs — require understanding of physics / SLA / risk
# ---------------------------------------------------------------------------

class DomainLogicBugTest(unittest.TestCase):

    def test_circularization_dv_perigee(self):
        """Semi-major axis at perigee: a = r / (1 - e), not r / (1 + e)."""
        dv = circularization_dv(400.0, 0.1)
        mu = 398600.4418
        r = 6371.0 + 400.0
        a_correct = r / (1 - 0.1)
        v_circ = sqrt(mu / r)
        v_at_perigee = sqrt(mu * (2.0 / r - 1.0 / a_correct))
        expected_dv = round(abs(v_at_perigee - v_circ), 4)
        self.assertAlmostEqual(dv, expected_dv, places=2)

    def test_circularization_dv_known_value(self):
        """With known eccentricity, computed dv must match vis-viva at perigee."""
        dv = circularization_dv(400.0, 0.2)
        mu = 398600.4418
        r = 6371.0 + 400.0
        a_correct = r / (1.0 - 0.2)
        v_circ = sqrt(mu / r)
        v_perigee = sqrt(mu * (2.0 / r - 1.0 / a_correct))
        expected = round(abs(v_perigee - v_circ), 4)
        self.assertAlmostEqual(dv, expected, places=2)

    def test_compound_risk_hold_on_single_high(self):
        """Hold should trigger when ANY satellite exceeds the threshold."""
        safe = OrbitalSnapshot("s1", 200.0, 5.0, 22.0, 500.0, datetime.now())
        danger = OrbitalSnapshot("s2", 50.0, 5.0, 80.0, 500.0, datetime.now())
        burns = []
        incidents = [
            IncidentTicket("i1", 4, "sys", "critical"),
            IncidentTicket("i2", 5, "sys", "emergency"),
        ]
        result = compound_risk([safe, danger], burns, incidents)
        self.assertTrue(result["hold_required"])

    def test_compound_risk_mean_dilution(self):
        """Many safe satellites should not mask a single dangerous one."""
        safe = OrbitalSnapshot("s1", 200.0, 5.0, 22.0, 500.0, datetime.now())
        risky = OrbitalSnapshot("s2", 50.0, 2.0, 80.0, 900.0, datetime.now())
        burns = [BurnPlan("w1", 2.0, "main", "correction", 0.5)]
        incidents = [IncidentTicket("i1", 4, "sys", "alert")]
        result = compound_risk([safe, safe, safe, risky], burns, incidents)
        self.assertTrue(result["hold_required"])

    def test_weighted_route_score_bandwidth(self):
        """Higher bandwidth should yield a lower (better) route score."""
        score_low_bw = weighted_route_score(100, 10.0, 0.99)
        score_high_bw = weighted_route_score(100, 90.0, 0.99)
        self.assertLess(score_high_bw, score_low_bw)

    def test_exponential_decay_mean_recent_heavier(self):
        """Recent values (end of list) should dominate the weighted mean."""
        values = [1.0] * 5 + [10.0] * 5
        result = exponential_decay_mean(values, half_life=3)
        plain_mean = sum(values) / len(values)
        self.assertGreater(result, plain_mean)

    def test_exponential_decay_mean_uniform(self):
        values = [5.0] * 10
        result = exponential_decay_mean(values, half_life=3)
        self.assertAlmostEqual(result, 5.0, places=2)

    def test_confidence_interval_narrows(self):
        """CI must narrow with increasing sample size."""
        small = [10.0, 12.0, 11.0, 9.0, 10.5]
        large = small * 4
        ci_small = confidence_interval(small, 0.95)
        ci_large = confidence_interval(large, 0.95)
        self.assertLess(ci_large[1] - ci_large[0], ci_small[1] - ci_small[0])

    def test_compute_link_budget_marginal_viable(self):
        """SNR 3.5 dB should be viable (> 3 dB threshold)."""
        result = compute_link_budget(
            transmit_power_dbm=10.0, antenna_gain_db=5.0,
            path_loss_db=111.5, noise_floor_dbm=-100.0,
        )
        self.assertTrue(result["link_viable"])

    def test_compute_link_budget_clear_viable(self):
        """SNR 10 dB should be clearly viable."""
        result = compute_link_budget(10.0, 5.0, 105.0, noise_floor_dbm=-100.0)
        self.assertTrue(result["link_viable"])


# ---------------------------------------------------------------------------
# 3. Multi-step Bugs — fixing one reveals another
# ---------------------------------------------------------------------------

class MultiStepBugTest(unittest.TestCase):

    def test_assess_orbit_safety_with_eccentricity(self):
        """Safety check must use correct circularization_dv AND ratio-based threshold."""
        snap = OrbitalSnapshot("sat-1", 80.0, 5.0, 22.0, 500.0, datetime.now())
        result = assess_orbit_safety(snap, 400.0, 0.15)
        self.assertGreater(result["dv_needed"], 0)
        remaining_ratio = result["remaining_fuel"] / 80.0
        self.assertGreater(remaining_ratio, 0.15)
        self.assertTrue(result["safe"])

    def test_assess_orbit_safety_low_fuel(self):
        snap = OrbitalSnapshot("sat-1", 60.0, 5.0, 22.0, 500.0, datetime.now())
        result = assess_orbit_safety(snap, 400.0, 0.3)
        remaining_ratio = result["remaining_fuel"] / 60.0
        self.assertLess(remaining_ratio, 0.2)
        self.assertFalse(result["safe"])

    def test_plan_fuel_budget_exact_threshold(self):
        """Exactly at reserve threshold should still be sufficient (>=)."""
        isp = 300.0
        g0 = 9.80665
        ve = isp * g0
        initial = 100.0
        target_remaining = 20.0
        dv = ve * log(initial / target_remaining)
        result = plan_fuel_budget(initial, [dv], min_reserve_pct=0.2)
        self.assertTrue(result["sufficient"])

    def test_compact_schedule_keeps_higher_priority(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        slots = [
            {"window_id": "w1", "start": now,
             "end": now + timedelta(minutes=5), "priority": 1},
            {"window_id": "w2", "start": now + timedelta(minutes=6),
             "end": now + timedelta(minutes=11), "priority": 5},
        ]
        result = compact_schedule(slots, min_gap_seconds=300)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["window_id"], "w2")

    def test_compact_schedule_preserves_non_conflicting(self):
        now = datetime(2026, 1, 1, 12, 0, 0)
        slots = [
            {"window_id": "w1", "start": now,
             "end": now + timedelta(minutes=5), "priority": 1},
            {"window_id": "w2", "start": now + timedelta(minutes=15),
             "end": now + timedelta(minutes=20), "priority": 2},
        ]
        result = compact_schedule(slots, min_gap_seconds=300)
        self.assertEqual(len(result), 2)

    def test_telemetry_health_relative_anomalies(self):
        values = [10.0] * 92 + [100.0] * 8
        result = telemetry_health_check(values, sensitivity=2.0, min_samples=50)
        self.assertEqual(result["status"], "degraded")


# ---------------------------------------------------------------------------
# 4. State Machine Bugs — invalid transitions, class-level leaks
# ---------------------------------------------------------------------------

class StateMachineBugTest(unittest.TestCase):

    def test_failover_requires_successful_probe(self):
        fc = FailoverCoordinator()
        fc.begin_probe()
        fc.record_probe(False)
        fc.record_probe(False)
        self.assertFalse(fc.commit_switch())

    def test_failover_error_count_resets(self):
        fc = FailoverCoordinator()
        fc.begin_probe()
        fc.record_probe(False)
        fc.record_probe(False)
        fc.record_probe(True)
        fc.commit_switch()
        fc.activate()
        fc.deactivate()
        self.assertEqual(fc.error_count, 0)
        self.assertTrue(fc.is_healthy())

    def test_pipeline_instance_isolation(self):
        """Two MissionPipeline instances must have independent logs."""
        MissionPipeline._shared_log.clear()
        p1 = MissionPipeline()
        p1.advance()
        p1.advance()

        p2 = MissionPipeline()
        log2 = p2.transition_log()
        self.assertEqual(len(log2), 0)

    def test_pipeline_log_tracks_own_only(self):
        """Pipeline log should only contain its own transitions."""
        MissionPipeline._shared_log.clear()
        p1 = MissionPipeline()
        p1.advance()

        p2 = MissionPipeline()
        p2.advance()
        p2.advance()

        self.assertEqual(len(p1.transition_log()), 1)

    def test_pipeline_advances_one_stage(self):
        p = MissionPipeline()
        self.assertEqual(p.current_stage(), "planning")
        p.advance()
        self.assertEqual(p.current_stage(), "validation")

    def test_pipeline_sequential_advance(self):
        p = MissionPipeline()
        visited = [p.current_stage()]
        for _ in range(5):
            p.advance()
            visited.append(p.current_stage())
        self.assertEqual(visited, MissionPipeline.STAGES)

    def test_pipeline_progress_at_start(self):
        p = MissionPipeline()
        self.assertAlmostEqual(p.progress_pct(), 0.0)
        p.advance()
        self.assertAlmostEqual(p.progress_pct(), 20.0, places=1)

    def test_safe_advance_to_completed(self):
        """Must be possible to reach terminal state 'completed'."""
        engine = WorkflowEngine()
        for target in ["validated", "scheduled", "in-progress",
                       "review", "approved", "executing"]:
            engine.advance(target)
        success, state = safe_advance(engine, "completed")
        self.assertTrue(success)
        self.assertEqual(state, "completed")

    def test_safe_advance_from_terminal_rejects(self):
        engine = WorkflowEngine()
        for target in ["validated", "scheduled", "in-progress",
                       "review", "approved", "executing", "completed"]:
            engine.advance(target)
        success, state = safe_advance(engine, "validated")
        self.assertFalse(success)
        self.assertEqual(state, "completed")


# ---------------------------------------------------------------------------
# 5. Concurrency Bugs — shared mutable state, reference aliasing
# ---------------------------------------------------------------------------

class ConcurrencyBugTest(unittest.TestCase):

    def test_replay_buffer_drain_independent(self):
        """Drained list must not be affected by subsequent buffer mutations."""
        buf = ReplayBuffer(capacity=100)
        buf.append({"event_id": "e1"})
        buf.append({"event_id": "e2"})
        drained = buf.drain()
        buf.append({"event_id": "e3"})
        self.assertEqual(len(drained), 2)
        self.assertEqual(drained[0]["event_id"], "e1")

    def test_permission_matrix_check_all(self):
        pm = PermissionMatrix()
        pm.grant("op-1", "read")
        pm.grant("op-1", "write")
        self.assertFalse(pm.check_all("op-1", {"read", "write", "delete"}))

    def test_event_buffer_calibration_isolation(self):
        """Second ingest must not use first call's calibration baseline."""
        buf1 = EventBuffer()
        events1 = [{"value": 10.0}, {"value": 20.0}]
        buf1.ingest(events1)

        buf2 = EventBuffer()
        events2 = [{"value": 100.0}, {"value": 200.0}]
        buf2.ingest(events2)
        drained = buf2.drain()
        self.assertAlmostEqual(drained[0]["calibrated"], -50.0, places=1)

    def test_event_buffer_explicit_calibration(self):
        """Explicit calibration dict avoids the mutable default."""
        buf = EventBuffer()
        events = [{"value": 50.0}]
        cal = {"baseline": 25.0}
        buf.ingest(events, calibration=cal)
        drained = buf.drain()
        self.assertAlmostEqual(drained[0]["calibrated"], 25.0, places=1)

    def test_event_buffer_drain_size(self):
        buf = EventBuffer()
        buf.ingest([{"value": 1.0}, {"value": 2.0}])
        self.assertEqual(buf.size(), 2)
        buf.drain()
        self.assertEqual(buf.size(), 0)

    def test_batch_accumulator_with_generator(self):
        """Accumulate should work correctly with generator input."""
        acc = BatchAccumulator()
        gen = (float(x) for x in range(1, 6))
        acc.accumulate("test", gen)
        self.assertEqual(acc.count("test"), 5)
        self.assertAlmostEqual(acc.total("test"), 15.0)

    def test_batch_accumulator_with_list(self):
        """Accumulate works with list (re-iterable)."""
        acc = BatchAccumulator()
        acc.accumulate("test", [1.0, 2.0, 3.0])
        self.assertEqual(acc.count("test"), 3)
        self.assertAlmostEqual(acc.total("test"), 6.0)

    def test_batch_accumulator_multiple_keys(self):
        acc = BatchAccumulator()
        acc.accumulate("a", [10.0, 20.0])
        acc.accumulate("b", [5.0])
        self.assertEqual(acc.count("a"), 2)
        self.assertEqual(acc.count("b"), 1)
        self.assertAlmostEqual(acc.average("a"), 15.0)


# ---------------------------------------------------------------------------
# 6. More Concurrency — shallow copy mutation of nested structures
# ---------------------------------------------------------------------------

class ConcurrencyMutationBugTest(unittest.TestCase):

    def test_rebalance_no_original_mutation(self):
        """Rebalancing must not modify the original items."""
        items = [
            {"id": "a", "severity": 5, "priority": 2, "history": ["initial"]},
        ]
        rebalance_with_history(items, boost_severity_above=3)
        self.assertEqual(len(items[0]["history"]), 1)

    def test_rebalance_history_independent(self):
        """Each rebalanced item should have its own history list."""
        shared_history = ["start"]
        items = [
            {"id": "a", "severity": 5, "priority": 2, "history": shared_history},
            {"id": "b", "severity": 4, "priority": 1, "history": shared_history},
        ]
        result = rebalance_with_history(items, boost_severity_above=3)
        self.assertIsNot(result[0]["history"], result[1]["history"])

    def test_rebalance_without_history_ok(self):
        """Items without pre-existing history get independent new lists."""
        items = [
            {"id": "x", "severity": 5, "priority": 1},
            {"id": "y", "severity": 4, "priority": 3},
        ]
        result = rebalance_with_history(items, boost_severity_above=3)
        self.assertEqual(result[0]["priority"], 11)
        self.assertIn("history", result[0])

    def test_rebalance_low_severity_no_boost(self):
        items = [{"id": "z", "severity": 1, "priority": 5}]
        result = rebalance_with_history(items, boost_severity_above=3)
        self.assertEqual(result[0]["priority"], 5)


# ---------------------------------------------------------------------------
# 7. Integration Bugs — cross-module interaction defects
# ---------------------------------------------------------------------------

class IntegrationBugTest(unittest.TestCase):

    def test_align_timestamps_absolute_drift(self):
        """Readings far from reference should be flagged even if close to each other."""
        ref = datetime(2026, 1, 1, 12, 0, 0)
        readings = [
            {"id": "r1", "timestamp": ref + timedelta(seconds=5)},
            {"id": "r2", "timestamp": ref + timedelta(seconds=200)},
            {"id": "r3", "timestamp": ref + timedelta(seconds=210)},
        ]
        result = align_telemetry_timestamps(readings, ref, max_drift_s=60.0)
        self.assertFalse(result[2]["aligned"])

    def test_align_timestamps_gradual_drift(self):
        """Gradual drift should be caught by absolute offset, not inter-reading gap."""
        ref = datetime(2026, 1, 1, 12, 0, 0)
        readings = [
            {"id": "r1", "timestamp": ref + timedelta(seconds=10)},
            {"id": "r2", "timestamp": ref + timedelta(seconds=35)},
            {"id": "r3", "timestamp": ref + timedelta(seconds=55)},
        ]
        result = align_telemetry_timestamps(readings, ref, max_drift_s=30.0)
        self.assertFalse(result[2]["aligned"])

    def test_align_timestamps_within_tolerance(self):
        """Readings within tolerance of reference should be aligned."""
        ref = datetime(2026, 1, 1, 12, 0, 0)
        readings = [
            {"id": "r1", "timestamp": ref + timedelta(seconds=5)},
            {"id": "r2", "timestamp": ref + timedelta(seconds=10)},
        ]
        result = align_telemetry_timestamps(readings, ref, max_drift_s=60.0)
        self.assertTrue(result[0]["aligned"])
        self.assertTrue(result[1]["aligned"])

    def test_full_mission_pipeline_stage(self):
        """Pipeline stage should be 'validation' after one advance."""
        result = full_mission_pipeline(
            sample_snapshot(),
            sample_windows(),
            sample_incidents(),
            {"sg-1": 95, "sg-2": 70},
            datetime(2026, 1, 1, 12, 3, 0),
        )
        self.assertEqual(result["pipeline_stage"], "validation")

    def test_full_mission_pipeline_progress(self):
        result = full_mission_pipeline(
            sample_snapshot(),
            sample_windows(),
            sample_incidents(),
            {"sg-1": 95, "sg-2": 70},
            datetime(2026, 1, 1, 12, 3, 0),
        )
        self.assertAlmostEqual(result["pipeline_progress"], 20.0, places=1)

    def test_full_mission_pipeline_has_fuel(self):
        result = full_mission_pipeline(
            sample_snapshot(),
            sample_windows(),
            sample_incidents(),
            {"sg-1": 95, "sg-2": 70},
            datetime(2026, 1, 1, 12, 3, 0),
        )
        self.assertGreaterEqual(result["fuel_remaining"], 0.0)


if __name__ == "__main__":
    unittest.main()
