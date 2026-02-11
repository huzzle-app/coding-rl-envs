import unittest

from aetherops.orbit import allocate_burns
from aetherops.policy import compliance_tags, evaluate_risk, requires_hold
from tests.test_helper import sample_incidents, sample_snapshot, sample_windows


class PolicyTest(unittest.TestCase):
    def test_risk_score_increases_with_load(self) -> None:
        snapshot = sample_snapshot()
        low = evaluate_risk(snapshot, allocate_burns(sample_windows(), 0.3), [])
        high = evaluate_risk(snapshot, allocate_burns(sample_windows(), 1.5), sample_incidents())
        self.assertGreater(high, low)

    def test_requires_hold(self) -> None:
        self.assertTrue(requires_hold(70.0, False))
        self.assertTrue(requires_hold(50.0, True))
        self.assertFalse(requires_hold(40.0, False))

    def test_compliance_tags(self) -> None:
        self.assertEqual(compliance_tags(72.0), ("review-required", "board-notify"))
        self.assertEqual(compliance_tags(10.0), ("routine", "auto-approved"))


if __name__ == "__main__":
    unittest.main()
