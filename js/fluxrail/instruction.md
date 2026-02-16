# FluxRail

## Run

```bash
cd js/fluxrail
npm test
```

## Objective

Fix ~57 production defects across 15 core modules in a JavaScript global intermodal dispatch control plane. 9,040 tests must all pass (`npm test`).

Constraints:
- Do not edit files under `tests/`.
- Preserve deterministic replay/idempotency behavior.
- Maintain authorization and policy invariants.

## Bug Categories

| Category | Count | Examples |
|----------|-------|---------|
| Sort direction / comparison | ~10 | Ascending vs descending, wrong comparator |
| Wrong operator (+/-/*/÷) | ~12 | Addition instead of subtraction, multiply vs add |
| Boundary errors (> vs >=) | ~8 | Off-by-one at limits, wrong boundary condition |
| Inverted logic | ~7 | Negated boolean, swapped true/false |
| Wrong denominator/divisor | ~8 | Dividing by count instead of weight sum |
| Missing/wrong state mapping | ~5 | FSM returns wrong state, missing method |
| Formula errors | ~4 | Wrong mathematical formula, swapped parameters |
| Return value errors | ~3 | Negative instead of positive, wrong default |

## Modules

| Module | Description |
|--------|-------------|
| `src/core/dispatch.js` | Route selection, priority assignment, manifest building |
| `src/core/capacity.js` | Rebalancing, load shedding, dynamic buffers, forecasting |
| `src/core/policy.js` | Override rules, escalation, risk scoring, compliance |
| `src/core/resilience.js` | Retry backoff, circuit breaker, replay state |
| `src/core/replay.js` | Replay budget, event deduplication, ordered replay |
| `src/core/security.js` | Role-action authorization, token freshness, fingerprints |
| `src/core/statistics.js` | Percentiles, bounded ratios, moving averages, correlation |
| `src/core/workflow.js` | State transitions, FSM, guarded transitions |
| `src/core/queue.js` | Adaptive queue, throttling, fair scheduling |
| `src/core/routing.js` | Hub selection, partitioning, churn rate, geo routing |
| `src/core/ledger.js` | Ledger entries, balance exposure, sequence gaps |
| `src/core/authorization.js` | Payload signing, verification, delegation chains |
| `src/core/economics.js` | Cost projection, margin ratio, budget pressure, DCF |
| `src/core/sla.js` | Breach risk, breach severity, compliance, MTTR |
| `src/core/dependency.js` | Topological sort |

## Getting Started

1. Run `npm test` to see initial test results (~366/9040 passing)
2. Start with scenarios in `scenarios/` for investigation entry points
3. Bugs span dependency chains - fixing one module may unblock tests in others
4. Focus on core functions tested by `tests/stress/hyper-matrix.test.js` (8000 tests) first

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-modal connections, dispatch consolidation, congestion optimization, scheduling API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Passenger Flow Predictor, Delay Propagation Simulator, Crew Scheduling Optimizer |

These tasks test different software engineering skills while using the same codebase.
