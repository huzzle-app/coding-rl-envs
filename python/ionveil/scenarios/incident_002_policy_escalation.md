# INC-2024-0912: Policy Engine Fails to Escalate During Multi-Failure Scenario

## Severity: P1 - Critical
## Status: Open
## Reported: 2024-03-18 09:45 UTC
## Service: ionveil-policy / policy-engine

---

### Executive Summary

During a severe weather event affecting the Gulf Coast region, the IonVeil policy engine failed to escalate from "normal" to "watch" status despite multiple consecutive backend failures. This left the system operating under relaxed retry limits and longer timeouts during a period requiring heightened resilience, contributing to cascading service degradation.

---

### Timeline

| Time (UTC) | Event |
|------------|-------|
| 09:00 | Hurricane warning issued for coastal zones |
| 09:15 | Incident volume increases 340% above baseline |
| 09:22 | First database connection timeout observed |
| 09:24 | Third consecutive failure recorded |
| 09:25 | Policy engine reports status: "normal" (expected: "watch") |
| 09:31 | Gateway begins rejecting requests due to timeout accumulation |
| 09:38 | Manual policy override applied by ops team |
| 09:45 | Incident raised |

---

### Symptoms Observed

1. **No Escalation on Failure Burst**: System remains in "normal" policy state after 3 consecutive failures
2. **Threshold Mismatch**: Policy escalation appears to require more failures than documented (>2 should trigger)
3. **Test Failures**: `next_policy("normal", 2)` returns "normal" instead of "watch"
4. **Cascade Effect**: Normal policy allows 3 retries with 30s timeout, overwhelming degraded backends

### Affected Tests

```
FAIL: tests/unit/policy_test.py::PolicyTests::test_next_policy_escalates_on_burst
FAIL: tests/stress/hyper_matrix_test.py::test_case_00000 (idx % 4 == 0 path)
FAIL: tests/stress/hyper_matrix_test.py::test_case_00004
FAIL: tests/stress/hyper_matrix_test.py::test_case_00008
... (approximately 3100 similar failures)
```

---

### Reproduction Steps

```python
from ionveil.policy import next_policy, ORDER, METADATA

# Simulate receiving 3 failures while in normal state
current = "normal"
failure_burst = 3

result = next_policy(current, failure_burst)
print(f"Result: {result}")  # Prints: "normal"
print(f"Expected: watch")

# The policy metadata shows watch has stricter limits:
print(METADATA["normal"])  # max_retries: 3, timeout_s: 30
print(METADATA["watch"])   # max_retries: 2, timeout_s: 20
```

---

### Log Excerpts

```
2024-03-18 09:22:14.881 [ionveil.policy] DEBUG: Evaluating policy transition: current=normal, failures=1
2024-03-18 09:23:02.447 [ionveil.policy] DEBUG: Evaluating policy transition: current=normal, failures=2
2024-03-18 09:24:18.223 [ionveil.policy] DEBUG: Evaluating policy transition: current=normal, failures=3
2024-03-18 09:24:18.224 [ionveil.policy] INFO: Policy unchanged: normal
2024-03-18 09:25:01.112 [ionveil.gateway] WARN: Request timeout after 30000ms (policy allows 30s)
2024-03-18 09:25:01.445 [ionveil.gateway] WARN: Retry 1/3 for incident-create
2024-03-18 09:25:31.891 [ionveil.gateway] WARN: Retry 2/3 for incident-create
2024-03-18 09:26:02.334 [ionveil.gateway] WARN: Retry 3/3 for incident-create
2024-03-18 09:26:02.335 [ionveil.gateway] ERROR: All retries exhausted for incident-create
```

---

### Business Impact

- **Availability**: Gateway rejection rate reached 34% during peak incident load
- **Response Delays**: Average incident creation time increased from 1.2s to 47s
- **Manual Intervention**: Ops team had to manually override policy settings
- **SLA Breach**: 12 P1 incidents exceeded 15-minute acknowledgment SLA
- **Credibility**: Regional EOC coordinators questioning system reliability

---

### Technical Context

The `next_policy()` function in `ionveil/policy.py` implements the policy state machine:
- States progress: normal -> watch -> restricted -> halted
- Escalation should occur when `failure_burst > 2` (documented threshold)
- Each elevated state has progressively stricter retry/timeout limits

The policy engine is critical during high-load scenarios because:
1. It reduces retry attempts, lowering backend load
2. It shortens timeouts, freeing connection pool resources faster
3. It triggers load shedding in the queue system

---

### Investigation Notes

- The threshold check in `next_policy()` appears to use wrong comparison operator
- Documented behavior says "> 2 failures triggers escalation"
- Current behavior appears to require "> some higher threshold"
- Problem affects all policy transitions, not just normal->watch

---

### Policy State Definitions

| State | Description | Max Retries | Timeout |
|-------|-------------|-------------|---------|
| normal | Standard operations | 3 | 30s |
| watch | Elevated monitoring | 2 | 20s |
| restricted | Limited operations | 1 | 10s |
| halted | All operations suspended | 0 | 5s |

---

### Stakeholders

- **Regional Coordinator**: J. Thompson (Gulf Coast EOC)
- **Platform Lead**: @policy-team
- **SRE**: @platform-oncall

---

### Related Incidents

- INC-2024-0445: Policy engine slow to de-escalate after recovery
- INC-2023-2201: Similar escalation delay during Black Friday load test
