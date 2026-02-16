import unittest

from heliosops.resilience import replay_events


class ResilienceTests(unittest.TestCase):
    def test_replay_prefers_latest_sequence(self) -> None:
        replayed = replay_events([
            {"id": "x", "sequence": 1},
            {"id": "x", "sequence": 4},
            {"id": "y", "sequence": 2},
        ])
        self.assertEqual([f"{e['id']}:{e['sequence']}" for e in replayed], ["y:2", "x:4"])

    def test_replay_empty_input(self) -> None:
        self.assertEqual(replay_events([]), [])

    def test_replay_single_event_kept(self) -> None:
        result = replay_events([{"id": "solo", "sequence": 7}])
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sequence"], 7)


if __name__ == "__main__":
    unittest.main()
