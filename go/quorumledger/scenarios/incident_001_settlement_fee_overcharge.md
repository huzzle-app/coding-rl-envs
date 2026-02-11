# INCIDENT-001: Settlement Fee Overcharges Causing Client Disputes

**Severity**: P1 - Critical
**Status**: Open
**Reported By**: Treasury Operations
**Date**: 2024-03-15 09:42 UTC
**Affected Systems**: Settlement Service, Netting Engine

---

## Executive Summary

Multiple institutional clients have reported discrepancies in their settlement fees. Preliminary analysis indicates fees are being calculated at approximately 10x the contracted rate. Finance has flagged $2.3M in potential overcharges across 847 settlements in the past 72 hours.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 2024-03-12 14:00 | First client complaint received (Meridian Capital) |
| 2024-03-13 09:30 | Additional complaints from 4 more clients |
| 2024-03-14 16:00 | Finance escalates after reconciliation finds pattern |
| 2024-03-15 09:42 | Incident declared, engineering engaged |

---

## Symptoms Observed

1. **Fee amounts are 10x expected value**
   - Client settled $1,000,000 at 25bp rate
   - Expected fee: $2,500
   - Actual charged: $25,000

2. **Affected test scenarios**:
   ```
   --- FAIL: TestSettlementFee
       settlement_test.go:34: expected fee 2500 (25bp on 1M), got 25000
   ```

3. **Pattern is consistent across all fee calculations**
   - Not a rounding error
   - Not currency conversion issue
   - Multiplier appears to be exactly 10x

---

## Sample Log Output

```
2024-03-15T08:23:41Z INFO  settlement/netting: computing fee batch_id=BT-29847
2024-03-15T08:23:41Z INFO  settlement/netting: principal=1000000 bps=25
2024-03-15T08:23:41Z INFO  settlement/netting: calculated_fee=25000
2024-03-15T08:23:41Z WARN  reconciliation/drift: fee_variance threshold_exceeded=true
```

---

## Business Impact

- **Financial**: $2.3M in disputed fees, potential refunds required
- **Reputational**: 5 institutional clients threatening to exit
- **Compliance**: Overcharging violates fee schedule in MSAs
- **Operational**: Settlement reconciliation workflow halted pending investigation

---

## Investigation Notes

The settlement fee function should apply basis points (1bp = 0.01% = 1/10000). Review the fee calculation logic in the netting module. The divisor used to convert basis points to a decimal appears to be incorrect.

---

## Related Failures

The following tests are also failing in CI, possibly related:

```
--- FAIL: TestOptimalBatching
    settlement_test.go:44: expected 3 batches, got 1

--- FAIL: TestSettlementFlowIntegration
    settlement_flow_test.go:18: unexpected settlement balance
```

---

## Stakeholders

- Treasury Operations (incident owner)
- Client Success (client communication)
- Finance (refund coordination)
- Legal (MSA compliance review)
- Engineering (root cause analysis)

---

## Action Required

Identify and fix the fee calculation defect. All settlement processing is suspended until resolution. Hotfix required within 4 hours.
