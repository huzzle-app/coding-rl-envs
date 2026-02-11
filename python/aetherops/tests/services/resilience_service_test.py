import unittest

from services.resilience.service import (
    ReplayPlan,
    build_replay_plan,
    classify_replay_mode,
    estimate_replay_coverage,
)


class ResilienceServiceTest(unittest.TestCase):
    def test_build_replay_plan_budget(self) -> None:
        plan = build_replay_plan(event_count=100, timeout_s=60)
        # budget = min(100, 60*12) * 0.9 = 100 * 0.9 = 90
        self.assertEqual(plan.budget, 90)

    def test_classify_replay_mode(self) -> None:
        # ratio = 90/100 = 0.9; >= 0.9 should be "full"
        mode = classify_replay_mode(event_count=100, budget=90)
        self.assertEqual(mode, "full")
        # ratio = 0.89 should be "partial"
        mode2 = classify_replay_mode(event_count=100, budget=89)
        self.assertEqual(mode2, "partial")

    def test_estimate_replay_coverage(self) -> None:
        plan = ReplayPlan(event_count=100, budget=90, mode="full", estimated_duration_s=10.0)
        coverage = estimate_replay_coverage(plan)
        self.assertAlmostEqual(coverage, 0.9, places=3)

    def test_build_replay_plan_zero(self) -> None:
        plan = build_replay_plan(event_count=0, timeout_s=60)
        self.assertEqual(plan.budget, 0)
        self.assertEqual(plan.mode, "skip")


if __name__ == "__main__":
    unittest.main()
