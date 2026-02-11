import unittest

from latticeforge.orbit import allocate_burns, compute_delta_v, drift_penalty, fuel_projection
from tests.test_helper import sample_snapshot, sample_windows


class OrbitTest(unittest.TestCase):
    def test_compute_delta_v_positive(self) -> None:
        self.assertGreater(compute_delta_v(12.0, 500.0), 0)

    def test_compute_delta_v_non_positive_inputs(self) -> None:
        self.assertEqual(compute_delta_v(0, 300), 0)
        self.assertEqual(compute_delta_v(4, 0), 0)

    def test_allocate_burns_respects_budget(self) -> None:
        plans = allocate_burns(sample_windows(), 1.1)
        self.assertGreater(len(plans), 0)
        self.assertLessEqual(sum(plan.delta_v for plan in plans), 1.1)

    def test_fuel_projection_floor(self) -> None:
        snapshot = sample_snapshot()
        plans = allocate_burns(sample_windows(), 9.0)
        self.assertGreaterEqual(fuel_projection(snapshot, plans), 0.0)

    def test_drift_penalty(self) -> None:
        self.assertAlmostEqual(drift_penalty([0.0, 1.0, -2.0]), 0.21)


if __name__ == "__main__":
    unittest.main()
