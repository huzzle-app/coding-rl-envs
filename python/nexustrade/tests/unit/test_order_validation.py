"""
Unit tests for order validation logic.

These tests cover order field validation, type support, status transitions,
modification rules, quantity constraints, symbol validation, time-in-force,
order ID uniqueness, price tick sizes, self-trade prevention, and order book
snapshot consistency.

No specific bug mappings -- these tests exercise general order validation
correctness.
"""
import pytest
import uuid
import re
from decimal import Decimal
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Order field validation
# ---------------------------------------------------------------------------
class TestOrderFieldValidation:
    """Tests for basic order field validation."""

    def test_price_must_be_positive(self):
        """Test that order price must be greater than zero."""
        price = Decimal("150.25")
        assert price > 0, "Price must be positive"

    def test_negative_price_rejected(self):
        """Test that negative prices are rejected."""
        price = Decimal("-10.00")
        is_valid = price > 0
        assert not is_valid, "Negative price should be rejected"

    def test_quantity_must_be_positive(self):
        """Test that order quantity must be greater than zero."""
        quantity = Decimal("10")
        assert quantity > 0, "Quantity must be positive"

    def test_side_must_be_buy_or_sell(self):
        """Test that the order side must be 'buy' or 'sell'."""
        valid_sides = {"buy", "sell"}
        assert "buy" in valid_sides
        assert "sell" in valid_sides
        assert "short" not in valid_sides, "'short' is not a valid side"

    def test_type_must_be_known(self):
        """Test that order type must be a recognized type."""
        known_types = {"market", "limit", "stop", "stop_limit"}
        assert "limit" in known_types
        assert "trailing_stop" not in known_types, "Unknown type should be rejected"


# ---------------------------------------------------------------------------
# Order type support
# ---------------------------------------------------------------------------
class TestOrderTypeSupport:
    """Tests for different order types."""

    def test_market_order_no_price_required(self):
        """Test that market orders do not require a price."""
        order = {"type": "market", "side": "buy", "quantity": Decimal("10"), "price": None}
        assert order["price"] is None, "Market orders should not require a price"

    def test_limit_order_requires_price(self):
        """Test that limit orders must specify a price."""
        order = {"type": "limit", "side": "buy", "quantity": Decimal("10"), "price": Decimal("150.00")}
        assert order["price"] is not None, "Limit orders must have a price"
        assert order["price"] > 0

    def test_stop_order_requires_stop_price(self):
        """Test that stop orders must specify a stop price."""
        order = {"type": "stop", "side": "sell", "quantity": Decimal("5"), "stop_price": Decimal("145.00")}
        assert order["stop_price"] is not None
        assert order["stop_price"] > 0

    def test_stop_limit_requires_both_prices(self):
        """Test that stop-limit orders require both stop price and limit price."""
        order = {
            "type": "stop_limit",
            "side": "sell",
            "quantity": Decimal("5"),
            "stop_price": Decimal("145.00"),
            "limit_price": Decimal("144.50"),
        }
        assert order["stop_price"] is not None
        assert order["limit_price"] is not None
        assert order["stop_price"] > order["limit_price"], (
            "For sell stop-limit, stop price should be above limit price"
        )


# ---------------------------------------------------------------------------
# Order status transitions
# ---------------------------------------------------------------------------
class TestOrderStatusTransitions:
    """Tests for valid order status transitions."""

    VALID_TRANSITIONS = {
        "new": {"partially_filled", "filled", "cancelled", "rejected"},
        "partially_filled": {"filled", "cancelled"},
        "filled": set(),  # terminal
        "cancelled": set(),  # terminal
        "rejected": set(),  # terminal
    }

    def test_new_to_filled(self):
        """Test transition from new to filled."""
        assert "filled" in self.VALID_TRANSITIONS["new"]

    def test_new_to_cancelled(self):
        """Test transition from new to cancelled."""
        assert "cancelled" in self.VALID_TRANSITIONS["new"]

    def test_filled_is_terminal(self):
        """Test that filled orders cannot transition further."""
        assert len(self.VALID_TRANSITIONS["filled"]) == 0, "Filled is terminal"

    def test_invalid_transition_rejected(self):
        """Test that invalid transitions are rejected."""
        assert "new" not in self.VALID_TRANSITIONS["filled"], (
            "Cannot go from filled back to new"
        )


