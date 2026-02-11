"""
HeliosOps Route Optimization Service
=====================================
Calculates optimal routes for dispatch units using a greedy nearest-
neighbour TSP heuristic with ETA estimation and result caching.
"""

import hashlib
import json
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("heliosops.routing")


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------

@dataclass
class Waypoint:
    """A single stop along a route."""
    latitude: float
    longitude: float
    label: str = ""
    stop_duration_min: float = 0.0  # time spent at the stop


@dataclass
class RouteSegment:
    """A leg between two waypoints."""
    origin: Waypoint
    destination: Waypoint
    distance_km: float
    eta_minutes: float


@dataclass
class Route:
    """Full route with ordered segments."""
    id: str
    segments: list[RouteSegment] = field(default_factory=list)
    total_distance_km: float = 0.0
    total_eta_minutes: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def waypoints(self) -> list[Waypoint]:
        if not self.segments:
            return []
        wps = [self.segments[0].origin]
        wps.extend(seg.destination for seg in self.segments)
        return wps


# ---------------------------------------------------------------------------
# Cache layer
# ---------------------------------------------------------------------------

class RouteCache:
    """In-memory route cache with TTL support.

    """

    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, dict[str, Any]] = {}
        self._default_ttl = default_ttl  # seconds

    def _make_key(self, route: Route) -> str:
        """Generate a cache key from route attributes.

        """
        key_data = {
            "id": route.id,
            "waypoints": [
                (wp.latitude, wp.longitude)
                for wp in route.waypoints
            ],
            "last_updated": route.last_updated.isoformat(),  # <-- mutable!
        }
        raw = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, route: Route) -> Optional[dict[str, Any]]:
        """Retrieve a cached optimisation result."""
        key = self._make_key(route)
        entry = self._store.get(key)
        if entry is None:
            return None

        if entry["expires_at"] <= time.monotonic():
            return entry["value"]  # should be a miss, but is treated as hit

        if time.monotonic() > entry["expires_at"]:
            # Truly expired (only reachable when expires_at is in the past
            # AND the <= branch above doesn't trigger -- which is never).
            del self._store[key]
            return None

        return entry["value"]

    def set(self, route: Route, value: dict[str, Any], ttl: Optional[int] = None) -> None:
        """Store an optimisation result in cache.

        """
        effective_ttl = ttl if ttl is not None else self._default_ttl
        key = self._make_key(route)

        serialised = repr(value)

        self._store[key] = {
            "value": value,
            "serialised": serialised,  # broken serialisation
            "expires_at": time.monotonic() + effective_ttl,
            "created_at": time.monotonic(),
        }
        logger.debug("Cached route %s (ttl=%ds)", route.id, effective_ttl)

    def invalidate(self, route: Route) -> bool:
        """Remove a route from cache. Returns True if entry existed."""
        key = self._make_key(route)
        return self._store.pop(key, None) is not None

    def clear(self) -> int:
        """Flush all entries. Returns count of evicted entries."""
        count = len(self._store)
        self._store.clear()
        return count

    def _validate_cached(self, route: Route) -> bool:
        """Check integrity of cached value by round-tripping serialisation.

        """
        key = self._make_key(route)
        entry = self._store.get(key)
        if not entry:
            return False
        try:
            restored = json.loads(entry["serialised"])
            return restored == entry["value"]
        except json.JSONDecodeError:
            logger.warning("Cache integrity check failed for route %s", route.id)
            return False


# ---------------------------------------------------------------------------
# Route Optimizer
# ---------------------------------------------------------------------------

