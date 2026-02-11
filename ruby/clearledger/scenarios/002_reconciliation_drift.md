# Engineering Ticket: Reconciliation Age and Break Count Anomalies

**Ticket**: CLR-4521
**Type**: Bug
**Priority**: P2 - High
**Component**: Reconciliation / Resilience
**Reporter**: Backend Platform Team
**Assignee**: Unassigned

---

## Description

Multiple reconciliation subsystems are reporting anomalous values that are causing incorrect alerting and replay decisions. The issues appear related to time calculations and set comparison logic.

## Issue 1: Negative Reconciliation Age

The `age_seconds` function in Reconciliation is returning negative values, causing the replay scheduler to skip records that should be processed.

### Reproduction
```ruby
# Record created at epoch 1705320000 (2024-01-15 10:00:00)
# Current time epoch 1705323600 (2024-01-15 11:00:00)
age = Reconciliation.age_seconds(1705320000, 1705323600)
# Expected: 3600 (1 hour old)
# Actual: -3600 (negative!)
```

### Impact
- Reconciliation replay is incorrectly marking fresh records as "from the future"
- Stale data detection inverted (old records pass, new records flagged)
- Checkpoint staleness alerts triggering incorrectly

## Issue 2: Break Count Returns Matches Instead of Breaks

The `break_count` function appears to be returning the count of matching entries rather than mismatching entries.

### Reproduction
```ruby
expected = [:a, :b, :c, :d, :e]
observed = [:a, :b, :f]  # c, d, e are missing; f is unexpected

breaks = Reconciliation.break_count(expected, observed)
# Expected: 3 (c, d, e are breaks)
# Actual: 2 (returning matches instead!)
```

### Impact
- Reconciliation break dashboards show inverted metrics
- High-break batches incorrectly marked as clean
- Clean batches flagged for manual review

## Issue 3: Checkpoint Age Also Negative

Similar to Issue 1, the Resilience module's `checkpoint_age` returns negative values:

```ruby
# Checkpoint at epoch 1000, current time epoch 2000
age = Resilience.checkpoint_age(1000, 2000)
# Expected: 1000
# Actual: -1000
```

## Issue 4: Audit Entry Age Inverted

The AuditChain `entry_age` function shows the same pattern:

```ruby
entry_age = AuditChain.entry_age(1705320000, 1705323600)
# Expected: 3600
# Actual: -3600
```

## Root Cause Hypothesis

The time difference calculations may have operands in the wrong order (`created_at - now` instead of `now - created_at`).

## Affected Workflows

1. Reconciliation replay scheduling
2. Stale checkpoint detection
3. Audit trail aging and retention
4. Break count alerting

## Acceptance Criteria

- [ ] `age_seconds(created_at, now)` returns positive values when now > created_at
- [ ] `break_count` returns count of entries in expected but not in observed
- [ ] `checkpoint_age(checkpoint_ts, now_ts)` returns positive age
- [ ] `entry_age(entry_ts, now_ts)` returns positive age
- [ ] Replay scheduler correctly identifies stale records
- [ ] Break count dashboard shows correct mismatch counts

## Related Alerts

- `reconciliation_age_negative` (firing continuously)
- `checkpoint_staleness_inverted` (firing continuously)
- `break_count_mismatch` (false negatives for 3 days)

## Test Commands

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Notes

This may be part of a broader pattern of operand ordering issues. Recommend auditing all subtraction operations in time-related calculations.
