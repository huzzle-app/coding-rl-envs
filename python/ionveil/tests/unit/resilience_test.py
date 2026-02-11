import unittest

from ionveil.resilience import replay_events


class ResilienceTests(unittest.TestCase):
    def test_replay_prefers_latest_sequence(self) -> None:
        replayed = replay_events([
            {"id": "x", "sequence": 1},
            {"id": "x", "sequence": 4},
            {"id": "y", "sequence": 2},
        ])
        self.assertEqual([f"{e['id']}:{e['sequence']}" for e in replayed], ["y:2", "x:4"])


if __name__ == "__main__":
    unittest.main()
