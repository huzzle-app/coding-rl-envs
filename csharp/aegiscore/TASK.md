# AegisCore - Hyper-Principal Maritime Dispatch Reliability Environment

AegisCore manages route dispatch, replay controls, queue pressure, and security policy gates for maritime operations. The platform coordinates vessel berth allocation, multi-leg route planning, policy escalation/de-escalation, circuit breaker resilience, and real-time workflow tracking across eight interconnected services.

The codebase contains issues across deep dependency links across policy, routing, replay, and workflow transitions.

## Difficulty

Hyper-Principal (70-140h expected).

## Infrastructure

- **PostgreSQL 15**: Primary persistence for orders, routes, manifests, checkpoints
- **Redis 7**: Token store, rate limiter state, queue overflow buffer

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that simulate production incidents, support tickets, and team discussions. Each scenario describes symptoms and business impact without revealing the exact fix.

| # | Scenario | Type | Module |
| 1 | [Dispatch Priority Inversion](scenarios/001_dispatch_priority_inversion.md) | Incident Report | Allocator |
| 2 | [Policy Escalation Premature](scenarios/002_policy_escalation_premature.md) | JIRA Ticket | Policy |
| 3 | [Security Path Traversal](scenarios/003_security_path_traversal.md) | Security Alert | Security |
| 4 | [Queue Wait Time Explosion](scenarios/004_queue_wait_time_explosion.md) | Slack Thread | QueueGuard |
| 5 | [Workflow Departed Cancellation](scenarios/005_workflow_departed_cancellation.md) | Post-Mortem | Workflow |

Use these scenarios to practice debugging by:
1. Reading the scenario to understand symptoms
2. Running the mentioned failing tests
3. Investigating the source code
4. Fixing the root cause

## Completion Criteria

- Full suite passes (`dotnet test`) with **9200+ scenarios**.
- Deterministic replay/routing behavior is preserved.
- Security and policy invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | RBAC integration, Queue refactoring, Circuit breaker perf, Security events, Token store migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Threat Detection Engine, Access Log Analyzer, Secret Rotation Service |

These tasks test different software engineering skills while using the same codebase.
