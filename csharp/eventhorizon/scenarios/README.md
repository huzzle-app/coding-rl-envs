# EventHorizon Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, security audits, support escalations, and QA reports you might encounter as an engineer on the EventHorizon ticketing platform team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, metrics, and user reports. Your task is to:

1. Analyze the symptoms and form hypotheses
2. Investigate the codebase to identify root causes
3. Implement fixes for the underlying bugs
4. Verify fixes don't cause regressions with `dotnet test`

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-double-charge-incident.md](./01-double-charge-incident.md) | PagerDuty Incident | Critical | Customers charged multiple times during flash sale |
| [02-security-assessment-report.md](./02-security-assessment-report.md) | Security Audit | Critical | JWT weakness, SQL injection, authorization bypass |
| [03-notification-memory-leak.md](./03-notification-memory-leak.md) | Grafana Alert | Critical | Memory growth, event handler leaks, orphaned streams |
| [04-order-saga-deadlock.md](./04-order-saga-deadlock.md) | Support Escalation | Urgent | Orders stuck processing, thread deadlocks |
| [05-data-inconsistency-report.md](./05-data-inconsistency-report.md) | QA Test Failures | High | Serialization mismatches, struct semantics, cache races |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1-2**: Clear symptoms pointing to specific subsystems (payments, security)
- **Scenario 3-4**: Concurrency issues requiring understanding of async patterns and locking
- **Scenario 5**: Cross-cutting concerns spanning multiple C# language features

## C# Patterns Covered

These scenarios exercise common C# pitfalls including:

- Async/await patterns (ConfigureAwait, ValueTask, fire-and-forget)
- Struct vs class value semantics
- System.Text.Json configuration
- Event handler subscription/cleanup
- IAsyncEnumerable cancellation
- SemaphoreSlim deadlocks
- Record equality with collections
- Nullable reference types and lifted operators

## Tips for Investigation

1. **Run tests**: `dotnet test` to see current failure state
2. **Run specific tests**: `dotnet test --filter "FullyQualifiedName~keyword"`
3. **Check logs**: Look for patterns in error messages and stack traces
4. **Use IDE debugging**: Set breakpoints in suspected code paths
5. **Search for patterns**: `grep -rn "pattern" src/` to find related code

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation and architecture overview
- Test files in `tests/` directory contain assertions that exercise these bugs

## Running Tests

```bash
# Run all tests
dotnet test

# Run tests for a specific service
dotnet test tests/Payments.Tests/

# Run with detailed output
dotnet test --logger "console;verbosity=detailed"

# Generate test report
dotnet test --logger "trx;LogFileName=results.trx"
```