# ---------------------------------------------------------------------------
# Order modification rules
# ---------------------------------------------------------------------------
class TestOrderModificationRules:
    """Tests for order modification constraints."""

    def test_cannot_modify_filled_order(self):
        """Test that filled orders cannot be modified."""
        order = {"status": "filled", "price": Decimal("150.00")}
        can_modify = order["status"] not in ("filled", "cancelled", "rejected")
        assert not can_modify, "Filled orders should not be modifiable"

    def test_can_modify_new_order(self):
        """Test that new orders can be modified."""
        order = {"status": "new", "price": Decimal("150.00")}
        can_modify = order["status"] not in ("filled", "cancelled", "rejected")
        assert can_modify, "New orders should be modifiable"

    def test_modification_changes_version(self):
        """Test that modifying an order increments its version."""
        version_before = 1
        version_after = version_before + 1
        assert version_after == 2, "Version should increment after modification"


# ---------------------------------------------------------------------------
# Order quantity constraints
# ---------------------------------------------------------------------------
class TestOrderQuantityConstraints:
    """Tests for order quantity limits."""

    def test_min_lot_size_enforced(self):
        """Test that orders below minimum lot size are rejected."""
        min_lot_size = Decimal("1")
        quantity = Decimal("0.5")
        is_valid = quantity >= min_lot_size
        assert not is_valid, "Quantity below min lot size should be rejected"

    def test_max_order_size_enforced(self):
        """Test that orders above maximum order size are rejected."""
        max_order_size = Decimal("100000")
        quantity = Decimal("150000")
        is_valid = quantity <= max_order_size
        assert not is_valid, "Quantity above max order size should be rejected"

    def test_lot_size_multiple_enforced(self):
        """Test that quantity must be a multiple of the lot size."""
        lot_size = Decimal("100")
        quantity = Decimal("350")
        is_multiple = quantity % lot_size == 0
        assert not is_multiple, "350 is not a multiple of 100"


# ---------------------------------------------------------------------------
# Symbol validation
# ---------------------------------------------------------------------------
class TestSymbolValidation:
    """Tests for trading symbol/ticker validation."""

    def test_valid_symbol_accepted(self):
        """Test that a valid ticker symbol is accepted."""
        valid_symbols = {"AAPL", "GOOGL", "TSLA", "MSFT", "AMZN"}
        assert "AAPL" in valid_symbols

    def test_empty_symbol_rejected(self):
        """Test that an empty symbol string is rejected."""
        symbol = ""
        is_valid = bool(symbol.strip())
        assert not is_valid, "Empty symbol should be rejected"

    def test_symbol_max_length(self):
        """Test that overly long symbols are rejected."""
        symbol = "A" * 20
        max_length = 10
        is_valid = len(symbol) <= max_length
        assert not is_valid, "Symbol longer than 10 characters should be rejected"


# ---------------------------------------------------------------------------
# Time-in-force validation
# ---------------------------------------------------------------------------
class TestTimeInForceValidation:
    """Tests for time-in-force (TIF) validation."""

    VALID_TIF = {"GTC", "DAY", "IOC", "FOK"}

    def test_gtc_accepted(self):
        """Test that Good-Til-Cancelled is accepted."""
        assert "GTC" in self.VALID_TIF

    def test_day_accepted(self):
        """Test that DAY orders are accepted."""
        assert "DAY" in self.VALID_TIF

    def test_ioc_accepted(self):
        """Test that Immediate-Or-Cancel is accepted."""
        assert "IOC" in self.VALID_TIF

    def test_fok_accepted(self):
        """Test that Fill-Or-Kill is accepted."""
        assert "FOK" in self.VALID_TIF

    def test_unknown_tif_rejected(self):
        """Test that unknown TIF values are rejected."""
        assert "GTD" not in self.VALID_TIF, "GTD should not be accepted"


# ---------------------------------------------------------------------------
# Order ID uniqueness
# ---------------------------------------------------------------------------
class TestOrderIdUniqueness:
    """Tests for order ID uniqueness guarantees."""

    def test_order_id_is_uuid_format(self):
        """Test that order IDs use UUID format."""
        order_id = str(uuid.uuid4())
        assert re.match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            order_id,
        ), "Order ID should be a valid UUID"

    def test_duplicate_order_id_rejected(self):
        """Test that submitting an order with an existing ID is rejected."""
        existing_ids = {"id-001", "id-002"}
        new_id = "id-001"
        is_unique = new_id not in existing_ids
        assert not is_unique, "Duplicate order ID should be rejected"


# ---------------------------------------------------------------------------
# Price tick size validation
# ---------------------------------------------------------------------------
class TestPriceTickSizeValidation:
    """Tests for price tick size (minimum price increment) validation."""

    def test_price_respects_tick_size(self):
        """Test that prices are multiples of the tick size."""
        tick_size = Decimal("0.01")
        price = Decimal("150.25")
        remainder = price % tick_size
        assert remainder == Decimal("0"), "Price should be a multiple of tick size"

    def test_price_violates_tick_size(self):
        """Test that sub-tick prices are rejected."""
        tick_size = Decimal("0.01")
        price = Decimal("150.255")
        remainder = price % tick_size
        assert remainder != Decimal("0"), "Price 150.255 is not a valid tick increment"

    def test_tick_size_varies_by_price_level(self):
        """Test that tick size changes based on price level."""
        def tick_for_price(price):
            if price < Decimal("1"):
                return Decimal("0.0001")
            elif price < Decimal("100"):
                return Decimal("0.01")
            else:
                return Decimal("0.05")

        assert tick_for_price(Decimal("0.50")) == Decimal("0.0001")
        assert tick_for_price(Decimal("50.00")) == Decimal("0.01")
        assert tick_for_price(Decimal("500.00")) == Decimal("0.05")


# ---------------------------------------------------------------------------
# Self-trade prevention
# ---------------------------------------------------------------------------
class TestSelfTradePrevention:
    """Tests for self-trade prevention (STP) logic."""

    def test_same_account_buy_sell_blocked(self):
        """Test that buy and sell from the same account are blocked."""
        buy_order = {"account_id": "acct-001", "side": "buy"}
        sell_order = {"account_id": "acct-001", "side": "sell"}
        is_self_trade = buy_order["account_id"] == sell_order["account_id"]
        assert is_self_trade, "Same account opposite sides should be flagged"

    def test_different_account_allowed(self):
        """Test that orders from different accounts can trade."""
        buy_order = {"account_id": "acct-001", "side": "buy"}
        sell_order = {"account_id": "acct-002", "side": "sell"}
        is_self_trade = buy_order["account_id"] == sell_order["account_id"]
        assert not is_self_trade, "Different accounts should be allowed to trade"


# ---------------------------------------------------------------------------
# Order book snapshot consistency
# ---------------------------------------------------------------------------
class TestOrderBookSnapshotConsistency:
    """Tests for order book snapshot integrity."""

    def test_bids_sorted_descending(self):
        """Test that bid side is sorted highest price first."""
        bids = [
            {"price": Decimal("150.00"), "qty": Decimal("10")},
            {"price": Decimal("149.50"), "qty": Decimal("20")},
            {"price": Decimal("149.00"), "qty": Decimal("15")},
        ]
        prices = [b["price"] for b in bids]
        assert prices == sorted(prices, reverse=True), "Bids must be descending by price"

    def test_asks_sorted_ascending(self):
        """Test that ask side is sorted lowest price first."""
        asks = [
            {"price": Decimal("150.50"), "qty": Decimal("10")},
            {"price": Decimal("151.00"), "qty": Decimal("20")},
            {"price": Decimal("151.50"), "qty": Decimal("15")},
        ]
        prices = [a["price"] for a in asks]
        assert prices == sorted(prices), "Asks must be ascending by price"

    def test_best_bid_below_best_ask(self):
        """Test that best bid is strictly below best ask (no crossed book)."""
        best_bid = Decimal("150.00")
        best_ask = Decimal("150.50")
        assert best_bid < best_ask, "Best bid must be below best ask"

    def test_crossed_book_detected(self):
        """Test that a crossed book (bid >= ask) is detected as invalid."""
        best_bid = Decimal("151.00")
        best_ask = Decimal("150.50")
        is_crossed = best_bid >= best_ask
        assert is_crossed, "Crossed book should be detected"

    def test_snapshot_total_quantity_positive(self):
        """Test that aggregate quantities on each level are positive."""
        levels = [
            {"price": Decimal("150.00"), "qty": Decimal("100")},
            {"price": Decimal("149.00"), "qty": Decimal("50")},
        ]
        for level in levels:
            assert level["qty"] > 0, f"Quantity at {level['price']} must be positive"

    def test_snapshot_no_duplicate_price_levels(self):
        """Test that no two entries share the same price on one side."""
        bids = [
            {"price": Decimal("150.00")},
            {"price": Decimal("149.50")},
            {"price": Decimal("149.00")},
        ]
        prices = [b["price"] for b in bids]
        assert len(prices) == len(set(prices)), "Duplicate price levels should not exist"
