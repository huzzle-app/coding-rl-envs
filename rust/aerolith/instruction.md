# Aerolith

Fix bugs in a Rust satellite constellation control platform.

## Run

```bash
docker compose up -d
cargo test
bash harbor/test.sh
```

A submission is correct when Harbor writes reward `1.0`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Conjunction Screening, Telemetry Pipeline, Power Budget, Ground Station API, Circuit Breaker 2.0 |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Debris Avoidance Planner, Solar Panel Optimizer, Telemetry Compression |

These tasks test different software engineering skills while using the same codebase.
