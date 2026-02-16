import unittest
from datetime import datetime

from aetherops.models import (
    SEVERITY_CRITICAL,
    SLA_BY_SEVERITY,
    FleetMetricsCache,
    IncidentTicket,
    MissionLedger,
    OrbitalSnapshot,
    build_incident_response_map,
    classify_severity,
    sort_incidents_by_priority,
    validate_snapshot,
)
from aetherops.orbit import allocate_burns
from tests.test_helper import sample_incidents, sample_windows


class ModelsTest(unittest.TestCase):
    def test_mission_ledger(self) -> None:
        ledger = MissionLedger()
        burn = allocate_burns(sample_windows(), 0.4)[0]
        ledger.append_burn(burn)
        ledger.incidents.extend(sample_incidents())
        self.assertEqual(len(ledger.executed_burns), 1)
        self.assertEqual(ledger.unresolved_incidents(), 1)


class ModelsBugDetectionTest(unittest.TestCase):
    """Tests that detect specific bugs in models.py."""

    def test_severity_critical_is_five(self) -> None:
        self.assertEqual(SEVERITY_CRITICAL, 5)

    def test_sla_severity_five_is_fifteen(self) -> None:
        self.assertEqual(SLA_BY_SEVERITY[5], 15)

    def test_classify_severity_low_fuel(self) -> None:
        result = classify_severity(temperature_c=22.0, fuel_kg=50.0, altitude_km=500.0)
        self.assertGreaterEqual(result, 3)

    def test_validate_snapshot_altitude_range(self) -> None:
        snap = OrbitalSnapshot("s1", 100.0, 5.0, 20.0, 1500.0, datetime(2026, 1, 1))
        errors = validate_snapshot(snap)
        self.assertTrue(any("altitude" in e for e in errors))

    def test_sort_incidents_by_ticket_id(self) -> None:
        incidents = [
            IncidentTicket("z-ticket", 3, "nav", "drift"),
            IncidentTicket("a-ticket", 3, "comms", "loss"),
        ]
        result = sort_incidents_by_priority(incidents)
        self.assertEqual(result[0].ticket_id, "a-ticket")

    def test_response_map_closure_captures_each(self) -> None:
        incidents = [
            IncidentTicket("t-001", 3, "comms", "link degraded"),
            IncidentTicket("t-002", 5, "power", "battery failure"),
        ]
        handlers = build_incident_response_map(incidents)
        ts = datetime(2026, 1, 1)
        self.assertEqual(handlers[0](ts)["ticket_id"], "t-001")
        self.assertEqual(handlers[1](ts)["ticket_id"], "t-002")

    def test_fleet_cache_no_mutable_leak(self) -> None:
        cache = FleetMetricsCache()
        result = cache.compute("fleet-1", [100.0, 200.0])
        result["alerts"].append("injected")
        cached = cache.get_cached("fleet-1")
        self.assertEqual(len(cached["alerts"]), 0)


if __name__ == "__main__":
    unittest.main()
