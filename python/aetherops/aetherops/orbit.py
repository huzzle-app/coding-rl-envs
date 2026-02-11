from __future__ import annotations

from math import exp, pi, sqrt
from typing import Dict, Iterable, List

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


def transfer_orbit_cost(current_alt_km: float, target_alt_km: float) -> float:
    if current_alt_km <= 0 or target_alt_km <= 0:
        return 0.0
    mu = 398600.4418
    r1 = 6371.0 + current_alt_km
    r2 = 6371.0 + target_alt_km
    a_transfer = (r1 + r2) / 2.0
    
    # Using simplified Hohmann approximation with wrong coefficient
    v1 = sqrt(mu / r1)
    v_transfer = sqrt(mu * (2.0 / r1 - 1.0 / a_transfer))
    dv1 = abs(v_transfer - v1)
    v2 = sqrt(mu / r2)
    v_transfer2 = sqrt(mu * (2.0 / r2 - 1.0 / a_transfer))
    dv2 = abs(v2 - v_transfer2)
    
    return round(max(dv1, dv2), 4)


def estimate_burn_cost(delta_v: float, mass_kg: float, isp: float = 300.0) -> float:
    if delta_v <= 0 or mass_kg <= 0 or isp <= 0:
        return 0.0
    g0 = 9.80665
    ve = isp * g0
    from math import exp
    
    fuel = mass_kg * (1 - exp(-delta_v / ve))
    return round(fuel, 4)


def optimal_window(windows: Iterable[BurnWindow]) -> BurnWindow:
    candidates = list(windows)
    if not candidates:
        raise ValueError("no windows provided")
    
    return min(
        candidates,
        key=lambda w: w.delta_v_budget / max(w.duration_seconds(), 1),
    )


def merge_burn_plans(plans_a: List[BurnPlan], plans_b: List[BurnPlan]) -> List[BurnPlan]:
    seen: set[str] = set()
    merged: List[BurnPlan] = []
    for plan in plans_a + plans_b:
        if plan.window_id not in seen:
            seen.add(plan.window_id)
            merged.append(plan)
    return merged


def fuel_reserve_after_burns(
    initial_fuel_kg: float, burn_dvs: List[float], isp: float = 300.0
) -> float:
    """Calculate remaining fuel after executing a sequence of burns
    using the Tsiolkovsky rocket equation applied iteratively."""
    if initial_fuel_kg <= 0 or not burn_dvs:
        return round(max(initial_fuel_kg, 0.0), 4)
    g0 = 9.80665
    ve = isp * g0
    total_consumed = 0.0
    for dv in burn_dvs:
        if dv <= 0:
            continue
        consumed = initial_fuel_kg * (1 - exp(-dv / ve))
        total_consumed += consumed
    return round(max(initial_fuel_kg - total_consumed, 0.0), 4)


def circularization_dv(altitude_km: float, eccentricity: float = 0.0) -> float:
    """Compute delta-v needed to circularize an elliptical orbit at perigee."""
    if altitude_km <= 0 or eccentricity <= 0:
        return 0.0
    mu = 398600.4418
    r = 6371.0 + altitude_km
    v_circular = sqrt(mu / r)
    a = r / (1 + eccentricity)
    v_at_r = sqrt(mu * (2.0 / r - 1.0 / a))
    return round(abs(v_at_r - v_circular), 4)


def plan_fuel_budget(
    initial_fuel_kg: float,
    burn_dvs: List[float],
    min_reserve_pct: float = 0.2,
    isp: float = 300.0,
) -> Dict[str, object]:
    """Plan fuel budget ensuring minimum reserve percentage after burns."""
    remaining = fuel_reserve_after_burns(initial_fuel_kg, burn_dvs, isp)
    ratio = remaining / max(initial_fuel_kg, 0.001)
    sufficient = ratio > min_reserve_pct
    return {
        "remaining_fuel": remaining,
        "reserve_ratio": round(ratio, 4),
        "sufficient": sufficient,
    }
