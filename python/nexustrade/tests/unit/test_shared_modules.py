"""
Unit tests for shared module bugs.

These tests import and call actual buggy code from shared/ modules,
ensuring bugs are detected when the circular import (L1) is fixed.
"""
import pytest
import time
import math
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch


# =============================================================================
# Tests for shared/utils/time.py bugs
# =============================================================================

class TestIsMarketOpen:
    """Tests for bug F5: Market close edge case in is_market_open()."""

    def test_market_close_exactly_4pm_rejected(self):
        """BUG F5: Orders at exactly 4:00 PM ET should be rejected."""
        from shared.utils.time import is_market_open
        # 4:00 PM Eastern = 9:00 PM UTC (EST offset -5h), Monday
        close_time = datetime(2024, 1, 8, 21, 0, 0, tzinfo=timezone.utc)
        result = is_market_open(close_time)
        
        assert result is False, "Market should be CLOSED at exactly 4:00 PM ET"

    def test_market_close_one_second_before(self):
        """Test that 3:59:59 PM is still open."""
        from shared.utils.time import is_market_open
        # 3:59:59 PM Eastern = 8:59:59 PM UTC
        before_close = datetime(2024, 1, 8, 20, 59, 59, tzinfo=timezone.utc)
        result = is_market_open(before_close)
        assert result is True, "Market should be open at 3:59:59 PM ET"

    def test_market_close_one_second_after(self):
        """Test that 4:00:01 PM is closed."""
        from shared.utils.time import is_market_open
        # 4:00:01 PM Eastern = 9:00:01 PM UTC
        after_close = datetime(2024, 1, 8, 21, 0, 1, tzinfo=timezone.utc)
        result = is_market_open(after_close)
        assert result is False, "Market should be closed at 4:00:01 PM ET"

    def test_weekend_saturday_closed(self):
        """Test that Saturday is closed."""
        from shared.utils.time import is_market_open
        # Saturday 12:00 PM Eastern = 5:00 PM UTC
        saturday = datetime(2024, 1, 6, 17, 0, 0, tzinfo=timezone.utc)
        result = is_market_open(saturday)
        assert result is False, "Market should be closed on Saturday"

    def test_weekend_sunday_closed(self):
        """Test that Sunday is closed."""
        from shared.utils.time import is_market_open
        # Sunday 12:00 PM Eastern = 5:00 PM UTC
        sunday = datetime(2024, 1, 7, 17, 0, 0, tzinfo=timezone.utc)
        result = is_market_open(sunday)
        assert result is False, "Market should be closed on Sunday"


class TestGetSettlementDate:
    """Tests for bug F8: Settlement date doesn't skip weekends."""

    def test_friday_t2_settles_tuesday(self):
        """BUG F8: Friday T+2 should settle Tuesday, not Sunday."""
        from shared.utils.time import get_settlement_date
        friday = datetime(2024, 1, 5, 12, 0, 0)  # Friday Jan 5
        settlement = get_settlement_date(friday, settlement_days=2)
        
        # Should return Tuesday Jan 9 (skip Sat/Sun)
        assert settlement.weekday() < 5, "Settlement should not be on weekend"
        assert settlement.day == 9, "Friday T+2 should settle Tuesday Jan 9"

    def test_thursday_t2_settles_monday(self):
        """Thursday T+2 should settle Monday."""
        from shared.utils.time import get_settlement_date
        thursday = datetime(2024, 1, 4, 12, 0, 0)  # Thursday Jan 4
        settlement = get_settlement_date(thursday, settlement_days=2)
        
        # Should return Monday Jan 8
        assert settlement.weekday() < 5, "Settlement should not be on weekend"

    def test_wednesday_t2_settles_friday(self):
        """Wednesday T+2 should settle Friday (no weekend skip needed)."""
        from shared.utils.time import get_settlement_date
        wednesday = datetime(2024, 1, 3, 12, 0, 0)  # Wednesday Jan 3
        settlement = get_settlement_date(wednesday, settlement_days=2)
        # This should work correctly: Wed + 2 = Fri
        assert settlement.weekday() == 4, "Wednesday T+2 should settle Friday"

    def test_t3_settlement_skips_weekend(self):
        """T+3 from Thursday should skip weekend."""
        from shared.utils.time import get_settlement_date
        thursday = datetime(2024, 1, 4, 12, 0, 0)  # Thursday Jan 4
        settlement = get_settlement_date(thursday, settlement_days=3)
        
        # Should return Tuesday Jan 9
        assert settlement.weekday() < 5, "T+3 settlement should not be on weekend"


class TestParseTimestamp:
    """Tests for bug B8: Timezone handling in parse_timestamp()."""

    def test_unix_timestamp_has_timezone(self):
        """BUG B8: Unix timestamp should return timezone-aware datetime."""
        from shared.utils.time import parse_timestamp
        unix_ts = 1704672000  # 2024-01-08 00:00:00 UTC
        result = parse_timestamp(unix_ts)
        
        assert result.tzinfo is not None, "Unix timestamp should return timezone-aware datetime"

    def test_string_timestamp_has_timezone(self):
        """BUG B8: String timestamp without TZ should default to UTC."""
        from shared.utils.time import parse_timestamp
        ts_string = "2024-01-08 12:00:00"
        result = parse_timestamp(ts_string, assume_utc=True)
        
        assert result.tzinfo is not None, "String timestamp should have timezone when assume_utc=True"

    def test_datetime_without_tz_preserved(self):
        """BUG B8: Naive datetime passed in should get UTC timezone added."""
        from shared.utils.time import parse_timestamp
        naive_dt = datetime(2024, 1, 8, 12, 0, 0)
        result = parse_timestamp(naive_dt, assume_utc=True)
        
        assert result.tzinfo is not None, "Naive datetime should get timezone added"


class TestRateLimiter:
    """Tests for bug I4: Rate limiter bypass via header."""

    def test_internal_header_bypasses_rate_limit(self):
        """BUG I4: X-Internal-Request header should NOT bypass rate limiting."""
        from shared.utils.time import RateLimiter
        limiter = RateLimiter(rate=1.0, capacity=1.0)

        # Exhaust the rate limit
        limiter.acquire(tokens=1)

        # Should NOT be able to bypass with header
        headers = {'X-Internal-Request': 'true'}
        result = limiter.acquire(tokens=1, headers=headers)
        
        assert result is False, "X-Internal-Request header should NOT bypass rate limit"

    def test_rate_limit_enforced_without_header(self):
        """Normal rate limiting should work without headers."""
        from shared.utils.time import RateLimiter
        limiter = RateLimiter(rate=1.0, capacity=1.0)

        # First acquire should succeed
        assert limiter.acquire(tokens=1) is True

        # Second immediate acquire should fail (no tokens left)
        assert limiter.acquire(tokens=1) is False

    def test_rate_limit_recovers_over_time(self):
        """Rate limit should recover based on rate."""
        from shared.utils.time import RateLimiter
        limiter = RateLimiter(rate=10.0, capacity=1.0)  # 10 tokens/sec

        # Exhaust
        limiter.acquire(tokens=1)

        # Wait for recovery (0.2 sec = 2 tokens at 10/sec)
        time.sleep(0.2)

        # Should have recovered
        assert limiter.acquire(tokens=1) is True

    def test_other_headers_dont_bypass(self):
        """Other headers should not bypass rate limiting."""
        from shared.utils.time import RateLimiter
        limiter = RateLimiter(rate=1.0, capacity=1.0)
        limiter.acquire(tokens=1)

        headers = {'X-Some-Other-Header': 'true'}
        result = limiter.acquire(tokens=1, headers=headers)
        assert result is False, "Random headers should not bypass rate limit"


# =============================================================================
# Tests for shared/clients/base.py bugs
# =============================================================================

class TestCircuitBreaker:
    """Tests for bug C1: Circuit breaker threshold check."""

    def test_circuit_opens_at_exactly_threshold(self):
        """BUG C1: Circuit should open at exactly failure_threshold failures."""
        from shared.clients.base import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=5)

        # Record exactly 5 failures
        for i in range(5):
            cb.record_failure()

        
        assert cb.state == CircuitState.OPEN, \
            f"Circuit should be OPEN after exactly {cb.failure_threshold} failures, got {cb.state}"

    def test_circuit_opens_above_threshold(self):
        """Circuit should definitely open above threshold."""
        from shared.clients.base import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=5)

        # Record 6 failures (above threshold)
        for _ in range(6):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_circuit_stays_closed_below_threshold(self):
        """Circuit should stay closed below threshold."""
        from shared.clients.base import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=5)

        # Record 4 failures (below threshold)
        for _ in range(4):
            cb.record_failure()

        assert cb.state == CircuitState.CLOSED

    def test_success_resets_failure_count(self):
        """Success should reset failure count."""
        from shared.clients.base import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=5)

        # Record 4 failures
        for _ in range(4):
            cb.record_failure()

        # Record success
        cb.record_success()

        # Record 4 more failures - should not open (count reset)
        for _ in range(4):
            cb.record_failure()

        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self):
        """Circuit should go to half-open after recovery timeout."""
        from shared.clients.base import CircuitBreaker, CircuitState
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=0.1)

        # Open the circuit
        for _ in range(6):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)

        # Check if can execute (triggers half-open)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN


# =============================================================================
# Tests for shared/utils/serialization.py bugs
# =============================================================================

class TestEventEncoder:
    """Tests for bug F1: Decimal to float precision loss."""

    def test_decimal_precision_lost_in_json(self):
        """BUG F1: Decimal to float conversion loses precision."""
        from shared.utils.serialization import EventEncoder
        import json

        encoder = EventEncoder()

        # High precision decimal
        value = Decimal("150.12345678901234567890")
        encoded = encoder.default(value)

        
        # The encoded value should preserve full precision
        back_to_decimal = Decimal(str(encoded))
        assert back_to_decimal == value, \
            f"Precision lost: {value} -> {encoded} -> {back_to_decimal}"

    def test_datetime_no_timezone_in_json(self):
        """BUG B8: Datetime serialization should preserve timezone."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()

        # Timezone-aware datetime
        dt_utc = datetime(2024, 1, 8, 12, 0, 0, tzinfo=timezone.utc)
        encoded = encoder.default(dt_utc)

        # Should contain timezone info
        assert '+00:00' in encoded or 'Z' in encoded, \
            f"Timezone not preserved in encoded datetime: {encoded}"


class TestSerializeEvent:
    """Tests for serialization bugs."""

    def test_pickle_format_insecure(self):
        """BUG I3: Pickle format should not be available (insecure)."""
        from shared.utils.serialization import serialize_event, deserialize_event

        class FakeEvent:
            event_type = "test"
            def to_dict(self):
                return {"type": "test"}

        event = FakeEvent()

        
        # Should raise an error or not support pickle at all
        try:
            serialized = serialize_event(event, format="pickle")
            # If we get here, pickle is supported (which is the bug)
            # Deserializing pickle from untrusted source is dangerous
            assert False, "Pickle format should not be supported (security vulnerability)"
        except ValueError:
            pass  # This would be correct behavior (pickle not supported)

    def test_decimal_precision_in_event(self):
        """BUG F1: Event serialization should preserve Decimal precision."""
        from shared.utils.serialization import encode_decimal, decode_decimal

        # High precision value
        original = Decimal("0.123456789012345678901234567890")

        # Encode with default precision (8 decimal places)
        encoded = encode_decimal(original, precision=8)
        decoded = decode_decimal(encoded)

        
        assert decoded == original, \
            f"Precision lost in encode/decode: {original} -> {encoded} -> {decoded}"


class TestDecodeDecimal:
    """Tests for decimal handling."""

    def test_large_decimal_precision(self):
        """Test that large decimals maintain precision."""
        from shared.utils.serialization import encode_decimal

        # Very large value
        large = Decimal("999999999999.12345678")
        encoded = encode_decimal(large, precision=8)

        # Should not overflow or lose precision
        assert "999999999999" in encoded


# =============================================================================
# Tests for shared/events/base.py bugs
# =============================================================================

class TestBaseEvent:
    """Tests for event base class bugs."""

    def test_event_timestamp_has_timezone(self):
        """BUG B8: Event timestamp should be timezone-aware."""
        from shared.events.base import BaseEvent

        # Create a mock event
        class TestEvent(BaseEvent):
            event_type: str = "test_event"
            aggregate_id: str = "agg-1"
            aggregate_type: str = "Test"

        event = TestEvent()

        
        assert event.timestamp.tzinfo is not None, \
            "Event timestamp should be timezone-aware (use datetime.now(timezone.utc))"

    def test_event_from_dict_handles_missing_fields(self):
        """BUG B5: from_dict should handle missing fields from old versions."""
        from shared.events.base import BaseEvent

        # Old version data missing new fields
        old_data = {
            "event_id": "550e8400-e29b-41d4-a716-446655440000",
            "event_type": "order_created",
            "timestamp": "2024-01-08T12:00:00",
            "aggregate_id": "order-1",
            "aggregate_type": "Order",
            # Missing: version, correlation_id, causation_id, metadata
        }

        
        try:
            event = BaseEvent.from_dict(old_data)
            # If we get here, check that defaults were applied
            assert hasattr(event, 'version')
            assert hasattr(event, 'metadata')
        except Exception as e:
            pytest.fail(f"from_dict should handle missing fields: {e}")


# =============================================================================
# Additional integration-style tests for shared modules
# =============================================================================

class TestSharedModuleIntegration:
    """Integration tests combining multiple shared modules."""

    def test_time_utilities_timezone_consistency(self):
        """All time utilities should return timezone-aware datetimes."""
        from shared.utils.time import utc_now, parse_timestamp

        now = utc_now()
        assert now.tzinfo is not None, "utc_now() should return timezone-aware datetime"

        # Parse the result
        parsed = parse_timestamp(now.isoformat())
        assert parsed.tzinfo is not None, "parse_timestamp should preserve timezone"

    def test_circuit_breaker_with_rate_limiter(self):
        """Test circuit breaker and rate limiter together."""
        from shared.clients.base import CircuitBreaker, CircuitState
        from shared.utils.time import RateLimiter

        cb = CircuitBreaker(failure_threshold=3)
        limiter = RateLimiter(rate=10.0, capacity=5.0)

        # Simulate failures with rate limiting
        for i in range(3):
            if limiter.acquire():
                cb.record_failure()

        
        assert cb.state == CircuitState.OPEN, \
            f"Circuit should be OPEN after 3 failures (threshold=3), got {cb.state}"


# =============================================================================
# Stress tests - multiple iterations to amplify bug detection
# =============================================================================

class TestMarketHoursStress:
    """Stress tests for market hours edge cases."""

    def test_market_close_boundary_multiple_days(self):
        """BUG F5: Test market close for multiple weekdays."""
        from shared.utils.time import is_market_open

        # Test each weekday at exactly 4:00 PM ET
        weekdays = [
            datetime(2024, 1, 8, 21, 0, 0, tzinfo=timezone.utc),   # Monday
            datetime(2024, 1, 9, 21, 0, 0, tzinfo=timezone.utc),   # Tuesday
            datetime(2024, 1, 10, 21, 0, 0, tzinfo=timezone.utc),  # Wednesday
            datetime(2024, 1, 11, 21, 0, 0, tzinfo=timezone.utc),  # Thursday
            datetime(2024, 1, 12, 21, 0, 0, tzinfo=timezone.utc),  # Friday
        ]

        for close_time in weekdays:
            result = is_market_open(close_time)
            assert result is False, f"Market should be closed at 4:00 PM on {close_time.strftime('%A')}"

    def test_market_open_boundary_multiple_days(self):
        """Test market open for multiple weekdays."""
        from shared.utils.time import is_market_open

        # Test each weekday at exactly 9:30 AM ET (2:30 PM UTC)
        for day in range(8, 13):  # Mon-Fri
            open_time = datetime(2024, 1, day, 14, 30, 0, tzinfo=timezone.utc)
            result = is_market_open(open_time)
            assert result is True, f"Market should be open at 9:30 AM on day {day}"


class TestSettlementStress:
    """Stress tests for settlement date calculations."""

    def test_settlement_all_weekdays(self):
        """BUG F8: Test T+2 settlement for all weekdays."""
        from shared.utils.time import get_settlement_date

        test_cases = [
            # (trade_day, expected_settlement_weekday)
            (datetime(2024, 1, 1, 12, 0), 2),   # Mon -> Wed (no weekend)
            (datetime(2024, 1, 2, 12, 0), 3),   # Tue -> Thu (no weekend)
            (datetime(2024, 1, 3, 12, 0), 4),   # Wed -> Fri (no weekend)
            (datetime(2024, 1, 4, 12, 0), 0),   # Thu -> Mon (skip weekend)
            (datetime(2024, 1, 5, 12, 0), 1),   # Fri -> Tue (skip weekend)
        ]

        for trade_date, expected_weekday in test_cases:
            settlement = get_settlement_date(trade_date, settlement_days=2)
            actual_weekday = settlement.weekday()
            assert actual_weekday == expected_weekday, \
                f"Trade on {trade_date.strftime('%A')} should settle on weekday {expected_weekday}, got {actual_weekday}"


class TestCircuitBreakerStress:
    """Stress tests for circuit breaker thresholds."""

    def test_circuit_threshold_boundaries(self):
        """BUG C1: Test circuit breaker at various thresholds."""
        from shared.clients.base import CircuitBreaker, CircuitState

        for threshold in [1, 2, 3, 5, 10]:
            cb = CircuitBreaker(failure_threshold=threshold)

            # Record exactly threshold failures
            for _ in range(threshold):
                cb.record_failure()

            assert cb.state == CircuitState.OPEN, \
                f"Circuit should OPEN at exactly {threshold} failures"

    def test_circuit_many_failures(self):
        """Test circuit with many failures."""
        from shared.clients.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=5)

        for i in range(100):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN


class TestRateLimiterStress:
    """Stress tests for rate limiter."""

    def test_rate_limit_header_bypass_multiple(self):
        """BUG I4: Header bypass should not work on multiple attempts."""
        from shared.utils.time import RateLimiter

        limiter = RateLimiter(rate=1.0, capacity=1.0)
        limiter.acquire()  # Exhaust

        bypass_headers = {'X-Internal-Request': 'true'}

        # Try 10 times with bypass header
        bypasses = 0
        for _ in range(10):
            if limiter.acquire(headers=bypass_headers):
                bypasses += 1

        
        assert bypasses == 0, f"Header should not bypass rate limit, but {bypasses} requests bypassed"


class TestDecimalPrecisionStress:
    """Stress tests for decimal precision."""

    def test_decimal_precision_many_values(self):
        """BUG F1: Test precision loss across many decimal values."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()
        precision_lost = 0

        for i in range(100):
            # Create high-precision decimal
            value = Decimal(f"1.{''.join(str(i % 10) for _ in range(20))}")
            encoded = encoder.default(value)
            back = Decimal(str(encoded))

            if back != value:
                precision_lost += 1

        assert precision_lost == 0, f"Lost precision in {precision_lost} of 100 decimal values"

    def test_decimal_multiplication_precision(self):
        """BUG F1: Test precision in multiplication."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()

        # Simulate trading calculation
        price = Decimal("150.123456789")
        quantity = Decimal("100.00000001")
        expected = price * quantity

        # Encode both values
        encoded_price = encoder.default(price)
        encoded_qty = encoder.default(quantity)

        # Calculate with encoded values (floats)
        float_result = encoded_price * encoded_qty
        float_as_decimal = Decimal(str(float_result))

        # Should match original
        assert abs(float_as_decimal - expected) < Decimal("0.000001"), \
            f"Precision lost: expected {expected}, got {float_as_decimal}"


class TestTimestampStress:
    """Stress tests for timestamp handling."""

    def test_parse_many_timestamps(self):
        """BUG B8: Parse many timestamps, all should have timezone."""
        from shared.utils.time import parse_timestamp

        no_tz_count = 0

        for i in range(50):
            # Unix timestamp
            ts = 1704672000 + i * 3600
            result = parse_timestamp(ts)
            if result.tzinfo is None:
                no_tz_count += 1

        assert no_tz_count == 0, f"{no_tz_count} of 50 timestamps missing timezone"

    def test_parse_various_formats(self):
        """BUG B8: All parsed timestamps should have timezone."""
        from shared.utils.time import parse_timestamp

        formats = [
            1704672000,  # Unix
            1704672000.5,  # Unix with ms
            "2024-01-08T12:00:00",
            "2024-01-08 12:00:00",
            "2024-01-08T12:00:00.123456",
        ]

        for ts in formats:
            result = parse_timestamp(ts, assume_utc=True)
            assert result.tzinfo is not None, f"Format {ts} should have timezone"


class TestEventTimestampStress:
    """Stress tests for event timestamps."""

    def test_many_events_have_timezone(self):
        """BUG B8: All events should have timezone-aware timestamps."""
        from shared.events.base import BaseEvent

        class TestEvent(BaseEvent):
            event_type: str = "test"
            aggregate_id: str = "agg"
            aggregate_type: str = "Test"

        no_tz_count = 0
        for _ in range(20):
            event = TestEvent()
            if event.timestamp.tzinfo is None:
                no_tz_count += 1

        assert no_tz_count == 0, f"{no_tz_count} of 20 events missing timezone"


# =============================================================================
# Auth client tests (local logic only, no HTTP)
# =============================================================================

class TestAuthClientLocal:
    """Tests for auth client local logic bugs."""

    def test_validate_token_missing_claims(self):
        """BUG E1: validate_token should return all claims."""
        import jwt
        from shared.clients.auth import AuthClient

        client = AuthClient()

        # Create token with full claims
        full_claims = {
            "sub": "user-123",
            "exp": int(time.time()) + 3600,
            "roles": ["admin", "trader"],
            "permissions": ["trade.execute", "trade.view"],
            "tenant_id": "tenant-456",
        }
        token = jwt.encode(full_claims, client.jwt_secret, algorithm="HS256")

        # Validate - should return all claims
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(
            client.validate_token(token)
        )

        
        assert "roles" in result, "validate_token should include 'roles' claim"
        assert "permissions" in result, "validate_token should include 'permissions' claim"
        assert "tenant_id" in result, "validate_token should include 'tenant_id' claim"


# =============================================================================
# Matrix stress tests - generate many test cases
# =============================================================================

class TestMarketHoursMatrix:
    """Matrix of market hours tests across time boundaries."""

    @pytest.mark.parametrize("minute", range(0, 60, 5))
    def test_market_close_hour_4pm(self, minute):
        """BUG F5: Test all minutes in the 4 PM hour."""
        from shared.utils.time import is_market_open

        # 4:XX PM Eastern = 9:XX PM UTC
        test_time = datetime(2024, 1, 8, 21, minute, 0, tzinfo=timezone.utc)
        result = is_market_open(test_time)

        # All times at or after 4:00 PM should be closed
        assert result is False, f"4:{minute:02d} PM should be closed"

    @pytest.mark.parametrize("minute", [0, 15, 30, 45, 59])
    def test_pre_market_hours(self, minute):
        """Test pre-market hours (before 9:30 AM)."""
        from shared.utils.time import is_market_open

        # 8:XX AM Eastern = 1:XX PM UTC
        test_time = datetime(2024, 1, 8, 13, minute, 0, tzinfo=timezone.utc)
        result = is_market_open(test_time)
        assert result is False, f"8:{minute:02d} AM should be closed (pre-market)"


class TestSettlementMatrix:
    """Matrix of settlement date tests."""

    @pytest.mark.parametrize("trade_day", range(1, 8))  # Jan 1-7, 2024
    def test_t2_settlement_no_weekend(self, trade_day):
        """BUG F8: T+2 should never land on weekend."""
        from shared.utils.time import get_settlement_date

        trade_date = datetime(2024, 1, trade_day, 12, 0, 0)
        settlement = get_settlement_date(trade_date, settlement_days=2)

        # Settlement should never be Sat (5) or Sun (6)
        assert settlement.weekday() < 5, \
            f"T+2 from Jan {trade_day} should not settle on weekend (got weekday {settlement.weekday()})"

    @pytest.mark.parametrize("days", [1, 2, 3, 5, 7])
    def test_various_settlement_periods(self, days):
        """BUG F8: Various T+N should skip weekends."""
        from shared.utils.time import get_settlement_date

        # Friday trade
        friday = datetime(2024, 1, 5, 12, 0, 0)
        settlement = get_settlement_date(friday, settlement_days=days)

        assert settlement.weekday() < 5, \
            f"T+{days} from Friday should not settle on weekend"


class TestCircuitBreakerMatrix:
    """Matrix of circuit breaker tests."""

    @pytest.mark.parametrize("threshold", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    def test_exact_threshold_opens_circuit(self, threshold):
        """BUG C1: Circuit should open at exactly threshold failures."""
        from shared.clients.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=threshold)

        for _ in range(threshold):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN, \
            f"Circuit should be OPEN at exactly {threshold} failures"

    @pytest.mark.parametrize("threshold", [1, 2, 3, 4, 5])
    def test_one_below_threshold_stays_closed(self, threshold):
        """Circuit should stay closed at threshold - 1."""
        from shared.clients.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=threshold)

        for _ in range(threshold - 1):
            cb.record_failure()

        assert cb.state == CircuitState.CLOSED, \
            f"Circuit should be CLOSED at {threshold - 1} failures (threshold={threshold})"


class TestRateLimiterMatrix:
    """Matrix of rate limiter tests."""

    @pytest.mark.parametrize("capacity", [1, 2, 5, 10])
    def test_capacity_respected(self, capacity):
        """Rate limiter should respect capacity."""
        from shared.utils.time import RateLimiter

        limiter = RateLimiter(rate=1.0, capacity=float(capacity))

        # Should be able to acquire exactly capacity tokens
        for i in range(capacity):
            assert limiter.acquire() is True, f"Should acquire token {i+1} of {capacity}"

        # Next one should fail
        assert limiter.acquire() is False, "Should fail after capacity exhausted"

    @pytest.mark.parametrize("header_value", ["true", "True", "TRUE", "1", "yes"])
    def test_header_bypass_variations(self, header_value):
        """BUG I4: No header value should bypass rate limiting."""
        from shared.utils.time import RateLimiter

        limiter = RateLimiter(rate=1.0, capacity=1.0)
        limiter.acquire()  # Exhaust

        headers = {'X-Internal-Request': header_value}
        result = limiter.acquire(headers=headers)

        assert result is False, f"Header value '{header_value}' should not bypass rate limit"


class TestDecimalMatrix:
    """Matrix of decimal precision tests."""

    @pytest.mark.parametrize("decimals", [8, 10, 12, 15, 18, 20])
    def test_precision_at_various_scales(self, decimals):
        """BUG F1: Precision should be maintained at various scales."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()

        # Create value with specified decimal places
        value = Decimal("1." + "1" * decimals)
        encoded = encoder.default(value)
        back = Decimal(str(encoded))

        assert back == value, f"Lost precision at {decimals} decimal places"

    @pytest.mark.parametrize("value", [
        "0.00000001",
        "0.123456789012345678",
        "999999999999.99999999",
        "0.00000000000000001",
    ])
    def test_specific_precision_values(self, value):
        """BUG F1: Specific values should maintain precision."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()
        original = Decimal(value)
        encoded = encoder.default(original)
        back = Decimal(str(encoded))

        assert back == original, f"Value {value} lost precision"


class TestTimestampMatrix:
    """Matrix of timestamp parsing tests."""

    @pytest.mark.parametrize("unix_ts", [
        1704672000,      # 2024-01-08
        1704758400,      # 2024-01-09
        0,               # 1970-01-01
        2147483647,      # 2038-01-19 (Y2K38)
    ])
    def test_unix_timestamps_have_timezone(self, unix_ts):
        """BUG B8: All unix timestamps should return timezone-aware."""
        from shared.utils.time import parse_timestamp

        result = parse_timestamp(unix_ts)
        assert result.tzinfo is not None, f"Unix {unix_ts} should have timezone"

    @pytest.mark.parametrize("ts_string", [
        "2024-01-08T12:00:00",
        "2024-01-08 12:00:00",
        "2024-01-08T12:00:00.123456",
        "2024-01-08 12:00:00.123456",
    ])
    def test_string_timestamps_have_timezone(self, ts_string):
        """BUG B8: String timestamps should get timezone."""
        from shared.utils.time import parse_timestamp

        result = parse_timestamp(ts_string, assume_utc=True)
        assert result.tzinfo is not None, f"String '{ts_string}' should have timezone"


class TestEventEncoderMatrix:
    """Matrix of event encoder tests."""

    @pytest.mark.parametrize("price,qty", [
        ("100.12345678", "1000"),
        ("0.00000001", "100000000"),
        ("999999.99999999", "0.00000001"),
        ("150.123456789012345", "100.00000001"),
    ])
    def test_trading_calculations_precision(self, price, qty):
        """BUG F1: Trading calculations should not lose precision."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()

        p = Decimal(price)
        q = Decimal(qty)
        expected = p * q

        encoded_p = Decimal(str(encoder.default(p)))
        encoded_q = Decimal(str(encoder.default(q)))
        actual = encoded_p * encoded_q

        # Allow small tolerance due to float conversion
        diff = abs(actual - expected)
        assert diff < Decimal("0.01"), f"{price} * {qty}: expected {expected}, got {actual}, diff {diff}"


# =============================================================================
# Extended matrix tests to increase coverage
# =============================================================================

class TestExtendedCircuitBreaker:
    """Extended circuit breaker tests with various configurations."""

    @pytest.mark.parametrize("threshold,recovery", [
        (1, 0.1), (2, 0.1), (3, 0.1), (4, 0.1), (5, 0.1),
        (1, 0.5), (2, 0.5), (3, 0.5), (4, 0.5), (5, 0.5),
    ])
    def test_threshold_with_recovery(self, threshold, recovery):
        """BUG C1: Test circuit at threshold with various recovery times."""
        from shared.clients.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=threshold, recovery_timeout=recovery)

        for _ in range(threshold):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN, \
            f"Circuit should OPEN at {threshold} failures with recovery={recovery}"


class TestExtendedSettlement:
    """Extended settlement date tests."""

    @pytest.mark.parametrize("month,day", [
        (1, 4), (1, 5), (2, 1), (2, 2), (3, 1), (3, 8),
        (4, 4), (4, 5), (5, 2), (5, 3), (6, 6), (6, 7),
    ])
    def test_settlement_skip_weekend_various_months(self, month, day):
        """BUG F8: T+2 settlement across various months."""
        from shared.utils.time import get_settlement_date

        trade = datetime(2024, month, day, 12, 0, 0)
        if trade.weekday() >= 5:  # Skip if trade date is weekend
            pytest.skip("Trade date is weekend")

        settlement = get_settlement_date(trade, settlement_days=2)
        assert settlement.weekday() < 5, \
            f"Settlement from {month}/{day} should not be on weekend"


class TestExtendedTimestamp:
    """Extended timestamp tests."""

    @pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
    @pytest.mark.parametrize("month", [1, 6, 12])
    def test_timestamps_various_dates(self, year, month):
        """BUG B8: Timestamps from various dates should have timezone."""
        from shared.utils.time import parse_timestamp

        ts_str = f"{year}-{month:02d}-15T12:00:00"
        result = parse_timestamp(ts_str, assume_utc=True)
        assert result.tzinfo is not None, f"Timestamp {ts_str} should have timezone"


class TestExtendedDecimal:
    """Extended decimal precision tests."""

    @pytest.mark.parametrize("integer_part", ["0", "1", "100", "999999"])
    @pytest.mark.parametrize("decimal_part", ["123456789", "00000001", "99999999"])
    def test_decimal_combinations(self, integer_part, decimal_part):
        """BUG F1: Various decimal combinations should maintain precision."""
        from shared.utils.serialization import EventEncoder

        encoder = EventEncoder()
        value = Decimal(f"{integer_part}.{decimal_part}")
        encoded = encoder.default(value)
        back = Decimal(str(encoded))

        assert back == value, f"{integer_part}.{decimal_part} lost precision"


class TestExtendedEvent:
    """Extended event tests."""

    @pytest.mark.parametrize("event_count", range(1, 15))
    def test_event_batch_timestamps(self, event_count):
        """BUG B8: Batch of events should all have timezone."""
        from shared.events.base import BaseEvent

        class BatchEvent(BaseEvent):
            event_type: str = "batch"
            aggregate_id: str = "agg"
            aggregate_type: str = "Batch"

        for i in range(event_count):
            event = BatchEvent()
            assert event.timestamp.tzinfo is not None, \
                f"Event {i+1} in batch of {event_count} should have timezone"


