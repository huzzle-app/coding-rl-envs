# Compliance Alert: Financial Calculation Discrepancies

## Risk Management System Alert

**Priority**: High
**Generated**: 2024-03-18 09:15:00 UTC
**Source**: Daily Reconciliation Process
**Team**: Risk & Compliance

---

## Executive Summary

Our daily reconciliation process detected discrepancies between QuantumCore's calculated values and the back-office system. The discrepancies are small but consistent, and they compound over time. This affects margin calculations, P&L reporting, and Value-at-Risk (VaR) computations.

## Discrepancy Details

### Margin Requirement Calculations

| Account | QC Margin | Back-Office Margin | Difference | % Diff |
|---------|-----------|-------------------|------------|--------|
| ACC-001 | $45,234.17 | $45,234.19 | -$0.02 | 0.00004% |
| ACC-002 | $128,991.03 | $128,991.08 | -$0.05 | 0.00004% |
| ACC-003 | $892,445.61 | $892,445.89 | -$0.28 | 0.00003% |
| ACC-004 | $2,341,892.14 | $2,341,893.02 | -$0.88 | 0.00004% |
| **Total** | **$3,408,562.95** | **$3,408,564.18** | **-$1.23** | **0.00004%** |

### P&L Calculations

```
Account: ACC-003 (Multi-asset hedge fund)
Position: AAPL - Long 10,000 shares

QuantumCore Calculated Unrealized P&L: $15,234.17
Back-Office Calculated Unrealized P&L: $15,234.23
Difference: -$0.06

Position: TSLA - Short 5,000 shares
QuantumCore Calculated Unrealized P&L: -$8,291.44
Back-Office Calculated Unrealized P&L: -$8,291.39
Difference: -$0.05
```

### Value-at-Risk (VaR) Calculations

```
Portfolio: FUND-ALPHA (95% VaR)
QuantumCore VaR: $1,234,567.89
Risk Model VaR:  $1,234,582.13
Difference: -$14.24 (0.0012%)

Portfolio: FUND-BETA (99% VaR)
QuantumCore VaR: $2,891,234.56
Risk Model VaR:  $2,891,289.91
Difference: -$55.35 (0.0019%)
```

## Pattern Analysis

The discrepancies have these characteristics:

1. **Always negative** - QuantumCore consistently underestimates values
2. **Proportional to portfolio size** - Larger portfolios have larger absolute differences
3. **Accumulates over time** - Difference grows with number of trades
4. **Affects complex calculations more** - VaR discrepancies are larger than simple margin

## Investigation Findings

### Code Review Observations

Our initial code review found several concerning patterns in the risk calculation code:

```rust
// From risk/calculator.rs - snippet shared by dev team
let position_value = position.quantity.abs() as f64 * price.to_string().parse::<f64>().unwrap_or(0.0);
let volatility = self.volatilities.get(symbol).map(|v| *v).unwrap_or(0.02);
let margin = position_value * volatility * 2.5;
total_margin += margin;
```

The pattern of converting `Decimal` to `f64` via string parsing, then back to `Decimal`, appears multiple times.

### Precision Loss Demonstration

Engineering provided this demonstration:

```rust
// Test case showing precision loss
let price = Decimal::from_str("100.10").unwrap();
let qty = 10000i64;

// Current approach (buggy)
let value_f64 = qty.abs() as f64 * price.to_string().parse::<f64>().unwrap();
let result_buggy = Decimal::from_f64_retain(value_f64);
// Result: 1001000.0000000001 (precision error!)

// Correct approach
let result_correct = price * Decimal::from(qty.abs());
// Result: 1001000.00 (exact)
```

## Regulatory Implications

Per SEC Rule 15c3-1 and FINRA Rule 4210:
- Margin calculations must be accurate
- Systematic underestimation could be considered a capital adequacy violation
- P&L reporting errors may require restatement of client statements

## Internal Slack Thread

**#risk-engineering** - March 18, 2024

**@compliance.alex** (09:20):
> Daily recon is flagging discrepancies again. Small amounts but consistent.

**@dev.marcus** (09:25):
> Let me check the calculation code. Are the discrepancies always in the same direction?

**@compliance.alex** (09:27):
> Always negative. QuantumCore always shows slightly less than back-office.

**@dev.marcus** (09:35):
> Found it. We're using f64 for intermediate calculations in the margin code. There's precision loss when converting between Decimal and f64.

**@dev.sarah** (09:40):
> Same pattern in VaR calculations. The whole covariance matrix calculation is done in f64.

**@risk.lead.chen** (09:45):
> This is a compliance issue. We can't underestimate margin requirements. Need a fix ASAP.

**@dev.marcus** (09:50):
> Looking at the code - this pattern is everywhere in the risk service. Someone used f64 because "it's faster" but for financial calculations we MUST use Decimal.

---

## Additional Observations

### Market Price Race Condition

We also noticed a race condition in margin checks:

```
Time T0: Check margin available = $100,000
Time T1: Another order consumes $50,000 margin (on different thread)
Time T2: Approve new order based on stale $100,000 (should have been $50,000)
```

This TOCTOU (time-of-check-time-of-use) pattern could lead to accounts being over-leveraged.

## Files to Investigate

Based on the patterns observed:
- `services/risk/src/calculator.rs` - Margin and VaR calculations
- `services/positions/src/pnl.rs` - P&L calculations
- Any code converting between `Decimal` and `f64`

## Recommended Actions

1. **Immediate**: Manual review of margin for all large accounts
2. **Short-term**: Add reconciliation alerts for any discrepancy > $0.01
3. **Long-term**: Refactor all financial calculations to use `rust_decimal` throughout

---

**Status**: UNDER INVESTIGATION
**Assigned**: @risk-engineering-team
**Compliance Review**: Required before production fix
**Deadline**: EOD March 19, 2024
