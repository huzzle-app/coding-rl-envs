# Scenario 03: Mysterious Penny Discrepancies in Trade Reports

**Severity**: P3 (Medium)
**Reported By**: Finance/Reconciliation Team
**Date**: End of Month Reconciliation

---

## Incident Summary

During monthly reconciliation, the Finance team discovered systematic discrepancies between calculated trade values and reported values. Differences are typically in the pennies or fractions of pennies, but accumulate to significant amounts across high-volume trading days.

## Symptoms

### Primary Complaint

Daily trade reconciliation reports show unexplained discrepancies:

```
Date: 2024-03-15
Total Trade Value (Calculated): $47,234,567.89
Total Trade Value (Reported):   $47,234,412.17
Discrepancy:                         -$155.72

Date: 2024-03-18
Total Trade Value (Calculated): $52,891,234.56
Total Trade Value (Reported):   $52,891,089.33
Discrepancy:                         -$145.23
```

### Observed Patterns

1. **Discrepancies correlate with trade volume**:
   - Low volume days: $5-20 discrepancy
   - Average volume days: $50-150 discrepancy
   - High volume days: $200-500 discrepancy

2. **Partial fills show largest errors**:
   ```
   Order: BUY 10,000 NVDA @ $875.4567

   Fill 1: 3,000 shares @ $875.4567
   Fill 2: 4,500 shares @ $875.4567
   Fill 3: 2,500 shares @ $875.4567

   Expected total: 10,000 * $875.4567 = $8,754,567.00
   Reported total: $8,754,566.82
   Difference: $0.18
   ```

3. **Commission calculations compound the issue**:
   ```
   Trade value: $875,456.70
   Commission rate: 0.1% (0.001)

   Expected commission: $875.4567
   Reported commission: $875.45

   Difference per trade: $0.0067
   Across 10,000 trades/day: $67.00 daily discrepancy
   ```

4. **Average fill price accumulation**:
   ```
   Fill 1: 100 @ $150.123456
   Fill 2: 200 @ $150.234567
   Fill 3: 150 @ $150.345678

   Correct weighted avg: $150.247160...
   Stored avg_fill_price: 150.24716 (truncated)

   Later position valuation uses truncated value,
   causing further downstream errors
   ```

### Error Accumulation Examples

| Symbol | Daily Trades | Per-Trade Error | Daily Total |
|--------|--------------|-----------------|-------------|
| AAPL   | 15,234       | ~$0.003         | $45.70      |
| MSFT   | 12,891       | ~$0.004         | $51.56      |
| GOOGL  | 8,234        | ~$0.005         | $41.17      |
| NVDA   | 22,456       | ~$0.003         | $67.37      |

## Impact

- **Financial**: $3,000-5,000 monthly reconciliation gaps
- **Audit**: External auditors flag unexplained variances
- **Reporting**: SEC filings require accurate trade reporting
- **Customer**: Institutional clients notice discrepancies in their statements

## Initial Investigation

### What We've Ruled Out
- Database rounding (Postgres Decimal fields are precise)
- Network/serialization issues (JSON preserves number precision)
- UI display truncation (backend values are incorrect)

### Suspicious Observations

1. **Commission stored as float in OrderFill model**:
   ```python
   commission = models.FloatField()  # Not DecimalField
   ```

2. **Float arithmetic in fill calculations**:
   ```python
   commission = float(fill_quantity) * float(fill_price) * 0.001
   ```

3. **Average fill price stored as float**:
   ```python
   avg_fill_price = models.FloatField(null=True)
   ```

4. **Price comparisons in matching engine use float()**:
   ```python
   if float(best_ask.price) > float(price):
   ```

### Relevant Code Paths
- `services/orders/views.py` - fill_order endpoint (commission calculation)
- `services/orders/models.py` - OrderFill model (commission field type)
- `services/matching/main.py` - price comparison logic
- `shared/events/trades.py` - trade value calculations
- `shared/events/orders.py` - partial fill fee calculations

## Reproduction Steps

1. Create an order for 1,000 shares at price $123.456789
2. Execute 7 partial fills of varying sizes
3. Calculate expected total value with exact arithmetic
4. Compare against stored/reported values
5. Expected: Values match to cent
6. Actual: Values differ by several cents

### Specific Test Case
```python
# This should demonstrate the issue
price = Decimal("123.456789")
qty = Decimal("1000")
rate = Decimal("0.001")

expected_commission = price * qty * rate  # Decimal: 123.456789
actual_commission = float(price) * float(qty) * 0.001  # Float: 123.45678900000001

print(f"Expected: {expected_commission}")
print(f"Actual: {actual_commission}")
print(f"Diff: {float(expected_commission) - actual_commission}")
```

## Questions for Investigation

- Which fields use `float` vs `Decimal` for financial values?
- Where in the calculation pipeline is precision lost?
- Are price comparisons done with Decimal or float?
- How is the average fill price calculated and stored?
- Is the commission rate applied with proper precision?

---

**Status**: Unresolved
**Assigned**: Trading Systems Team
**SLA**: 72 hours (P3)
