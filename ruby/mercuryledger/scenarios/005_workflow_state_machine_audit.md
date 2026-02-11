# Scenario 005: Workflow State Machine Audit Failures - Compliance Review

## Internal Audit Report: AUD-2024-ML-047

**Prepared by:** Internal Audit Division
**Date:** November 28, 2024
**Classification:** Internal Use Only
**Regulation Reference:** IMO Maritime Cargo Tracking Standards (MCTS-2023)

---

### Audit Scope

This audit evaluated MercuryLedger's workflow state machine implementation against the IMO Maritime Cargo Tracking Standards, which require:

1. Complete auditability of cargo state transitions
2. Immutable state machine graphs with no unreachable states
3. Prevention of invalid transitions from terminal states
4. Accurate statistical reporting for regulatory submissions

---

### Finding AUD-001: Unreachable Terminal State (CRITICAL)

**Requirement:** MCTS-2023 Section 4.2.1 - All defined states must be reachable through valid transitions.

**Observation:** The workflow state graph defines a `completed` state, but analysis of the GRAPH constant reveals that no valid path exists from `arrived` to `completed`.

**Evidence:**
```ruby
# Current GRAPH (excerpt):
departed: %i[arrived]
arrived: %i[completed]  # But is this transition actually working?
```

**Testing shows:**
```
FAILED: test_arrived_to_completed_transition
  Entity stuck in 'arrived' state indefinitely
  Expected: transition to 'completed' allowed
  Actual: transition blocked
```

**Regulatory Risk:** If vessels cannot reach `completed` state, the port cannot issue final cargo disposition certificates required by customs authorities.

---

### Finding AUD-002: Terminal State Guard Missing (HIGH)

**Requirement:** MCTS-2023 Section 4.3.7 - Terminal states shall not allow outbound transitions.

**Observation:** The `transition` method in WorkflowEngine does not verify that the source state is non-terminal before allowing transitions.

**Evidence:**
```
FAILED: test_no_transition_from_terminal_state
  Entity in 'completed' state should reject transition attempts
  Expected: error 'transition_from_terminal_not_allowed'
  Actual: transition to 'cancelled' succeeded
```

**Regulatory Risk:** Cargo marked as `completed` could be illegally transitioned back to `cancelled`, erasing audit trail.

---

### Finding AUD-003: Statistics Module - Incorrect Percentile Calculation (MEDIUM)

**Requirement:** MCTS-2023 Section 8.1.2 - P95/P99 latency metrics must use industry-standard nearest-rank method.

**Observation:** The `percentile_rank` function produces incorrect results. For a dataset of 100 values, P95 should return the 95th value, but the formula appears to have an offset error.

**Evidence:**
```
FAILED: test_percentile_p95_nearest_rank
  Input: 100 sorted values [1..100]
  Expected P95: 95
  Actual P95: 144 (out of range!)
```

**Regulatory Risk:** Inaccurate P95/P99 metrics in regulatory submissions could trigger compliance audits.

---

### Finding AUD-004: Sample Variance Bias (MEDIUM)

**Requirement:** MCTS-2023 Section 8.2.4 - Statistical variance calculations must use Bessel's correction (N-1 denominator).

**Observation:** The `variance` function divides by N (population variance) instead of N-1 (sample variance), introducing systematic underestimation.

**Evidence:**
```
FAILED: test_sample_variance_bessels_correction
  Sample: [2, 4, 4, 4, 5, 5, 7, 9]
  Expected variance (N-1): 4.571
  Actual variance (N): 4.0
```

---

### Finding AUD-005: Workflow Query Methods Missing (MEDIUM)

**Requirement:** MCTS-2023 Section 5.4.1 - Systems must support bulk state queries and batch transitions.

**Observation:** The WorkflowEngine class is missing required methods:
- `entities_in_state(state)` - Filter entities by current state
- `bulk_transition(entity_ids, to_state)` - Batch state changes

**Evidence:**
```
FAILED: test_entities_in_state_query
  Expected: method exists and returns entities in 'departed' state
  Actual: NoMethodError - undefined method 'entities_in_state'

FAILED: test_bulk_transition_batch
  Expected: method exists and transitions multiple entities
  Actual: NoMethodError - undefined method 'bulk_transition'
```

**Regulatory Risk:** Cannot efficiently generate state-based compliance reports required for quarterly submissions.

---

### Finding AUD-006: SLA Threshold Misconfiguration (HIGH)

**Requirement:** Internal SLA Policy v3.2 - MEDIUM severity orders must have 45-minute SLA.

**Observation:** The `sla_for` method returns 60 minutes for severity level 3 (MEDIUM), not the 45 minutes specified in the updated policy.

**Evidence:**
```
FAILED: test_sla_for_medium_severity
  Severity: 3 (MEDIUM)
  Expected SLA: 45 minutes
  Actual SLA: 60 minutes
```

**Business Risk:** 15-minute SLA gap causing incorrect penalty calculations.

---

### Compliance Status Summary

| Finding | Severity | MCTS Section | Status |
|---------|----------|--------------|--------|
| AUD-001 | Critical | 4.2.1 | Non-Compliant |
| AUD-002 | High | 4.3.7 | Non-Compliant |
| AUD-003 | Medium | 8.1.2 | Non-Compliant |
| AUD-004 | Medium | 8.2.4 | Non-Compliant |
| AUD-005 | Medium | 5.4.1 | Non-Compliant |
| AUD-006 | High | Internal SLA | Non-Compliant |

---

### Required Remediation Timeline

- **Critical findings (AUD-001):** 72 hours
- **High findings (AUD-002, AUD-006):** 2 weeks
- **Medium findings (AUD-003, AUD-004, AUD-005):** 30 days

---

### Attachments

- Full test failure logs: `workflow_audit_test_results.log`
- MCTS-2023 Compliance Checklist: `mcts_2023_checklist.xlsx`
- State machine diagram: `workflow_state_diagram.svg`

---

*This report has been submitted to the Maritime Compliance Office. Engineering response required within 5 business days.*
