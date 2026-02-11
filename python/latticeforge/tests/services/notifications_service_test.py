import unittest
from datetime import datetime

from latticeforge.models import IncidentTicket
from services.notifications.service import NotificationPlanner


class NotificationsServiceTest(unittest.TestCase):
    def test_severity_five_uses_all_channels(self) -> None:
        planner = NotificationPlanner(throttle_minutes=5)
        incidents = [IncidentTicket("i-5", severity=5, subsystem="orbit", description="critical drift")]
        recipients = [{"id": "oncall-1"}]
        messages = planner.plan_incident_notifications(
            incidents=incidents,
            recipients=recipients,
            now=datetime(2026, 1, 1, 12, 0, 0),
        )
        channels = sorted(message.channel for message in messages)
        self.assertEqual(channels, ["email", "pager", "sms"])

    def test_throttle_size(self) -> None:
        planner = NotificationPlanner(throttle_minutes=5)
        incidents = [IncidentTicket("i-1", severity=2, subsystem="power", description="warning")]
        recipients = [{"id": "ops"}]
        planner.plan_incident_notifications(incidents, recipients, datetime(2026, 1, 1, 12, 0, 0))
        self.assertGreater(planner.throttle_size(), 0)


if __name__ == "__main__":
    unittest.main()
