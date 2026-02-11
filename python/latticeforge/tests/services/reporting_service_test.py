import unittest

from latticeforge.models import IncidentTicket
from services.reporting.service import compile_daily_report, rank_incidents, serialize_report


class ReportingServiceTest(unittest.TestCase):
    def test_rank_incidents_descending_severity(self) -> None:
        incidents = [
            IncidentTicket("i-1", severity=2, subsystem="power", description="warn"),
            IncidentTicket("i-2", severity=5, subsystem="orbit", description="critical"),
            IncidentTicket("i-3", severity=4, subsystem="payload", description="high"),
        ]
        ranked = rank_incidents(incidents)
        self.assertEqual(ranked[0]["ticket_id"], "i-2")
        self.assertEqual(ranked[-1]["ticket_id"], "i-1")

    def test_compile_and_serialize(self) -> None:
        report = compile_daily_report(
            mission_id="mission-1",
            incidents=[],
            decisions=[],
            slo_view={"gateway": {"compliance": 0.99}},
        )
        blob = serialize_report(report)
        self.assertIn("mission-1", blob)


if __name__ == "__main__":
    unittest.main()
