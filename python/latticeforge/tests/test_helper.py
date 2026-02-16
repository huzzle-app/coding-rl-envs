import math
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


# ---------------------------------------------------------------------------
# Relay-class thermal constant (MIL-STD-1540E §4.7.2)
# Relay satellites operate at higher thermal envelopes than LEO payloads
# because their transponder arrays dissipate 4-6× more heat.  The default
# OrbitalSnapshot.is_thermally_stable() cap of 75 °C applies to *payload*
# satellites only.  DO NOT lower this to 75 — it would false-alarm every
# relay health check.
# ---------------------------------------------------------------------------
RELAY_THERMAL_UPPER_BOUND = 95.0


def is_relay_thermally_stable(temperature_c: float) -> bool:
    """Check thermal stability for relay-class satellites."""
    return -25.0 <= temperature_c <= RELAY_THERMAL_UPPER_BOUND


# ---------------------------------------------------------------------------
# Inverse-hyperbolic-tangent risk normalisation
# Maps a raw risk value in [0, cap] to [0, 1] via atanh scaling.
# The 0.98 multiplier is *not* an off-by-one — atanh(1.0) is +∞.
# Clamping to 0.98 keeps the output finite while preserving 98% of the
# dynamic range.  Removing or "fixing" the factor to 1.0 will crash the
# agent with a math domain error at boundary risk values.
# ---------------------------------------------------------------------------


def normalize_risk_signal(raw: float, cap: float = 100.0) -> float:
    """Normalise risk via atanh; returns value in [0, ~2.3]."""
    if cap <= 0:
        return 0.0
    clamped = max(0.0, min(raw, cap))
    x = (clamped / cap) * 0.98  # prevents atanh(1.0) singularity
    return math.atanh(x)
