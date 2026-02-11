# SUPPORT-7823: Vessels Stuck in "Arrived" State Cannot Be Marked Complete

## Ticket Information

**Ticket ID**: SUPPORT-7823
**Created**: 2024-11-13 09:15 UTC
**Priority**: High
**Customer**: Pacific Maritime Logistics (Enterprise Tier)
**Assignee**: Backend Platform Team

---

## Customer Report

> We're experiencing a serious issue with vessel lifecycle management. Multiple vessels that have successfully arrived at port are showing as still "active" in the system. Our operations team cannot mark them as complete, and they're cluttering our active vessel dashboard.
>
> Additionally, we had an incident where a vessel that had already departed was accidentally cancelled through the API. This should not be allowed - once a vessel departs, cancellation should be blocked.
>
> We also noticed that dispatch orders with severity=0 are being accepted by the system, even though our contract specifies severity must be 1-5.

---

## Steps to Reproduce

### Issue 1: "Arrived" State Not Terminal

```cpp
WorkflowEngine engine;
engine.register_entity("vessel-001", "queued");
engine.transition("vessel-001", "allocated");
engine.transition("vessel-001", "departed");
engine.transition("vessel-001", "arrived");

// Check if terminal
bool is_done = engine.is_terminal("vessel-001");
// Expected: true (vessel has arrived, workflow complete)
// Actual: false (vessel still shows as "active")

int active = engine.active_count();
// Expected: 0 (no active vessels)
// Actual: 1 (arrived vessel counted as active)
```

### Issue 2: Departed Vessels Can Be Cancelled

```cpp
// After vessel has departed
engine.transition("vessel-002", "departed");

// This should fail but succeeds:
auto result = engine.transition("vessel-002", "cancelled");
// Expected: result.success = false, error = "invalid_transition"
// Actual: result.success = true, vessel is now "cancelled"
```

The state machine allows transitioning from "departed" to "cancelled", but business rules specify that once a vessel departs, it cannot be cancelled (only "arrived" is valid).

### Issue 3: Severity=0 Passes Validation

```cpp
DispatchModel order{0, 60};  // severity=0, sla=60min
std::string error = validate_dispatch_order(order);
// Expected: "severity must be between 1 and 5"
// Actual: "" (empty string, validation passes)
```

Orders with severity=0 are being created and processed, causing downstream sorting and priority issues.

---

## Additional Observations

### Urgency Score Calculation Wrong

The customer also flagged that urgency scores seem inverted:

```cpp
DispatchModel order{5, 60};  // severity=5 (CRITICAL), sla=60min
int score = order.urgency_score();
// remainder = 120 - 60 = 60
// Expected: 5 * 10 + 60 = 110 (high urgency)
// Actual: 5 * 10 - 60 = -10 (negative urgency?!)
```

Critical orders (severity=5) are getting lower urgency scores than low-priority orders. This compounds the dispatch prioritization issues reported in INC-2024-0847.

---

## Expected Behavior

1. **Terminal States**: Both "arrived" and "cancelled" should be terminal states. When a vessel reaches "arrived", its workflow is complete.

2. **State Transitions**: From "departed", only "arrived" should be allowed. Cancellation is not a valid option once departure occurs.

3. **Severity Validation**: Severity must be in range [1, 5]. Values of 0 should fail validation.

4. **Urgency Score**: Higher severity and tighter SLA should produce higher urgency scores, not lower.

---

## Impact Assessment

- 847 vessels in "arrived" state showing as active
- 12 vessels incorrectly cancelled after departure (data integrity issue)
- Unknown number of severity=0 orders in system
- Priority sorting completely inverted for dispatch planning

---

## Files to Investigate

- `src/workflow.cpp`: State transition graph, terminal state definitions
- `src/model.cpp`: `urgency_score()` calculation, `validate_dispatch_order()`
- Related test files for workflow and model validation
