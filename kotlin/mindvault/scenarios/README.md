# MindVault Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, security audits, and operational alerts you might encounter as an engineer on the MindVault platform team.

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
| [01-service-startup-failures.md](./01-service-startup-failures.md) | PagerDuty Incident | Critical | Services fail to start, Gradle build issues, config errors |
| [02-security-audit-findings.md](./02-security-audit-findings.md) | Security Report | Critical | SQL injection, path traversal, JWT bypass, XXE vulnerabilities |
| [03-coroutine-deadlocks.md](./03-coroutine-deadlocks.md) | Customer Escalation | High | API timeouts, unresponsive endpoints, resource exhaustion |
| [04-data-corruption-sync.md](./04-data-corruption-sync.md) | Slack Discussion | High | Document equality failures, stale cache, serialization errors |
| [05-billing-calculation-errors.md](./05-billing-calculation-errors.md) | Finance Escalation | Critical | Incorrect invoices, transaction failures, financial discrepancies |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Build/configuration issues that block all other work
- **Scenario 2**: Security vulnerabilities requiring careful code review
- **Scenario 3**: Concurrency bugs that are intermittent and hard to reproduce
- **Scenario 4**: Data integrity issues spanning multiple services
- **Scenario 5**: Cross-cutting concerns involving database, serialization, and business logic

## Tips for Investigation

1. **Run tests incrementally**: `./gradlew :module:test --no-daemon`
2. **Check coroutine behavior**: Look for blocking calls in suspend functions
3. **Review serialization**: Verify correct annotations and serializer registration
4. **Test with race detection**: Kotlin coroutines can have subtle concurrency bugs
5. **Check dependency chains**: Some bugs cannot be fixed until prerequisites are resolved

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in each module's `src/test/kotlin/` directory contain assertions that exercise these bugs
