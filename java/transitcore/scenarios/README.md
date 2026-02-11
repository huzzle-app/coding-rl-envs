# TransitCore Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, operations tickets, and alerts you might encounter as an engineer on the TransitCore transit dispatch platform.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, operator reports, and operational metrics. Your task is to:

1. Reproduce the issue (if possible via tests)
2. Investigate root cause in the codebase
3. Identify the buggy code
4. Implement a fix
5. Verify the fix with the existing test suite

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-slow-route-selection.md](./01-slow-route-selection.md) | Operations Escalation | Critical | Dispatches consistently routed to slowest paths, SLA breaches |
| [02-capacity-overcommit.md](./02-capacity-overcommit.md) | PagerDuty Incident | High | Fleet capacity exceeded, vehicle shedding not triggering |
| [03-escalation-failures.md](./03-escalation-failures.md) | Incident Response Post-Mortem | High | Critical incidents not escalating, queue bypasses rejected |
| [04-replay-drift.md](./04-replay-drift.md) | Slack Discussion | Medium | State reconstruction errors after failover, event replay issues |
| [05-sla-reporting-anomalies.md](./05-sla-reporting-anomalies.md) | Executive Dashboard Alert | Critical | SLA metrics showing incorrect breach classification |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1-2**: Clear symptoms pointing to specific subsystems (routing, capacity)
- **Scenario 3**: Multiple policy components with interconnected failures
- **Scenario 4**: Complex event replay and resilience logic
- **Scenario 5**: Cross-cutting concerns spanning SLA, compliance, and statistics

## Tips for Investigation

1. **Run the test suite**: `mvn test -q` to see which tests are failing
2. **Check specific test classes**: Tests are named after components (e.g., `DispatchPlannerTest`, `CapacityBalancerTest`)
3. **Search for related code**: Use grep to find relevant classes
4. **Look for boundary conditions**: Many transit bugs involve off-by-one errors in thresholds
5. **Check comparison operators**: `>` vs `>=`, `<` vs `<=` are common sources of issues

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `src/test/java/` directory contain assertions that exercise these bugs
