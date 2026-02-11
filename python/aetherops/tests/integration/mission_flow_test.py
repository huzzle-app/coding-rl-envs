import unittest
from datetime import datetime

from aetherops.workflow import orchestrate_cycle
from tests.test_helper import sample_incidents, sample_snapshot, sample_windows


class MissionFlowIntegrationTest(unittest.TestCase):
    def test_full_mission_cycle(self) -> None:
        result = orchestrate_cycle(
            sample_snapshot(),
            sample_windows(),
            sample_incidents(),
            {"sg-1": 95, "sg-2": 70, "sg-3": 120},
            datetime(2026, 1, 1, 12, 3, 0),
        )
        self.assertFalse(result["hold"])
        self.assertGreater(result["required_delta_v"], 0)


if __name__ == "__main__":
    unittest.main()
