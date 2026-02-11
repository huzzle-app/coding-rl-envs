# HealthLink Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the HealthLink team.

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
| [01-startup-failure-incident.md](./01-startup-failure-incident.md) | PagerDuty Incident | Critical | Application crash loop, DI container fails, authentication not working |
| [02-security-audit-findings.md](./02-security-audit-findings.md) | Security Report | Critical | SQL injection, path traversal, weak JWT keys, auth bypass |
| [03-appointment-api-timeout.md](./03-appointment-api-timeout.md) | Customer Escalation | High | Single appointment lookup hangs indefinitely, thread pool exhaustion |
| [04-socket-exhaustion-alert.md](./04-socket-exhaustion-alert.md) | Grafana Alert | Critical | External API failures, socket exhaustion, TIME_WAIT accumulation |
| [05-stale-patient-data.md](./05-stale-patient-data.md) | Support Ticket | High | Stale cached data, duplicate database queries, null reference exceptions |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Clear startup failures with stack traces pointing to specific issues
- **Scenario 2**: Security vulnerabilities requiring code review and testing
- **Scenario 3-4**: Concurrency and resource management issues requiring deeper analysis
- **Scenario 5**: Subtle data layer issues affecting multiple components

## Bug Categories Covered

| Scenario | Bug Categories |
|----------|----------------|
| Scenario 1 | Setup/DI (L1-L4) - Circular dependency, singleton DbContext, config mismatch, middleware order |
| Scenario 2 | Security (I1-I4) - SQL injection, path traversal, weak JWT, auth bypass |
| Scenario 3 | Async/Await (A1) - Task.Result deadlock |
| Scenario 4 | IDisposable (D3) - HttpClient socket exhaustion |
| Scenario 5 | LINQ (C1), EF Core (E1), Nullable (B1, B4) - Deferred execution, change tracker, null suppression |

## Tips for Investigation

1. **Run tests first**: `dotnet test` to see which tests are failing
2. **Check application logs**: Error messages often point to specific code paths
3. **Use the debugger**: Attach to understand control flow and state
4. **Review dependency injection**: Check `Program.cs` for service registration issues
5. **Search for patterns**: `grep -rn "keyword" src/`

## Healthcare Context

HealthLink is a healthcare appointment and patient management platform. When investigating these issues, keep in mind:

- **Patient Safety**: Data integrity issues (Scenario 5) can have real patient safety implications
- **HIPAA Compliance**: Security vulnerabilities (Scenario 2) may expose Protected Health Information
- **Clinical Workflow**: API timeouts (Scenario 3) directly impact patient check-in times
- **Integration Dependencies**: External API failures (Scenario 4) affect insurance verification and lab results

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation and debugging approach
- Test files in `tests/` directory contain assertions that exercise these bugs
