# TensorForge - Apex-Principal Rust Reliability Platform

## Architecture

14 source modules covering allocation, routing, policy, resilience, security, workflow, statistics, events, concurrency, config, telemetry, and contracts. 13 microservices with dependency DAG.

## Getting Started

```bash
cargo test
```

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.

## Success Criteria

- All 12,tests pass
- Replay determinism preserved
- Security invariants enforced
- Policy escalation/deescalation correct

## Reward Function

The environment uses 10-tier sparse rewards (Apex):

```
Pass Rate → Reward
≥ 1.00 → 1.0
≥ 0.99 → 0.85
≥ 0.96 → 0.66
≥ 0.90 → 0.47
≥ 0.80 → 0.31
≥ 0.67 → 0.19
≥ 0.52 → 0.11
≥ 0.36 → 0.05
≥ 0.22 → 0.015
< 0.22 → 0.0
```

Good luck!

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Batch scheduler, workflow refactoring, statistics optimization, routing API, lock-free queue |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Model Registry, GPU Memory Allocator, Training Checkpoint Manager |

These tasks test different software engineering skills while using the same codebase.
