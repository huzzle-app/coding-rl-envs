# Scenario 001: Port Capacity Crisis During Peak Season

## Incident Report: MERC-2024-0847

**Severity:** P1 - Critical
**Status:** Open
**Reporter:** Harbor Operations Center
**Affected Systems:** Berth Allocation, Dispatch Scheduling
**Business Impact:** $2.3M/day in delayed cargo operations

---

### Executive Summary

During our peak Q4 shipping season, Port of Rotterdam operations have reported that the MercuryLedger berth allocation system is rejecting valid berth assignments and prematurely triggering capacity alerts. Vessel queues are growing at 3x the normal rate despite having available berth slots.

---

### Timeline of Events

**2024-11-15 06:00 UTC** - Night shift reports unusual rejection rates for medium-priority vessels.

**2024-11-15 08:30 UTC** - Day shift escalation: capacity warning alerts firing continuously even with only 78% berth utilization.

**2024-11-15 09:15 UTC** - Operations manually overrides system to allow MV Pacific Fortune into Berth 7, which the system incorrectly flagged as occupied.

**2024-11-15 11:00 UTC** - Engineering notified. Initial hypothesis: database corruption.

**2024-11-15 14:00 UTC** - Database verified clean. Issue reproduced in staging environment.

---

### Observed Symptoms

1. **Premature Capacity Warnings**: The system triggers `:warning` status at roughly 78-80% utilization, causing unnecessary load shedding when we should have ~20% headroom.

2. **False Slot Conflicts**: Adjacent berth time slots (e.g., Berth 3 ending at 14:00 and Berth 3 starting at 14:00) are being marked as conflicts, blocking back-to-back scheduling.

3. **Urgency Miscalculation**: High-severity orders (severity 4-5) appear to receive artificially inflated urgency scores. A severity-5 order with 30-minute SLA is being prioritized identically to a severity-4 order with 10-minute SLA.

4. **Turnaround Underestimation**: Crane operations are taking ~10% longer than estimated, causing cascade delays when the next vessel arrives before the current one departs.

---

### Failing Test Suites

The following test categories are showing failures related to this incident:

- `test_dispatch_capacity_threshold_*`
- `test_berth_slot_conflict_detection_*`
- `test_order_urgency_score_calculation_*`
- `test_turnaround_time_estimation_*`

Sample failure output:
```
Failure: test_dispatch_capacity_warning_at_80_percent
  Expected: :normal (at 79% utilization)
  Actual: :warning

Failure: test_adjacent_slots_no_conflict
  Expected: false (slots ending/starting at same hour should not conflict)
  Actual: true
```

---

### Business Impact

- **Revenue Loss**: Estimated $2.3M/day in delayed cargo handling fees
- **Customer Complaints**: 47 shipping companies have filed formal complaints
- **Contractual Penalties**: Rotterdam port authority SLA breach imminent (4-hour max queue time)
- **Ripple Effect**: Downstream supply chain disruptions affecting automotive and electronics sectors

---

### Requested Actions

1. Investigate capacity threshold calculations in dispatch module
2. Review berth slot overlap/conflict detection logic
3. Audit urgency scoring formula for severity weights
4. Verify turnaround time estimation includes proper buffers

---

### Attachments

- berth_allocation_logs_20241115.json (12MB)
- capacity_metrics_dashboard_screenshot.png
- customer_complaint_summary.xlsx
