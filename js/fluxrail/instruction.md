# FluxRail

## Run

```bash
cd js/fluxrail
npm test
```

## Objective

Fix production defects across dispatch, capacity, policy, resilience, security, queue, and analytics modules until full pass rate reaches 100%.

Constraints:
- Do not edit files under `tests/`.
- Preserve deterministic replay/idempotency behavior.
- Maintain authorization and policy invariants.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-modal connections, dispatch consolidation, congestion optimization, scheduling API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Passenger Flow Predictor, Delay Propagation Simulator, Crew Scheduling Optimizer |

These tasks test different software engineering skills while using the same codebase.
