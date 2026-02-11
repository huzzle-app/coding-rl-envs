# Support Ticket: Daily Reports Show Incidents in Wrong Order

**Ticket ID:** SUP-4521
**Submitted by:** Mission Director, Satellite Operations
**Priority:** Medium
**Status:** Investigating
**Created:** 2024-03-20 09:15 UTC

## Description

The daily mission reports are listing incidents in the wrong order. Low-severity issues appear at the top while critical incidents are buried at the bottom of the list. This is causing operators to miss important issues during morning briefings.

## Steps to Reproduce

1. Generate a daily report with mixed severity incidents
2. View the "Incident Rank" section
3. Notice that severity-1 (low) incidents appear before severity-5 (critical)

## Expected Result

Incidents should be ranked by severity descending:
- Severity 5 (critical) at top
- Severity 4 (high) next
- ...
- Severity 1 (low) at bottom

## Actual Result

Incidents are sorted by severity ascending:
- Severity 1 (low) at top
- Severity 5 (critical) at bottom

## Example

**Expected order:**
```
1. [SEV-5] Fuel pressure anomaly
2. [SEV-4] Telemetry dropout
3. [SEV-2] Minor sensor drift
```

**Actual order:**
```
1. [SEV-2] Minor sensor drift
2. [SEV-4] Telemetry dropout
3. [SEV-5] Fuel pressure anomaly
```

## Business Impact

- Flight directors spend extra time scrolling to find critical issues
- Risk of overlooking high-severity incidents in morning reviews
- Compliance concern: audit reports may not highlight critical issues first

## Workaround

Operators manually scroll to bottom of report to find critical issues.

## Related Tests

- `test_rank_incidents_descending_severity`

## Notes from Engineering Review

Suspected issue in `reporting/service.py` - the `rank_incidents` function may be sorting in wrong direction. The `sorted()` call should use `reverse=True` for descending order or negate the sort key.
