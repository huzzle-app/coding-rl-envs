# QuorumLedger - Hyper-Principal Distributed Treasury Reliability Environment

QuorumLedger orchestrates quorum consensus, ledger settlement, replay resilience, risk gating, and strict security policy enforcement across a distributed treasury platform with 14 internal modules.

The codebase contains issues spanning 14 categories with dependency chains across consensus, settlement, replay, policy, security, and infrastructure layers.

## Difficulty

Hyper-Principal (3-6 days expected, 70-140h).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that simulate production incidents and help guide investigation:

| Scenario | Type | Focus Area |
| `incident_001_settlement_fee_overcharge.md` | Incident Report | Settlement fee calculations are 10x too high |
| `incident_002_consensus_quorum_failures.md` | Incident Report | Consensus layer rejecting valid quorum votes |
| `ticket_003_statistics_sla_violations.md` | Support Ticket | SLA metrics showing negative/incorrect values |
| `alert_004_failover_cascade.md` | Monitoring Alert | Circuit breakers and leader election cascading failures |
| `slack_005_security_audit_concerns.md` | Team Discussion | Security audit findings (timing attacks, permission issues) |

Each scenario describes **symptoms and business impact** without revealing exact fixes. Use them to understand real-world context for the bugs you're investigating.

## Completion Criteria

- Full suite passes (`go test -race -v ./...`) with **7,583 test scenarios**.
- Deterministic consensus, settlement, and failover behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-currency netting, consensus strategies, ledger optimization, streaming reconciliation, legacy migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cross-Ledger Bridge Service, Compliance Reporting Engine, Event Sourcing Journal |

These tasks test different software engineering skills while using the same codebase.
