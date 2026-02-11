import unittest

from latticeforge.scheduler import batch_schedule_with_cooldown, estimate_completion_time


class BatchScheduleTest(unittest.TestCase):
    def test_first_batch_starts_at_zero(self) -> None:
        ops = [{"id": f"op-{i}"} for i in range(4)]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=10)
        self.assertEqual(scheduled[0]["scheduled_offset_s"], 0)
        self.assertEqual(scheduled[1]["scheduled_offset_s"], 0)

    def test_second_batch_offset_by_cooldown(self) -> None:
        ops = [{"id": f"op-{i}"} for i in range(4)]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=10)
        self.assertEqual(scheduled[2]["scheduled_offset_s"], 10)
        self.assertEqual(scheduled[3]["scheduled_offset_s"], 10)

    def test_three_batches(self) -> None:
        ops = [{"id": f"op-{i}"} for i in range(5)]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=15)
        offsets = [s["scheduled_offset_s"] for s in scheduled]
        self.assertEqual(offsets, [0, 0, 15, 15, 30])

    def test_empty_operations(self) -> None:
        self.assertEqual(batch_schedule_with_cooldown([], batch_size=2, cooldown_s=10), [])

    def test_single_batch_no_cooldown_needed(self) -> None:
        ops = [{"id": "op-0"}, {"id": "op-1"}]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=5, cooldown_s=20)
        self.assertEqual(len(scheduled), 2)
        self.assertEqual(scheduled[0]["scheduled_offset_s"], 0)


class EstimateCompletionTimeTest(unittest.TestCase):
    def test_correctly_scheduled_operations(self) -> None:
        scheduled = [
            {"id": "op-0", "scheduled_offset_s": 0},
            {"id": "op-1", "scheduled_offset_s": 0},
            {"id": "op-2", "scheduled_offset_s": 10},
            {"id": "op-3", "scheduled_offset_s": 10},
            {"id": "op-4", "scheduled_offset_s": 20},
        ]
        total = estimate_completion_time(scheduled, per_op_duration_s=5, cooldown_s=10)
        self.assertEqual(total, 25)

    def test_single_batch(self) -> None:
        scheduled = [{"id": "op-0", "scheduled_offset_s": 0}]
        total = estimate_completion_time(scheduled, per_op_duration_s=5, cooldown_s=10)
        self.assertEqual(total, 5)

    def test_empty_schedule(self) -> None:
        self.assertEqual(estimate_completion_time([], per_op_duration_s=5, cooldown_s=10), 0)


class ScheduleEstimateIntegrationTest(unittest.TestCase):
    def test_end_to_end_timing(self) -> None:
        ops = [{"id": f"op-{i}"} for i in range(5)]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=10)
        total = estimate_completion_time(scheduled, per_op_duration_s=5, cooldown_s=10)
        self.assertEqual(total, 25)

    def test_schedule_offsets_correct(self) -> None:
        ops = [{"id": f"op-{i}"} for i in range(5)]
        scheduled = batch_schedule_with_cooldown(ops, batch_size=2, cooldown_s=10)
        self.assertEqual(scheduled[0]["scheduled_offset_s"], 0)


if __name__ == "__main__":
    unittest.main()
