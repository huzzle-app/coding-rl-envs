# MercuryLedger - Hyper-Principal Maritime Settlement Reliability Environment

MercuryLedger coordinates settlement dispatch, replay resilience, corridor policy, and security controls for maritime operations. The platform manages berth allocation, multi-leg corridor planning, policy escalation/de-escalation, circuit breaker resilience, and real-time workflow tracking across eight interconnected services.

The codebase contains issues across deep cross-module dependencies and deterministic invariants.

## Difficulty

Hyper-Principal (70-140h expected).

## Test Breakdown

| Category | Tests |
|----------|-------|
| Unit tests (9 modules) | 10 |
| Extended tests | 49 |
| Advanced bug tests | 144 |
| Anti-tampering tests | 12 |
| Integration tests | 3 |
| Contract tests | 1 |
| Service tests (8 services × 4) | 32 |
| Service mesh matrix (stress) | 2,168 |
| Hyper matrix (stress) | 7,000 |
| **Total** | **9,419** |

## Infrastructure

- **PostgreSQL 15**: Primary persistence for orders, corridors, manifests, checkpoints
- **Redis 7**: Token store, rate limiter state, queue overflow buffer

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios to help contextualize the bugs:

| Scenario | Type | Description |
| [001 - Berth Capacity Crisis](scenarios/001_berth_capacity_crisis.md) | Incident Report | Port operations failing due to capacity threshold and slot conflict issues |
| [002 - Circuit Breaker Cascade](scenarios/002_circuit_breaker_cascading_failure.md) | Slack Thread | Resilience module not tripping correctly during partner API outage |
| [003 - Security Bypass](scenarios/003_security_bypass_pentest_findings.md) | Pentest Report | Path traversal, token scope, and replay attack vulnerabilities |
| [004 - Routing Optimization](scenarios/004_routing_optimization_failure.md) | JIRA Ticket | Suboptimal vessel routing due to weight miscalculations |
| [005 - Workflow State Machine](scenarios/005_workflow_state_machine_audit.md) | Audit Report | Compliance failures in state transitions and statistics |

Each scenario describes **symptoms and business impact** without revealing fixes. Use them to understand the real-world consequences of the bugs you are fixing.

## Objective

Fix production defects in source files only.

## Completion Criteria

- Full suite passes (`ruby -Ilib -Itests tests/run_all.rb`) with **9,419 scenarios**.
- Deterministic settlement, replay, and routing behavior is preserved.
- Security and workflow invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-currency settlement, circuit breaker consolidation, queue batch optimization, corridor analytics, Redis token migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Balance Snapshot Service, Transaction Categorization Engine, Ledger Export Service |

These tasks test different software engineering skills while using the same codebase.
