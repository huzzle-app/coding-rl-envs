# FluxRail - Global Intermodal Dispatch and Reliability Control Plane

You are debugging a JavaScript control platform for real-time dispatch routing, capacity balancing,
policy overrides, resilience replay, and audit-safe publication across 15 core modules.

The codebase contains issues across dependency chains across dispatch, capacity, policy, security, and workflow layers.

## Difficulty

Hyper-Principal (3-6 days expected, 70-140h).

## Modules

| Module | Description |
|--------|-------------|
| `src/core/dispatch.js` | Route selection, priority assignment |
| `src/core/capacity.js` | Rebalancing, load shedding, dynamic buffers |
| `src/core/policy.js` | Override rules, escalation levels, policy evaluation |
| `src/core/resilience.js` | Retry backoff, circuit breaker, replay state |
| `src/core/replay.js` | Replay budget, event deduplication, ordered replay |
| `src/core/security.js` | Role-action authorization, token freshness, fingerprints |
| `src/core/statistics.js` | Percentiles, bounded ratios, moving averages |
| `src/core/workflow.js` | State transitions, workflow events |
| `src/core/queue.js` | Policy selection, throttling, penalty scoring |
| `src/core/routing.js` | Hub selection, deterministic partitioning, churn rate |
| `src/core/ledger.js` | Ledger entries, balance exposure, sequence gaps |
| `src/core/authorization.js` | Payload signing, verification, step-up auth |
| `src/core/economics.js` | Cost projection, margin ratio, budget pressure |
| `src/core/sla.js` | Breach risk, breach severity |
| `src/core/dependency.js` | Topological sort |

## Success Criteria

- All 9,040 tests pass (`npm test`).
- Replay and idempotency chaos suites are fully green.
- Security/compliance suites remain stable while fixing routing/capacity regressions.
- Do not edit files under `tests/`.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents. Each scenario describes symptoms and business impact without revealing exact fixes:

| Scenario | Format | Modules | Description |
| [001](scenarios/001-urgent-freight-wrong-priority.md) | Incident Report | dispatch | Urgent freight being deprioritized, SLA breaches |
| [002](scenarios/002-security-access-control-failures.md) | Security Alert | security, authorization | Access control returning inverted results |
| [003](scenarios/003-capacity-shed-not-triggering.md) | Slack Thread | capacity | Load shedding not triggering at limits |
| [004](scenarios/004-replay-state-corruption.md) | Post-Mortem | replay, resilience | State corruption during event replay |
| [005](scenarios/005-sla-breach-detection-delayed.md) | JIRA Ticket | sla, economics | Breach detection too late, cost miscalculations |

These scenarios cover 8 of issues categories. Use them as entry points for investigation or to understand the business context of the bugs you're fixing.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-modal connections, dispatch consolidation, congestion optimization, scheduling API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Passenger Flow Predictor, Delay Propagation Simulator, Crew Scheduling Optimizer |

These tasks test different software engineering skills while using the same codebase.
