import unittest

from latticeforge.queue import BoundedPriorityChannel
from latticeforge.telemetry import CachedSensorView


class CachedSensorViewTest(unittest.TestCase):
    def test_basic_average(self) -> None:
        view = CachedSensorView()
        view.record("temp", 20.0)
        view.record("temp", 30.0)
        self.assertAlmostEqual(view.get_average("temp"), 25.0)

    def test_average_after_interleaved_access(self) -> None:
        view = CachedSensorView()
        view.record("temp", 20.0)
        view.record("pressure", 1000.0)
        view.get_average("temp")
        view.record("temp", 40.0)
        view.get_average("pressure")
        avg = view.get_average("temp")
        self.assertAlmostEqual(avg, 30.0, places=4)

    def test_average_reflects_new_records(self) -> None:
        view = CachedSensorView()
        view.record("s1", 10.0)
        view.get_average("s1")
        view.record("s1", 30.0)
        avg = view.get_average("s1")
        self.assertAlmostEqual(avg, 20.0, places=4)

    def test_multiple_sensors_independent(self) -> None:
        view = CachedSensorView()
        view.record("a", 10.0)
        view.record("b", 50.0)
        view.get_average("a")
        view.record("a", 20.0)
        view.record("b", 60.0)
        view.get_average("b")
        avg_a = view.get_average("a")
        self.assertAlmostEqual(avg_a, 15.0, places=4)

    def test_all_averages_refreshes_fully(self) -> None:
        view = CachedSensorView()
        view.record("x", 100.0)
        view.record("y", 200.0)
        avgs = view.all_averages()
        self.assertAlmostEqual(avgs["x"], 100.0)
        self.assertAlmostEqual(avgs["y"], 200.0)

    def test_interleaved_record_and_read(self) -> None:
        view = CachedSensorView()
        for i in range(5):
            view.record("sensor", float(i * 10))
        view.get_average("sensor")
        view.record("sensor", 100.0)
        view.record("other", 0.0)
        view.get_average("other")
        avg = view.get_average("sensor")
        expected = round(sum(i * 10 for i in range(5)) / 5, 4)
        self.assertNotAlmostEqual(avg, expected, places=2)
        actual_expected = round((sum(i * 10 for i in range(5)) + 100.0) / 6, 4)
        self.assertAlmostEqual(avg, actual_expected, places=2)


class BoundedPriorityChannelTest(unittest.TestCase):
    def test_basic_send_drain(self) -> None:
        ch = BoundedPriorityChannel(capacity=5)
        ch.send("t1", 3, 100)
        ch.send("t2", 5, 200)
        batch = ch.drain(2)
        self.assertEqual(len(batch), 2)
        self.assertEqual(ch.size, 0)

    def test_full_channel_rejects(self) -> None:
        ch = BoundedPriorityChannel(capacity=3)
        self.assertTrue(ch.send("t1", 1, 10))
        self.assertTrue(ch.send("t2", 2, 20))
        self.assertTrue(ch.send("t3", 3, 30))
        self.assertFalse(ch.send("t4", 4, 40))

    def test_send_after_partial_drain(self) -> None:
        ch = BoundedPriorityChannel(capacity=3)
        ch.send("t1", 1, 10)
        ch.send("t2", 2, 20)
        ch.send("t3", 3, 30)
        ch.drain(2)
        accepted = ch.send("t4", 4, 40)
        self.assertLessEqual(ch.pending_count, ch.capacity)

    def test_pending_tracks_all_items(self) -> None:
        ch = BoundedPriorityChannel(capacity=5)
        ch.send("t1", 3, 100)
        ch.send("t2", 5, 200)
        ch.send("t3", 1, 50)
        ch.drain(2)
        ch.send("t4", 4, 150)
        self.assertEqual(ch.pending_count, 4)
        self.assertLessEqual(ch.pending_count, ch.capacity)

    def test_acknowledge_reduces_pending(self) -> None:
        ch = BoundedPriorityChannel(capacity=5)
        ch.send("t1", 3, 100)
        ch.send("t2", 5, 200)
        batch = ch.drain(2)
        acked_ids = {batch[0].ticket_id}
        ch.acknowledge(acked_ids)
        self.assertEqual(ch.pending_count, 1)

    def test_drain_send_cycle(self) -> None:
        ch = BoundedPriorityChannel(capacity=4)
        for i in range(4):
            ch.send(f"t-{i}", severity=i + 1, wait_seconds=i * 50)
        ch.drain(3)
        for i in range(4, 7):
            ch.send(f"t-{i}", severity=1, wait_seconds=10)
        self.assertLessEqual(ch.pending_count, ch.capacity)

    def test_close_prevents_send(self) -> None:
        ch = BoundedPriorityChannel(capacity=5)
        ch.send("t1", 3, 100)
        ch.close()
        self.assertFalse(ch.send("t2", 5, 200))


if __name__ == "__main__":
    unittest.main()
