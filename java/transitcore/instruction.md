# TransitCore - Intermodal Dispatch and Capacity Command Platform

## Task

Fix all defects in this ultra-principal Java environment so the full suite passes.

## Getting Started

```bash
cd java/transitcore
mvn test -q
```

## Reward Profile

Sparse 8-threshold schedule (ultra-principal):

- `< 25%` -> `0.0`
- `25-39%` -> `0.05`
- `40-54%` -> `0.12`
- `55-69%` -> `0.22`
- `70-84%` -> `0.38`
- `85-94%` -> `0.55`
- `95-99%` -> `0.78`
- `100%` -> `1.0`

## Success Criteria

- All tests pass
- Replay determinism under ordering/idempotency stress
- Compliance and security checks remain green

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-Modal Transfer Coordination, Queue Domain Extraction, Decision Caching, Telemetry API, Event Sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Passenger Info Display, Accessibility Routing, Arrival Predictor |

These tasks test different software engineering skills while using the same codebase.
