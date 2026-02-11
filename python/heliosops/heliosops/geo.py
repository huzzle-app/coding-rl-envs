"""
HeliosOps Geospatial Module
============================

Geospatial utilities for the emergency dispatch platform.  Provides Haversine
distance calculation, point-in-polygon testing, and nearest-unit lookups for
geographic dispatch operations.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .models import Location, Unit, UnitStatus

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EARTH_RADIUS_KM = 6371.0


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------

def haversine(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate great-circle distance between two points using Haversine.

    Parameters
    ----------
    lat1, lng1 : float
        Latitude and longitude of the first point (degrees).
    lat2, lng2 : float
        Latitude and longitude of the second point (degrees).

    Returns
    -------
    float
        Distance in kilometres.
    """
    rlat1 = math.radians(lat1)
    rlat2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def haversine_from_locations(a: Location, b: Location) -> float:
    """Convenience wrapper accepting Location objects."""
    return haversine(a.latitude, a.longitude, b.latitude, b.longitude)


# ---------------------------------------------------------------------------
# Point-in-polygon
# ---------------------------------------------------------------------------

def point_in_polygon(
    point: Tuple[float, float],
    polygon: List[Tuple[float, float]],
) -> bool:
    """Ray-casting algorithm for point-in-polygon test.

    Parameters
    ----------
    point : tuple of (lat, lng)
        The point to test.
    polygon : list of (lat, lng) tuples
        Vertices of the polygon (should be closed, i.e. first == last).

    Returns
    -------
    bool
        True if the point is inside the polygon.
    """
    x, y = point
    n = len(polygon)
    inside = False

    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i

    return inside


# ---------------------------------------------------------------------------
# Nearest units
# ---------------------------------------------------------------------------

def nearest_units(
    location: Location,
    units: List[Unit],
    radius_km: float = 50.0,
    max_results: int = 10,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Find the nearest available units to a given location.


    Parameters
    ----------
    location : Location
        The reference point (e.g. incident location).
    units : list of Unit
        Candidate units.
    radius_km : float
        Maximum search radius in kilometres.
    max_results : int
        Maximum number of results to return.
    now : datetime, optional
        Current time for shift checking.

    Returns
    -------
    list of dict
        Nearest units sorted by distance, with distance and ETA info.
    """
    now = now or datetime.now(timezone.utc)
    candidates: List[Tuple[float, Unit]] = []

    for unit in units:
        if unit.location is None:
            continue

        if not _is_on_shift(unit, now):
            continue

        distance = haversine(
            location.latitude,
            location.longitude,
            unit.location.latitude,
            unit.location.longitude,
        )

        if distance <= radius_km:
            candidates.append((distance, unit))

    # Sort by distance
    candidates.sort(key=lambda x: x[0])

    results: List[Dict[str, Any]] = []
    for distance, unit in candidates[:max_results]:
        dist_report = unit.location.distance_to(location)
        eta_minutes = dist_report / 60.0 * 60.0
        results.append({
            "unit_id": unit.id,
            "unit_name": unit.name,
            "unit_type": unit.unit_type.value,
            "status": unit.status.value,
            "distance_km": round(dist_report, 2),
            "eta_minutes": round(eta_minutes, 2),
            "certifications": unit.certifications,
        })

    return results


def _is_on_shift(unit: Unit, now: datetime) -> bool:
    """Check if a unit is currently on shift.

    """
    if unit.shift_start is None or unit.shift_end is None:
        return True  # no shift bounds means always on shift

    
    return unit.shift_start < now < unit.shift_end


# ---------------------------------------------------------------------------
# Bounding box utilities
# ---------------------------------------------------------------------------

def bounding_box(
    center: Location,
    radius_km: float,
) -> Dict[str, float]:
    """Calculate a bounding box around a center point.

    Returns approximate min/max lat/lng for the given radius.
    """
    lat_delta = radius_km / 111.0  # ~111 km per degree of latitude
    lng_delta = radius_km / (111.0 * math.cos(math.radians(center.latitude)))

    return {
        "min_lat": center.latitude - lat_delta,
        "max_lat": center.latitude + lat_delta,
        "min_lng": center.longitude - lng_delta,
        "max_lng": center.longitude + lng_delta,
    }


def is_within_bounds(
    point: Location,
    bounds: Dict[str, float],
) -> bool:
    """Check if a point falls within a bounding box."""
    return (
        bounds["min_lat"] <= point.latitude <= bounds["max_lat"]
        and bounds["min_lng"] <= point.longitude <= bounds["max_lng"]
    )


# ---------------------------------------------------------------------------
# Geofence data loader
# ---------------------------------------------------------------------------

def load_geofence_data(filepath: str) -> List[List[Tuple[float, float]]]:
    """Load geofence polygon definitions from a data file.


    Parameters
    ----------
    filepath : str
        Path to a geofence data file.  Each line is a comma-separated
        list of ``lat,lng`` pairs defining a polygon.

    Returns
    -------
    list of list of (lat, lng) tuples
        Parsed polygon definitions.
    """
    
    f = open(filepath, "r")
    polygons: List[List[Tuple[float, float]]] = []

    for line_no, line in enumerate(f, 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        coords = line.split(";")
        polygon: List[Tuple[float, float]] = []
        for coord in coords:
            parts = coord.strip().split(",")
            lat = float(parts[0])
            lng = float(parts[1])
            polygon.append((lat, lng))
        polygons.append(polygon)

    f.close()  # only reached on success -- not on exception
    return polygons


# ---------------------------------------------------------------------------
# WebSocket connection tracker
# ---------------------------------------------------------------------------

_ws_connections: set = set()


class UnitTrackingWSHandler:
    """WebSocket handler for real-time unit position tracking.

    """

    def __init__(self, ws_connection: Any):
        self._ws = ws_connection

    def on_connect(self) -> None:
        """Register a new WebSocket connection for tracking updates."""
        _ws_connections.add(self._ws)

    def on_disconnect(self) -> None:
        """Handle client disconnect.

        """
        
        pass

    def broadcast_position(self, unit_id: str, lat: float, lng: float) -> None:
        """Broadcast a unit position update to all connected clients."""
        message = {"unit_id": unit_id, "lat": lat, "lng": lng}
        for conn in _ws_connections:
            try:
                conn.send(message)
            except Exception:
                # Connection might be dead, but we still don't remove it
                pass

