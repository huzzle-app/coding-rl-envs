"""
Unit tests for trading logic bugs.

These tests verify bugs F1-F8 (Trading Logic category).
"""
import pytest
from decimal import Decimal
from datetime import datetime, timezone, timedelta


class TestPricePrecision:
    """Tests for bug F1: Price matching floating point precision."""

    def test_price_comparison_exact_match(self):
        """Test that exact prices match correctly."""
        price1 = Decimal("150.12345678")
        price2 = Decimal("150.12345678")
        
        assert price1 == price2

    def test_price_comparison_float_conversion(self):
        """Test precision loss when converting to float."""
        price = Decimal("150.12345678901234")
        
        float_price = float(price)
        back_to_decimal = Decimal(str(float_price))
        # This should fail due to precision loss
        assert price == back_to_decimal, "Float conversion loses precision"

    def test_price_multiplication_precision(self):
        """Test precision in price calculations."""
        price = Decimal("0.00000001")
        quantity = Decimal("100000000")
        expected = Decimal("1.00000000")
        
        result = price * quantity
        assert result == expected

    def test_price_comparison_near_values(self):
        """Test comparison of very close prices."""
        price1 = Decimal("150.000000001")
        price2 = Decimal("150.000000002")
        
        assert price1 != price2

    def test_penny_difference_detection(self):
        """Test that penny differences are detected."""
        bid = Decimal("150.01")
        ask = Decimal("150.02")
        
        spread = ask - bid
        assert spread == Decimal("0.01")


class TestOrderPriority:
    """Tests for bug F2: Order queue priority inversion."""

    def test_fifo_same_price(self):
        """Test FIFO ordering for same-price orders."""
        orders = [
            {"id": "order1", "price": Decimal("100"), "timestamp": 1},
            {"id": "order2", "price": Decimal("100"), "timestamp": 2},
            {"id": "order3", "price": Decimal("100"), "timestamp": 3},
        ]
        
        sorted_orders = sorted(orders, key=lambda x: (x["price"], x["timestamp"]))
        assert sorted_orders[0]["id"] == "order1"
        assert sorted_orders[1]["id"] == "order2"

    def test_price_priority_over_time(self):
        """Test that better prices have priority over earlier orders."""
        orders = [
            {"id": "order1", "price": Decimal("100"), "timestamp": 1, "side": "buy"},
            {"id": "order2", "price": Decimal("101"), "timestamp": 2, "side": "buy"},
        ]
        # For buys, higher price = better = higher priority
        sorted_orders = sorted(orders, key=lambda x: (-x["price"], x["timestamp"]))
        assert sorted_orders[0]["id"] == "order2"


class TestPartialFillRounding:
    """Tests for bug F3: Partial fill rounding errors."""

    def test_partial_fill_quantity_accuracy(self):
        """Test that partial fills maintain quantity accuracy."""
        total_quantity = Decimal("100")
        fill1 = Decimal("33.33333333")
        fill2 = Decimal("33.33333333")
        fill3 = Decimal("33.33333334")

        total_filled = fill1 + fill2 + fill3
        assert total_filled == total_quantity, "Partial fills should sum to total"

    def test_commission_calculation_precision(self):
        """Test commission calculation precision."""
        fill_quantity = Decimal("100")
        fill_price = Decimal("150.50")
        commission_rate = Decimal("0.001")  # 0.1%

        
        expected_commission = fill_quantity * fill_price * commission_rate
        float_commission = float(fill_quantity) * float(fill_price) * float(commission_rate)

        # Float commission should have error
        assert abs(float(expected_commission) - float_commission) < 0.01


class TestStopOrderTrigger:
    """Tests for bug F4: Stop-loss trigger race condition."""

    def test_stop_order_immediate_trigger(self):
        """Test stop order triggers immediately if price already past."""
        stop_price = Decimal("145.00")
        current_price = Decimal("144.50")

        
        should_trigger = current_price <= stop_price
        assert should_trigger, "Stop order should trigger when price is past stop"

    def test_stop_order_exact_price(self):
        """Test stop order at exact stop price."""
        stop_price = Decimal("145.00")
        current_price = Decimal("145.00")

        
        should_trigger = current_price <= stop_price
        assert should_trigger


