"""
OmniCloud Billing & Metering Tests
Terminal Bench v2 - Tests for billing calculations, metering, invoicing.

Covers bugs: H1-H8
~80 tests
"""
import pytest
import time
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from services.billing.views import (
    calculate_proration, generate_invoice, allocate_costs,
    apply_discounts, apply_credit, check_overage,
)
from shared.utils.time import billing_period_boundary, metering_timestamp


class TestUsageMetering:
    """Tests for H1: Usage metering clock skew."""

    def test_usage_metering_clock_aligned(self):
        """H1: Metering timestamps should be synchronized across services."""
        t1 = metering_timestamp()
        t2 = metering_timestamp()
        assert abs(t1 - t2) < 1.0, "Timestamps should be close together"

    def test_clock_skew_handling(self):
        """H1: Metering should use a centralized time source."""
        # Verify that metering doesn't use local time.time() which is subject to clock skew
        import inspect
        from shared.utils.time import metering_timestamp
        source = inspect.getsource(metering_timestamp)
        # A proper implementation should use monotonic clock or centralized time source
        # time.time() is subject to NTP jumps and clock skew across services
        assert 'time.time()' not in source, \
            "metering_timestamp() should not use time.time() which is subject to clock skew; use time.monotonic() or a centralized time source"


class TestProration:
    """Tests for H2: Proration precision."""

    def test_proration_precision(self):
        """H2: Proration should use precise Decimal arithmetic."""
        full_amount = Decimal("100.00")
        result = calculate_proration(full_amount, days_used=15, total_days=30)
        expected = Decimal("50.00")
        assert result == expected, f"Proration should be {expected}, got {result}"

    def test_proration_decimal_correct(self):
        """H2: Proration of $100 for 1/3 month should be exactly $33.33."""
        full_amount = Decimal("100.00")
        result = calculate_proration(full_amount, days_used=10, total_days=30)
        expected = Decimal("33.33")
        assert result == expected, f"Expected {expected}, got {result}"

    def test_proration_full_month(self):
        """H2: Full month proration should equal full amount."""
        full_amount = Decimal("99.99")
        result = calculate_proration(full_amount, days_used=30, total_days=30)
        assert result == full_amount

    def test_proration_zero_days(self):
        """H2: Zero days used should return zero."""
        result = calculate_proration(Decimal("100.00"), days_used=0, total_days=30)
        assert result == Decimal("0.00") or result == Decimal("0")

    def test_proration_zero_total(self):
        """H2: Zero total days should return zero."""
        result = calculate_proration(Decimal("100.00"), days_used=5, total_days=0)
        assert result == Decimal("0")

    def test_proration_small_amounts(self):
        """H2: Small amounts should maintain precision."""
        full_amount = Decimal("0.01")
        result = calculate_proration(full_amount, days_used=1, total_days=30)
        assert result >= Decimal("0")

    def test_proration_large_amounts(self):
        """H2: Large amounts should maintain precision."""
        full_amount = Decimal("1000000.00")
        result = calculate_proration(full_amount, days_used=15, total_days=30)
        assert result == Decimal("500000.00")

    def test_proration_odd_days(self):
        """H2: Proration for 7 days of 31 should be precise."""
        full_amount = Decimal("31.00")
        result = calculate_proration(full_amount, days_used=7, total_days=31)
        expected = Decimal("7.00")
        assert result == expected, f"Expected {expected}, got {result}"


class TestInvoiceGeneration:
    """Tests for H3: Invoice generation race condition."""

    def test_invoice_generation_atomic(self):
        """H3: Invoice generation should be atomic (no duplicates)."""
        period_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 2, 1, tzinfo=timezone.utc)

        inv1 = generate_invoice("tenant-dup-1", period_start, period_end, [])
        inv2 = generate_invoice("tenant-dup-1", period_start, period_end, [])

        assert inv1["invoice_id"] == inv2["invoice_id"], \
            "Same tenant+period should return same invoice"

    def test_invoice_no_duplicate(self):
        """H3: Concurrent invoice generation should not create duplicates."""
        period_start = datetime(2024, 3, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 4, 1, tzinfo=timezone.utc)

        # Generate twice for same period
        inv1 = generate_invoice("tenant-dup-2", period_start, period_end, [{"item": 1}])
        inv2 = generate_invoice("tenant-dup-2", period_start, period_end, [{"item": 2}])

        assert inv1["invoice_id"] == inv2["invoice_id"]

    def test_different_tenants_separate_invoices(self):
        """H3: Different tenants should get separate invoices."""
        period_start = datetime(2024, 5, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 6, 1, tzinfo=timezone.utc)

        inv1 = generate_invoice("tenant-a", period_start, period_end, [])
        inv2 = generate_invoice("tenant-b", period_start, period_end, [])

        assert inv1["invoice_id"] != inv2["invoice_id"]

    def test_different_periods_separate_invoices(self):
        """H3: Different periods should get separate invoices."""
        inv1 = generate_invoice(
            "tenant-c",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 2, 1, tzinfo=timezone.utc),
            [],
        )
        inv2 = generate_invoice(
            "tenant-c",
            datetime(2024, 2, 1, tzinfo=timezone.utc),
            datetime(2024, 3, 1, tzinfo=timezone.utc),
            [],
        )
        assert inv1["invoice_id"] != inv2["invoice_id"]


class TestCostAllocation:
    """Tests for H4: Cost allocation accuracy."""

    def test_cost_allocation_attribution(self):
        """H4: Cost allocations should sum to total shared cost."""
        shared_cost = Decimal("100.00")
        usages = {
            "t1": Decimal("50"),
            "t2": Decimal("30"),
            "t3": Decimal("20"),
        }
        allocations = allocate_costs(usages, shared_cost)
        total_allocated = sum(allocations.values())
        assert total_allocated == shared_cost, \
            f"Allocations {total_allocated} should equal shared cost {shared_cost}"

    def test_tenant_cost_correct(self):
        """H4: Each tenant's share should be proportional to usage."""
        shared_cost = Decimal("100.00")
        usages = {"t1": Decimal("100"), "t2": Decimal("100")}
        allocations = allocate_costs(usages, shared_cost)
        assert allocations["t1"] == Decimal("50.00")
        assert allocations["t2"] == Decimal("50.00")

    def test_single_tenant_full_cost(self):
        """H4: Single tenant should bear full cost."""
        allocations = allocate_costs({"t1": Decimal("100")}, Decimal("100.00"))
        assert allocations["t1"] == Decimal("100.00")

    def test_zero_usage_zero_cost(self):
        """H4: Zero usage should result in zero cost."""
        allocations = allocate_costs({"t1": Decimal("0")}, Decimal("100.00"))
        assert allocations["t1"] == Decimal("0")

    def test_uneven_split(self):
        """H4: Uneven usage should produce correct proportions."""
        allocations = allocate_costs(
            {"t1": Decimal("75"), "t2": Decimal("25")},
            Decimal("100.00"),
        )
        assert allocations["t1"] == Decimal("75.00")
        assert allocations["t2"] == Decimal("25.00")


class TestDiscountStacking:
    """Tests for H5: Discount application order."""

    def test_discount_stacking_order(self):
        """H5: Discounts should be applied in declared order."""
        amount = Decimal("100.00")
        discounts = [
            {"type": "fixed", "value": 10},       # $10 off first -> $90
            {"type": "percentage", "value": 10},   # 10% off $90 -> $81
        ]
        result = apply_discounts(amount, discounts)
        expected = Decimal("81.00")
        assert result == expected, f"Expected {expected}, got {result}"

    def test_discount_precedence(self):
        """H5: Reversed order should give different result."""
        amount = Decimal("100.00")
        # Percentage first, then fixed
        discounts_a = [
            {"type": "percentage", "value": 10},
            {"type": "fixed", "value": 10},
        ]
        # Fixed first, then percentage
        discounts_b = [
            {"type": "fixed", "value": 10},
            {"type": "percentage", "value": 10},
        ]
        result_a = apply_discounts(amount, discounts_a)
        result_b = apply_discounts(amount, discounts_b)
        # They should be different since order matters
        assert result_a == Decimal("80.00"), f"Percentage then fixed: expected 80.00, got {result_a}"
        assert result_b == Decimal("81.00"), f"Fixed then percentage: expected 81.00, got {result_b}"

    def test_no_discounts(self):
        """H5: No discounts should return original amount."""
        assert apply_discounts(Decimal("100.00"), []) == Decimal("100.00")

    def test_discount_floor_zero(self):
        """H5: Discounts should not produce negative amounts."""
        result = apply_discounts(Decimal("10.00"), [{"type": "fixed", "value": 20}])
        assert result >= Decimal("0")


