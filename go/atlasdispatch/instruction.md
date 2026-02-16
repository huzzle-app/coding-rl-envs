Fix production defects in AtlasDispatch by editing source code only.

## Environment

- **Language**: Go
- **Tier**: Hyper-Principal (70–140h estimated)
- **Tests**: ~18,300 scenarios across 7 test packages
- **Initial pass rate**: ~1.7% (most tests fail due to embedded bugs)

## Bug Categories

| Category | Modules | Examples |
|----------|---------|----------|
| Sort/comparison inversion | allocator, routing, queue | Ascending instead of descending, inverted comparators |
| Off-by-one / boundary | allocator, routing, policy, resilience | `>` vs `>=`, `<` vs `<=`, loop bounds |
| Missing validation | allocator, security | Earliest-time constraint, URL-encoding bypass |
| Wrong constants/coefficients | routing, policy, resilience, statistics | Delay surcharge, checkpoint threshold, EMA init |
| Logic errors | policy, resilience, workflow, statistics | Mutual exclusivity, threshold multiplication, formula bugs |
| State machine | workflow, policy | Missing transitions, wrong defaults, no rollback |
| Missing behavior | workflow, allocator, resilience | No audit log writes, no preemption tracking, no gap-aware checkpointing |
| Concurrency | statistics, resilience | Missing mutex locks, TOCTOU races |
| Domain logic | models, queue, statistics | Fleet utilization denominator, weighted mean normalization, correlation formula |

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and routing behavior.
- Keep security and policy controls enforced.
- The test suite verifies file integrity and enforces a minimum test count.

## Getting Started

```bash
# Run full test suite
go test -race -v ./...

# Run specific package tests
go test -race -v ./tests/unit/...
go test -race -v ./tests/stress/...
go test -race -v ./tests/concurrency/...
```

## Source Structure

| Directory | Description |
|-----------|-------------|
| `internal/allocator/` | Dispatch planning, berth scheduling, cost estimation |
| `internal/routing/` | Route selection, multi-leg planning, scoring |
| `internal/policy/` | Operational mode state machine, SLA compliance |
| `internal/security/` | Token management, signatures, path sanitization |
| `internal/resilience/` | Event replay, circuit breakers, checkpoints |
| `internal/queue/` | Priority queue, rate limiting, load shedding |
| `internal/statistics/` | Percentiles, variance, correlation, moving averages |
| `internal/workflow/` | State transitions, batch transitions, audit logging |
| `pkg/models/` | Core domain types, fleet utilization, prioritization |

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios describing symptoms:

| Scenario | Type | Key Symptoms |
|----------|------|-------------|
| 01_urgent_cargo_delays | Incident | Priority inversion, wrong capacity/turnaround |
| 02_route_selection_anomaly | Support Ticket | Highest-latency routes selected, inverted scoring |
| 03_security_audit_findings | Security Alert | Token validation inverted, path traversal, case sensitivity |
| 04_replay_divergence | Slack Discussion | Keeps oldest events, checkpoint/circuit breaker bugs |
| 05_workflow_stuck_orders | PagerDuty Alert | Missing transitions, wrong defaults, policy threshold bugs |

Primary objective: make the full suite pass with robust production-safe fixes.
