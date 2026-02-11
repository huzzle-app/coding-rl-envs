# PagerDuty Alert: Orders Stuck in Arrived State

**Alert ID:** PD-20241113-9827
**Severity:** P1 - Service Impact
**Triggered:** 2024-11-13 03:42 UTC
**Acknowledged:** 2024-11-13 03:45 UTC
**Responder:** On-call: Alex Thompson

---

## Alert Details

**Monitor:** order-state-watchdog
**Threshold:** > 100 orders in non-terminal state for > 2 hours
**Current Value:** 847 orders stuck

---

## Initial Investigation Log

### 03:45 UTC - Alex Thompson

Acknowledged alert. Checking order state distribution:

```
queued:     23
allocated:  156
departed:   41
arrived:    627  <- This is the problem
cancelled:  0
completed:  0
```

627 orders stuck in "arrived" state. They should transition to "completed" but they can't.

### 03:52 UTC - Alex Thompson

Checked the workflow state machine. The `graph` variable defines allowed transitions:

```
arrived -> {}  (empty set of valid transitions)
```

There's no transition from "arrived" to "completed". Orders reach the port but can't be marked complete.

### 03:58 UTC - Alex Thompson

Also noticing orders skipping the "queued" state entirely. When we register new orders without specifying initial state, they start in "allocated" instead of "queued". This is causing audit trail gaps:

```
Order ORD-99182:
  Expected history: queued -> allocated -> departed -> arrived
  Actual history:   allocated -> departed -> arrived
```

The intake/queue step is being bypassed.

### 04:10 UTC - Alex Thompson

Found another issue with state validation. The `IsValidState("completed")` function returns `true` even though "completed" isn't in the graph. This is because it also checks `terminalStates` which only contains "arrived" and "cancelled".

Wait... "completed" shouldn't be in terminalStates either. But the function accepts it because of how the OR condition works.

### 04:22 UTC - Alex Thompson

The `CanTransition` function has no guard for invalid states. Calling it with a non-existent "from" state causes a nil map access:

```go
CanTransition("nonexistent", "queued")
// Accesses graph["nonexistent"] which is nil
// Then accesses nil["queued"] which panics? No, returns false but silently
```

Actually it returns false silently which masks configuration errors.

### 04:35 UTC - Alex Thompson

`ShortestPath` has an edge case. When from == to, it returns a single-element path `[from]` instead of an empty path. This affects the path length calculations for SLA compliance.

---

## Related: Policy Engine Issues

From earlier investigation by @ops-team:

### Policy Escalation Sensitivity

The policy escalation appears too sensitive. A single failure (failureBurst=1) shouldn't escalate policy, but we're seeing escalations on single failures:

```
Current policy: normal
Failure burst: 1 (single failure)
Expected: Stay at normal (threshold is 2)
Actual: Policy unchanged BUT the check uses < 2 instead of <= 1
```

Actually wait, re-reading the logs. The issue is the OPPOSITE - the system is NOT escalating when it should because the condition is wrong.

### Policy De-escalation Difficulty

De-escalation requires 3x the threshold in successes. For "watch" state with threshold 3, that means 9 consecutive successes to de-escalate. Our SRE team says this should be 2x (6 successes).

```
Current: watch (threshold=3)
Successes needed to de-escalate: 3 * 3 = 9
Expected: 3 * 2 = 6
```

### SLA Compliance Edge Case

The SLA compliance check fails for exact matches:

```
Response time: 30 minutes
Target SLA: 30 minutes
Expected: COMPLIANT (met exactly)
Actual: NON-COMPLIANT (check uses < instead of <=)
```

### SLA Percentage Division by Zero

When calculating SLA percentage with total=0, the function attempts division by zero:

```
met = 0, total = 0
Expected: Return 0% or handle gracefully
Actual: Division by zero (guard checks < 0, not <= 0)
```

### Metadata Lookup Case Sensitivity

Policy metadata lookup is case-sensitive:

```
GetMetadata("NORMAL") returns empty metadata
GetMetadata("Normal") returns empty metadata
GetMetadata("normal") returns correct metadata
```

---

## Load Shedding Related Issues

From @capacity-team:

The queue is shedding load too aggressively:

```
Current depth: 500
Hard limit: 500 (incorrectly set to 500, should be 1000)
ShouldShed(500, 500) returns true (sheds at exact limit, should only shed when > limit)
```

Also, queue warnings trigger too early:

```
WarnRatio = 0.5 (should be 0.6)
At 50% capacity, we get warnings that imply imminent overload
This causes unnecessary paging of on-call
```

Wait time estimation returns negative values for negative queue depth (data corruption edge case).

---

## Immediate Actions Required

1. **CRITICAL**: Add "arrived" -> "completed" transition to workflow graph
2. **HIGH**: Fix default initial state to "queued" instead of "allocated"
3. **HIGH**: Fix policy escalation/de-escalation thresholds
4. **MEDIUM**: Fix SLA compliance exact-match handling
5. **MEDIUM**: Fix queue shedding boundary conditions

---

## Escalation

Paging @workflow-team and @policy-team for immediate review.

---

**Resolution Status:** In Progress
**ETA:** TBD
**Post-mortem:** Scheduled for 2024-11-14
