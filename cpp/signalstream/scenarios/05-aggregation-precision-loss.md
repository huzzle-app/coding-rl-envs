# Support Ticket: Incorrect Aggregation Results

## Zendesk Ticket #58234

**Priority**: High
**Customer**: GlobalMetrics Analytics (Enterprise)
**Account Value**: $180,000 ARR
**Created**: 2024-01-25 10:30 UTC
**Status**: Escalated to Engineering

---

## Customer Report

> We've been using SignalStream for real-time financial aggregations and we're seeing incorrect results. Our compliance team flagged discrepancies between SignalStream aggregations and our batch validation system. The differences are small but consistent, and for regulatory reporting we need exact precision.

### Specific Issues Reported

1. **Sum aggregations drift over time**: Running totals lose precision
2. **Average calculations show impossible values**: Sometimes negative or NaN
3. **Window boundaries seem off by one**: 5-minute windows include 4m59s or 5m01s of data
4. **Comparisons fail unexpectedly**: Values that should match don't

---

## Technical Investigation

### Issue 1: Running Sum Precision Loss

Customer provided test case:
```
Input stream (1000 values, each = 0.1):
  0.1, 0.1, 0.1, ... (1000 times)

Expected sum: 100.0
SignalStream result: 99.99999999999859

Difference: 0.00000000000141 (after just 1000 values!)
```

After 1 million values, the drift becomes significant:
```
Expected: 100000.0
Actual: 99998.47236491
Drift: 1.527 (0.0015% error, but unacceptable for financial compliance)
```

**Engineering Analysis**:
The aggregation service appears to use naive summation instead of a compensated algorithm (like Kahan summation). Floating-point rounding errors accumulate.

---

### Issue 2: Integer Overflow in Accumulation

When aggregating large values:
```
Input stream: [2^62, 2^62, 2^62]

Expected sum: 3 * 2^62 = 13835058055282163712
Actual result: -4611686018427387904 (NEGATIVE?!)
```

**Engineering Analysis**:
Log output shows:
```
2024-01-25T10:45:00Z [aggregate] Accumulating: 4611686018427387904
2024-01-25T10:45:00Z [aggregate] Current sum: 4611686018427387904
2024-01-25T10:45:00Z [aggregate] After add: -4611686018427387904
2024-01-25T10:45:00Z [WARN] Unexpected sign change in accumulation
```

Signed integer overflow is occurring and wrapping to negative values.

---

### Issue 3: Float Equality Comparison Failures

Customer's data pipeline checks for duplicate values:
```
Value A: 0.1 + 0.2 = 0.30000000000000004
Value B: 0.3

Comparison: A == B ? false
Expected: true (within floating-point tolerance)
```

Log output:
```
2024-01-25T11:00:00Z [aggregate] Checking equality: 0.30000000000000004 == 0.3
2024-01-25T11:00:00Z [aggregate] Result: NOT EQUAL
2024-01-25T11:00:00Z [WARN] Duplicate detection failed - treating as unique
```

No epsilon tolerance is used in floating-point comparisons.

---

### Issue 4: NaN Propagation

When processing streams with occasional invalid data:
```
Input: [10.0, 20.0, NaN, 30.0, 40.0]

Expected average (ignoring NaN): (10+20+30+40)/4 = 25.0
Actual average: NaN
```

Log output:
```
2024-01-25T11:15:00Z [aggregate] Processing value: 10.0, running_sum: 10.0
2024-01-25T11:15:00Z [aggregate] Processing value: 20.0, running_sum: 30.0
2024-01-25T11:15:00Z [aggregate] Processing value: NaN, running_sum: NaN
2024-01-25T11:15:00Z [aggregate] Processing value: 30.0, running_sum: NaN
2024-01-25T11:15:00Z [aggregate] Final average: NaN
```

NaN values are not being filtered before aggregation.

---

### Issue 5: Window Boundary Off-by-One

5-minute aggregation windows show inconsistent boundaries:
```
Window 1: 10:00:00.000 - 10:04:59.999 (should end at 10:05:00.000?)
Window 2: 10:05:00.001 - 10:09:59.999 (0.001ms gap!)

Events at exactly 10:05:00.000 are sometimes:
- Included in Window 1
- Included in Window 2
- Dropped entirely (!)
```

Log output:
```
2024-01-25T10:04:59.999Z [aggregate] Event in window 1
2024-01-25T10:05:00.000Z [aggregate] Event boundary check: t >= start && t < end
2024-01-25T10:05:00.000Z [aggregate] Window 1 end: 10:05:00.000, Event: 10:05:00.000
2024-01-25T10:05:00.000Z [aggregate] 10:05:00.000 < 10:05:00.000 ? false
2024-01-25T10:05:00.000Z [aggregate] Event NOT in window 1
2024-01-25T10:05:00.000Z [aggregate] Window 2 start: 10:05:00.001
2024-01-25T10:05:00.000Z [aggregate] 10:05:00.000 >= 10:05:00.001 ? false
2024-01-25T10:05:00.000Z [aggregate] Event NOT in window 2 either!
2024-01-25T10:05:00.000Z [ERROR] Event dropped - not in any window
```

---

### Issue 6: std::accumulate Type Truncation

When computing averages of double values:
```cpp
// Pseudo-code observation from logs
std::accumulate(values.begin(), values.end(), 0)  // Initial value is int!
// Result: doubles are truncated to int before summation
```

Log output:
```
2024-01-25T11:30:00Z [aggregate] Values: [1.7, 2.3, 3.9]
2024-01-25T11:30:00Z [aggregate] Sum: 6 (expected 7.9)
2024-01-25T11:30:00Z [aggregate] Count: 3
2024-01-25T11:30:00Z [aggregate] Average: 2 (expected 2.633...)
```

---

### Issue 7: Thread-Local Storage Destruction Order

Aggregation workers crash during shutdown:
```
2024-01-25T12:00:00Z [aggregate] Shutting down aggregation worker pool...
2024-01-25T12:00:00Z [aggregate] Worker thread 3 cleaning up...
2024-01-25T12:00:01Z [FATAL] Segmentation fault in TLS destructor

Stack trace:
#0 AggregationContext::~AggregationContext() at aggregate/context.cpp:45
#1 __call_tls_dtors() at /lib/libc.so.6
#2 __pthread_cleanup_routine() at /lib/libpthread.so.0
```

Thread-local storage is being destroyed in the wrong order, causing use-after-free.

---

## Impact Assessment

- **Financial Accuracy**: Aggregations off by up to 0.002% for running sums
- **Regulatory Risk**: Compliance reports may contain incorrect totals
- **Data Integrity**: Events at window boundaries being dropped
- **Service Stability**: Workers crashing on shutdown

---

## Questions for Investigation

1. Why doesn't the running sum use compensated summation (Kahan)?
2. Why are large integers allowed to overflow without detection?
3. Why do float comparisons use exact equality instead of epsilon?
4. Why isn't NaN filtered before aggregation?
5. Why is the window boundary check using `<` instead of `<=` (or vice versa)?
6. Why does std::accumulate use an int initial value for double data?
7. Why is TLS destruction order causing crashes?

---

## Files to Investigate

Based on symptoms:
- `src/services/aggregate/aggregate.cpp` - Summation, overflow, NaN handling
- `src/services/aggregate/window.cpp` - Window boundary logic
- `src/services/aggregate/accumulator.cpp` - std::accumulate usage
- `src/services/aggregate/worker.cpp` - TLS destruction

---

**Status**: INVESTIGATING
**Assigned**: @numerics-team
**SLA**: Fix required within 48 hours for compliance deadline
