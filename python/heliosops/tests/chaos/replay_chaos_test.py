import unittest

from heliosops.resilience import replay_events


class ReplayChaosTests(unittest.TestCase):
    def test_ordered_vs_shuffled_replay_converges(self) -> None:
        ordered = replay_events([{"id": "k", "sequence": 1}, {"id": "k", "sequence": 2}])
        shuffled = replay_events([{"id": "k", "sequence": 2}, {"id": "k", "sequence": 1}])
        self.assertEqual(ordered, shuffled)


if __name__ == "__main__":
    unittest.main()
