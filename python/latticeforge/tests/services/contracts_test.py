import unittest

from shared.contracts.contracts import REQUIRED_COMMAND_FIELDS, REQUIRED_EVENT_FIELDS, SERVICE_SLO


class ServiceContractsTest(unittest.TestCase):
    def test_required_event_fields(self) -> None:
        self.assertIn("trace_id", REQUIRED_EVENT_FIELDS)
        self.assertIn("payload", REQUIRED_EVENT_FIELDS)

    def test_required_command_fields(self) -> None:
        self.assertIn("signature", REQUIRED_COMMAND_FIELDS)
        self.assertIn("deadline", REQUIRED_COMMAND_FIELDS)

    def test_service_slo_has_core_services(self) -> None:
        for service in ["gateway", "orbit", "security"]:
            self.assertIn(service, SERVICE_SLO)
            self.assertGreater(SERVICE_SLO[service]["availability"], 0.99)


if __name__ == "__main__":
    unittest.main()
