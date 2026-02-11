# DataNexus Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the DataNexus team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Reproduce the issue (if possible)
2. Investigate root cause
3. Identify the buggy code
4. Implement a fix
5. Verify the fix doesn't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-stream-processing-data-loss.md](./01-stream-processing-data-loss.md) | PagerDuty Incident | Critical | Events missing from windows, memory growth |
| [02-query-engine-security-audit.md](./02-query-engine-security-audit.md) | Security Report | Critical | SQL injection, data exposure, stale cache |
| [03-alert-flapping-incident.md](./03-alert-flapping-incident.md) | Customer Escalation | High | Duplicate alerts, missed alerts, escalation storms |
| [04-aggregation-precision-errors.md](./04-aggregation-precision-errors.md) | Slack Discussion | Medium | Wrong counts, histogram bucket errors, billing discrepancies |
| [05-scheduler-jobs-stuck.md](./05-scheduler-jobs-stuck.md) | Grafana Alert | Critical | Jobs running out of order, stuck in pending, split-brain |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1-2**: Critical issues with clear production impact
- **Scenario 3-4**: Subtle precision and timing issues affecting reliability
- **Scenario 5**: Distributed coordination issues spanning scheduler components

## Tips for Investigation

1. **Run tests with verbose output**: `npm test -- --verbose`
2. **Check logs for patterns**: Error messages often point to specific code paths
3. **Review shared modules first**: `shared/` contains core stream and event handling
4. **Search for related code**: `grep -rn "keyword" services/`
5. **Trace request flow**: Gateway -> Service -> Shared modules

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs
