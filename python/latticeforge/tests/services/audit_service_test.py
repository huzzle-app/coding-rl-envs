import unittest
from datetime import datetime, timedelta, timezone

from services.audit.service import AuditEvent, AuditLedger


class AuditServiceTest(unittest.TestCase):
    def test_ledger_rejects_duplicate_event_id(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        event = AuditEvent(
            event_id="evt-1",
            trace_id="trace-1",
            mission_id="mission-1",
            service="gateway",
            kind="ingest",
            payload={"ok": True},
            timestamp=now,
        )
        ledger = AuditLedger()
        self.assertTrue(ledger.append(event))
        self.assertFalse(ledger.append(event))
        self.assertEqual(len(ledger.by_trace("trace-1")), 1)

    def test_gap_seconds(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ledger = AuditLedger()
        ledger.append(
            AuditEvent(
                event_id="evt-a",
                trace_id="trace-a",
                mission_id="m-1",
                service="planner",
                kind="a",
                payload={},
                timestamp=now,
            )
        )
        ledger.append(
            AuditEvent(
                event_id="evt-b",
                trace_id="trace-a",
                mission_id="m-1",
                service="planner",
                kind="b",
                payload={},
                timestamp=now + timedelta(seconds=35),
            )
        )
        self.assertEqual(ledger.mission_gap_seconds("m-1"), 35)


if __name__ == "__main__":
    unittest.main()
