# Scenario 06: Fulfillment State Machine Violations

## Incident Type
P2 Operations Escalation / State Integrity Breach

---

## Operations Escalation

**From:** Senior Operations Manager, ChillPharma Logistics
**To:** PolarisCore Platform Team
**Subject:** URGENT: Shipments marked "Delivered" that were never in transit

We have multiple shipments showing as "Delivered" in your system that our warehouse team confirms never left the staging area. Our tracking GPS shows these pallets sitting in the Allocated bay, yet your system says they've been delivered. This is causing downstream invoicing chaos and compliance audit failures.

Additionally, our fulfillment cost projections are wildly off — margins showing 5000%+ which is obviously impossible. Something is fundamentally broken in the orchestration layer.

---

## Internal Investigation Notes

**#platform-incidents** Slack Thread

**@ops-lead**: Pulled the state machine logs for ChillPharma. Found the issue — shipments are going from Allocated directly to Delivered, bypassing InTransit entirely.

**@backend-eng**: That shouldn't be possible. Let me check `can_deliver()`.

```rust
// Current code in src/workflow.rs
pub fn can_deliver(&self) -> bool {
    self.state == ShipmentState::Allocated || self.state == ShipmentState::InTransit
}
```

**@backend-eng**: Found it. `can_deliver()` returns true for both Allocated AND InTransit. It should only be true for InTransit. Allocated means the shipment has a slot reserved but hasn't been picked up by a carrier yet.

**@ops-lead**: There's more. We also see shipments going from Held to Delivered. Held is supposed to be a quarantine state — the only valid exit is back to Queued for re-evaluation.

**@backend-eng**: Checking the transition table...

```rust
(ShipmentState::Held, ShipmentState::Queued)     // valid — re-queue for review
| (ShipmentState::Held, ShipmentState::Delivered) // BUG — should not be valid
```

**@backend-eng**: The Held → Delivered arm needs to be removed. That's a dangerous shortcut that bypasses all compliance checks.

---

## Risk Aggregation Anomaly

**@risk-analyst**: I'm seeing another issue in `plan_fulfillment`. When we run multi-batch fulfillment plans, the combined risk score is always equal to the HIGHEST batch score, not the average. This means a single high-risk batch makes the entire plan appear maximum-risk, triggering unnecessary holds.

```
Batch 1 risk: 12.5 (low)
Batch 2 risk: 78.3 (high)

Expected combined: (12.5 + 78.3) / 2 = 45.4 (ops-review tier)
Actual combined:   max(12.5, 78.3)   = 78.3 (near hold threshold)
```

**@backend-eng**: The `plan_fulfillment` function uses `f64::max` fold instead of averaging:

```rust
let combined_risk = risk_scores.iter().copied().fold(0.0_f64, f64::max);
```

Should be a simple average of all batch risk scores.

---

## Margin Calculation Defect

**@finance-eng**: Found the margin bug. The `overall_margin` in `plan_fulfillment` divides by cost instead of revenue:

```rust
(total_revenue - total_cost) as f64 / total_cost as f64  // BUG: cost-based
```

For small batches where revenue = cost + 75000, if cost is tiny (e.g., 147 cents for 1 unit), margin becomes 75000/147 ≈ 510. That's a 51,000% margin which is nonsensical.

**@finance-eng**: Revenue-based margin `(revenue - cost) / revenue` is always in [0, 1) for profitable operations, which is what downstream systems expect.

---

## Multi-Batch Capacity Leak

**@scheduler-eng**: Final issue — `multi_batch_schedule` shares a single mutable capacity vector across all batches. Batch 0 consumes window capacity, and batch 1 gets whatever's left.

```
Window w1 capacity: 5 units
Batch 0: 5 units → allocated (cap now 0)
Batch 1: 5 units → 0 allocated (no capacity left!)
```

**@scheduler-eng**: Each batch should get independent capacity from the windows. The `caps` vector needs to be rebuilt per batch, not shared.

---

## Business Impact

- **ChillPharma contract at risk**: $6.8M annual, regulatory audit pending
- **State integrity breach**: 340+ shipments with invalid Delivered status
- **Margin reporting**: Finance dashboards showing impossible margins, eroding trust
- **Over-holding**: Multi-batch plans triggering unnecessary holds due to max-risk aggregation
- **Capacity starvation**: Later batches systematically under-allocated

---

## Affected Test Files

- `tests/workflow_targeted_tests.rs` — Targeted tests for each of the 5 workflow bugs
- `tests/workflow_integration_tests.rs` — End-to-end orchestration cycle
- `tests/hyper_matrix_tests.rs` — Stress tests covering state machine, plan_fulfillment, multi_batch_schedule

---

## Relevant Module

- `src/workflow.rs` — ShipmentStateMachine, plan_fulfillment, multi_batch_schedule

---

## Investigation Questions

1. What states does `can_deliver()` accept? Should Allocated be deliverable?
2. Is the Held → Delivered transition in the `transition()` match arm valid?
3. How is `combined_risk` computed in `plan_fulfillment` — max or average?
4. What is the divisor for `overall_margin` — revenue or cost?
5. Does `multi_batch_schedule` reset window capacities for each batch?

---

## Resolution Criteria

- `can_deliver()` must return true ONLY for InTransit state
- Held → Delivered must be an invalid transition (remove the match arm)
- `combined_risk` must be the average of batch risk scores, not the maximum
- `overall_margin` must divide by `total_revenue`, not `total_cost`
- `multi_batch_schedule` must rebuild capacities independently per batch
- All workflow targeted and integration tests must pass
