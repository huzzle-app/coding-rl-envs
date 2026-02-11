# MediaFlow Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, customer escalations, security audits, and operational alerts you might encounter as an engineer on the MediaFlow team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, and user reports. Your task is to:

1. Analyze the symptoms and error messages
2. Form hypotheses about root causes
3. Investigate the codebase to confirm your hypotheses
4. Identify the buggy code
5. Implement fixes
6. Verify the fixes don't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-video-quality-complaints.md](./01-video-quality-complaints.md) | Customer Reports | High | Poor video quality in high-motion content despite premium subscriptions |
| [02-billing-discrepancies.md](./02-billing-discrepancies.md) | Customer Escalation | Critical | Proration errors, double charges, immediate access revocation on cancel |
| [03-cache-stampede-incident.md](./03-cache-stampede-incident.md) | PagerDuty Incident | Critical | Cache miss thundering herd, database connection exhaustion during popular release |
| [04-security-audit-findings.md](./04-security-audit-findings.md) | Security Report | Critical | SQL injection, JWT validation weaknesses, permission cache issues |
| [05-distributed-system-failures.md](./05-distributed-system-failures.md) | Incident Report | Critical | Split-brain, event ordering violations, lock timeouts during region failover |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1**: Focused on a single service (transcode), clear calculation errors
- **Scenario 2**: Multiple related issues in billing logic, requires tracing payment flows
- **Scenario 3**: Infrastructure-level caching issues, requires understanding distributed systems
- **Scenario 4**: Security vulnerabilities across multiple endpoints, requires security mindset
- **Scenario 5**: Complex distributed systems failures, requires understanding consensus and coordination

## Bug Categories Covered

| Scenario | Categories |
|----------|------------|
| Video Quality | Media Processing (F) - bitrate calculation, motion factor |
| Billing | Billing Logic (G) - proration, subscription state, races |
| Cache Stampede | Caching & CDN (H) - stampede protection, TTL jitter, hot keys |
| Security Audit | Security (I) - SQL injection, input validation; Auth (E) - JWT, permissions |
| Distributed Failures | Distributed Consensus (A) - leader election, locks; Event Sourcing (B) - ordering, idempotency |

## Tips for Investigation

1. **Read error messages carefully**: They often point to specific code paths
2. **Check the timeline**: Understanding when things started failing helps isolate the issue
3. **Look for patterns**: Are failures correlated with specific content types, user actions, or times?
4. **Run tests locally**: `npm test` will show which tests are failing
5. **Search for related code**: Use grep to find related functionality
6. **Check configuration**: Many bugs are configuration-related (timeouts, thresholds)

## Common Commands

```bash
# Run all tests
npm test

# Run specific test file
npm test -- tests/unit/transcode.test.js

# Search for bug-related code
grep -rn "bitrate" services/transcode/
grep -rn "idempotency" shared/events/

# Check test output for specific failures
npm test 2>&1 | grep -A5 "FAIL"
```

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation and environment overview
- Test files in `tests/` directory contain assertions that exercise these bugs
- `environment/reward.js` - Reward function for tracking fix progress
