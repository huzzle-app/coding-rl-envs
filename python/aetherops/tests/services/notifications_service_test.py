import unittest

from services.notifications.service import (
    NotificationPlanner,
    should_throttle,
    batch_notify,
)


class NotificationsServiceTest(unittest.TestCase):
    def test_plan_channels_severity_5(self) -> None:
        planner = NotificationPlanner(severity=5, operator_id="op1")
        channels = planner.plan_channels()
        # Severity 5 should include "pager"
        self.assertIn("pager", channels)
        self.assertIn("email", channels)
        self.assertIn("sms", channels)

    def test_should_throttle_boundary(self) -> None:
        # At exactly max_per_window, should throttle (>= not >)
        self.assertTrue(should_throttle(recent_count=10, max_per_window=10, severity=3))
        # Below max should not throttle
        self.assertFalse(should_throttle(recent_count=9, max_per_window=10, severity=3))

    def test_should_throttle_critical_bypass(self) -> None:
        # Severity 5 should never be throttled
        self.assertFalse(should_throttle(recent_count=100, max_per_window=10, severity=5))

    def test_batch_notify_dedup(self) -> None:
        operators = ["op1", "op2", "op1", "op3"]
        results = batch_notify(operators, severity=3, message="alert")
        # Should deduplicate operators: only 3 unique
        self.assertEqual(len(results), 3)


if __name__ == "__main__":
    unittest.main()
