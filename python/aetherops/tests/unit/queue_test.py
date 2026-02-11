import unittest

from aetherops.queue import WeightedQueue


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
        self.assertGreater(queue.pressure(), 0.0)

    def test_queue_pop_empty(self) -> None:
        queue = WeightedQueue()
        self.assertIsNone(queue.pop())


if __name__ == "__main__":
    unittest.main()
