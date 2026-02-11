import unittest
from datetime import datetime, timedelta, timezone

from services.intake.service import normalize_intake_batch, partition_by_urgency


def _command(command_id: str, deadline: datetime) -> dict[str, object]:
    return {
        "command_id": command_id,
        "satellite_id": "sat-7",
        "intent": "orbit-adjust",
        "issued_by": "planner",
        "signature": "abc123",
        "deadline": deadline.isoformat(),
        "trace_id": f"trace-{command_id}",
        "payload": {"burn": 0.4},
    }


class IntakeServiceTest(unittest.TestCase):
    def test_batch_keeps_distinct_command_ids(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        batch = [
            _command("cmd-1", now + timedelta(minutes=15)),
            _command("cmd-2", now + timedelta(minutes=25)),
        ]
        normalized, errors = normalize_intake_batch(batch, now)
        self.assertEqual(errors, [])
        self.assertEqual(len(normalized), 2)

    def test_batch_rejects_missing_required_fields(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        bad = [{"command_id": "cmd-x", "intent": "orbit-adjust"}]
        normalized, errors = normalize_intake_batch(bad, now)
        self.assertEqual(normalized, [])
        self.assertGreater(len(errors), 0)

    def test_urgency_partition(self) -> None:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        batch = [
            _command("cmd-a", now + timedelta(minutes=5)),
            _command("cmd-b", now + timedelta(minutes=90)),
        ]
        normalized, errors = normalize_intake_batch(batch, now)
        self.assertEqual(errors, [])
        urgent, normal = partition_by_urgency(normalized, now, horizon_minutes=20)
        self.assertEqual(len(urgent), 1)
        self.assertEqual(len(normal), 1)


if __name__ == "__main__":
    unittest.main()
