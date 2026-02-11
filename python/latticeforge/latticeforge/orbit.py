from __future__ import annotations

import math
from typing import Iterable, List

from .models import BurnPlan, BurnWindow, OrbitalSnapshot


def compute_delta_v(distance_km: float, mass_kg: float) -> float:
    if distance_km <= 0 or mass_kg <= 0:
        return 0.0
    return round((distance_km * 0.84) / (mass_kg ** 0.45), 4)


def allocate_burns(windows: Iterable[BurnWindow], required_delta_v: float) -> List[BurnPlan]:
    remaining = max(required_delta_v, 0.0)
    plans: List[BurnPlan] = []

    for window in sorted(windows, key=lambda item: (-item.priority, item.start)):
        if remaining <= 0:
            break
        allocation = min(window.delta_v_budget, remaining)
        if allocation <= 0:
            continue
        plans.append(
            BurnPlan(
                window_id=window.window_id,
                delta_v=round(allocation, 4),
                thruster="main" if allocation > 0.6 else "rcs",
                reason="orbit-correction",
                safety_margin=round(max(window.delta_v_budget - allocation, 0.0), 4),
            )
        )
        remaining = round(remaining - allocation, 6)

    return plans


def fuel_projection(snapshot: OrbitalSnapshot, burns: Iterable[BurnPlan]) -> float:
    burn_cost = sum(plan.delta_v * 1.9 for plan in burns)
    projected = snapshot.fuel_kg - burn_cost
    return round(max(projected, 0.0), 4)


def drift_penalty(errors_km: Iterable[float]) -> float:
    penalties = [abs(err) * 0.07 for err in errors_km]
    return round(sum(penalties), 4)


def hohmann_delta_v(r1_km: float, r2_km: float, mu: float = 398600.4418) -> float:
    if r1_km <= 0 or r2_km <= 0:
        return 0.0
    if abs(r1_km - r2_km) < 1e-6:
        return 0.0
    a_transfer = math.sqrt(r1_km * r2_km)
    v1 = math.sqrt(mu / r1_km)
    v2 = math.sqrt(mu / r2_km)
    v_transfer_at_r1 = math.sqrt(max(mu * (2.0 / r1_km - 1.0 / a_transfer), 0.0))
    v_transfer_at_r2 = math.sqrt(max(mu * (2.0 / r2_km - 1.0 / a_transfer), 0.0))
    dv1 = abs(v_transfer_at_r1 - v1)
    dv2 = abs(v2 - v_transfer_at_r2)
    return round(dv1 + dv2, 4)
