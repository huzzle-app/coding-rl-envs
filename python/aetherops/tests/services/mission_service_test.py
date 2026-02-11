import unittest

from services.mission.service import (
    PHASE_TRANSITIONS,
    MissionState,
    MissionRegistry,
    validate_phase_transition,
    compute_mission_health,
    phase_index,
)


class MissionServiceTest(unittest.TestCase):
    def test_validate_phase_transition_orbit_to_aborted(self) -> None:
        # "orbit" should be able to transition to "aborted"
        self.assertTrue(validate_phase_transition("orbit", "aborted"))
        self.assertTrue(validate_phase_transition("orbit", "deorbit"))

    def test_compute_mission_health(self) -> None:
        state = MissionState(mission_id="m1", phase="orbit", fuel_loaded_kg=100.0)
        state.satellites = ["sat-1"]
        health = compute_mission_health(state)
        # With 1 satellite (< 2), should subtract 10 (not 20), so health = 90
        self.assertAlmostEqual(health, 90.0, places=1)

    def test_mission_registry(self) -> None:
        reg = MissionRegistry()
        reg.register("m1")
        reg.register("m2")
        self.assertEqual(reg.count(), 2)
        self.assertIsNotNone(reg.get("m1"))
        self.assertIsNone(reg.get("m3"))
        self.assertEqual(reg.all_ids(), ["m1", "m2"])

    def test_phase_index(self) -> None:
        self.assertEqual(phase_index("planning"), 0)
        self.assertEqual(phase_index("complete"), 5)
        self.assertEqual(phase_index("aborted"), 6)
        self.assertEqual(phase_index("nonexistent"), -1)


if __name__ == "__main__":
    unittest.main()
