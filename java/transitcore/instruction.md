# TransitCore - Intermodal Dispatch and Capacity Command Platform

## Task

Fix all defects in this ultra-principal Java environment so the full suite passes.

## Getting Started

```bash
cd java/transitcore
mvn test -q
```

## Reward Profile

Very sparse 10-threshold schedule:

- `< 22%` -> `0.0`
- `22-35%` -> `0.015`
- `36-51%` -> `0.05`
- `52-66%` -> `0.11`
- `67-79%` -> `0.19`
- `80-89%` -> `0.31`
- `90-95%` -> `0.47`
- `96-98%` -> `0.66`
- `99%` -> `0.85`
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
