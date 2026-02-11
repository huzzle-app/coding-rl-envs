# Incident Report INC-2024-002

## Incident Summary
**Severity**: P2 - High
**Status**: Open
**Duration**: Discovered during monthly reconciliation
**Affected Service**: VertexGrid Billing & Settlement Engine
**Impact**: Revenue discrepancy of $12,847.63 in March settlement cycle

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 2024-04-02 09:15 | Finance team flags discrepancy between invoice totals and bank deposits |
| 2024-04-02 11:30 | Billing team confirms $12,847.63 shortfall across 47,000+ invoices |
| 2024-04-02 14:00 | Engineering begins investigation of revenue calculation pipeline |
| 2024-04-02 16:45 | Discrepancy traced to accumulated rounding errors in batch processing |
| 2024-04-03 10:00 | Secondary issue discovered: empty invoices causing system crashes |

---

## Symptoms

### Symptom 1: Accumulated Precision Loss

When calculating total revenue across large invoice batches, the reported total diverges from the sum of individual invoice amounts:

```
Expected total (sum of invoices): $2,847,392.47
Reported batch total:             $2,834,544.84
Difference:                       $12,847.63 (0.45%)
```

The error increases proportionally with batch size. Testing with smaller batches shows the error compounds:

| Batch Size | Observed Error |
|------------|----------------|
| 100 invoices | $0.27 |
| 1,000 invoices | $2.73 |
| 10,000 invoices | $27.31 |
| 47,000 invoices | $12,847.63 |

### Symptom 2: Divide-by-Zero Crashes

Invoices with zero line items cause the average price calculation to crash:

```
java.lang.ArithmeticException: / by zero
    at java.math.BigDecimal.divideToIntegralValue(BigDecimal.java:1744)
    at com.vertexgrid.billing.service.InvoiceService.calculateAverageItemPrice(InvoiceService.java:46)
```

### Symptom 3: Geographic Billing Zone Mismatches

Customers near zone boundaries are sometimes billed under the wrong tariff zone:

```
Customer location: 40.7589, -73.9851 (Midtown Manhattan)
Expected zone: ZONE-N-W (NYC Metro tariff)
Assigned zone: ZONE-N-W (Correct in this case, but...)

Customer location: 40.7501, -73.9972 (Penn Station area)
Expected zone: ZONE-N-W (NYC Metro tariff)
Assigned zone: ZONE-N-E (New Jersey tariff - WRONG)
```

Customers within ~1km of zone boundaries show inconsistent billing.

---

## Business Impact

- **Revenue Leakage**: $12,847.63 unrecoverable for March cycle
- **Customer Trust**: 23 customers received incorrect zone-based charges
- **Audit Risk**: Financial controls flagged for SOX compliance review
- **Settlement Delays**: April settlements delayed pending investigation

---

## Affected Tests

```
BillingServiceTest.test_empty_invoice_average_price
BillingServiceTest.test_revenue_accumulation_precision
BillingServiceTest.test_geo_zone_boundary_precision
RouteServiceTest.test_cost_calculation_precision
RouteServiceTest.test_bigdecimal_equality_comparison
```

---

## Log Analysis

Revenue calculation trace showing precision degradation:

```
2024-04-01 23:45:12.847 INFO  [billing-batch] Processing invoice batch 47/50
2024-04-01 23:45:12.848 DEBUG [billing-batch] Invoice #INV-2024-47001: $127.99
2024-04-01 23:45:12.848 DEBUG [billing-batch] Running total: 2658432.8399999997  <-- precision loss visible
2024-04-01 23:45:12.849 DEBUG [billing-batch] Invoice #INV-2024-47002: $84.50
2024-04-01 23:45:12.849 DEBUG [billing-batch] Running total: 2658517.3399999994  <-- error accumulating
```

Zone calculation for boundary case:

```
2024-04-01 18:22:33.104 DEBUG [billing-zone] Calculating zone for (40.7501, -73.9972)
2024-04-01 18:22:33.104 DEBUG [billing-zone] Truncated coords: (40.75, -73.99)
2024-04-01 18:22:33.105 DEBUG [billing-zone] Zone result: ZONE-N-W
```

Compare with correctly handled location:

```
2024-04-01 18:22:34.221 DEBUG [billing-zone] Calculating zone for (40.7589, -73.9851)
2024-04-01 18:22:34.221 DEBUG [billing-zone] Truncated coords: (40.75, -73.98)
2024-04-01 18:22:34.222 DEBUG [billing-zone] Zone result: ZONE-N-W
```

---

## Investigation Areas

1. **Revenue Accumulation**: Review `InvoiceService.calculateTotalRevenue()` for numeric type handling
2. **Empty Invoice Guard**: Check `InvoiceService.calculateAverageItemPrice()` for edge case handling
3. **Coordinate Precision**: Examine `InvoiceService.getBillingZone()` truncation logic
4. **Route Cost Calculation**: Similar floating-point concerns in `RouteService.calculateRouteCost()`

---

## References

- Finance Ticket: FIN-2024-0412
- Affected Invoices: /data/billing/march-2024/discrepancy-report.csv
- Zone Mapping Documentation: https://wiki.vertexgrid.internal/billing-zones
