import unittest

from services.mission.service import MissionRegistry


class MissionServiceTest(unittest.TestCase):
    def test_invalid_transition_raises(self) -> None:
        registry = MissionRegistry()
        registry.register("mission-1", org_id="ops", created_by="alice")
        with self.assertRaises(ValueError):
            registry.transition("mission-1", "completed", actor="alice")

    def test_valid_transition(self) -> None:
        registry = MissionRegistry()
        registry.register("mission-2", org_id="ops", created_by="alice")
        record = registry.transition("mission-2", "queued", actor="alice")
        self.assertEqual(record.state, "queued")


if __name__ == "__main__":
    unittest.main()
