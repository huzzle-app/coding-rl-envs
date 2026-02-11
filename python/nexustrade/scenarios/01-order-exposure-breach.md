# Scenario 01: Customer Exceeds Risk Limits on Rapid-Fire Orders

**Severity**: P1 (Critical)
**Reported By**: Risk Management Team
**Date**: Tuesday, 10:47 AM EST

---

## Incident Summary

A hedge fund client exceeded their $50M exposure limit by over $8M during a volatile market session. The risk management system was supposed to prevent orders that would breach the limit.

## Symptoms

### Primary Complaint
- Customer "Apex Trading Partners" has a configured maximum exposure limit of $50,000,000
- At 10:32 AM, during a market spike, they submitted multiple large orders within a 200ms window
- All orders were accepted and executed
- Total exposure reached $58,234,000 before our systems flagged it
- Customer should have been blocked at $50M

### Observed Behaviors

1. **Individual orders passed risk checks**:
   ```
   Order 1: BUY 5000 AAPL @ $195.50 -> Risk check: APPROVED
   Order 2: BUY 3000 MSFT @ $412.00 -> Risk check: APPROVED
   Order 3: BUY 2000 GOOGL @ $175.25 -> Risk check: APPROVED
   [... 12 more orders in rapid succession ...]
   ```

2. **Risk service logs show each order passing individually**:
   ```
   [10:32:01.123] check_order_risk: user=apex-trading, current_exposure=$42M, order_value=$1.5M -> approved
   [10:32:01.145] check_order_risk: user=apex-trading, current_exposure=$42M, order_value=$1.2M -> approved
   [10:32:01.167] check_order_risk: user=apex-trading, current_exposure=$42M, order_value=$2.1M -> approved
   ```

3. **Exposure update appears to lag behind order creation**:
   - All 15 orders show `current_exposure=$42M` in risk logs
   - Final exposure snapshot shows $58.2M

4. **No errors in service logs**:
   - Risk service returned 200 OK for all checks
   - Orders service processed all orders successfully
   - Settlement pipeline accepted all trades

### Timing Correlation
- Issue only occurs when orders arrive within ~50-200ms of each other
- Single orders or orders spaced >1 second apart correctly update exposure
- High-frequency trading clients are most affected

## Impact

- **Financial**: Potential $8M+ in losses if positions move adversely
- **Regulatory**: SEC/FINRA requires real-time exposure controls
- **Trust**: Client claims this violates our service agreement

## Initial Investigation

### What We've Ruled Out
- Network issues (all services healthy, <5ms latency)
- Database bottlenecks (Postgres replica lag <10ms)
- Kafka message ordering (events arrive in sequence)

### Suspicious Observations
1. The `_exposure_cache` in risk service shows the same value for concurrent requests
2. No distributed lock acquisition logs visible for exposure updates
3. Orders service and risk service appear to operate without coordination

### Relevant Code Paths
- `services/risk/views.py` - check_order_risk endpoint
- `services/orders/views.py` - create_order endpoint
- `shared/events/risk.py` - exposure event handling

## Reproduction Steps

1. Configure a test user with $100,000 max exposure
2. Submit 5 orders of $30,000 each within 100ms
3. Expected: Orders 1-3 accepted, orders 4-5 rejected (would exceed limit)
4. Actual: All 5 orders accepted, $150,000 total exposure

## Questions for Investigation

- How does the risk service track current exposure between concurrent requests?
- Is there a caching layer between real-time exposure and the risk check?
- What synchronization exists between the orders and risk services?
- Are exposure updates atomic with order creation?

---

**Status**: Unresolved
**Assigned**: Platform Engineering
**SLA**: 4 hours (P1)
