Fix production defects in MercuryLedger by editing source code only.

## Environment

MercuryLedger is a hyper-principal maritime settlement reliability platform built with Ruby 3.2 / Minitest. It coordinates berth allocation, multi-leg corridor planning, policy escalation, circuit breaker resilience, and real-time workflow tracking across eight interconnected services.

## Architecture

The codebase has three layers:
- **Core modules** (9): `lib/mercuryledger/core/*.rb` — domain logic, state machines, data structures
- **Service modules** (8): `services/{gateway,audit,analytics,notifications,policy,resilience,routing,security}/service.rb` — microservice wrappers
- **Contracts**: `shared/contracts/contracts.rb` — service registry, dependency graph, URL resolution

Bugs are embedded in the source codes in source files. The issues IDs (MGL0001–MGL1240) map to specific test failures through `environment/reward.rb`. Bugs appear in:
- 9 core modules (~54 bugs): off-by-one errors, wrong thresholds, missing validations
- 8 service modules (~40 bugs): inverted logic, missing features, wrong weights
- Contracts (~5 bugs): wrong protocol, missing fields, off-by-one in depth calculation

## Codebase Structure

- `lib/mercuryledger/core/order.rb` - Orders, Severity, VesselManifest, OrderFactory
- `lib/mercuryledger/core/dispatch.rb` - Berth allocation, settlement planning, cost estimation
- `lib/mercuryledger/core/routing.rb` - Corridor selection, channel scoring, multi-leg planning
- `lib/mercuryledger/core/policy.rb` - Policy state machine, escalation/de-escalation, SLA
- `lib/mercuryledger/core/queue.rb` - Load shedding, priority queue, rate limiting
- `lib/mercuryledger/core/security.rb` - SHA-256 digest, manifest signing, token store, path sanitization
- `lib/mercuryledger/core/resilience.rb` - Event replay, circuit breaker FSM, checkpoints
- `lib/mercuryledger/core/statistics.rb` - Percentile, variance, moving average, heatmap
- `lib/mercuryledger/core/workflow.rb` - State transitions, BFS shortest path, audit log
- `shared/contracts/contracts.rb` - Service registry, topological ordering, URL resolution
- `services/*/service.rb` - 8 service modules (gateway, audit, analytics, notifications, policy, resilience, routing, security)

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and routing behavior.
- Keep security and policy controls enforced.
- All thread-safe classes use `Mutex` for synchronization — maintain this pattern.

## Bug Count

1,240 issues across 18 modules (9 core + 8 services + 1 contracts) with deep cross-module dependency chains.

## Test Breakdown

| Category | Tests |
|----------|-------|
| Unit tests | 10 |
| Extended tests | 49 |
| Advanced bug tests | 144 |
| Anti-tampering tests | 12 |
| Integration tests | 3 |
| Contract tests | 1 |
| Service tests | 32 |
| Service mesh matrix | 2,168 |
| Hyper matrix | 7,000 |
| **Total** | **9,419** |

## Reward Tiers (8-threshold)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.0 |
| >= 0.95 | 0.78 |
| >= 0.85 | 0.55 |
| >= 0.70 | 0.38 |
| >= 0.55 | 0.22 |
| >= 0.40 | 0.12 |
| >= 0.25 | 0.05 |
| < 0.25 | 0.0 |

## Running Tests

```bash
cd ruby/mercuryledger && ruby -Ilib -Itests tests/run_all.rb
```

Primary objective: make the full suite pass with robust production-safe fixes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-currency settlement, circuit breaker consolidation, queue batch optimization, corridor analytics, Redis token migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Balance Snapshot Service, Transaction Categorization Engine, Ledger Export Service |

These tasks test different software engineering skills while using the same codebase.
