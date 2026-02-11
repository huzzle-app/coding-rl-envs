# Finance Escalation: Billing Calculation Errors

## Incident Summary

**Severity**: Critical (P0)
**Reported By**: Finance Team / CFO Office
**Date**: 2024-02-19
**Status**: Engineering Investigation Required

---

## Finance Team Report

From: Sarah Chen, VP Finance
To: Engineering Leadership, Billing Team
Subject: URGENT - Customer Invoicing Errors

> We've received complaints from multiple enterprise customers about incorrect invoices. Some customers are being overcharged, others undercharged. Our monthly reconciliation is showing a $47,000 discrepancy that we cannot explain.
>
> This is a compliance issue. We need root cause analysis and fix ASAP. CFO is requesting a status update by EOD.

---

## Customer Complaints

### Enterprise Customer A (Overcharged)

**Ticket #91234**
> "Our February invoice shows $12,847.32 but based on our usage tracking, it should be approximately $8,200. When we asked for a breakdown, the line items don't add up to the total. Something is wrong with your billing calculations."

**Invoice Details**:
```
Item                    Quantity    Unit Price    Subtotal
-----------------------  --------    ----------    --------
Document Storage         500 GB      $0.10/GB      $50.00
API Calls               1.2M        $0.001/call   $1,200.00
Search Queries          450K        $0.005/query  $2,250.00
Collaboration Seats     25          $50/seat      $1,250.00
---
Expected Subtotal:                                $4,750.00
Invoice Total:                                    $12,847.32  <- ???
```

### Enterprise Customer B (Data Loss)

**Ticket #91456**
> "We tried to retrieve our invoice history and the API returned null for several months. When we query through your dashboard, some invoices show $0.00 even though we definitely had usage. Are you losing our billing data?"

**API Response**:
```json
{
  "invoices": [
    {"month": "2024-01", "total": 5234.50, "status": "paid"},
    {"month": "2023-12", "total": null, "status": "unknown"},
    {"month": "2023-11", "total": 0.00, "status": "paid"},
    {"month": "2023-10", "total": null, "status": "unknown"}
  ]
}
```

### Enterprise Customer C (Transaction Failures)

**Ticket #91678**
> "When we have high-volume batch operations, some transactions silently fail. We're seeing 'dirty read' errors in our audit logs. Are our financial transactions actually being committed?"

---

## Engineering Investigation Logs

### Billing Service Errors

```
2024-02-19T08:23:45.123Z [ERROR] Invoice calculation failed
java.lang.ArithmeticException: Non-terminating decimal expansion;
no exact representable decimal result.
    at java.math.BigDecimal.divide(BigDecimal.java:1716)
    at com.mindvault.billing.InvoiceCalculator.calculateProration(InvoiceCalculator.kt:89)

Context: Dividing $100.00 by 3 months for prorated billing
```

### Database Transaction Warnings

```
2024-02-19T09:12:34.567Z [WARN] Transaction isolation level: READ_UNCOMMITTED
    at com.mindvault.billing.BillingRepository.processPayment(BillingRepository.kt:45)

Note: Dirty reads possible - seeing uncommitted data from concurrent transactions
```

### Batch Insert Performance

```
2024-02-19T10:45:23.789Z [ERROR] Batch insert failed
java.lang.OutOfMemoryError: Java heap space
    at org.jetbrains.exposed.sql.statements.BatchInsertStatement.execute
    at com.mindvault.billing.InvoiceRepository.createBulkInvoices(InvoiceRepository.kt:123)

Batch size: 50,000 invoice line items
shouldReturnGeneratedValues: true <- causing OOM by fetching all generated IDs
```

### Null Handling Issues

```
2024-02-19T11:30:45.012Z [ERROR] NullPointerException in balance comparison
java.lang.NullPointerException: Cannot invoke compareTo on null
    at com.mindvault.billing.AccountService.checkBalance(AccountService.kt:67)

account.balance was null (nullable DB column)
Code assumed non-null: if (balance > threshold)
```

