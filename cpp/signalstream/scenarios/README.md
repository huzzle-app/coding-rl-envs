# SignalStream Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the SignalStream platform team.

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
| [01-service-crash-on-startup.md](./01-service-crash-on-startup.md) | PagerDuty Incident | Critical | Services crash on startup, static initialization failures |
| [02-data-corruption-under-load.md](./02-data-corruption-under-load.md) | Customer Escalation | Critical | Financial data corruption, race conditions, memory errors |
| [03-security-audit-findings.md](./03-security-audit-findings.md) | Security Report | High | JWT bypass, injection vulnerabilities, weak crypto |
| [04-alerting-system-failures.md](./04-alerting-system-failures.md) | Slack Thread | High | Alerts not firing, circuit breaker stuck, retry storms |
| [05-aggregation-precision-loss.md](./05-aggregation-precision-loss.md) | Support Ticket | Medium | Incorrect aggregations, precision loss, NaN propagation |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Clear startup failures with stack traces pointing to initialization code
- **Scenario 2**: Intermittent concurrency and memory issues requiring deeper analysis
- **Scenario 3**: Security vulnerabilities with proof-of-concept exploits
- **Scenario 4**: Distributed system issues in alerting with complex state machines
- **Scenario 5**: Subtle numerical bugs requiring precision analysis

## Tips for Investigation

1. **Build with sanitizers**: Add `-fsanitize=address,thread,undefined` to catch memory and concurrency bugs
2. **Run tests with verbose output**: `ctest --output-on-failure`
3. **Check for data races**: ThreadSanitizer output often points to specific code paths
4. **Review template instantiations**: C++20 concepts and SFINAE errors can be subtle
5. **Trace distributed state**: Circuit breaker and distributed lock issues require understanding FSM transitions

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs
