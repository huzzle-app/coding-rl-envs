import unittest
from datetime import datetime

from aetherops.workflow import (
    MissionPipeline,
    WorkflowEngine,
    can_transition,
    orchestrate_cycle,
    safe_advance,
)
from tests.test_helper import sample_incidents, sample_snapshot, sample_windows


class WorkflowTest(unittest.TestCase):
    def test_orchestrate_cycle(self) -> None:
        result = orchestrate_cycle(
            snapshot=sample_snapshot(),
            windows=sample_windows(),
            incidents=sample_incidents(),
            stations={"sg-1": 80, "sg-2": 65},
            now=datetime(2026, 1, 1, 12, 0, 0),
        )
        self.assertEqual(result["burn_count"], 1)
        self.assertAlmostEqual(result["risk_score"], 16.809, places=2)
        self.assertAlmostEqual(result["projected_fuel"], 178.7817, places=2)
        self.assertEqual(result["schedule_size"], 3)
        self.assertEqual(result["station"], "sg-2")
        self.assertFalse(result["hold"])


class WorkflowBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in workflow.py."""

    def test_approved_can_cancel(self) -> None:
        self.assertTrue(can_transition("approved", "cancelled"))

    def test_step_count_excludes_initial(self) -> None:
        engine = WorkflowEngine()
        self.assertEqual(engine.step_count(), 0)
        engine.advance("validated")
        self.assertEqual(engine.step_count(), 1)

    def test_mission_pipeline_independent_logs(self) -> None:
        p1 = MissionPipeline()
        p2 = MissionPipeline()
        p1.advance()
        self.assertEqual(p2.transition_log(), [])

    def test_safe_advance_allows_terminal_targets(self) -> None:
        engine = WorkflowEngine()
        engine.advance("validated")
        engine.advance("scheduled")
        engine.advance("in-progress")
        engine.advance("review")
        engine.advance("approved")
        engine.advance("executing")
        result, state = safe_advance(engine, "completed")
        self.assertTrue(result)
        self.assertEqual(state, "completed")


if __name__ == "__main__":
    unittest.main()
