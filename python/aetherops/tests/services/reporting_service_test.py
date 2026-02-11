import unittest

from services.reporting.service import (
    rank_incidents,
    compliance_report,
    format_incident_row,
    generate_executive_summary,
)


class ReportingServiceTest(unittest.TestCase):
    def test_rank_incidents_descending(self) -> None:
        incidents = [
            {"ticket_id": "t1", "severity": 2},
            {"ticket_id": "t2", "severity": 5},
            {"ticket_id": "t3", "severity": 3},
        ]
        ranked = rank_incidents(incidents)
        # Should be sorted descending by severity (highest first)
        self.assertEqual(ranked[0]["severity"], 5)
        self.assertEqual(ranked[-1]["severity"], 2)

    def test_compliance_report_threshold(self) -> None:
        # 94% resolution, 96% SLA met -> should NOT be compliant (threshold >= 95%)
        report = compliance_report(resolved=94, total=100, sla_met_pct=96.0)
        self.assertFalse(report["compliant"])
        # 95% resolution, 96% SLA met -> should be compliant
        report2 = compliance_report(resolved=95, total=100, sla_met_pct=96.0)
        self.assertTrue(report2["compliant"])

    def test_format_incident_row_description(self) -> None:
        incident = {
            "ticket_id": "t1",
            "severity": 4,
            "subsystem": "comms",
            "description": "packet loss detected",
        }
        row = format_incident_row(incident)
        # Should include description in the formatted row
        self.assertIn("packet loss detected", row)

    def test_generate_executive_summary(self) -> None:
        incidents = [
            {"severity": 5}, {"severity": 4}, {"severity": 2},
        ]
        # fleet_health of 0.85 should be "healthy" (threshold >= 0.8)
        summary = generate_executive_summary(incidents, fleet_health=0.85)
        self.assertEqual(summary["health_status"], "healthy")
        self.assertEqual(summary["critical_incidents"], 2)


if __name__ == "__main__":
    unittest.main()
