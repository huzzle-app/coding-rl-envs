# StrataGuard Debugging Scenarios

This directory contains realistic debugging scenarios that simulate real-world incidents, support tickets, monitoring alerts, and team discussions. Each scenario describes **symptoms and business impact** without revealing the exact fixes.

## Scenario Index

| File | Format | Summary |
|------|--------|---------|
| `incident_001_dispatch_priority_inversion.md` | Incident Report | Critical dispatch orders processed after low-priority ones |
| `incident_002_replay_sequence_corruption.md` | Incident Report | Replay engine selecting wrong sequence during failover |
| `ticket_003_route_selection_latency.md` | Support Ticket | Routes selected by highest latency instead of lowest |
| `alert_004_queue_drain_overflow.md` | Monitoring Alert | DrainBatch returning more items than requested |
| `slack_005_statistics_integer_division.md` | Team Discussion | Multiple metrics returning 0 instead of decimal values |

## How to Use These Scenarios

These scenarios are designed to help you:

1. **Understand the business context** of bugs before diving into code
2. **Practice realistic debugging** by starting from symptoms, not solutions
3. **Learn the codebase** through investigation rather than direct hints

### Recommended Workflow

1. Read the scenario description and understand the reported symptoms
2. Identify which tests are failing (mentioned in each scenario)
3. Run the failing tests to confirm the behavior: `dotnet test --filter "TestName"`
4. Trace from test assertions back to source code
5. Identify the root cause and implement a fix
6. Verify the fix passes all related tests

## Scenario Types

### Incident Reports (INC-*)
Formal post-mortem style documents with:
- Executive summary and timeline
- Affected tests and log excerpts
- Business impact assessment
- Investigation notes

### Support Tickets (STRATA-*)
Customer-reported issues including:
- Customer evidence and reproduction steps
- Internal test failures
- Business impact on the customer
- Temporary workarounds

### Monitoring Alerts (ALT-*)
Production alerting system notifications with:
- Prometheus queries and thresholds
- Grafana dashboard snapshots
- Stack traces and metrics
- Runbook actions

### Team Discussions (Slack)
Informal debugging conversations showing:
- Real-time investigation process
- Pattern recognition across modules
- Test failure analysis
- Collaborative problem-solving

## Related Documentation

- [TASK.md](../TASK.md) - Full environment description and bug categories
- [Tests](../tests/) - Test suite with assertions that define expected behavior
- [Source](../src/StrataGuard/) - Implementation files to investigate

## Bug Categories Covered

These scenarios cover multiple bug categories from the environment:

| Category | Scenarios |
|----------|-----------|
| Order/direction | incident_001, ticket_003 |
| Wrong comparison | incident_002 |
| Off-by-one | alert_004 |
| Integer division | slack_005 |
| Wrong formula | slack_005 |
| Wrong field | incident_002 |

## Notes

- Scenarios reference real test names that you can run with `dotnet test`
- Log timestamps and incident IDs are fictional but realistic
- Business context reflects actual use cases for the StrataGuard platform
- Some scenarios hint at multiple related bugs across different modules
