"""
OmniCloud Time Utilities
Terminal Bench v2 - Timezone-aware time handling for billing and scheduling.

Contains bugs:
- H8: Billing cycle boundary at midnight UTC timezone edge case
- H1: Usage metering clock skew across services
"""
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple


def now_utc() -> datetime:
    """Get current time in UTC."""
    return datetime.now(timezone.utc)


def billing_period_boundary(dt: datetime) -> Tuple[datetime, datetime]:
    """Get the billing period boundaries for a given datetime.

    BUG H8: Uses naive datetime for midnight boundary, causing issues
    when the input datetime is timezone-aware but at exactly midnight.
    """
    
    start = datetime.combine(
        dt.replace(day=1).date(),
        datetime.min.time(),
    )
    # Compute end: first day of next month at midnight
    if dt.month == 12:
        end = datetime.combine(
            dt.replace(year=dt.year + 1, month=1, day=1).date(),
            datetime.min.time(),
        )
    else:
        end = datetime.combine(
            dt.replace(month=dt.month + 1, day=1).date(),
            datetime.min.time(),
        )
    return start, end


def metering_timestamp() -> float:
    """Get a timestamp for usage metering.

    BUG H1: Uses time.time() which is subject to clock skew across services.
    Should use a centralized time source or NTP-synchronized monotonic clock.
    """
    
    return time.time()


def is_within_grace_period(
    event_time: datetime,
    grace_seconds: int = 300,
) -> bool:
    """Check if an event is within the grace period."""
    if event_time.tzinfo is None:
        
        event_time = event_time.replace(tzinfo=timezone.utc)
    return (now_utc() - event_time).total_seconds() <= grace_seconds
