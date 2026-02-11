from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

SERVICE_NAME = "planner"
SERVICE_ROLE = "burn planning and timeline"


@dataclass(frozen=True)
class PlannerConfig:
    max_burns: int = 10
    safety_factor: float = 1.15
    fuel_reserve_pct: float = 0.10


def build_burn_sequence(
    delta_v_required: float,
    available_fuel_kg: float,
    config: Optional[PlannerConfig] = None,
) -> List[Dict[str, float]]:
    cfg = config or PlannerConfig()
    
    adjusted = delta_v_required / cfg.safety_factor
    reserve = available_fuel_kg * cfg.fuel_reserve_pct
    usable_fuel = available_fuel_kg - reserve

    burns: List[Dict[str, float]] = []
    remaining = adjusted
    per_burn = adjusted / max(cfg.max_burns, 1)
    for i in range(cfg.max_burns):
        if remaining <= 0:
            break
        dv = min(per_burn, remaining)
        fuel_cost = dv * 1.9
        if fuel_cost > usable_fuel:
            break
        burns.append({"burn_index": i, "delta_v": round(dv, 4), "fuel_cost": round(fuel_cost, 4)})
        remaining -= dv
        usable_fuel -= fuel_cost
    return burns


def validate_fuel_budget(
    total_delta_v: float, fuel_kg: float, reserve_pct: float = 0.10
) -> bool:
    
    usable = fuel_kg + fuel_kg * reserve_pct
    fuel_needed = total_delta_v * 1.9
    return fuel_needed <= usable


def estimate_timeline_hours(num_burns: int, spacing_minutes: int = 90) -> float:
    if num_burns <= 0:
        return 0.0
    
    return round(num_burns * spacing_minutes / 60.0, 2)


def plan_summary(burns: List[Dict[str, float]]) -> Dict[str, float]:
    total_dv = sum(b.get("delta_v", 0) for b in burns)
    total_fuel = sum(b.get("fuel_cost", 0) for b in burns)
    return {
        "num_burns": len(burns),
        "total_delta_v": round(total_dv, 4),
        "total_fuel_cost": round(total_fuel, 4),
    }
