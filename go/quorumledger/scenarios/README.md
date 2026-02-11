# QuorumLedger Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, monitoring alerts, and team discussions. Each scenario describes symptoms and business impact without revealing the exact fixes.

## Scenario Overview

| File | Type | Affected Module | Summary |
|------|------|-----------------|---------|
| `incident_001_settlement_fee_overcharge.md` | Incident Report | `internal/settlement/netting.go` | Settlement fees calculated at 10x the contracted rate, causing $2.3M in client disputes |
| `incident_002_consensus_quorum_failures.md` | Incident Report | `internal/consensus/quorum.go` | Consensus layer failing to achieve quorum on valid votes, Byzantine tolerance miscalculated |
| `ticket_003_statistics_sla_violations.md` | Support Ticket | `internal/statistics/latency.go` | SLA metrics showing negative percentiles, incorrect means, and boundary failures |
| `alert_004_failover_cascade.md` | Monitoring Alert | `internal/resilience/failover.go` | Circuit breakers triggering prematurely, leader election returning empty, retry backoff excessive |
| `slack_005_security_audit_concerns.md` | Team Discussion | `internal/security/policy.go` | Security audit findings: timing attacks, permission swaps, step-up bypass, missing audit events |

## How to Use These Scenarios

1. **Read the scenario** to understand the symptoms and business context
2. **Run the test suite** to confirm the failures mentioned in the scenario
3. **Investigate the affected module** based on the clues provided
4. **Fix the defects** without modifying test files
5. **Verify your fix** by running the relevant unit tests

## Running Tests

```bash
# Run all tests
go test -race -v ./...

# Run tests for a specific module
go test -race -v ./tests/unit/settlement_test.go
go test -race -v ./tests/unit/quorum_test.go
go test -race -v ./tests/unit/statistics_test.go
go test -race -v ./tests/unit/resilience_test.go
go test -race -v ./tests/unit/security_test.go
```

## Scenario Difficulty

Each scenario covers multiple related bugs within a module:

| Scenario | Bug Count | Interconnected |
|----------|-----------|----------------|
| Incident 001 | 4 | Settlement batching depends on fee calculation |
| Incident 002 | 6 | Byzantine tolerance affects quorum decisions |
| Ticket 003 | 6 | SLA checks use percentile and mean functions |
| Alert 004 | 5 | Circuit breaker state affects retry behavior |
| Slack 005 | 6-7 | Permission levels affect step-up requirements |

## Notes

- Scenarios describe **symptoms**, not solutions
- Test names and line numbers reference actual test files
- Log output formats match QuorumLedger's logging conventions
- Business impact sections reflect real treasury platform concerns
- Some bugs are interdependent; fixing one may unblock others

## Related Documentation

- [TASK.md](../TASK.md) - Full bug categories and completion criteria
- [pkg/models/models.go](../pkg/models/models.go) - Domain model definitions
- [tests/](../tests/) - Unit, integration, chaos, and stress tests
