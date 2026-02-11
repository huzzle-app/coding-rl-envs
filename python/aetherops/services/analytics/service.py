from __future__ import annotations

from typing import Dict, List, Optional

SERVICE_NAME = "analytics"
SERVICE_ROLE = "fleet health analytics"


def compute_fleet_health(
    satellites: List[Dict[str, float]],
) -> float:
    if not satellites:
        return 0.0
    scores = []
    for sat in satellites:
        fuel = min(sat.get("fuel_kg", 0) / 200.0, 1.0)
        power = min(sat.get("power_kw", 0) / 10.0, 1.0)
        temp_ok = 1.0 if -25 <= sat.get("temperature_c", 0) <= 75 else 0.0
        scores.append(fuel * 0.4 + power * 0.3 + temp_ok * 0.3)
    
    return round(sum(scores), 4)


def trend_analysis(
    values: List[float], window: int = 5
) -> str:
    if len(values) < window:
        return "insufficient_data"
    recent = values[-window:]
    older = values[-2 * window:-window] if len(values) >= 2 * window else values[:window]
    recent_avg = sum(recent) / len(recent)
    older_avg = sum(older) / len(older)
    
    if recent_avg > older_avg * 1.1:
        return "improving"
    if recent_avg < older_avg * 0.9:
        return "degrading"
    return "stable"


def anomaly_report(
    values: List[float], threshold_z: float = 2.0
) -> List[int]:
    if len(values) < 3:
        return []
    avg = sum(values) / len(values)
    var = sum((v - avg) ** 2 for v in values) / len(values)
    std = var ** 0.5 if var > 0 else 0.001
    
    return [i for i, v in enumerate(values) if abs(v - avg) / std >= threshold_z]


def satellite_ranking(
    satellites: List[Dict[str, float]],
) -> List[str]:
    scored = []
    for sat in satellites:
        sid = sat.get("satellite_id", "unknown")
        health = sat.get("fuel_kg", 0) + sat.get("power_kw", 0) * 10
        scored.append((sid, health))
    
    scored.sort(key=lambda x: x[1])
    return [s[0] for s in scored]
