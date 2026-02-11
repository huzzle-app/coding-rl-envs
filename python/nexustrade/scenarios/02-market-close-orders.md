# Scenario 02: Orders Executed After Market Close

**Severity**: P2 (High)
**Reported By**: Compliance Team
**Date**: Friday, 5:23 PM EST

---

## Incident Summary

Multiple customer orders were executed at exactly 4:00:00 PM EST, which should be rejected as the NYSE market closes at 4:00 PM. Additionally, some orders placed around the DST transition weekend showed anomalous behavior.

## Symptoms

### Primary Complaint

1. **Orders at exactly market close are being accepted**:
   ```
   Order ID: ord-7d3f8c2a
   Symbol: SPY
   Submitted: 2024-03-15 16:00:00.000 EST
   Status: FILLED
   Expected: REJECTED (market closed)
   ```

2. **DST transition orders are incorrectly handled**:
   - Orders submitted at 3:45 PM EDT on the Sunday after DST "spring forward" were rejected
   - System appears to think market is closed when it should be open

### Observed Behaviors

1. **Matching engine logs show orders at 4:00 PM accepted**:
   ```
   [16:00:00.005] Received order ord-7d3f8c2a for SPY
   [16:00:00.008] is_market_open() returned True
   [16:00:00.012] Order added to book, matched against bid
   [16:00:00.015] Trade executed: trade-9e2a1b3c
   ```

2. **Comparison in is_market_open appears too permissive**:
   ```python
   # From matching engine debug logs:
   eastern_time = 16:00:00
   market_close = 16:00:00
   comparison result: True (order accepted)
   ```

3. **Eastern timezone offset is hardcoded**:
   ```
   During EST: UTC-5 (correct)
   During EDT: UTC-5 (should be UTC-4)
   ```

### DST-Related Issues

- During EDT (Daylight Time), the system uses EST offset (-5 hours)
- This causes a 1-hour discrepancy in market hour calculations
- Orders at 3:30 PM EDT are sometimes rejected as "before market open"
- Orders at 4:30 PM EDT are sometimes accepted as "during market hours"

### Affected Time Windows

| Actual Time (EDT) | System Thinks | Result |
|-------------------|---------------|--------|
| 9:30 AM | 8:30 AM | Incorrectly rejected |
| 4:00 PM | 3:00 PM | Incorrectly accepted |
| 4:30 PM | 3:30 PM | Incorrectly accepted |

## Impact

- **Regulatory**: FINRA Rule 4560 requires accurate trade timestamps
- **Financial**: After-hours trades have different settlement rules
- **Customer**: Users confused when valid orders are rejected

## Initial Investigation

### What We've Ruled Out
- Server clock drift (NTP synchronized, <100ms drift)
- Database timestamp issues (all timestamps are UTC)
- Kafka message delays (sub-millisecond latency)

### Suspicious Observations
1. Hardcoded timezone offset in `shared/utils/time.py`
2. No use of `pytz` or `zoneinfo` for proper DST handling
3. Boundary condition at exactly 4:00 PM uses `<=` instead of `<`
4. Settlement date calculation also ignores weekends/holidays

### Relevant Code Paths
- `shared/utils/time.py` - is_market_open function
- `services/matching/main.py` - order validation before matching
- `shared/utils/time.py` - get_settlement_date function

## Reproduction Steps

### Edge Case Test
1. Set system time to 15:59:59 EST
2. Submit a limit order
3. Wait until clock shows 16:00:00.000
4. Submit another limit order
5. Expected: Second order rejected
6. Actual: Second order accepted

### DST Test
1. Set system time to first Sunday in March, 2:00 AM EST
2. Spring forward to 3:00 AM EDT
3. At 9:30 AM EDT, submit order
4. Expected: Order accepted (market open)
5. Actual: Order rejected (system thinks it's 8:30 AM)

## Questions for Investigation

- How is the Eastern timezone offset determined?
- Does the market hours check use `<` or `<=` for the close time?
- Is there handling for market holidays?
- Why is settlement date calculation adding calendar days instead of business days?

---

**Status**: Unresolved
**Assigned**: Trading Systems Team
**SLA**: 24 hours (P2)
