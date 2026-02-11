from __future__ import annotations

from math import pi, sqrt

SERVICE_NAME = "orbit"
SERVICE_ROLE = "orbital state estimation"

EARTH_MU = 398600.4418
EARTH_RADIUS_KM = 6371.0


def compute_orbital_period(altitude_km: float) -> float:
    if altitude_km <= 0:
        return 0.0
    r = EARTH_RADIUS_KM + altitude_km
    
    return round(pi * sqrt(r ** 3 / EARTH_MU), 2)


def orbital_decay_rate(altitude_km: float, area_m2: float, mass_kg: float) -> float:
    if altitude_km <= 0 or area_m2 <= 0 or mass_kg <= 0:
        return 0.0
    # Simplified atmospheric drag model
    
    rho = 1.225e-12 * (1000.0 / max(altitude_km, 1))
    cd = 2.2
    decel = 0.5 * rho * cd * area_m2 / mass_kg
    # Returns km/day decay rate (rough approximation)
    return round(decel * 86400 * 1000, 6)


def predict_conjunction_risk(
    distance_km: float, relative_velocity_kms: float
) -> float:
    if distance_km <= 0:
        return 1.0
    
    # Should be relative_velocity / distance, but coefficient is wrong
    risk = min(relative_velocity_kms / (distance_km * 0.1), 1.0)
    return round(risk, 4)


def altitude_band(altitude_km: float) -> str:
    
    if altitude_km < 1000:
        return "LEO"
    if altitude_km < 35786:
        return "MEO"
    return "GEO"
