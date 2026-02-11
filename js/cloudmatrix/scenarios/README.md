# CloudMatrix Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, security audits, and operational alerts you might encounter as an engineer on the CloudMatrix team.

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
| [01-realtime-collaboration-incident.md](./01-realtime-collaboration-incident.md) | PagerDuty Incident | Critical | Document divergence, cursor drift, undo corruption |
| [02-security-audit-report.md](./02-security-audit-report.md) | Security Report | Critical | SQL injection, SSRF, prototype pollution, ReDoS |
| [03-websocket-connection-issues.md](./03-websocket-connection-issues.md) | Customer Escalation | High | Disconnections, ghost users, memory leaks, message ordering |
| [04-search-indexing-failures.md](./04-search-indexing-failures.md) | Slack Discussion | High | Missing documents, stale autocomplete, injection vulnerabilities |
| [05-service-startup-failures.md](./05-service-startup-failures.md) | PagerDuty Incident | Critical | Circular imports, WebSocket bind race, missing exchanges/indexes |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Real-time collaboration bugs - requires understanding CRDT/OT algorithms
- **Scenario 2**: Security vulnerabilities - requires security mindset and input validation knowledge
- **Scenario 3**: WebSocket management - requires understanding connection lifecycle and cleanup
- **Scenario 4**: Search and indexing - requires understanding distributed search and caching
- **Scenario 5**: Service startup - requires understanding module loading and async initialization

## Tips for Investigation

1. **Run tests first**: `npm test` to see which tests are failing
2. **Check logs for patterns**: Error messages often point to specific code paths
3. **Search for related code**: Use grep to find relevant functions
4. **Understand the architecture**: 15 microservices with complex interactions
5. **Look for common patterns**: Missing await, race conditions, input validation

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs

## Bug Categories Covered

| Scenario | Bug Categories |
|----------|---------------|
| 01 - Real-Time | A (Real-Time Sync), D (Collaboration Features) |
| 02 - Security | I (Security), C (Document Processing), G (Auth & Permissions) |
| 03 - WebSocket | B (WebSocket Management), L (Setup Hell) |
| 04 - Search | E (Search & Indexing), I (Security) |
| 05 - Startup | L (Setup Hell), K (Configuration) |
