# Scenario 02: Berth Scheduling Conflicts

## Type: Customer Support Ticket

## Priority: High

## Ticket: BERTH-7892

---

### Customer Report

**From**: Harbor Operations Manager
**To**: VectorHarbor Support
**Subject**: Adjacent berth slots incorrectly flagged as conflicts

---

Hello Support Team,

We've been experiencing issues with berth scheduling since the last platform update. Our operations team has identified two related problems:

**Problem 1: False Conflict Detection**

When scheduling vessels in adjacent time slots, the system incorrectly reports conflicts. For example:

- Vessel Alpha: Berth A, hours 8-12
- Vessel Beta: Berth A, hours 12-16

These should be valid adjacent bookings (one ends at noon, the next starts at noon), but the system rejects Vessel Beta's booking with "conflict detected."

Our harbor master says: *"We've been manually overriding these for days. The old system understood that if one vessel departs at 1200 and another arrives at 1200, there's a 2-hour buffer built into our turnaround procedures."*

**Problem 2: Queue Wait Time Estimates**

The dispatch queue is showing wildly incorrect wait time estimates. When we have 10 items in queue with a processing rate of 2 items/hour, the system shows "50 hours estimated wait" instead of "5 hours."

Additionally, during high-traffic periods (emergency flag set), the load shedding seems to kick in one item too late. When we set hard_limit=100 and have 80 items queued (exactly 80%), emergency shedding should activate but doesn't until we hit 81 items.

### Steps to Reproduce

**Conflict Issue:**
```
Slot 1: berth="A", start=10, end=14
Slot 2: berth="A", start=14, end=18

Expected: No conflict (adjacent, not overlapping)
Actual: Conflict reported
```

**Wait Time Issue:**
```
Queue depth: 50
Processing rate: 5.0 items/second
Expected wait: 10 seconds (50 / 5)
Actual displayed: 250 seconds (50 * 5)
```

### Business Impact

- 15% reduction in berth utilization due to false gaps between bookings
- Customer complaints about inaccurate wait time displays
- Emergency load shedding not protecting the system at the documented 80% threshold

### Environment

- VectorHarbor v2.4.1
- Rust services
- PostgreSQL 15

---

**Support Response (Internal)**:

Escalating to engineering. The conflict detection in `allocator.rs` uses `<=` for range comparison where it should use `<`. For adjacent slots [8,12] and [12,16], the check `12 <= 12` returns true (conflict) when it should return false.

The wait time calculation in `queue.rs` appears to be multiplying instead of dividing.

The emergency threshold check uses `>` instead of `>=`, so 80% exactly doesn't trigger shedding.

---

**Status**: Escalated to Engineering
**Affected Modules**: allocator.rs, queue.rs
