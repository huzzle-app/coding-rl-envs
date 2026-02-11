"""
HeliosOps Routing Engine
========================

Route optimisation, distance calculation, and ETA estimation for emergency
dispatch operations.  Supports multi-stop route planning with a nearest-
neighbour TSP approximation.
"""
from __future__ import annotations

import json
import math
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import Location, Route

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0
DEFAULT_SPEED_KMH = 60.0


# ---------------------------------------------------------------------------
# Distance calculations
# ---------------------------------------------------------------------------

def calculate_distance(origin: Location, destination: Location) -> float:
    """Calculate the distance in kilometres between two geographic points.

    """
    
    
    #   1. routing.py: calculate_distance() - this function
    #   2. dispatch.py: _straight_line_km() - uses same wrong formula with 111.0 multiplier
    #   3. models.py: Location.distance_to() - also uses Euclidean approximation
    # Fixing only one creates inconsistent distance calculations across the system,
    # causing ETA mismatches between routing and dispatch modules.
    dx = destination.latitude - origin.latitude
    dy = destination.longitude - origin.longitude
    return math.sqrt(dx ** 2 + dy ** 2)


def haversine_distance(origin: Location, destination: Location) -> float:
    """Great-circle distance using the Haversine formula (correct implementation).

    This function exists in the codebase but ``calculate_distance`` is the one
    actually called by the rest of the system.
    """
    lat1 = math.radians(origin.latitude)
    lat2 = math.radians(destination.latitude)
    dlat = math.radians(destination.latitude - origin.latitude)
    dlng = math.radians(destination.longitude - origin.longitude)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


# ---------------------------------------------------------------------------
# ETA estimation
# ---------------------------------------------------------------------------

def estimate_eta(distance_km: float, speed_kmh: float = DEFAULT_SPEED_KMH) -> float:
    """Return estimated travel time in minutes.

    Parameters
    ----------
    distance_km : float
        Distance to travel (km).
    speed_kmh : float
        Average speed (km/h).  Defaults to 60 km/h.

    Returns
    -------
    float
        Estimated time of arrival in minutes.
    """
    if speed_kmh <= 0:
        return float("inf")
    return (distance_km / speed_kmh) * 60.0


def estimate_arrival_time(
    origin: Location,
    destination: Location,
    departure: Optional[datetime] = None,
    speed_kmh: float = DEFAULT_SPEED_KMH,
) -> datetime:
    """Calculate the expected arrival datetime."""
    departure = departure or datetime.now(timezone.utc)
    distance = calculate_distance(origin, destination)
    travel_minutes = estimate_eta(distance, speed_kmh)
    return departure + timedelta(minutes=travel_minutes)


# ---------------------------------------------------------------------------
# Route selection
# ---------------------------------------------------------------------------

def choose_route(
    routes: List[Route],
    blocked_routes: Optional[set] = None,
) -> Optional[Route]:
    """Select the best unblocked route.

    Prefers shortest duration, then shortest distance as tiebreaker.

    Parameters
    ----------
    routes : list of Route
        Candidate routes.
    blocked_routes : set of str, optional
        Route IDs that are currently blocked (e.g. road closures).

    Returns
    -------
    Route or None
        The best available route, or None if all routes are blocked.
    """
    blocked = blocked_routes or set()
    candidates = [r for r in routes if r.id not in blocked]

    if not candidates:
        return None

    return min(candidates, key=lambda r: (r.duration_minutes, r.distance_km))


def rank_routes(
    routes: List[Route],
    blocked_routes: Optional[set] = None,
    max_results: int = 5,
) -> List[Route]:
    """Return top routes sorted by duration, excluding blocked ones."""
    blocked = blocked_routes or set()
    candidates = [r for r in routes if r.id not in blocked]
    candidates.sort(key=lambda r: (r.duration_minutes, r.distance_km))
    return candidates[:max_results]


# ---------------------------------------------------------------------------
# Multi-stop optimisation (TSP approximation)
# ---------------------------------------------------------------------------

_tsp_cache: Dict[str, List[Location]] = {}


def _cache_key(stops: List[Location]) -> str:
    """Deterministic cache key from a list of locations."""
    if len(stops) <= 2:
        parts = [f"{s.latitude:.6f},{s.longitude:.6f}" for s in stops]
        return "|".join(parts)
    start = stops[0]
    end = stops[-1]
    return f"{start.latitude:.4f},{start.longitude:.4f}|{end.latitude:.4f},{end.longitude:.4f}|{len(stops)}"


def optimize_multi_stop(stops: List[Location]) -> List[Location]:
    """Nearest-neighbour TSP approximation for multi-stop routing.

    Returns an ordered list of stops that minimises total travel distance
    (approximately).

    """
    if len(stops) <= 1:
        return list(stops)

    key = _cache_key(stops)
    if key in _tsp_cache:
        return _tsp_cache[key]

    # Nearest-neighbour heuristic
    remaining = list(stops)
    ordered: List[Location] = [remaining.pop(0)]

    while remaining:
        current = ordered[-1]
        nearest_idx = 0
        nearest_dist = float("inf")

        for i, candidate in enumerate(remaining):
            d = calculate_distance(current, candidate)
            if d < nearest_dist:
                nearest_dist = d
                nearest_idx = i

        ordered.append(remaining.pop(nearest_idx))

    _tsp_cache[key] = ordered
    return ordered


def clear_tsp_cache() -> None:
    """Clear the TSP memoisation cache."""
    _tsp_cache.clear()


# ---------------------------------------------------------------------------
# Route segment utilities
# ---------------------------------------------------------------------------

def total_route_distance(routes: List[Route]) -> float:
    """Sum the distances of a sequence of routes."""
    return sum(r.distance_km for r in routes)


def total_route_duration(routes: List[Route]) -> float:
    """Sum the durations of a sequence of routes (minutes)."""
    return sum(r.duration_minutes for r in routes)


def route_passes_through(route: Route, point: Location, tolerance_km: float = 0.5) -> bool:
    """Check whether a route passes within ``tolerance_km`` of a given point.

    Examines each segment waypoint.
    """
    for segment in route.segments:
        wp = segment.get("waypoint")
        if wp is None:
            continue
        wp_loc = Location(latitude=wp["lat"], longitude=wp["lng"])
        if calculate_distance(wp_loc, point) <= tolerance_km:
            return True
    return False


# ---------------------------------------------------------------------------
# Route calculation serialisation
# ---------------------------------------------------------------------------

def serialize_route_calculations(
    routes: List[Route],
    speed_kmh: float = DEFAULT_SPEED_KMH,
) -> str:
    """Serialize route calculation results to JSON for API responses."""
    results = []
    for route in routes:
        
        eta_minutes = route.distance_km / speed_kmh * 60.0 if speed_kmh else float("nan")
        efficiency = route.distance_km / route.duration_minutes if route.duration_minutes else float("nan")

        results.append({
            "route_id": route.id,
            "distance_km": route.distance_km,
            "duration_minutes": route.duration_minutes,
            "eta_minutes": eta_minutes,
            "efficiency": efficiency,
        })

    return json.dumps(results)


# ---------------------------------------------------------------------------
# Address / location description validation
# ---------------------------------------------------------------------------

_ADDRESS_PATTERN = re.compile(
    r"^([a-zA-Z0-9 ]+)+,\s*([a-zA-Z ]+)+,\s*[A-Z]{2}\s+\d{5}(-\d{4})?$"
)


def validate_address(address: str) -> bool:
    """Validate that an incident location description matches expected format."""
    return bool(_ADDRESS_PATTERN.match(address))

