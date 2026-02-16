import unittest
from datetime import datetime, timedelta

from aetherops.models import BurnWindow
from aetherops.scheduler import (
    compact_schedule,
    has_window_overlap,
    merge_schedules,
    rolling_schedule,
    schedule_operations,
    sequence_from_dependencies,
    validate_schedule,
)
from tests.test_helper import sample_incidents, sample_windows


class SchedulerTest(unittest.TestCase):
    def test_schedule_operations_future_only(self) -> None:
        now = datetime(2026, 1, 1, 12, 5, 0)
        slots = schedule_operations(sample_windows(), sample_incidents(), now)
        self.assertEqual(len(slots), 3)
        self.assertEqual(slots[0]["window_id"], "w1")
        self.assertEqual(slots[0]["priority"], 6)
        self.assertEqual(slots[0]["duration"], 480)

    def test_sequence_from_dependencies(self) -> None:
        order = sequence_from_dependencies(["intake", "plan", "dispatch"], [("intake", "plan"), ("plan", "dispatch")])
        self.assertEqual(order, ["intake", "plan", "dispatch"])

    def test_window_overlap_detection(self) -> None:
        windows = sample_windows()
        self.assertFalse(has_window_overlap(windows))


class SchedulerBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in scheduler.py."""

    def test_rolling_schedule_includes_cutoff_boundary(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0)
        w = BurnWindow("w-boundary", now + timedelta(minutes=60),
                        now + timedelta(minutes=70), 1.0, 1)
        slots = rolling_schedule([w], horizon_minutes=60, now=now)
        self.assertEqual(len(slots), 1)

    def test_merge_schedules_sorts_by_start(self) -> None:
        a = [{"window_id": "w1", "start": datetime(2026, 1, 1, 14, 0), "priority": 10}]
        b = [{"window_id": "w2", "start": datetime(2026, 1, 1, 12, 0), "priority": 20}]
        merged = merge_schedules(a, b)
        self.assertEqual(merged[0]["window_id"], "w2")

    def test_validate_schedule_flags_zero_priority(self) -> None:
        slots = [{"window_id": "w1", "priority": 0}]
        errors = validate_schedule(slots)
        self.assertTrue(any("priority" in e.lower() for e in errors))

    def test_compact_schedule_keeps_higher_priority(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0)
        slots = [
            {"window_id": "low", "start": now,
             "end": now + timedelta(minutes=3), "priority": 1},
            {"window_id": "high", "start": now + timedelta(minutes=4),
             "end": now + timedelta(minutes=7), "priority": 10},
        ]
        result = compact_schedule(slots, min_gap_seconds=300)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["window_id"], "high")


if __name__ == "__main__":
    unittest.main()
