from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

# ---------------------------------------------------------------------------
# Core route selection (preserved signature)
# ---------------------------------------------------------------------------

def choose_route(routes: Iterable[Dict[str, int]], blocked: Iterable[str]) -> Optional[Dict[str, int]]:
    blocked_set = set(blocked)
    candidates = [
        route
        for route in routes
        if str(route.get("channel")) not in blocked_set and int(route.get("latency", -1)) >= 0
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda r: (-int(r["latency"]), str(r["channel"])))[0]


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class Waypoint:
    name: str
    latitude: float = 0.0
    longitude: float = 0.0
    dwell_minutes: int = 0


@dataclass
class MultiLegPlan:
    legs: List[Waypoint] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_time_minutes: float = 0.0

    def leg_count(self) -> int:
        return max(0, len(self.legs) - 1) if len(self.legs) > 1 else 0


# ---------------------------------------------------------------------------
# Scoring and estimation
# ---------------------------------------------------------------------------

def channel_score(latency: float, reliability: float, weight: float = 0.6) -> float:
    lat_norm = max(0.0, 1.0 - latency / 100.0)
    return round(weight * reliability + (1.0 - weight) * lat_norm, 4)


def estimate_transit_time(distance_km: float, speed_knots: float = 12.0) -> float:
    speed_kmh = speed_knots * 1.852
    if speed_kmh <= 0:
        return 0.0
    return round(distance_km / speed_kmh * 60.0, 2)


def estimate_route_cost(distance_km: float, urgency: int) -> float:
    base = distance_km * 0.35
    urgency_mult = 1.0 + (urgency * 0.1)
    return round(base * urgency_mult, 2)


def compare_routes(a: Dict[str, Any], b: Dict[str, Any]) -> int:
    la = int(a.get("latency", 0))
    lb = int(b.get("latency", 0))
    if la != lb:
        return -1 if la < lb else 1
    ca = str(a.get("channel", ""))
    cb = str(b.get("channel", ""))
    if ca != cb:
        return -1 if ca < cb else 1
    return 0


# ---------------------------------------------------------------------------
# Multi-leg planning
# ---------------------------------------------------------------------------

def plan_multi_leg(waypoints: List[Waypoint]) -> MultiLegPlan:
    if len(waypoints) < 2:
        return MultiLegPlan(legs=list(waypoints))
    total_dist = 0.0
    total_time = 0.0
    for i in range(len(waypoints) - 1):
        a, b = waypoints[i], waypoints[i + 1]
        dx = abs(a.latitude - b.latitude) * 111.0
        dy = abs(a.longitude - b.longitude) * 111.0 * 0.7
        seg_dist = (dx ** 2 + dy ** 2) ** 0.5
        total_dist += seg_dist
        total_time += estimate_transit_time(seg_dist)
        total_time += b.dwell_minutes
    return MultiLegPlan(legs=list(waypoints), total_distance_km=round(total_dist, 2), total_time_minutes=round(total_time, 2))


# ---------------------------------------------------------------------------
# RouteTable — thread-safe route registry
# ---------------------------------------------------------------------------

class RouteTable:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._routes: Dict[str, Dict[str, Any]] = {}

    def add(self, channel: str, route: Dict[str, Any]) -> None:
        with self._lock:
            self._routes[channel] = route

    def get(self, channel: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self._routes.get(channel)

    def all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._routes.values())

    def remove(self, channel: str) -> bool:
        with self._lock:
            return self._routes.pop(channel, None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._routes)

    def best_route(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._routes:
                return None
            return min(self._routes.values(), key=lambda r: int(r.get("latency", 0)))


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    import math
    R = 6371.0
    lat1_r, lat2_r = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat1_r) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)


# ---------------------------------------------------------------------------
# Cheapest route finder
# ---------------------------------------------------------------------------

def find_cheapest_route(routes: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not routes:
        return None
    return min(routes, key=lambda r: float(r.get("cost") or 0))


# ---------------------------------------------------------------------------
# Adjacency cost matrix
# ---------------------------------------------------------------------------

def build_adjacency_costs(waypoints: List[Waypoint]) -> List[List[float]]:
    n = len(waypoints)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dx = abs(waypoints[i].latitude - waypoints[j].latitude) * 111.0
            dy = abs(waypoints[i].longitude - waypoints[j].longitude) * 111.0 * 0.7
            dist = round((dx ** 2 + dy ** 2) ** 0.5, 2)
            matrix[i][j] = dist
    return matrix
