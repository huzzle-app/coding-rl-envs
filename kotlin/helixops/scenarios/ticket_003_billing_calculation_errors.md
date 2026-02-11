# SUPPORT-47291: Incorrect Invoice Calculations and Financial Discrepancies

**Priority:** High
**Queue:** Billing Support Escalation
**Customer:** Acme Healthcare Corp (Enterprise Tier)
**Account Manager:** @jennifer.wu
**Created:** 2024-11-19 09:15 PST

---

## Customer Report

> We've been reviewing our November invoices and found significant discrepancies in the billing amounts. Several invoices show incorrect totals, and tax calculations appear to be wrong. We're also seeing some invoices where the total doesn't match the sum of line items. This is causing issues with our accounting team's month-end reconciliation.
>
> Additionally, we tried to transfer credits between two of our department accounts and the system threw an error about "insufficient credits" even though the source account clearly had enough balance.
>
> This is a blocker for our finance department. We need this resolved before the 25th.

**Contact:** Robert Chen, VP Finance
**Email:** r.chen@acmehealthcare.com

---

## Technical Investigation

### Issue 1: Invoice Total Mismatch

When line items are modified after invoice creation using Kotlin's `copy()` function, the computed total field retains the old value.

**Example from customer data:**
```
Invoice ID: INV-2024-8847
Original line items: [$100, $200, $150] -> Total: $450
After modification: [$100, $200, $150, $300] -> Total: $450 (WRONG, should be $750)
```

**Relevant test failure:**
```
BillingTests > testInvoiceCopyUpdatesTotal FAILED
    Expected: 750.00
    Actual: 450.00

    Invoice was created, then copy(lineItems = ...) was called
    but invoice.total still reflects original line items
```

### Issue 2: Tax Calculation Errors

The tax application function is producing incorrect results. For a $100 invoice with 10% tax, customers are seeing $100.10 instead of $110.00.

**Customer example:**
```
Invoice: INV-2024-9012
Subtotal: $5,000.00
Tax Rate: 8.25%
Expected Tax Amount: $5,412.50
Actual Charged: $5,008.25
Difference: $404.25 UNDERCHARGED
```

**Test output:**
```
BillingTests > testTaxCalculation FAILED
    Input: base=$100.00, taxRate=0.10
    Expected: $110.00
    Actual: $100.10

    The tax function appears to ADD the rate instead of MULTIPLYING
```

### Issue 3: Monthly Bill Calculation Crashes

Customers without overage charges or discounts are experiencing calculation failures.

**Error log:**
```
2024-11-19T09:22:14.567Z ERROR [billing] --- NullPointerException
    at java.math.BigDecimal.add(BigDecimal.java:1345)
    at com.helixops.billing.BillingService.calculateMonthlyBill(BillingService.kt:71)

    Customer: CUST-4821 (no overage, no discount)
    Base plan: $29.99
    Overage: null
    Discount: null
```

### Issue 4: Credit Transfer Failures

The credit transfer operation is experiencing race conditions under concurrent access.

**Customer scenario:**
```
Account A balance: $10,000
Account B balance: $2,000
Attempted transfer: $5,000 from A to B

Result: "Insufficient credits: 10000 < 5000" error
(Balance check passed, but transfer failed)
```

**Test failure:**
```
BillingTests > testConcurrentCreditTransfer FAILED
    Two concurrent transfers of $3000 each from account with $5000
    Expected: One succeeds, one fails
    Actual: Both read $5000, both attempted, inconsistent state
```

### Issue 5: Bulk Invoice Import OOM

When importing large batches of invoices (10K+), the system runs out of memory.

**Production log:**
```
2024-11-19T08:45:22.123Z ERROR [billing] --- OutOfMemoryError: Java heap space
    at java.util.ArrayList.grow(ArrayList.java:265)
    at com.helixops.billing.BillingService.importInvoices(BillingService.kt:83)

    Import job: JOB-20241119-001
    Invoice count: 45,000
    Line items total: 180,000
```

---

## Failing Tests

```bash
./gradlew :billing:test

BillingTests > testDataClassCopyPreservesTotal FAILED
BillingTests > testBigDecimalExtensionTaxCalculation FAILED
BillingTests > testNullableBigDecimalArithmetic FAILED
BillingTests > testTransactionIsolationLevel FAILED
BillingTests > testBatchInsertMemoryEfficiency FAILED
```

---

## Customer Impact

| Customer | Issue | Financial Impact |
|----------|-------|------------------|
| Acme Healthcare | Tax undercharge | $12,847 uncollected |
| Midwest Medical | Invoice totals wrong | $8,234 disputed |
| Pacific Labs | Transfer failures | 3 failed transactions |
| Metro Clinic | Import OOM | 45K invoices pending |

---

## Workaround Attempts

1. **Manual invoice recalculation**: Works but doesn't scale
2. **Disable copy() usage**: Requires code changes in multiple places
3. **Single-threaded transfers**: Fixes race but creates bottleneck

---

## Resolution Requirements

- All billing calculations must match expected values
- Tax calculations must multiply, not add
- Nullable arithmetic must handle null values safely
- Concurrent operations must maintain consistency
- Bulk operations must not exhaust memory

**Deadline:** 2024-11-25 (customer month-end close)
