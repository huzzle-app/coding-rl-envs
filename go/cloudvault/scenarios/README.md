# CloudVault Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the CloudVault team.

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
| [01-memory-leak-incident.md](./01-memory-leak-incident.md) | PagerDuty Incident | Critical | Memory usage growing unbounded, OOM kills |
| [02-security-audit-findings.md](./02-security-audit-findings.md) | Security Report | High | Pentest findings, OWASP violations |
| [03-sync-race-conditions.md](./03-sync-race-conditions.md) | Customer Escalation | High | Data corruption during concurrent syncs |
| [04-rate-limiter-bypass.md](./04-rate-limiter-bypass.md) | Slack Discussion | Medium | Rate limiting not working under load |
| [05-database-connection-exhaustion.md](./05-database-connection-exhaustion.md) | Grafana Alert | Critical | Connection pool exhausted, timeouts |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1-2**: Clear symptoms pointing to specific subsystems
- **Scenario 3-4**: Intermittent issues requiring deeper concurrency analysis
- **Scenario 5**: Cross-cutting concerns spanning multiple components

## Tips for Investigation

1. **Run tests with race detection**: `go test -race -v ./...`
2. **Check logs for patterns**: Error messages often point to specific code paths
3. **Use profiling tools**: `go tool pprof` for memory/CPU profiling
4. **Review recent changes**: `git log --oneline -20` to see recent commits
5. **Search for related code**: `grep -rn "keyword" internal/`

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs
