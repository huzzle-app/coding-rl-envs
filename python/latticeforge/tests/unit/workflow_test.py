import unittest
from datetime import datetime

from latticeforge.workflow import orchestrate_cycle
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
        self.assertIn("risk_score", result)
        self.assertIn("projected_fuel", result)
        self.assertGreaterEqual(result["schedule_size"], 1)


if __name__ == "__main__":
    unittest.main()
