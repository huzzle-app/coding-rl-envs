from datetime import datetime, timedelta

from latticeforge.models import BurnWindow, IncidentTicket, OrbitalSnapshot


def sample_snapshot() -> OrbitalSnapshot:
    return OrbitalSnapshot(
        satellite_id="sat-7",
        fuel_kg=180.0,
        power_kw=5.4,
        temperature_c=22.5,
        altitude_km=556.0,
        epoch=datetime(2026, 1, 1, 12, 0, 0),
    )


def sample_windows() -> list[BurnWindow]:
    base = datetime(2026, 1, 1, 12, 0, 0)
    return [
        BurnWindow("w1", base + timedelta(minutes=10), base + timedelta(minutes=18), 0.52, 2),
        BurnWindow("w2", base + timedelta(minutes=30), base + timedelta(minutes=40), 0.90, 3),
        BurnWindow("w3", base + timedelta(minutes=55), base + timedelta(minutes=67), 0.65, 1),
    ]


def sample_incidents() -> list[IncidentTicket]:
    return [
        IncidentTicket("i1", severity=3, subsystem="comms", description="packet loss"),
        IncidentTicket("i2", severity=1, subsystem="payload", description="sensor drift"),
    ]
