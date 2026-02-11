# PulseMap Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the PulseMap team.

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
| [01-startup-crash.md](./01-startup-crash.md) | PagerDuty Incident | Critical | Application fails to start, plugin exception, serialization errors |
| [02-tile-service-deadlock.md](./02-tile-service-deadlock.md) | Grafana Alert | Critical | Request timeouts, thread pool exhaustion, map tile API unresponsive |
| [03-sensor-deduplication-failures.md](./03-sensor-deduplication-failures.md) | Customer Escalation | High | Duplicate sensor readings, data inconsistency, memory growth |
| [04-security-audit-findings.md](./04-security-audit-findings.md) | Security Report | High | SQL injection, path traversal, authorization bypass |
| [05-geocoding-async-issues.md](./05-geocoding-async-issues.md) | Slack Discussion | Medium | Geocoding returns wrong addresses, Flow aggregation wrong, missing backpressure |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Critical startup blockers - must be fixed first before anything else works
- **Scenario 2**: Kotlin coroutine deadlocks and concurrency issues
- **Scenario 3**: Kotlin-specific data class semantics and equality pitfalls
- **Scenario 4**: Security vulnerabilities requiring careful code review
- **Scenario 5**: Subtle async/coroutine bugs requiring deep understanding of Kotlin Flow and coroutine semantics

## Tips for Investigation

1. **Run tests with verbose output**: `./gradlew test --info`
2. **Check logs for patterns**: Stack traces often point to specific code paths
3. **Understand Kotlin semantics**: Many bugs stem from Kotlin-specific behaviors (data class equality, coroutine contexts, extension function shadowing)
4. **Review recent changes**: `git log --oneline -20` to see recent commits
5. **Search for related code**: `grep -rn "keyword" src/`

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `src/test/kotlin/com/pulsemap/` directory contain assertions that exercise these bugs
