# DocuVault Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the DocuVault team.

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
| [01-application-startup-failure.md](./01-application-startup-failure.md) | PagerDuty Incident | Critical | Application fails to start, bean creation errors |
| [02-security-penetration-test.md](./02-security-penetration-test.md) | Security Report | Critical | SQL injection, path traversal, JWT vulnerabilities |
| [03-concurrent-document-corruption.md](./03-concurrent-document-corruption.md) | Customer Escalation | High | Data loss, race conditions, thread-safety issues |
| [04-database-performance-degradation.md](./04-database-performance-degradation.md) | Grafana Alert | High | N+1 queries, connection exhaustion, transaction failures |
| [05-cache-inconsistency-slack.md](./05-cache-inconsistency-slack.md) | Slack Discussion | Medium | Stale cache data, Spring proxy issues, collection errors |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Clear startup failures with stack traces
- **Scenario 2**: Security vulnerabilities identified by pentest
- **Scenario 3-4**: Intermittent issues requiring concurrency/database analysis
- **Scenario 5**: Cross-cutting concerns spanning caching, collections, and Spring proxies

## Tips for Investigation

1. **Start with startup errors**: Fix bean creation issues first - nothing else works until the application loads
2. **Check Spring profiles**: Ensure beans are available under the test profile
3. **Run specific test categories**: `mvn test -Dtest="com.docuvault.concurrency.*"`
4. **Enable debug logging**: Add `-Dlogging.level.org.springframework=DEBUG`
5. **Check for proxy bypass**: Self-invocation bypasses `@Transactional`, `@Async`, `@Cacheable`

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `src/test/java/com/docuvault/` directory contain assertions that exercise these bugs
