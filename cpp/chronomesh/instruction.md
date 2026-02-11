# ChronoMesh

Maritime dispatch reliability platform coordinating route dispatch, replay controls, queue pressure, and policy gating under tight latency constraints.

## Modules

- **Allocator** — Dispatch planning, berth management, cost estimation, rolling window scheduling
- **Routing** — Route selection, multi-leg planning, channel scoring, concurrent route table
- **Policy** — Operational mode escalation/de-escalation, SLA compliance, policy engine with history
- **Queue** — Priority queue, token-bucket rate limiter, queue health monitoring, load shedding
- **Security** — Digest hashing, HMAC signing, token management, path sanitisation, origin allowlist
- **Resilience** — Replay deduplication, checkpoint management, circuit breaker state machine
- **Statistics** — Percentile calculation, descriptive stats, response time tracking, heatmap generation
- **Workflow** — State transition graph, BFS shortest path, entity lifecycle management, audit logging
- **Models** — Dispatch orders, vessel manifests, severity classification, batch creation
- **Contracts** — Service definitions, URL resolution, contract validation, topological ordering

## Constraints

- Fix only source files (`src/*.cpp`, `include/chronomesh/core.hpp`)
- Do not modify test files under `tests/`
- Do not modify `environment/`, `harbor/`, or configuration files

## Success Criteria

All `ctest` tests pass including the 9200-scenario hyper-matrix:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Debug && cmake --build build && ctest --test-dir build --output-on-failure
```

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Time-series aggregation, queue decoupling, route optimization, batch API, WAL migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Downsampling Engine, Retention Policy Enforcer, Anomaly Detection Pipeline |

These tasks test different software engineering skills while using the same codebase.
