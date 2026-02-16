import unittest

from aetherops.queue import (
    BatchAccumulator,
    DrainableQueue,
    EventBuffer,
    PriorityQueue,
    SharedCounter,
    WeightedQueue,
    estimate_wait_time,
    queue_health,
)


class QueueTest(unittest.TestCase):
    def test_weighted_queue_priority(self) -> None:
        queue = WeightedQueue()
        queue.push("a", severity=2, wait_seconds=10)
        queue.push("b", severity=4, wait_seconds=0)
        queue.push("c", severity=1, wait_seconds=600)
        self.assertEqual(queue.pop().ticket_id, "b")

    def test_queue_pressure(self) -> None:
        queue = WeightedQueue()
        queue.push("a", severity=3, wait_seconds=120)
        queue.push("b", severity=2, wait_seconds=60)
        self.assertAlmostEqual(queue.pressure(), 6.0, places=2)

    def test_queue_pop_empty(self) -> None:
        queue = WeightedQueue()
        self.assertIsNone(queue.pop())


class QueueBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in queue.py."""

    def test_priority_queue_dequeues_highest(self) -> None:
        q = PriorityQueue()
        q.enqueue("low", 1)
        q.enqueue("high", 10)
        q.enqueue("mid", 5)
        item = q.dequeue()
        self.assertEqual(item["id"], "high")

    def test_queue_health_utilization_ratio(self) -> None:
        result = queue_health(50, 100, 100.0)
        self.assertAlmostEqual(result["utilization"], 0.5)

    def test_estimate_wait_time_divides(self) -> None:
        wait = estimate_wait_time(10, 2.0)
        self.assertEqual(wait, 5.0)

    def test_drainable_queue_fifo_order(self) -> None:
        q = DrainableQueue()
        q.push({"id": "first"})
        q.push({"id": "second"})
        q.push({"id": "third"})
        batch = q.drain_batch(2)
        self.assertEqual(batch[0]["id"], "first")
        self.assertEqual(batch[1]["id"], "second")

    def test_shared_counter_increment_before_snapshot(self) -> None:
        c = SharedCounter()
        val, snap = c.increment_and_snapshot(5)
        self.assertEqual(val, 5)
        self.assertEqual(snap, 5)

    def test_event_buffer_no_shared_calibration(self) -> None:
        buf1 = EventBuffer()
        buf2 = EventBuffer()
        buf1.ingest([{"value": 100.0}])
        cal = buf2.ingest([{"value": 200.0}])
        self.assertAlmostEqual(cal["baseline"], 200.0)

    def test_batch_accumulator_handles_generator(self) -> None:
        acc = BatchAccumulator()
        acc.accumulate("key", (x for x in [1, 2, 3]))
        self.assertEqual(acc.count("key"), 3)
        self.assertEqual(acc.total("key"), 6.0)


if __name__ == "__main__":
    unittest.main()
