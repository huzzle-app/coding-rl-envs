# Incident Report: INC-2024-1847

**Severity**: P1 - Critical
**Status**: Open
**Reported By**: Operations Center - STRATAGUARD-OPS
**Date**: 2024-11-15 03:42 UTC
**Affected System**: StrataGuard Dispatch Allocation Engine

---

## Executive Summary

Critical dispatch orders are being placed behind lower-priority orders in the allocation queue, causing SLA breaches on emergency response incidents. Multiple high-severity cyber incidents are experiencing delayed response times despite available capacity.

## Timeline

- **03:12 UTC**: SOC receives critical APT intrusion alert (Severity 5, SLA 15min)
- **03:14 UTC**: Dispatch system allocates response team
- **03:18 UTC**: Secondary medium-priority incident (Severity 3, SLA 60min) submitted
- **03:19 UTC**: Team observes medium-priority incident processed before critical
- **03:42 UTC**: P1 incident declared after third occurrence observed

## Symptoms

1. `Allocator.SortByPriority()` returns orders in unexpected sequence
2. Lower urgency scores appearing at top of sorted dispatch lists
3. Test `SortByPriorityDescending` failing with assertion:
   ```
   Expected: "b" (urgency=5)
   Actual first element: "a" (urgency=1)
   ```

## Impact

- **Financial**: Estimated $2.3M in SLA penalty exposure
- **Operational**: 7 critical incidents experienced delayed dispatch
- **Regulatory**: Potential CISA compliance violation for response times

## Affected Tests

```
FAILED: ExtendedTests.SortByPriorityDescending
FAILED: HyperMatrixTests.HyperMatrixCase (bucket=9, indices 9,29,49,...)
```

## Log Excerpt

```
2024-11-15T03:19:22.847Z [WARN] dispatch.allocator: Sort order anomaly detected
  expected_first_urgency=5 actual_first_urgency=1
  order_ids=["a","b","c"] urgencies=[1,5,3]

2024-11-15T03:19:22.848Z [ERROR] dispatch.sla: SLA breach imminent
  order_id="b" sla_remaining_ms=312000 position_in_queue=2

2024-11-15T03:42:15.001Z [ALERT] ops.escalation: P1 incident declared
  incident_id=INC-2024-1847 root_cause="priority_inversion"
```

## Reproduction

```csharp
var orders = Allocator.SortByPriority([
    new DispatchOrder("a", 1, 60),  // Low priority
    new DispatchOrder("b", 5, 60),  // Critical priority
    new DispatchOrder("c", 3, 60)   // Medium priority
]);
// Expected: b, c, a (descending by urgency)
// Actual: a, c, b (ascending - inverted!)
```

## Business Context

The dispatch allocation system must process highest-urgency incidents first to meet contractual SLA requirements. A priority inversion causes:
- Critical APT responses delayed by routine vulnerability scans
- Emergency containment teams assigned to lower-priority tasks
- Cascading delays across the incident queue

## Investigation Notes

The sort appears to be using the wrong ordering direction. Engineering should review the `OrderBy` vs `OrderByDescending` usage in the allocation pipeline.

---

**Assigned To**: Platform Engineering
**Target Resolution**: 2024-11-15 06:00 UTC
**Escalation Contact**: @incident-commander
