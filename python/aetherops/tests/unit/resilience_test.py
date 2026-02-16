import unittest

from aetherops.resilience import (
    CircuitBreaker,
    FailoverCoordinator,
    ReplayBuffer,
    choose_failover_region,
    classify_outage,
    replay_budget,
    replay_converges,
    retry_backoff,
)


class ResilienceTest(unittest.TestCase):
    def test_retry_backoff_caps(self) -> None:
        self.assertEqual(retry_backoff(1), 80)
        self.assertEqual(retry_backoff(8, cap_ms=1000), 1000)

    def test_choose_failover_region(self) -> None:
        region = choose_failover_region("us-east", ["us-east", "us-west", "eu-central"], ["us-west"])
        self.assertEqual(region, "eu-central")

    def test_replay_budget(self) -> None:
        self.assertEqual(replay_budget(100, 3), 32)
        self.assertEqual(replay_budget(0, 9), 0)

    def test_classify_outage(self) -> None:
        self.assertEqual(classify_outage(5, 1), "minor")
        self.assertEqual(classify_outage(50, 3), "major")


class ResilienceBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in resilience.py."""

    def test_circuit_breaker_opens_at_threshold(self) -> None:
        cb = CircuitBreaker(failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        state = cb.record_failure()
        self.assertEqual(state, "open")

    def test_replay_buffer_drain_returns_data(self) -> None:
        buf = ReplayBuffer(capacity=100)
        buf.append({"event_id": "e1"})
        buf.append({"event_id": "e2"})
        drained = buf.drain()
        self.assertEqual(len(drained), 2)
        self.assertEqual(drained[0]["event_id"], "e1")

    def test_failover_resets_errors_on_deactivate(self) -> None:
        fc = FailoverCoordinator()
        fc.begin_probe()
        fc.record_probe(False)
        fc.record_probe(False)
        fc.record_probe(True)
        fc.commit_switch()
        fc.activate()
        fc.deactivate()
        self.assertEqual(fc.error_count, 0)

    def test_replay_converges_checks_full_payload(self) -> None:
        orig = [{"event_id": "e1", "payload": "A"}]
        repl = [{"event_id": "e1", "payload": "DIFFERENT"}]
        self.assertFalse(replay_converges(orig, repl))


if __name__ == "__main__":
    unittest.main()