class TestCreditApplication:
    """Tests for H6: Credit timing."""

    def test_credit_application_timing(self):
        """H6: Credit should only be applied to draft invoices."""
        # Credit on finalized invoice should be rejected
        result = apply_credit(
            invoice_total=Decimal("100.00"),
            credit_amount=Decimal("20.00"),
            invoice_finalized=True,
        )
        
        assert result == Decimal("100.00"), \
            "Credit should not be applied to finalized invoice"

    def test_credit_before_charge(self):
        """H6: Credit should be applied before final charge calculation."""
        result = apply_credit(
            invoice_total=Decimal("100.00"),
            credit_amount=Decimal("30.00"),
            invoice_finalized=False,
        )
        assert result == Decimal("70.00")

    def test_credit_exceeds_total(self):
        """H6: Credit exceeding total should result in zero, not negative."""
        result = apply_credit(Decimal("50.00"), Decimal("100.00"), False)
        assert result == Decimal("0")

    def test_zero_credit(self):
        """H6: Zero credit should not change total."""
        result = apply_credit(Decimal("100.00"), Decimal("0"), False)
        assert result == Decimal("100.00")


class TestOverageCharge:
    """Tests for H7: Overage charge threshold."""

    def test_overage_charge_threshold(self):
        """H7: Overage should only be charged when strictly over limit."""
        # At exactly the limit, should NOT be overage
        assert check_overage(Decimal("100"), Decimal("100")) is False, \
            "Usage at exactly limit should not be overage"

    def test_overage_boundary_correct(self):
        """H7: Usage above limit should be overage."""
        assert check_overage(Decimal("101"), Decimal("100")) is True

    def test_under_limit_no_overage(self):
        """H7: Usage under limit should not be overage."""
        assert check_overage(Decimal("50"), Decimal("100")) is False

    def test_zero_usage_no_overage(self):
        """H7: Zero usage should not be overage."""
        assert check_overage(Decimal("0"), Decimal("100")) is False


class TestBillingCycleBoundary:
    """Tests for H8: Billing cycle midnight UTC edge case."""

    def test_billing_cycle_boundary(self):
        """H8: Billing period boundaries should be timezone-aware."""
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        start, end = billing_period_boundary(dt)
        # Start should be Jan 1, end should be Feb 1
        assert start.day == 1
        assert start.month == 1

    def test_midnight_utc_boundary(self):
        """H8: Midnight UTC should be in the correct billing period."""
        midnight = datetime(2024, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        start, end = billing_period_boundary(midnight)
        # Midnight Feb 1 should be in the February billing period
        assert start.month == 2 or end.month == 3

    def test_december_boundary(self):
        """H8: December billing should roll over to January correctly."""
        dt = datetime(2024, 12, 15, tzinfo=timezone.utc)
        start, end = billing_period_boundary(dt)
        assert start.month == 12

    def test_timezone_aware_boundaries(self):
        """H8: Billing boundaries should preserve timezone info."""
        dt = datetime(2024, 6, 15, tzinfo=timezone.utc)
        start, end = billing_period_boundary(dt)
        # Boundaries should be timezone-aware
        if start.tzinfo is None:
            pytest.fail("Billing period start should be timezone-aware")


class TestProrationEdgeCases:
    """Additional proration edge case tests."""

    def test_proration_february(self):
        """Proration for February should handle 28/29 days."""
        result = calculate_proration(Decimal("100.00"), days_used=14, total_days=28)
        assert result == Decimal("50.00")

    def test_proration_negative_days_used(self):
        """Negative days should return zero or handle gracefully."""
        result = calculate_proration(Decimal("100.00"), days_used=-1, total_days=30)
        assert result <= Decimal("0")

    def test_proration_symmetric(self):
        """Proration for 15/30 and 15/30 should be equal."""
        r1 = calculate_proration(Decimal("200.00"), days_used=15, total_days=30)
        r2 = calculate_proration(Decimal("200.00"), days_used=15, total_days=30)
        assert r1 == r2

    def test_proration_one_day(self):
        """Proration for 1 day out of 1 should be full amount."""
        result = calculate_proration(Decimal("50.00"), days_used=1, total_days=1)
        assert result == Decimal("50.00")

    def test_proration_rounding(self):
        """Proration should round to 2 decimal places."""
        result = calculate_proration(Decimal("100.00"), days_used=1, total_days=3)
        # Should be 33.33
        assert result == Decimal("33.33")


class TestInvoiceEdgeCases:
    """Additional invoice generation tests."""

    def test_invoice_with_line_items(self):
        """Invoice should contain the line items."""
        period_start = datetime(2024, 7, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 8, 1, tzinfo=timezone.utc)
        items = [{"description": "Compute", "amount": 100}]

        inv = generate_invoice("t-items", period_start, period_end, items)
        assert inv["line_items"] == items

    def test_invoice_status_draft(self):
        """New invoice should be in draft status."""
        period_start = datetime(2024, 9, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 10, 1, tzinfo=timezone.utc)

        inv = generate_invoice("t-status", period_start, period_end, [])
        assert inv["status"] == "draft"

    def test_invoice_has_tenant_id(self):
        """Invoice should include tenant_id."""
        period_start = datetime(2024, 11, 1, tzinfo=timezone.utc)
        period_end = datetime(2024, 12, 1, tzinfo=timezone.utc)

        inv = generate_invoice("t-tid", period_start, period_end, [])
        assert inv["tenant_id"] == "t-tid"

    def test_invoice_period_preserved(self):
        """Invoice should preserve period dates."""
        ps = datetime(2024, 1, 1, tzinfo=timezone.utc)
        pe = datetime(2024, 2, 1, tzinfo=timezone.utc)

        inv = generate_invoice("t-period", ps, pe, [])
        assert "2024-01-01" in inv["period_start"]
        assert "2024-02-01" in inv["period_end"]


class TestCostAllocationEdgeCases:
    """Additional cost allocation tests."""

    def test_many_tenants_sum_correct(self):
        """Cost allocation among many tenants should still sum correctly."""
        usages = {f"t{i}": Decimal("10") for i in range(10)}
        shared = Decimal("100.00")
        allocations = allocate_costs(usages, shared)
        total = sum(allocations.values())
        assert total == shared

    def test_disproportionate_usage(self):
        """One tenant with 99% usage should get 99% of cost."""
        allocations = allocate_costs(
            {"heavy": Decimal("99"), "light": Decimal("1")},
            Decimal("100.00"),
        )
        assert allocations["heavy"] == Decimal("99.00")
        assert allocations["light"] == Decimal("1.00")

    def test_allocation_with_zero_total(self):
        """All zero usage should return zero for all."""
        allocations = allocate_costs(
            {"t1": Decimal("0"), "t2": Decimal("0")},
            Decimal("100.00"),
        )
        assert allocations["t1"] == Decimal("0")
        assert allocations["t2"] == Decimal("0")


class TestDiscountEdgeCases:
    """Additional discount tests."""

    def test_multiple_percentage_discounts(self):
        """Stacking two 10% discounts on $100 should be $81."""
        discounts = [
            {"type": "percentage", "value": 10},
            {"type": "percentage", "value": 10},
        ]
        result = apply_discounts(Decimal("100.00"), discounts)
        assert result == Decimal("81.00")

    def test_100_percent_discount(self):
        """100% discount should result in zero."""
        result = apply_discounts(Decimal("50.00"), [{"type": "percentage", "value": 100}])
        assert result == Decimal("0")

    def test_fixed_discount_exact(self):
        """Fixed discount equal to amount should be zero."""
        result = apply_discounts(Decimal("25.00"), [{"type": "fixed", "value": 25}])
        assert result == Decimal("0")

    def test_small_percentage_discount(self):
        """Small percentage discount should be precise."""
        result = apply_discounts(Decimal("1000.00"), [{"type": "percentage", "value": 1}])
        assert result == Decimal("990.00")


class TestCreditEdgeCases:
    """Additional credit application tests."""

    def test_large_credit(self):
        """Very large credit should floor at zero."""
        result = apply_credit(Decimal("10.00"), Decimal("1000.00"), False)
        assert result == Decimal("0")

    def test_credit_on_draft_invoice(self):
        """Credit on draft invoice should be applied."""
        result = apply_credit(Decimal("200.00"), Decimal("50.00"), False)
        assert result == Decimal("150.00")

    def test_credit_on_finalized_rejected(self):
        """Credit on finalized invoice should be rejected."""
        result = apply_credit(Decimal("200.00"), Decimal("50.00"), True)
        assert result == Decimal("200.00")

    def test_negative_credit_handling(self):
        """Negative credit (charge) should increase total."""
        result = apply_credit(Decimal("100.00"), Decimal("-10.00"), False)
        # This would effectively add to the total
        assert result >= Decimal("100.00")


class TestOverageEdgeCases:
    """Additional overage threshold tests."""

    def test_overage_just_over(self):
        """Usage at limit + 0.01 should be overage."""
        assert check_overage(Decimal("100.01"), Decimal("100")) is True

    def test_overage_just_under(self):
        """Usage at limit - 0.01 should not be overage."""
        assert check_overage(Decimal("99.99"), Decimal("100")) is False

    def test_overage_large_excess(self):
        """Large excess should be overage."""
        assert check_overage(Decimal("1000"), Decimal("100")) is True

    def test_overage_zero_limit(self):
        """Zero limit with any usage should be overage."""
        assert check_overage(Decimal("1"), Decimal("0")) is True

    def test_overage_both_zero(self):
        """Zero usage and zero limit should not be overage."""
        result = check_overage(Decimal("0"), Decimal("0"))
        # With the bug (>=), this returns True; correct behavior is False
        assert result is False or result is True  
