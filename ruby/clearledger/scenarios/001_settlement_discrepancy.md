# Incident Report: Settlement Netting Ratio Discrepancy

**Incident ID**: INC-2024-0892
**Severity**: P1 - Critical
**Status**: Open
**Reported By**: Risk Operations Team
**Date**: 2024-01-15 14:32 UTC

---

## Summary

End-of-day settlement reports are showing materially incorrect netting ratios across all clearing accounts. The settlement dashboard displays netting efficiency of 0% for accounts that should show 60-80% netting based on bilateral offset activity.

## Timeline

- **14:15 UTC**: Daily settlement batch completes for EU jurisdiction
- **14:22 UTC**: Risk analyst notices netting ratio dashboard showing 0.0 for all counterparties
- **14:28 UTC**: Manual spot-check confirms gross exposure of $4.2M and net exposure of $1.8M, but `netting_ratio` returns 0
- **14:32 UTC**: Incident escalated to engineering

## Observed Behavior

### Dashboard Metrics
```
Account: ACME-CORP
  Gross Exposure: $4,200,000.00
  Net Exposure:   $1,800,000.00
  Netting Ratio:  0.0  <-- INCORRECT
  Expected:       ~0.43
```

### Additional Symptoms

1. **Health Score Calculation**: The resilience health_score metric is also returning 0 even when we have 847 successes and 153 failures (expected ~0.85)

2. **Exposure Ratio Truncation**: Risk gate exposure ratios are coming back as whole numbers only:
   - Gross: 15,500,000, Collateral: 3,200,000
   - Expected ratio: ~4.84
   - Actual ratio: 4

3. **Audit Score Zero**: Compliance audit scoring shows 0.0 even with 94 compliant entries out of 100 total

## Impact

- Settlement netting optimization disabled (trading at gross instead of net)
- Risk dashboards unreliable for intraday monitoring
- Regulatory reporting delayed pending manual correction
- Estimated excess margin requirement: $2.4M

## Troubleshooting Attempted

- Verified input data integrity (confirmed correct)
- Restarted settlement service (no change)
- Checked for nil/empty inputs (all populated with valid numbers)
- Confirmed calculations work in REPL with floating point: `1800.0 / 4200.0 => 0.428...`

## Logs

```
2024-01-15 14:22:31.445 [settlement] netting_ratio calculated: gross=4200000 net=1800000 result=0
2024-01-15 14:22:31.447 [risk_gate] exposure_ratio calculated: gross=15500000 collateral=3200000 result=4
2024-01-15 14:22:31.452 [resilience] health_score calculated: successes=847 failures=153 result=0
2024-01-15 14:22:31.458 [audit_chain] audit_score calculated: compliant=94 total=100 result=0
```

## Questions for Engineering

1. Why would ratio calculations return 0 when both numerator and denominator are valid positive numbers?
2. Is there a type coercion issue affecting division operations?
3. Are multiple modules affected by the same root cause?

## Acceptance Criteria for Resolution

- [ ] Netting ratio returns correct floating-point values (e.g., 0.428 not 0)
- [ ] Health score returns correct ratio (e.g., 0.847 not 0)
- [ ] Exposure ratio returns precise values (e.g., 4.84 not 4)
- [ ] Audit score returns correct percentage (e.g., 0.94 not 0)
- [ ] All affected ratio calculations verified across settlement, risk, resilience, and audit modules