class TestExtendedRateLimiter:
    """Extended rate limiter tests."""

    @pytest.mark.parametrize("rate,capacity", [
        (1.0, 1.0), (1.0, 5.0), (10.0, 10.0),
        (0.5, 1.0), (2.0, 5.0), (5.0, 20.0),
    ])
    def test_bypass_header_various_configs(self, rate, capacity):
        """BUG I4: Header bypass should not work with any config."""
        from shared.utils.time import RateLimiter

        limiter = RateLimiter(rate=rate, capacity=capacity)

        # Exhaust capacity
        while limiter.acquire():
            pass

        # Try bypass
        headers = {'X-Internal-Request': 'true'}
        result = limiter.acquire(headers=headers)

        assert result is False, f"Bypass should not work with rate={rate}, capacity={capacity}"


class TestMarketHoursExtended:
    """Extended market hours tests."""

    @pytest.mark.parametrize("day_offset", range(7, 14))  # Second week of Jan
    def test_second_week_market_close(self, day_offset):
        """BUG F5: Market close edge case for second week."""
        from shared.utils.time import is_market_open

        test_date = datetime(2024, 1, day_offset, 21, 0, 0, tzinfo=timezone.utc)

        if test_date.weekday() < 5:  # Weekday
            result = is_market_open(test_date)
            assert result is False, f"Jan {day_offset} 4:00 PM should be closed"