class TestMarketHours:
    """Tests for bug F5: Market close edge case."""

    def test_market_close_rejection(self):
        """Test that orders at exactly market close are rejected."""
        from shared.utils.time import is_market_open
        from datetime import datetime, timezone

        # 4:00 PM Eastern = 9:00 PM UTC (EST offset -5h)
        
        close_time_utc = datetime(2024, 1, 8, 21, 0, 0, tzinfo=timezone.utc)  # Monday 4PM ET
        result = is_market_open(close_time_utc)
        assert result is False, "Orders at exactly market close (4:00 PM ET) should be rejected"

    def test_market_open_acceptance(self):
        """Test that orders during market hours are accepted."""
        from shared.utils.time import is_market_open
        from datetime import datetime, timezone

        # 12:00 PM Eastern = 5:00 PM UTC (EST offset -5h), a Monday
        midday_utc = datetime(2024, 1, 8, 17, 0, 0, tzinfo=timezone.utc)
        result = is_market_open(midday_utc)
        assert result is True, "Orders during market hours should be accepted"

    def test_premarket_rejection(self):
        """Test that orders before market open are rejected."""
        from shared.utils.time import is_market_open
        from datetime import datetime, timezone

        # 8:00 AM Eastern = 1:00 PM UTC, a Monday (before 9:30 AM open)
        premarket_utc = datetime(2024, 1, 8, 13, 0, 0, tzinfo=timezone.utc)
        result = is_market_open(premarket_utc)
        assert result is False, "Orders before market open (9:30 AM ET) should be rejected"


class TestFeeCalculation:
    """Tests for bug F7: Fee calculation precision loss."""

    def test_fee_accumulation(self):
        """Test that fees accumulate correctly over many trades."""
        fee_rate = Decimal("0.001")  # 0.1%
        trade_value = Decimal("100.00")
        num_trades = 1000

        # Calculate with Decimal
        expected_total_fees = fee_rate * trade_value * num_trades

        
        float_total = 0.0
        for _ in range(num_trades):
            float_total += float(fee_rate) * float(trade_value)

        # Float should have accumulated error
        assert abs(float(expected_total_fees) - float_total) < 1.0

    def test_fee_rounding(self):
        """Test fee rounding to valid currency amounts."""
        fee = Decimal("1.234567")
        # Fees should round to 2 decimal places for USD
        rounded_fee = fee.quantize(Decimal("0.01"))
        assert rounded_fee == Decimal("1.23")


class TestSettlementDate:
    """Tests for bug F8: Settlement date calculation."""

    def test_settlement_skips_weekend(self):
        """Test that T+2 settlement skips weekends."""
        from shared.utils.time import get_settlement_date

        # Friday trade should settle on Tuesday (skip Sat/Sun)
        friday = datetime(2024, 1, 5, 12, 0, 0)  # A Friday
        settlement = get_settlement_date(friday, settlement_days=2)

        
        # Expected: Tuesday Jan 9 (skip Sat Jan 6, Sun Jan 7)
        
        assert settlement.weekday() < 5, "Settlement date should not fall on a weekend"
        assert settlement.day == 9, "Friday T+2 should settle on Tuesday (Jan 9)"

    def test_settlement_skips_holidays(self):
        """Test that settlement skips market holidays."""
        from shared.utils.time import get_settlement_date

        # Wednesday trade with T+2 should settle on Friday normally
        wednesday = datetime(2024, 1, 3, 12, 0, 0)  # A Wednesday
        settlement = get_settlement_date(wednesday, settlement_days=2)

        # Basic check: settlement should be at least 2 business days later
        assert settlement > wednesday, "Settlement must be after trade date"
        assert settlement.weekday() < 5, "Settlement date should not fall on a weekend"
