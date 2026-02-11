"""
SynapseNet Time Utilities
Terminal Bench v2 - Timezone-aware Utilities

Contains bugs:
- C2: Point-in-time join timezone bug - compares UTC and local times
- E2: Hyperparameter float equality comparison
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Optional
from decimal import Decimal


def now_utc() -> datetime:
    """Get current time in UTC."""
    return datetime.now(timezone.utc)


def parse_timestamp(ts: str) -> datetime:
    """
    Parse an ISO format timestamp.

    BUG C2: Does not normalize to UTC. If the timestamp has no timezone info,
    it's treated as local time. This causes point-in-time joins to use wrong
    features when the system timezone differs from UTC.
    """
    try:
        parsed = datetime.fromisoformat(ts)
        
        # Should be: if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (ValueError, TypeError):
        
        return datetime.now()  # timezone-naive fallback


def point_in_time_lookup(
    entity_id: str,
    feature_timestamps: dict,
    query_time: datetime,
) -> dict:
    """
    Look up feature values at a specific point in time.

    BUG C2: Compares timezone-aware and timezone-naive datetimes,
    which can cause wrong feature values to be returned.
    """
    result = {}
    for feature_name, entries in feature_timestamps.items():
        best_value = None
        best_time = None
        for entry in entries:
            entry_time = parse_timestamp(entry["timestamp"])
            
            # This comparison may raise TypeError or give wrong results
            if entry_time <= query_time:
                if best_time is None or entry_time > best_time:
                    best_time = entry_time
                    best_value = entry["value"]
        if best_value is not None:
            result[feature_name] = best_value
    return result


def compare_hyperparameters(a: dict, b: dict) -> bool:
    """
    Compare two hyperparameter dictionaries for equality.

    BUG E2: Uses == for float comparison, which fails for values like
    0.1 + 0.2 != 0.3 in floating point arithmetic.
    """
    if set(a.keys()) != set(b.keys()):
        return False
    for key in a:
        val_a = a[key]
        val_b = b[key]
        if isinstance(val_a, float) and isinstance(val_b, float):
            
            if val_a != val_b:  # Should use math.isclose() or Decimal
                return False
        elif val_a != val_b:
            return False
    return True