class TestSerializationExtended:
    """Extended serialization tests."""

    @pytest.mark.parametrize("precision", [2, 4, 6, 8, 10, 12, 14, 16])
    def test_encode_decimal_precision(self, precision):
        """BUG F1: encode_decimal should preserve requested precision."""
        from shared.utils.serialization import encode_decimal, decode_decimal

        # Create value with more precision than requested
        extra_precision = "1" * (precision + 5)
        value = Decimal(f"0.{extra_precision}")

        encoded = encode_decimal(value, precision=precision)
        decoded = decode_decimal(encoded)

        # Full precision should be preserved
        assert decoded == value, f"Precision {precision} should preserve full value"


# =============================================================================
# Additional matrix tests to increase coverage and failure detection
# =============================================================================

class TestTimestampParsingMatrix:
    """Matrix tests for timestamp parsing bugs."""

    @pytest.mark.parametrize("unix_ts", [0, 86400, 1000000000, 1700000000, 1800000000])
    def test_unix_timestamp_has_timezone(self, unix_ts):
        """BUG B8: Unix timestamps should return aware datetime."""
        from shared.utils.time import parse_timestamp

        result = parse_timestamp(unix_ts)
        assert result.tzinfo is not None, f"Unix {unix_ts} should be timezone-aware"

    @pytest.mark.parametrize("year", [2020, 2021, 2022, 2023, 2024, 2025])
    def test_strptime_formats_are_aware(self, year):
        """BUG B8: strptime formats should return aware datetimes."""
        from shared.utils.time import parse_timestamp

        ts_str = f"{year}-06-15 12:30:45"
        result = parse_timestamp(ts_str, assume_utc=True)
        assert result.tzinfo is not None, f"Year {year} string should be timezone-aware"


