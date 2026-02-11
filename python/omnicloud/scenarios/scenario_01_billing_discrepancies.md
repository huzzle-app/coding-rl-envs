# Scenario 1: Customer Billing Discrepancies

## Incident Report

**Incident ID**: INC-2024-1847
**Severity**: P2 - Major
**Status**: Open
**Reported By**: Customer Success Team
**Date Opened**: 2024-01-15 09:23 UTC

---

## Summary

Multiple enterprise customers have reported billing discrepancies on their monthly invoices. Some customers claim they are being overcharged, while others have received duplicate invoices for the same billing period.

---

## Symptoms Reported

### 1. Proration Calculation Errors

> "We upgraded our compute tier mid-month and the prorated charges don't add up. We used the service for 15 days out of 30, but the charge is $502.00 instead of the expected $500.00. This happens consistently on accounts with mid-cycle changes."
> -- Enterprise Customer (Tenant ID: ent-acme-corp)

### 2. Duplicate Invoice Generation

> "Our finance team received two invoices for the October billing period with different invoice IDs but identical line items. Both were marked as 'draft' status. We tried to pay one but couldn't tell which was authoritative."
> -- Enterprise Customer (Tenant ID: ent-globex-industries)

The customer support team confirmed this happens when multiple API requests hit the billing endpoint simultaneously during month-end processing.

### 3. Discount Application Order Issues

> "We have a 10% enterprise discount and a $50 promotional credit. Last month we were charged $855 but based on our calculations it should be $805. It seems like the discounts are being applied in the wrong order."
> -- Enterprise Customer (Tenant ID: ent-initech)

Customer provided calculation:
- Base amount: $1000
- Expected: $1000 * 0.90 - $50 = $850
- Received: $1000 - $50 * 0.90 = $855

### 4. Credits Applied to Finalized Invoices

> "We requested a $200 service credit due to an outage last month. The credit was applied to an already-finalized and paid invoice instead of the current billing period. Our accounts receivable team is confused about the reconciliation."
> -- Enterprise Customer (Tenant ID: ent-umbrella)

### 5. Overage Charges at Exactly the Limit

> "Our storage plan includes 1TB. We used exactly 1TB this month (not a byte over) but were charged an overage fee. The Terms of Service says overage is charged when usage EXCEEDS the limit, not equals it."
> -- SMB Customer (Tenant ID: smb-wayne-tech)

### 6. Cost Allocation Rounding Errors

Shared infrastructure costs allocated to tenants don't sum to the total:

```
Tenant A usage: 33.33%  -> Allocated: $333.30
Tenant B usage: 33.33%  -> Allocated: $333.30
Tenant C usage: 33.34%  -> Allocated: $333.30
Total allocated: $999.90 (should be $1000.00)
```

---

## Timeline

- **2024-01-10**: First customer complaint about proration
- **2024-01-12**: Second complaint about duplicate invoices
- **2024-01-14**: Finance escalation about discount ordering
- **2024-01-15**: Incident opened after pattern recognized

---

## Affected Components

- `services/billing/views.py` - Invoice generation, proration, discounts
- `services/tenants/models.py` - Tenant billing isolation
- `shared/utils/time.py` - Billing cycle boundary calculations

---

## Diagnostic Data

### API Logs (Invoice Generation)

```
2024-01-10T23:59:58.234Z billing [INFO] Generating invoice for tenant=ent-globex-industries period=2024-01
2024-01-10T23:59:58.267Z billing [INFO] Generating invoice for tenant=ent-globex-industries period=2024-01
2024-01-10T23:59:58.312Z billing [INFO] Invoice created: inv-a1b2c3d4
2024-01-10T23:59:58.345Z billing [INFO] Invoice created: inv-e5f6g7h8
```

### Database State

```sql
SELECT invoice_id, tenant_id, period_start, status, created_at
FROM invoices
WHERE tenant_id = 'ent-globex-industries' AND period_start = '2024-01-01';

-- Results:
-- inv-a1b2c3d4 | ent-globex-industries | 2024-01-01 | draft | 2024-01-10T23:59:58.312Z
-- inv-e5f6g7h8 | ent-globex-industries | 2024-01-01 | draft | 2024-01-10T23:59:58.345Z
```

### Test Failures Related

```
FAILED tests/unit/test_billing_metering.py::TestBillingMetering::test_proration_precision
FAILED tests/unit/test_billing_metering.py::TestBillingMetering::test_invoice_generation_idempotent
FAILED tests/unit/test_billing_metering.py::TestBillingMetering::test_discount_stacking_order
FAILED tests/unit/test_billing_metering.py::TestBillingMetering::test_credit_on_finalized_invoice
FAILED tests/unit/test_billing_metering.py::TestBillingMetering::test_overage_at_limit
FAILED tests/unit/test_billing_metering.py::TestBillingMetering::test_cost_allocation_sums_to_total
```

---

## Impact

- **Financial**: Estimated $15,000 in billing errors across 47 affected accounts
- **Customer Trust**: 3 enterprise customers threatening contract review
- **Operational**: Finance team spending 8+ hours per week on manual reconciliation

---

## Investigation Notes

The billing service uses a mix of float and Decimal types for monetary calculations. Some code paths appear to convert between types inconsistently. Additionally, the invoice generation endpoint doesn't appear to have proper idempotency controls.
