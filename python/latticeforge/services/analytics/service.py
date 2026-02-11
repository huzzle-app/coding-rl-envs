from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from latticeforge.models import IncidentTicket
from latticeforge.statistics import percentile, rolling_sla, trimmed_mean
from latticeforge.telemetry import anomaly_score, ewma, moving_average

SERVICE_NAME = "analytics"
SERVICE_ROLE = "fleet health analytics"


@dataclass(frozen=True)
class SLOSnapshot:
    service: str
    objective_ms: int
    p95_ms: float
    compliance: float
    mean_ms: float


def compute_slo_snapshots(
    latencies_by_service: Mapping[str, Sequence[int]],
    objectives_ms: Mapping[str, int],
) -> list[SLOSnapshot]:
    snapshots: list[SLOSnapshot] = []
    for service, latencies in sorted(latencies_by_service.items()):
        objective = int(objectives_ms.get(service, 200))
        if not latencies:
            snapshots.append(SLOSnapshot(service, objective, 0.0, 0.0, 0.0))
            continue
        snapshots.append(
            SLOSnapshot(
                service=service,
                objective_ms=objective,
                p95_ms=percentile(latencies, 95),
                compliance=rolling_sla(latencies, objective),
                mean_ms=trimmed_mean([float(value) for value in latencies], 0.05),
            )
        )
    return snapshots


def incident_burn_rate(incidents: Iterable[IncidentTicket], horizon_minutes: int = 60) -> float:
    incidents = list(incidents)
    if not incidents:
        return 0.0
    weight = sum(max(incident.severity, 1) ** 1.6 for incident in incidents)
    return round(weight / max(horizon_minutes, 1), 4)


def telemetry_digest(values: Sequence[float], baseline: float, tolerance: float) -> dict[str, object]:
    if not values:
        return {"anomaly": 0.0, "ewma": [], "moving_average": []}
    return {
        "anomaly": anomaly_score(values, baseline=baseline, tolerance=tolerance),
        "ewma": ewma(values, alpha=0.35),
        "moving_average": moving_average(values, window=5),
    }
