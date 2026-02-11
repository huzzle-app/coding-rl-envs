# Customer Escalation: Position Data Corruption and Reconciliation Failures

## Zendesk Ticket #89234

**Priority**: Urgent
**Customer**: Apex Capital Partners (Institutional Tier)
**Account Value**: $1.2M ARR
**CSM**: Michael Torres
**Created**: 2024-03-27 08:45 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We're experiencing serious issues with position tracking. Our back-office reconciliation is failing daily, and we're seeing positions that don't match our actual holdings. This is affecting our risk management and reporting. We need this fixed immediately - we have regulatory reporting deadlines.

### Reported Symptoms

1. **Position Quantity Mismatches**: End-of-day positions don't match trade history
2. **Missing Fills**: Some fills appear to be dropped or not recorded
3. **Duplicate Events**: Occasionally seeing the same fill applied twice
4. **Snapshot Corruption**: Position snapshots contain inconsistent data
5. **Event Replay Failures**: Replaying events from log produces different results

---

## Reconciliation Report

```
Date: 2024-03-26
Account: APEX-MAIN

Symbol   Expected Qty   QuantumCore Qty   Difference   Status
----------------------------------------------------------------
AAPL     +15,000        +15,002           +2           MISMATCH
MSFT     -8,000         -7,998            +2           MISMATCH
GOOGL    +3,500         +3,500            0            OK
NVDA     +12,000        +11,997           -3           MISMATCH
TSLA     -5,000         -5,001            -1           MISMATCH
AMZN     +7,500         +7,500            0            OK
META     +4,200         +4,203            +3           MISMATCH

Total Discrepancies: 5 of 7 positions (71.4%)
Net Quantity Error: +2 units
```

## Event Log Analysis

Engineering extracted the event log for one problematic position:

```
Symbol: AAPL
Expected final quantity: +15,000

Event Log (ordered by timestamp):
---------------------------------
Event #1001 | 09:30:00.123 | Opened | +5,000 @ $185.50
Event #1002 | 09:45:12.456 | Increased | +3,000 @ $185.75
Event #1003 | 10:15:33.789 | Increased | +2,000 @ $186.00
Event #1004 | 11:30:45.012 | Decreased | -1,000 @ $186.50 (realized: +$500)
Event #1005 | 14:00:22.345 | Increased | +6,000 @ $185.25

Sum from events: 5000 + 3000 + 2000 - 1000 + 6000 = 15,000 (CORRECT)
Actual stored quantity: 15,002 (INCORRECT)
```

### Event Ordering Anomaly

When we examined the event log more closely, we found events with out-of-order sequence numbers:

```
Events sorted by sequence number:
Event #1001 (seq: 45023) | 09:30:00.123
Event #1003 (seq: 45024) | 10:15:33.789  <- Arrived before #1002?
Event #1002 (seq: 45025) | 09:45:12.456  <- Out of order!
Event #1004 (seq: 45026) | 11:30:45.012
Event #1005 (seq: 45027) | 14:00:22.345

Note: Events #1002 and #1003 have swapped sequence numbers
Their timestamps show #1002 happened first, but sequence says #1003
```

## Snapshot Investigation

We captured a position snapshot during active trading and found inconsistencies:

```
Snapshot taken at: 14:30:00.000 UTC
Last event ID in snapshot: 45100

Problems found:
- Account APEX-MAIN, Symbol NVDA:
  - Snapshot quantity: 11,997
  - Events up to #45100 sum to: 12,000
  - Difference: -3 units

- Event #45098 timestamp: 14:30:00.050 (AFTER snapshot timestamp)
  - But event is included in snapshot!
  - Snapshot captured mid-modification
```

## Race Condition Evidence

QA was able to capture this log sequence showing concurrent modification:

```
Thread-A 14:30:00.001: Reading position NVDA for snapshot
Thread-B 14:30:00.002: Applying fill to NVDA (+100 @ $875.50)
Thread-A 14:30:00.003: Position read complete, qty=11,997
Thread-B 14:30:00.004: Fill applied, qty=12,097
Thread-A 14:30:00.005: Writing snapshot with qty=11,997
Thread-B 14:30:00.006: Incrementing version to 4523

Result: Snapshot has qty=11,997, but version 4523 should have qty=12,097
```

## Event Sourcing Failure

When attempting to rebuild state from events:

```rust
// Attempted replay from events
let events = fetch_events(account_id)?;
let rebuilt_positions = tracker.rebuild_from_events(&events)?;

// Result:
AAPL: Rebuilt=15,002, Current=15,002, Expected=15,000 (ALL WRONG)

// The bug: Events are sorted by timestamp, not sequence number
// Clock skew between servers causes events to be applied out of order
```

---

## Internal Slack Thread

**#positions-oncall** - March 27, 2024

**@oncall.david** (09:00):
> Apex Capital is on fire. Their positions don't match reality.

**@dev.lisa** (09:05):
> Looking at their event log. Events are being recorded but the sequence numbers are not monotonically increasing with timestamps.

**@oncall.david** (09:07):
> How is that possible? We use an atomic counter for sequences.

**@dev.lisa** (09:10):
> The counter is atomic, but we're using Relaxed ordering. Under high concurrency, two threads can get sequences out of order relative to when they actually applied the fill.

**@dev.marcus** (09:15):
> That explains the event ordering issues. But what about the snapshot corruption?

**@dev.lisa** (09:18):
> The snapshot code iterates over DashMap without any coordination. While we're taking the snapshot, other threads are modifying positions. We're capturing a point-in-time that never actually existed.

**@dev.marcus** (09:20):
> So the snapshot has some positions from T0 and some from T1? That's bad.

**@dev.lisa** (09:22):
> Exactly. And the rebuild_from_events function sorts by timestamp instead of sequence, so it makes things worse when clocks are skewed.

**@lead.james** (09:25):
> We need version checks on position updates. If the version doesn't match expected, reject the update and retry.

**@dev.lisa** (09:28):
> That's optimistic locking. Would work but need to refactor the update path.

---

## Reproduction Steps

Engineering reproduced with this test:

```bash
# Start position service
cargo run --bin positions-service

# Hammer with concurrent fills
for i in {1..10}; do
  (
    for j in {1..100}; do
      curl -X POST localhost:8005/fill \
        -d '{"account":"TEST","symbol":"AAPL","qty":1,"price":"185.50"}'
    done
  ) &
done
wait

# Check final position
curl localhost:8005/position/TEST/AAPL
# Expected: +1000
# Actual: varies between 997-1003 depending on race conditions
```

## Customer Impact

- **Regulatory risk**: Cannot file accurate position reports
- **Risk management**: Wrong position data leads to wrong risk calculations
- **P&L accuracy**: If positions are wrong, P&L is wrong
- **Trust**: Customer questioning data integrity of entire platform

## Files to Investigate

Based on investigation:
- `services/positions/src/tracker.rs` - Position updates, event logging, snapshots
- `services/positions/src/pnl.rs` - P&L calculations dependent on position accuracy
- Any code using atomic operations with `Ordering::Relaxed`

---

**Status**: CRITICAL - INVESTIGATING
**Assigned**: @positions-team, @data-integrity-team
**Customer Call**: Scheduled for March 28, 2024 09:00 UTC
**Deadline**: Fix required within 72 hours per SLA
