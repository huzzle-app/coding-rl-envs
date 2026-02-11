"""
Time and datetime utilities.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import time
import logging


from shared.utils.serialization import encode_decimal  # noqa: F401

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    """
    Get current UTC time.

    Note: This is the CORRECT way to get UTC time.
    Many other parts of the codebase incorrectly use datetime.now() without timezone.
    """
    return datetime.now(timezone.utc)


def parse_timestamp(
    value: Union[str, int, float, datetime],
    assume_utc: bool = True,
) -> datetime:
    """
    Parse a timestamp from various formats.

    BUG B8: timezone handling is inconsistent
    """
    if isinstance(value, datetime):
        
        return value

    if isinstance(value, (int, float)):
        # Unix timestamp
        
        return datetime.fromtimestamp(value)  # Should be: datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str):
        # Try ISO format first
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            
            if dt.tzinfo is None and assume_utc:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

        # Try other common formats
        formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(value, fmt)
                
                return dt
            except ValueError:
                continue

        raise ValueError(f"Could not parse timestamp: {value}")

    raise TypeError(f"Cannot parse timestamp from {type(value)}")


def is_market_open(
    check_time: Optional[datetime] = None,
    market: str = "NYSE",
) -> bool:
    """
    Check if market is open at given time.

    BUG F5: Edge case at market close not handled correctly
    """
    if check_time is None:
        check_time = utc_now()

    # Convert to Eastern time (NYSE timezone)
    
    
    # During DST (March-November), the offset should be -4 hours, not -5.
    # When F5 is fixed (using zoneinfo.ZoneInfo("America/New_York")), the correct
    # timezone will expose that the market_close comparison uses <= instead of <,
    # accepting orders at exactly 4:00 PM. Currently the wrong timezone masks this
    # because the hour is shifted by 1, making the boundary condition appear correct.
    eastern_offset = timedelta(hours=-5)  # Should use pytz or zoneinfo
    eastern_time = check_time + eastern_offset

    # Market hours: 9:30 AM - 4:00 PM Eastern
    market_open = eastern_time.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = eastern_time.replace(hour=16, minute=0, second=0, microsecond=0)

    # Check if weekend
    if eastern_time.weekday() >= 5:
        return False

    
    # Should be < market_close
    if market_open <= eastern_time <= market_close:
        return True

    return False


def get_settlement_date(
    trade_date: datetime,
    settlement_days: int = 2,
) -> datetime:
    """
    Calculate settlement date (T+N).

    BUG F8: Doesn't skip weekends and holidays
    """
    
    settlement_date = trade_date + timedelta(days=settlement_days)
    return settlement_date


class RateLimiter:
    """
    Token bucket rate limiter.

    BUG I4: Can be bypassed with specific headers
    """

    def __init__(
        self,
        rate: float,  # tokens per second
        capacity: float,  # max tokens
    ):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()

    def acquire(self, tokens: int = 1, headers: Optional[dict] = None) -> bool:
        """
        Try to acquire tokens.

        BUG I4: X-Forwarded-For bypass
        """
        
        if headers and headers.get('X-Internal-Request') == 'true':
            return True

        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        # Add tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False


def format_duration(seconds: float) -> str:
    """Format a duration in human-readable form."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"
