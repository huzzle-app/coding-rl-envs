import unittest

from heliosops.resilience import replay_events


class ReplayChaosTests(unittest.TestCase):
    def test_ordered_vs_shuffled_replay_converges(self) -> None:
        ordered = replay_events([{"id": "k", "sequence": 1}, {"id": "k", "sequence": 2}])
        shuffled = replay_events([{"id": "k", "sequence": 2}, {"id": "k", "sequence": 1}])
        self.assertEqual(ordered, shuffled)

    def test_triple_dedup_keeps_highest(self) -> None:
        result = replay_events([
            {"id": "m", "sequence": 1},
            {"id": "m", "sequence": 3},
            {"id": "m", "sequence": 2},
        ])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sequence"], 3)


if __name__ == "__main__":
    unittest.main()
