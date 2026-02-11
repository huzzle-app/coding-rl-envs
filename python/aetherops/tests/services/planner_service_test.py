import unittest

from services.planner.service import (
    PlannerConfig,
    build_burn_sequence,
    validate_fuel_budget,
    estimate_timeline_hours,
)


class PlannerServiceTest(unittest.TestCase):
    def test_build_burn_sequence_safety_factor(self) -> None:
        cfg = PlannerConfig(max_burns=5, safety_factor=1.15, fuel_reserve_pct=0.10)
        burns = build_burn_sequence(delta_v_required=10.0, available_fuel_kg=500.0, config=cfg)
        # Safety factor should MULTIPLY required dv: adjusted = 10.0 * 1.15 = 11.5
        total_dv = sum(b["delta_v"] for b in burns)
        self.assertGreater(total_dv, 10.0)
        self.assertAlmostEqual(total_dv, 11.5, places=1)

    def test_validate_fuel_budget_reserve(self) -> None:
        # With 100 kg fuel and 10% reserve, usable = 90 kg
        # fuel_needed = 10 * 1.9 = 19 kg, should pass
        self.assertTrue(validate_fuel_budget(10.0, 100.0, reserve_pct=0.10))
        # fuel_needed = 50 * 1.9 = 95 kg, usable = 90 kg, should FAIL
        self.assertFalse(validate_fuel_budget(50.0, 100.0, reserve_pct=0.10))

    def test_estimate_timeline_hours(self) -> None:
        # 3 burns with 90 min spacing: (3-1) * 90 / 60 = 3.0 hours
        result = estimate_timeline_hours(num_burns=3, spacing_minutes=90)
        self.assertAlmostEqual(result, 3.0, places=1)

    def test_estimate_timeline_single_burn(self) -> None:
        # 1 burn: (1-1) * 90 / 60 = 0.0 hours (no spacing needed)
        result = estimate_timeline_hours(num_burns=1, spacing_minutes=90)
        self.assertAlmostEqual(result, 0.0, places=1)


if __name__ == "__main__":
    unittest.main()