### Data Class Copy Bug

```
2024-02-19T12:15:23.456Z [DEBUG] Invoice recalculation mismatch
Original Invoice: total=1000.00, items=[...], calculated=1000.00
Copied Invoice:   total=1000.00, items=[..., newItem], calculated=1000.00

Note: total field in data class constructor is not recalculated on copy()
Adding items to copied invoice doesn't update the total
```

---

## Slack Thread: #billing-engineering

**@dev.billing** (13:00):
> Investigating the overcharge issue. Found something weird - the `Invoice` data class has `total` as a constructor parameter that's calculated at creation time. When we `copy()` an invoice and add line items, the total doesn't update.

**@dev.marcus** (13:05):
> That's by design with data class copy - it just copies the value, doesn't recalculate. You need to make `total` a computed property instead.

**@dev.billing** (13:08):
> Also found the BigDecimal division issue. We're calling `.divide(other)` without specifying scale or rounding mode. For non-terminating decimals like 1/3, it throws an exception.

**@dev.sarah** (13:15):
> The null balance issue is a platform type problem. JDBC returns `BigDecimal?` (nullable) but Kotlin infers it as `BigDecimal!` (platform type). The code treats it as non-null.

---

**@dev.billing** (14:00):
> Found the batch insert OOM. When `shouldReturnGeneratedValues = true`, Exposed fetches all generated IDs back from PostgreSQL. With 50K rows, that's a lot of memory.

**@sre.alex** (14:05):
> Can we just set it to false?

**@dev.billing** (14:07):
> Yes, unless we actually need the generated IDs. For bulk invoice creation, we don't - we can query them separately if needed.

---

**@dev.marcus** (15:30):
> The transaction isolation issue is concerning. `READ_UNCOMMITTED` means we can read data from transactions that haven't committed yet. If those transactions roll back, we've made decisions based on phantom data.

**@dev.billing** (15:33):
> That explains the sporadic "balance mismatch" errors. Two concurrent payments reading uncommitted balances and both succeeding when only one should.

**@sre.alex** (15:35):
> What isolation level should we be using?

**@dev.marcus** (15:37):
> At minimum `READ_COMMITTED`. For financial operations, probably `SERIALIZABLE` or use explicit row-level locking.

---

**@qa.jennifer** (16:00):
> Also seeing test pollution issues. The singleton `BillingConfig` object holds mutable state. Tests are failing intermittently because they're seeing state from previous tests.

**@dev.billing** (16:03):
> We need to either reset that state between tests or not use a singleton for configuration.

---

## Impact Assessment

- **Revenue Impact**: $47,000 identified discrepancy (likely more undiscovered)
- **Customers Affected**: At least 23 enterprise accounts flagged
- **Compliance Risk**: SOC2 audit findings likely if not addressed
- **Legal Risk**: Potential overbilling lawsuits

## Questions for Investigation

1. Why does BigDecimal division throw exceptions for non-terminating results?
2. Why isn't the invoice total being recalculated when items are added?
3. Why are we using `READ_UNCOMMITTED` isolation for financial transactions?
4. Why does batch insert cause OOM on large datasets?
5. Why is account balance null when it should have a default value?
6. Why do tests affect each other through singleton state?

## Files to Investigate

- `billing/src/main/kotlin/com/mindvault/billing/Invoice.kt`
- `billing/src/main/kotlin/com/mindvault/billing/InvoiceCalculator.kt`
- `billing/src/main/kotlin/com/mindvault/billing/BillingRepository.kt`
- `billing/src/main/kotlin/com/mindvault/billing/AccountService.kt`
- `shared/src/main/kotlin/com/mindvault/shared/config/BillingConfig.kt`

---

**Assigned**: @billing-team
**Deadline**: EOD 2024-02-19
**Escalation**: CFO briefing scheduled for 2024-02-20 09:00
