# Support Ticket: Portfolio Value Discrepancies

## Ticket Details

**Ticket ID**: TRADE-4892
**Priority**: P2 - High
**Created**: 2024-03-18 09:15 UTC
**Customer**: Velocity Capital (Enterprise Tier)
**Assigned To**: Trading Platform Team

## Customer Report

> Subject: Our portfolio values don't match our internal accounting
>
> Hi Support Team,
>
> We've noticed discrepancies between the portfolio values shown in your platform and our internal reconciliation. The differences are small but consistent. Here are some examples from today:
>
> | Account | Your System | Our Records | Difference |
> |---------|-------------|-------------|------------|
> | ACC-7291 | $1,234,567.89 | $1,234,567.92 | -$0.03 |
> | ACC-7292 | $892,451.23 | $892,451.20 | +$0.03 |
> | ACC-7293 | $2,891,003.47 | $2,891,003.56 | -$0.09 |
>
> These amounts seem random but they accumulate. Over the past month, we estimate the total discrepancy across all accounts is approximately $847.
>
> We process about 15,000 trades per day. The larger accounts with more trading activity seem to have bigger discrepancies.
>
> Can you investigate?
>
> Best regards,
> Jennifer Chen
> Head of Operations, Velocity Capital

## Engineering Investigation Log

### Day 1 - Initial Triage

**10:30 UTC** - Reviewed customer data. Confirmed discrepancies exist.

Ran query to compare calculated values:
```sql
SELECT
    account_id,
    SUM(quantity * avg_price) as calculated_value,
    cash_balance,
    total_portfolio_value,
    total_portfolio_value - (SUM(quantity * avg_price) + cash_balance) as drift
FROM positions
JOIN portfolios USING (account_id)
GROUP BY account_id, cash_balance, total_portfolio_value
HAVING ABS(drift) > 0.001
LIMIT 20;
```

Results show small but consistent drift in most active accounts.

**14:00 UTC** - Traced P&L calculation path

Relevant code paths:
- `internal/risk/calculator.go` - Calculates position P&L
- `internal/positions/tracker.go` - Tracks position changes
- `internal/portfolio/manager.go` - Aggregates portfolio value
- `pkg/decimal/decimal.go` - Decimal arithmetic library

### Day 2 - Deeper Analysis

**09:00 UTC** - Wrote test to reproduce

```go
func TestPrecisionLoss(t *testing.T) {
    // Simulate 10,000 small trades
    total := 0.0
    for i := 0; i < 10000; i++ {
        // Typical trade: 100 shares at $45.67
        tradeValue := 100.0 * 45.67
        fee := tradeValue * 0.0001 // 1 basis point
        total += tradeValue - fee
    }
    expected := 45665433.00 // Known correct value
    diff := math.Abs(total - expected)
    t.Logf("Difference after 10k trades: $%.6f", diff)
}
```

Test shows drift of ~$0.04 after 10,000 trades.

**11:30 UTC** - Found suspicious patterns in code

Observed in multiple files:
- Position quantities stored as `float64`
- Prices stored as `float64`
- P&L calculated using float arithmetic
- Some code converts between types inconsistently

Example from logs:
```
DEBUG position update: quantity=100.00000000000001 (should be 100)
DEBUG price lookup: got 45.670000000000002 (should be 45.67)
DEBUG pnl calc: result=4567.0000000000009
```

**15:00 UTC** - Reviewed decimal package

The `pkg/decimal` package exists but appears to have issues:
- Some functions use `float64` internally
- Conversions between types may lose precision
- Rounding behavior seems inconsistent

### Symptoms Catalog

1. **Small cumulative errors**: Errors are typically $0.01-$0.10 per trade, accumulating over time
2. **High-volume accounts affected most**: More trades = more accumulated error
3. **Fee calculations inconsistent**: Sometimes fees are $0.01 off
4. **Margin calculations occasionally wrong**: Risk limits trigger incorrectly by small amounts
5. **P&L display shows many decimal places**: Values like `1234.5600000000001` in logs

### Affected Areas

- Portfolio value calculation
- P&L reporting
- Margin requirement calculation
- Fee calculation
- Position quantity tracking
- Trade execution price recording

### Test Results

```
=== RUN   TestDecimalPrecision
    decimal_test.go:45: 0.1 + 0.2 = 0.30000000000000004 (expected 0.3)
    decimal_test.go:52: After 1000 additions of 0.01: 9.999999999999831 (expected 10.0)
--- FAIL: TestDecimalPrecision (0.01s)

=== RUN   TestMarginCalculation
    calculator_test.go:89: Margin for $100,000 position at 10% rate
    calculator_test.go:90: Expected: $10,000.00, Got: $9,999.999999999998
--- FAIL: TestMarginCalculation (0.00s)

=== RUN   TestFeeCalculation
    decimal_test.go:78: Fee on $45,670 trade at 0.01%
    decimal_test.go:79: Expected: $4.567, Got: $4.566999999999999
--- FAIL: TestFeeCalculation (0.00s)
```

### Key Questions

1. Why is `float64` being used for financial calculations?
2. Is the decimal package being used correctly?
3. Are there type conversions that introduce precision loss?
4. Is there a rounding mode inconsistency between components?

### Files to Review

- `pkg/decimal/decimal.go` - Decimal arithmetic implementation
- `internal/risk/calculator.go` - Risk and margin calculations
- `internal/positions/tracker.go` - Position P&L tracking
- `internal/portfolio/manager.go` - Portfolio aggregation

### Customer Impact

- Financial reporting inaccuracies
- Regulatory compliance concerns (must report accurate values)
- Customer trust issues
- Potential margin call discrepancies

## Status

**Awaiting**: Engineering fix for precision issues across financial calculation paths
