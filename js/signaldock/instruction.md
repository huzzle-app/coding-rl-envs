# SignalDock - Hyper-Principal Maritime Dispatch Reliability Environment

## Overview
- **Name:** SignalDock
- **Language:** JavaScript (Node.js)
- **Bug Count:** issues
- **Test Count:** 9213 scenario tests
- **Difficulty:** Hyper-Principal (70-140h expected)

## Bug Categories
| Category | Count | Files |
|----------|-------|-------|
| Scheduling | 7 | scheduling.js |
| Routing | 6 | routing.js |
| Policy | 5 | policy.js |
| Resilience | 5 | resilience.js |
| Security | 5 | security.js |
| Statistics | 4 | statistics.js |
| Workflow | 4 | workflow.js |
| Queue | 5 | queue.js |
| Models | 4 | dispatch-ticket.js |

## Getting Started
```bash
npm install
npm test
```

## Constraints
- Do not modify files under `tests/`.
- Preserve deterministic ordering and replay behavior.
- Keep security and policy controls enforced.

## Success Criteria
- Full test suite passes (`npm test`) with **9213+ scenarios**.
- All bugs fixed in source files only.
- No regressions in existing functionality.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Zone aggregation, Policy DSL, Circuit breaker optimization, Manifest API, Replay storage |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | AIS Signal Decoder, Port Congestion Monitor, Vessel ETA Predictor |

These tasks test different software engineering skills while using the same codebase.