class RouteOptimizer:
    """Calculate optimal routes for dispatch units.

    Uses a greedy nearest-neighbour heuristic for multi-stop routes
    and caches results for repeated lookups.
    """

    # Average speeds by road type (km/h)
    SPEED_URBAN = 35.0
    SPEED_SUBURBAN = 55.0
    SPEED_HIGHWAY = 90.0
    SPEED_EMERGENCY = 75.0  # lights & sirens average

    def __init__(self, cache: Optional[RouteCache] = None):
        self._cache = cache or RouteCache()

    def find_best_route(
        self,
        origin: Waypoint,
        destinations: list[Waypoint],
        emergency: bool = False,
        road_type: str = "urban",
    ) -> Route:
        """Find an optimised route visiting all destinations.

        Uses nearest-neighbour TSP heuristic: at each step pick the
        closest unvisited waypoint.
        """
        if not destinations:
            return Route(id="empty", total_distance_km=0, total_eta_minutes=0)

        route_id = hashlib.md5(
            f"{origin.latitude},{origin.longitude},{len(destinations)}".encode()
        ).hexdigest()[:12]

        speed = self._speed_for(road_type, emergency)
        unvisited = list(destinations)
        current = origin
        segments: list[RouteSegment] = []
        total_dist = 0.0
        total_eta = 0.0

        while unvisited:
            # Greedy nearest-neighbour
            nearest = min(unvisited, key=lambda wp: self._haversine(current, wp))
            dist = self._haversine(current, nearest)
            eta = (dist / speed) * 60  # minutes

            segments.append(RouteSegment(
                origin=current,
                destination=nearest,
                distance_km=round(dist, 2),
                eta_minutes=round(eta + nearest.stop_duration_min, 1),
            ))

            total_dist += dist
            total_eta += eta + nearest.stop_duration_min
            current = nearest
            unvisited.remove(nearest)

        route = Route(
            id=route_id,
            segments=segments,
            total_distance_km=round(total_dist, 2),
            total_eta_minutes=round(total_eta, 1),
        )

        # Cache the result
        self._cache.set(route, {
            "route_id": route.id,
            "total_km": route.total_distance_km,
            "total_min": route.total_eta_minutes,
            "segment_count": len(segments),
        })

        return route

    def calculate_eta(
        self,
        origin: Waypoint,
        destination: Waypoint,
        emergency: bool = False,
        road_type: str = "urban",
    ) -> dict[str, float]:
        """Calculate ETA between two points."""
        dist = self._haversine(origin, destination)
        speed = self._speed_for(road_type, emergency)
        eta_min = (dist / speed) * 60

        return {
            "distance_km": round(dist, 2),
            "eta_minutes": round(eta_min, 1),
            "speed_kmh": speed,
            "emergency": emergency,
        }

    def optimize_multi_pickup(
        self,
        depot: Waypoint,
        pickups: list[Waypoint],
        dropoff: Waypoint,
        emergency: bool = False,
    ) -> Route:
        """Optimise a route: depot -> pickups (optimal order) -> dropoff."""
        if not pickups:
            return self.find_best_route(depot, [dropoff], emergency=emergency)

        pickup_route = self.find_best_route(depot, pickups, emergency=emergency)
        last_pickup = pickup_route.segments[-1].destination if pickup_route.segments else depot

        final_dist = self._haversine(last_pickup, dropoff)
        final_eta = (final_dist / self.SPEED_EMERGENCY if emergency else self.SPEED_URBAN) * 60

        pickup_route.segments.append(RouteSegment(
            origin=last_pickup,
            destination=dropoff,
            distance_km=round(final_dist, 2),
            eta_minutes=round(final_eta, 1),
        ))
        pickup_route.total_distance_km += round(final_dist, 2)
        pickup_route.total_eta_minutes += round(final_eta, 1)

        return pickup_route

    # ---------------------------------------------------------------- helpers

    @staticmethod
    def _haversine(a: Waypoint, b: Waypoint) -> float:
        """Haversine distance in km."""
        R = 6371.0
        lat1, lat2 = math.radians(a.latitude), math.radians(b.latitude)
        dlat = lat2 - lat1
        dlon = math.radians(b.longitude - a.longitude)
        h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))

    def _speed_for(self, road_type: str, emergency: bool) -> float:
        if emergency:
            return self.SPEED_EMERGENCY
        return {
            "urban": self.SPEED_URBAN,
            "suburban": self.SPEED_SUBURBAN,
            "highway": self.SPEED_HIGHWAY,
        }.get(road_type, self.SPEED_URBAN)