class TestMarketCloseMatrix:
    """Matrix tests for market close bugs."""

    @pytest.mark.parametrize("month", range(1, 13))
    def test_monthly_market_close_boundary(self, month):
        """BUG F5: Market close edge case for each month."""
        from shared.utils.time import is_market_open

        # First Monday of each month at 4:00 PM ET (9:00 PM UTC)
        # Approximate - just need a weekday
        day = 8 if month != 2 else 7  # Adjust for Feb
        test_date = datetime(2024, month, day, 21, 0, 0, tzinfo=timezone.utc)

        if test_date.weekday() < 5:  # Weekday
            result = is_market_open(test_date)
            assert result is False, f"Month {month} 4:00 PM should be closed"


class TestSettlementMatrix:
    """Matrix tests for settlement date bugs."""

    @pytest.mark.parametrize("trade_day", range(7))  # Each day of week
    def test_settlement_respects_weekends(self, trade_day):
        """BUG F8: Settlement should skip weekends."""
        from shared.utils.time import get_settlement_date

        # Start from a known Monday (Jan 8, 2024)
        base_date = datetime(2024, 1, 8) + timedelta(days=trade_day)
        result = get_settlement_date(base_date, settlement_days=2)

        # Settlement should never land on weekend
        assert result.weekday() < 5, f"Trade day {trade_day} settlement should not be weekend"


class TestRateLimiterBypassMatrix:
    """Matrix tests for rate limiter bypass bugs."""

    @pytest.mark.parametrize("header_value", ["true", "True", "TRUE", "1", "yes"])
    def test_bypass_header_variations(self, header_value):
        """BUG I4: None of these header values should bypass."""
        from shared.utils.time import RateLimiter

        limiter = RateLimiter(rate=1.0, capacity=1.0)
        limiter.tokens = 0  # Exhausted

        headers = {'X-Internal-Request': header_value}
        result = limiter.acquire(headers=headers)

        # Only 'true' exactly bypasses (that's the bug), but for proper behavior
        # no header should bypass rate limiting
        assert result is False, f"Header value '{header_value}' should not bypass"


class TestDecimalEncodingMatrix:
    """Matrix tests for decimal encoding bugs."""

    @pytest.mark.parametrize("digits", range(9, 20))
    def test_high_precision_decimal(self, digits):
        """BUG F1: High precision decimals should be preserved."""
        from shared.utils.serialization import encode_decimal, decode_decimal

        # Create decimal with exactly 'digits' decimal places
        decimal_str = "0." + "1" * digits
        value = Decimal(decimal_str)

        encoded = encode_decimal(value, precision=8)  # Default precision
        decoded = decode_decimal(encoded)

        assert decoded == value, f"{digits} digits should be preserved"


class TestEventTimestampMatrix:
    """Matrix tests for event timestamp bugs."""

    @pytest.mark.parametrize("hour", range(24))
    def test_hourly_timestamp_precision(self, hour):
        """BUG B8: Timestamps at each hour should preserve timezone."""
        from shared.events.base import BaseEvent

        ts = datetime(2024, 1, 15, hour, 30, 45, tzinfo=timezone.utc)
        event = BaseEvent(event_type="test", timestamp=ts)
        data = event.to_dict()

        # Parse back and verify timezone
        parsed = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
        assert parsed.tzinfo is not None, f"Hour {hour} timestamp should preserve tz"


class TestCircuitBreakerMatrix:
    """Matrix tests for circuit breaker bugs."""

    @pytest.mark.parametrize("threshold", [0.4, 0.5, 0.6, 0.7])
    def test_threshold_boundary_exact(self, threshold):
        """BUG C1: Circuit breaker threshold at exact boundary."""
        from shared.clients.base import CircuitBreaker

        breaker = CircuitBreaker(failure_threshold=threshold, reset_timeout=60)

        # Record failures to reach exactly threshold
        fail_count = int(threshold * 10)
        for _ in range(fail_count):
            breaker.record_failure()

        # Additional call that pushes just over
        success_count = 10 - fail_count
        for _ in range(success_count):
            breaker.record_success()

        # Should not be open if ratio is exactly at threshold
        
        breaker.record_failure()

        assert breaker.is_open is True, f"Should be open after exceeding {threshold}"
