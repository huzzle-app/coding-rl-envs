import unittest
from datetime import datetime

from aetherops.scheduler import has_window_overlap, schedule_operations, sequence_from_dependencies
from tests.test_helper import sample_incidents, sample_windows


class SchedulerTest(unittest.TestCase):
    def test_schedule_operations_future_only(self) -> None:
        now = datetime(2026, 1, 1, 12, 5, 0)
        slots = schedule_operations(sample_windows(), sample_incidents(), now)
        self.assertEqual(len(slots), 3)
        self.assertGreater(slots[0]["priority"], 0)

    def test_sequence_from_dependencies(self) -> None:
        order = sequence_from_dependencies(["intake", "plan", "dispatch"], [("intake", "plan"), ("plan", "dispatch")])
        self.assertEqual(order, ["intake", "plan", "dispatch"])

    def test_window_overlap_detection(self) -> None:
        windows = sample_windows()
        self.assertFalse(has_window_overlap(windows))


if __name__ == "__main__":
    unittest.main()
