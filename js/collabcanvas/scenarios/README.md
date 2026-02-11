# CollabCanvas Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the CollabCanvas team.

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
| [01-realtime-sync-failures.md](./01-realtime-sync-failures.md) | PagerDuty Incident | Critical | Missing updates, lost edits during collaboration |
| [02-security-audit-findings.md](./02-security-audit-findings.md) | Security Report | High | File upload vulnerabilities, OAuth CSRF |
| [03-memory-leak-presence.md](./03-memory-leak-presence.md) | Grafana Alert | Critical | Memory growing unbounded, event listener accumulation |
| [04-undo-redo-corruption.md](./04-undo-redo-corruption.md) | Customer Escalation | High | Undo restores wrong state, history corruption |
| [05-startup-database-errors.md](./05-startup-database-errors.md) | Deploy Failure | Critical | Application fails to start, circular dependency |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Clear real-time sync failures with visible symptoms
- **Scenario 2**: Security vulnerabilities found during penetration testing
- **Scenario 3**: Gradual memory leak that manifests over time
- **Scenario 4**: Subtle state management bugs requiring understanding of object references
- **Scenario 5**: Configuration and startup issues that block deployment

## Tips for Investigation

1. **Run the test suite**: `npm test` to see which tests are failing
2. **Check logs for patterns**: Error messages often point to specific code paths
3. **Use browser DevTools**: Network tab for WebSocket frames, Console for errors
4. **Review service files**: Bug comments in source indicate intentional defects
5. **Search for related code**: `grep -rn "keyword" src/`

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs
