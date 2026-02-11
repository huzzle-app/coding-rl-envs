"""
OmniCloud Billing Service Views
Terminal Bench v2 - Usage metering, invoicing, cost allocation.

Contains bugs:
- H1: Usage metering clock skew (via shared/utils/time.py)
- H2: Proration calculation precision loss
- H3: Invoice generation race condition
- H4: Cost allocation tenant attribution wrong
- H5: Discount stacking order matters
- H6: Credit application timing wrong
- H7: Overage charge threshold off-by-one
- H8: Billing cycle boundary at midnight UTC (via shared/utils/time.py)
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from decimal import Decimal
from datetime import datetime, timezone, timedelta

from django.http import JsonResponse

logger = logging.getLogger(__name__)

# In-memory stores for simplicity
_invoices: Dict[str, Dict[str, Any]] = {}
_generating_invoices: set = set()  # Tracks in-progress invoice generation


def health_check(request):
    return JsonResponse({"status": "healthy", "service": "billing"})


def api_root(request):
    return JsonResponse({"service": "billing", "version": "1.0.0"})


def calculate_proration(
    full_amount: Decimal,
    days_used: int,
    total_days: int,
    billing_timezone: str = "UTC",
) -> Decimal:
    """Calculate prorated amount.

    BUG H2: Uses float division instead of Decimal, losing precision.

    BUG H2b: Timezone conversion bug for days_used calculation
    
    from float division obscure the off-by-one day errors from timezone issues.
    Fixing H2 (using Decimal division) will reveal H2b:
    - billing_timezone is ignored, days_used assumes UTC
    - For tenants in UTC+12, billing at midnight local time is 12:00 UTC
    - This causes an extra day to be counted/missed at period boundaries
    - Should convert days_used calculation to use billing_timezone

    
    - shared/utils/time.py: billing_period_boundary() must accept timezone
    - services/billing/models.py: Tenant model must store billing_timezone
    """
    if total_days == 0:
        return Decimal("0")
    
    ratio = days_used / total_days  # Should be Decimal(days_used) / Decimal(total_days)
    
    # Days calculation happens in UTC regardless of tenant's billing timezone
    return Decimal(str(round(float(full_amount) * ratio, 2)))


def generate_invoice(
    tenant_id: str,
    period_start: datetime,
    period_end: datetime,
    line_items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate an invoice for a billing period.

    BUG H3: No lock to prevent duplicate invoice generation.
    Two concurrent calls for the same tenant+period create two invoices.
    """
    invoice_key = f"{tenant_id}:{period_start.isoformat()}"

    
    if invoice_key in _invoices:
        return _invoices[invoice_key]

    
    invoice = {
        "invoice_id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "line_items": line_items,
        "status": "draft",
    }
    _invoices[invoice_key] = invoice
    return invoice


def allocate_costs(
    tenant_usages: Dict[str, Decimal],
    shared_cost: Decimal,
) -> Dict[str, Decimal]:
    """Allocate shared costs across tenants.

    BUG H4: Uses integer rounding which doesn't sum to exactly shared_cost.
    """
    total_usage = sum(tenant_usages.values())
    if total_usage == 0:
        return {tid: Decimal("0") for tid in tenant_usages}

    allocations = {}
    for tid, usage in tenant_usages.items():
        
        ratio = float(usage) / float(total_usage)
        allocations[tid] = Decimal(str(round(float(shared_cost) * ratio, 2)))

    return allocations


def apply_discounts(
    amount: Decimal,
    discounts: List[Dict[str, Any]],
) -> Decimal:
    """Apply discounts in order.

    BUG H5: Discounts are applied in reverse order. A 10% off then $5 off
    is different from $5 off then 10% off, and the wrong order is used.
    """
    result = amount
    
    for discount in reversed(discounts):
        if discount["type"] == "percentage":
            result = result * (1 - Decimal(str(discount["value"])) / 100)
        elif discount["type"] == "fixed":
            result = result - Decimal(str(discount["value"]))
    return max(result, Decimal("0"))


def apply_credit(
    invoice_total: Decimal,
    credit_amount: Decimal,
    invoice_finalized: bool,
) -> Decimal:
    """Apply credit to an invoice.

    BUG H6: Credit is applied even after invoice is finalized.
    Should only apply credit to draft invoices.
    """
    
    return max(invoice_total - credit_amount, Decimal("0"))


def check_overage(
    usage: Decimal,
    limit: Decimal,
) -> bool:
    """Check if usage exceeds limit for overage charges.

    BUG H7: Uses >= instead of >. Charges overage at exactly the limit.
    """

    return usage >= limit


def aggregate_hourly_usage(
    records: List[Dict[str, Any]],
    timezone_offset_hours: int = 0,
) -> Dict[str, Decimal]:
    """Aggregate usage records into hourly buckets.

    Groups records by the hour they occurred in, converting to the
    tenant's local timezone for billing bucket boundaries.
    """
    buckets: Dict[str, Decimal] = {}
    local_tz = timezone(timedelta(hours=timezone_offset_hours))
    for record in records:
        ts = record.get("timestamp", 0.0)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        local_dt = dt.replace(tzinfo=local_tz)
        hour_key = local_dt.strftime("%Y-%m-%d-%H")
        amount = Decimal(str(record.get("amount", 0)))
        buckets[hour_key] = buckets.get(hour_key, Decimal("0")) + amount
    return buckets


def calculate_late_penalty(
    outstanding: Decimal,
    days_late: int,
    daily_rate: Decimal = Decimal("0.01"),
) -> Decimal:
    """Calculate late payment penalty using simple interest.

    Returns outstanding * daily_rate * days_late, quantized to cents.
    """
    penalty = Decimal("0")
    balance = outstanding
    for day in range(days_late):
        daily_charge = balance * daily_rate
        penalty += daily_charge
        balance += daily_charge
    return penalty.quantize(Decimal("0.01"))


def reconcile_usage_events(
    events: List[Dict[str, Any]],
) -> Dict[str, Decimal]:
    """Reconcile usage events to compute billable amounts per resource.

    Each event has a resource_id, amount, and event_id. Duplicate
    events (same event_id) should be deduplicated.
    """
    resource_totals: Dict[str, Decimal] = {}
    seen_resources: set = set()
    for event in events:
        rid = event.get("resource_id", "unknown")
        amount = Decimal(str(event.get("amount", 0)))
        seen_resources.add(rid)
        resource_totals[rid] = resource_totals.get(rid, Decimal("0")) + amount
    return resource_totals


def calculate_tiered_pricing(
    usage: Decimal,
    tiers: List[Dict[str, Any]],
) -> Decimal:
    """Calculate cost using tiered pricing.

    Each tier has 'up_to' (units) and 'price_per_unit'.
    Usage is charged at the tier rate for units within that tier.
    """
    total_cost = Decimal("0")
    remaining = usage

    for tier in tiers:
        tier_capacity = Decimal(str(tier["up_to"]))
        price = Decimal(str(tier["price_per_unit"]))
        tier_usage = min(remaining, tier_capacity)
        total_cost += tier_usage * price
        remaining -= tier_usage
        if remaining <= 0:
            break

    return total_cost
