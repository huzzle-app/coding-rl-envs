from __future__ import annotations

from datetime import datetime
from typing import Dict, Iterable

from .models import BurnWindow, IncidentTicket, OrbitalSnapshot
from .orbit import allocate_burns, compute_delta_v, fuel_projection
from .policy import compliance_tags, evaluate_risk, requires_hold
from .routing import choose_ground_station
from .scheduler import schedule_operations


def orchestrate_cycle(
    snapshot: OrbitalSnapshot,
    windows: Iterable[BurnWindow],
    incidents: Iterable[IncidentTicket],
    stations: Dict[str, int],
    now: datetime,
) -> Dict[str, object]:
    distance = abs(snapshot.altitude_km - 540.0)
    required_delta_v = compute_delta_v(distance_km=distance, mass_kg=max(snapshot.fuel_kg, 1.0) * 4.8)
    burns = allocate_burns(windows, required_delta_v)

    risk_score = evaluate_risk(snapshot, burns, incidents)
    hold = requires_hold(risk_score, comms_degraded=False)
    tags = compliance_tags(risk_score)

    schedule = schedule_operations(windows, incidents, now)
    station = choose_ground_station(stations.keys(), stations, blackout=[])

    return {
        "required_delta_v": required_delta_v,
        "burn_count": len(burns),
        "projected_fuel": fuel_projection(snapshot, burns),
        "risk_score": risk_score,
        "hold": hold,
        "tags": tags,
        "schedule_size": len(schedule),
        "station": station,
    }
