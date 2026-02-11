import unittest

from aetherops.policy import requires_hold
from aetherops.resilience import replay_budget


class ReplayGovernanceIntegrationTest(unittest.TestCase):
    def test_replay_budget_stays_bounded(self) -> None:
        budget = replay_budget(events=1000, timeout_s=20)
        self.assertLessEqual(budget, 216)

    def test_hold_gate_for_risky_replay(self) -> None:
        self.assertTrue(requires_hold(65.0, comms_degraded=False))


if __name__ == "__main__":
    unittest.main()
