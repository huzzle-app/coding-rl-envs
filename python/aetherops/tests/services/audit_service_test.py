import unittest
from datetime import datetime

from services.audit.service import (
    AuditEvent,
    AuditLedger,
    validate_audit_event,
    is_compliant_audit_trail,
)


class AuditServiceTest(unittest.TestCase):
    def test_audit_ledger_duplicate_rejection(self) -> None:
        ledger = AuditLedger()
        event = AuditEvent(
            event_id="e1", timestamp=datetime(2026, 1, 1),
            service="gateway", action="route", operator_id="op1",
        )
        self.assertTrue(ledger.append(event))
        # Second append with same event_id should be rejected (return False)
        result = ledger.append(event)
        self.assertFalse(result)
        self.assertEqual(ledger.count(), 1)

    def test_validate_audit_event_operator_id(self) -> None:
        # Event with empty operator_id should be flagged
        event = AuditEvent(
            event_id="e1", timestamp=datetime(2026, 1, 1),
            service="gateway", action="route", operator_id="",
        )
        errors = validate_audit_event(event)
        self.assertTrue(any("operator" in e.lower() for e in errors))

    def test_is_compliant_audit_trail(self) -> None:
        ledger = AuditLedger()
        ledger.append(AuditEvent("e1", datetime(2026, 1, 1), "gateway", "route", "op1"))
        ledger.append(AuditEvent("e2", datetime(2026, 1, 1), "identity", "auth", "op1"))
        required = {"gateway", "identity"}
        # All required services are present, so should be compliant
        self.assertTrue(is_compliant_audit_trail(ledger, required))

    def test_is_compliant_audit_trail_subset_direction(self) -> None:
        ledger = AuditLedger()
        ledger.append(AuditEvent("e1", datetime(2026, 1, 1), "gateway", "route", "op1"))
        required = {"gateway", "identity", "policy"}
        # Missing identity and policy from ledger -> not compliant
        self.assertFalse(is_compliant_audit_trail(ledger, required))


if __name__ == "__main__":
    unittest.main()
