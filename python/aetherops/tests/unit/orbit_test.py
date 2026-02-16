import unittest
from datetime import datetime, timedelta

from aetherops.models import BurnWindow
from aetherops.orbit import (
    allocate_burns,
    compute_delta_v,
    drift_penalty,
    fuel_projection,
    fuel_reserve_after_burns,
    optimal_window,
    plan_fuel_budget,
    transfer_orbit_cost,
)
from tests.test_helper import sample_snapshot, sample_windows


class OrbitTest(unittest.TestCase):
    def test_compute_delta_v_positive(self) -> None:
        self.assertAlmostEqual(compute_delta_v(12.0, 500.0), 0.6151, places=3)

    def test_compute_delta_v_non_positive_inputs(self) -> None:
        self.assertEqual(compute_delta_v(0, 300), 0)
        self.assertEqual(compute_delta_v(4, 0), 0)

    def test_allocate_burns_respects_budget(self) -> None:
        plans = allocate_burns(sample_windows(), 1.1)
        self.assertEqual(len(plans), 2)
        self.assertEqual(plans[0].window_id, "w2")
        self.assertAlmostEqual(plans[0].delta_v, 0.9, places=3)
        self.assertAlmostEqual(plans[1].delta_v, 0.2, places=3)
        self.assertAlmostEqual(sum(plan.delta_v for plan in plans), 1.1, places=3)

    def test_fuel_projection_floor(self) -> None:
        snapshot = sample_snapshot()
        plans = allocate_burns(sample_windows(), 9.0)
        self.assertAlmostEqual(fuel_projection(snapshot, plans), 176.067, places=2)

    def test_drift_penalty(self) -> None:
        self.assertAlmostEqual(drift_penalty([0.0, 1.0, -2.0]), 0.21)


class OrbitBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in orbit.py."""

    def test_transfer_orbit_cost_sums_both_burns(self) -> None:
        cost = transfer_orbit_cost(200.0, 800.0)
        self.assertGreater(cost, 0.25)

    def test_optimal_window_selects_highest_efficiency(self) -> None:
        base = datetime(2026, 1, 1)
        w_high = BurnWindow("high", base, base + timedelta(seconds=100), 1.0, 1)
        w_low = BurnWindow("low", base, base + timedelta(seconds=100), 0.1, 1)
        result = optimal_window([w_high, w_low])
        self.assertEqual(result.window_id, "high")

    def test_fuel_reserve_sequential_burns_tsiolkovsky(self) -> None:
        reserve_one = fuel_reserve_after_burns(1000.0, [2000.0], isp=300.0)
        reserve_two = fuel_reserve_after_burns(1000.0, [1000.0, 1000.0], isp=300.0)
        self.assertAlmostEqual(reserve_one, reserve_two, places=1)

    def test_plan_fuel_budget_boundary_sufficient(self) -> None:
        result = plan_fuel_budget(100.0, [], min_reserve_pct=1.0)
        self.assertTrue(result["sufficient"])


if __name__ == "__main__":
    unittest.main()
