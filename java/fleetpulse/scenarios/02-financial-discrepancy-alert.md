# Finance Escalation: Billing Discrepancies in January Invoices

## Jira Ticket: FLEET-4892

**Type**: Bug
**Priority**: High
**Reported By**: Sarah Chen (Finance Director)
**Assignee**: Unassigned
**Labels**: billing, financial, urgent, customer-facing

---

## Summary

Multiple customers are reporting invoice discrepancies for January 2024. Total variance across affected customers is approximately $47,000 in overcharges. We need an immediate investigation before processing February invoices.

---

## Description

Our finance team identified significant discrepancies during the monthly reconciliation process. Invoice totals don't match the expected calculations based on mileage and fuel costs.

### Affected Customers

| Customer | Expected Total | Invoiced Total | Variance |
|----------|----------------|----------------|----------|
| Acme Logistics | $12,847.50 | $12,847.72 | +$0.22 |
| FastTrack Freight | $89,234.00 | $89,891.67 | +$657.67 |
| Metro Delivery | $45,123.75 | $48,571.23 | +$3,447.48 |
| Continental Transport | $234,567.00 | $276,891.45 | +$42,324.45 |

### Pattern Observed

The variance seems to correlate with:
1. **Number of trips** - More trips = larger discrepancy
2. **Trip distances** - Longer trips have larger errors
3. **Fuel cost calculations** - Toll costs also affected

---

## Customer Complaint: Continental Transport

From support ticket #CTL-2024-0189:

> "We've been a FleetPulse customer for 3 years and never had billing issues before. Our January invoice is $42,000 higher than expected. When we manually calculated based on our trip logs:
>
> - Total miles: 234,567
> - Rate per mile: $0.85
> - Expected base: $199,381.95
> - Fuel surcharges: $35,185.05
> - Total expected: $234,567.00
>
> But we were charged $276,891.45. The fuel surcharges alone are off by almost $40,000. Something is very wrong with your billing system."

---

## Technical Investigation Notes

### From Billing Service Logs

```
2024-01-31T23:45:12.445Z INFO  Calculating invoice for customer=continental-transport
2024-01-31T23:45:12.446Z DEBUG Total trips: 4,521
2024-01-31T23:45:12.447Z DEBUG Processing trip 1: distance=52.3 miles, fuel_cost=4.892342...
2024-01-31T23:45:12.448Z DEBUG Cumulative fuel total: 4.892342567892134
2024-01-31T23:45:12.449Z DEBUG Processing trip 2: distance=127.8 miles, fuel_cost=11.94729...
2024-01-31T23:45:12.450Z DEBUG Cumulative fuel total: 16.839632812374912
...
2024-01-31T23:52:47.123Z DEBUG Processing trip 4521: distance=45.2 miles, fuel_cost=4.22678...
2024-01-31T23:52:47.124Z DEBUG Final fuel total: 77324.45123847293
2024-01-31T23:52:47.125Z INFO  Invoice generated: base=$199381.95, fuel=$77509.50, total=$276891.45
```

### Observations

1. **Precision issues**: Fuel costs show 15+ decimal places in intermediate calculations
2. **Rounding happens only at the end**: Individual trip fuel costs accumulate without rounding
3. **Floating-point artifacts**: Numbers like `4.892342567892134` suggest `double` arithmetic

### Comparison Test

We ran a simple test with 1000 identical $1.001 charges:

```java
// Current code behavior (suspected)
double total = 0.0;
for (int i = 0; i < 1000; i++) {
    total += 1.001;
}
System.out.println(total);  // Output: 1000.9999999999859

// Expected behavior
BigDecimal total = BigDecimal.ZERO;
for (int i = 0; i < 1000; i++) {
    total = total.add(new BigDecimal("1.001"));
}
System.out.println(total);  // Output: 1001.000
```

---

## Related Issues

### GPS Coordinate Precision (Toll Calculations)

Toll booth matching also seems affected. From driver complaint:

> "The system is charging me for the Lincoln Tunnel toll twice. I'm pretty sure I only went through once, but the GPS shows me at two different locations that are both 'close enough' to the toll booth."

Log analysis:
```
2024-01-15T14:23:45.001Z DEBUG GPS position: lat=40.7589, lon=-74.0012 (float precision)
2024-01-15T14:23:45.002Z DEBUG Toll booth location: lat=40.758900, lon=-74.001200
2024-01-15T14:23:45.003Z DEBUG Distance to toll: 8.234 meters - TOLL TRIGGERED
...
2024-01-15T14:23:52.001Z DEBUG GPS position: lat=40.7589, lon=-74.0013 (different due to float rounding)
2024-01-15T14:23:52.002Z DEBUG Toll booth location: lat=40.758900, lon=-74.001300 (also rounded differently)
2024-01-15T14:23:52.003Z DEBUG Distance to toll: 7.891 meters - TOLL TRIGGERED AGAIN
```

### Division Edge Case

For some zero-distance trips (e.g., cancelled immediately after start), the per-mile rate calculation fails:

```
2024-01-22T09:15:33.445Z ERROR ArithmeticException: Division by zero
    at com.fleetpulse.billing.service.RateCalculator.calculatePerMileRate(RateCalculator.java:87)
    at com.fleetpulse.billing.service.InvoiceService.generateLineItem(InvoiceService.java:234)
```

---

## Questions for Engineering

1. Why are we using `double` for currency calculations?
2. Is `BigDecimal` being used correctly where it exists? (We see `BigDecimal.equals()` comparisons in the code)
3. Why are GPS coordinates being truncated to `float` precision?
4. What happens when a trip has zero distance?

## Files to Investigate

Based on the symptoms:
- `billing/src/main/java/com/fleetpulse/billing/service/InvoiceService.java`
- `billing/src/main/java/com/fleetpulse/billing/service/RateCalculator.java`
- `routes/src/main/java/com/fleetpulse/routes/service/TollCalculator.java`
- `tracking/src/main/java/com/fleetpulse/tracking/service/PositionService.java`

---

**Status**: Investigation Required
**SLA**: Resolution required before February 5th invoice run
**Finance Contact**: Sarah Chen (sarah.chen@company.com)
