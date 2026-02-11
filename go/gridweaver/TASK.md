# GridWeaver - National Smart Grid Orchestration Platform

You are debugging a distributed smart-grid control platform built with Go microservices.
The platform coordinates forecast ingestion, grid state estimation, dispatch optimization,
substation controls, outage response, and demand-response actions across regions.

The codebase contains issues across 12 services and 11 internal packages. All tests must pass before the task is complete.

## Architecture

### Internal Packages
| Package | Purpose |
|---------|---------|
| `internal/config` | Platform configuration and validation |
| `internal/topology` | Grid topology graph, pathfinding, capacity |
| `internal/dispatch` | Dispatch planning, merit order, constraints |
| `internal/estimator` | Load estimation, forecasting, meter quality |
| `internal/security` | Authentication, authorization, input validation |
| `internal/resilience` | Retry logic, circuit breakers, load shedding |
| `internal/demandresponse` | DR program management and dispatch |
| `internal/outage` | Outage tracking, prioritization, recovery |
| `internal/workflow` | Control decision orchestration |
| `internal/concurrency` | Worker pools, fan-out, pipelines |
| `internal/events` | Event ordering, deduplication, windowing |
| `internal/consensus` | Leader election, quorum, split-brain detection |

### Services
| Service | Purpose |
|---------|---------|
| Gateway | API entry point, routing, header validation |
| Auth | Authentication, role management |
| Forecast | Load forecasting, temperature/wind impact |
| Topology | Region management, edge deduplication |
| Estimator | State estimation caching |
| Dispatch | Dispatch execution, event history |
| Constraint | Constraint validation and ordering |
| Control | Substation state management |
| Outage | Outage reporting and resolution |
| Demand Response | DR dispatch tracking |
| Settlement | Billing calculations |
| Audit | Compliance logging and querying |

## Infrastructure

- NATS JetStream (event streaming)
- PostgreSQL (persistent storage)
- Redis (caching)
- InfluxDB (time-series telemetry)
- etcd (distributed coordination)

## Known Issues

Current state: most tests broken. Main concerns include API endpoints, background processing, and database operations.

Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run full test suite
go test -race -v ./...

# Run targeted tests
go test -race -v ./tests/unit/...
go test -race -v ./tests/integration/...
go test -race -v ./tests/stress/...
```

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that describe symptoms observed in production-like environments. These scenarios present the problems from an operator's perspective without revealing the underlying root causes.

| Scenario | Type | Focus Area |
| `01_consensus_election_failure.md` | Incident Report | Leader election, quorum, split-brain detection |
| `02_dispatch_negative_generation.md` | Support Ticket | Dispatch planning, numerical errors |
| `03_topology_capacity_mismatch.md` | Slack Discussion | Grid topology, capacity calculations |
| `04_event_ordering_anomaly.md` | Alert Investigation | Event pipeline, filtering, deduplication |
| `05_resilience_cascade_failure.md` | Post-Mortem Draft | Circuit breakers, retry logic, concurrency |

Use these scenarios to guide your investigation. Each describes observable symptoms that point to bugs in specific packages without explicitly naming the fixes.

## Success Criteria

- All 1160+ tests pass
- No regressions in safety/security categories
- Full test suite pass rate reaches 100%
- `go test -race` detects no data races after fixes

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-region dispatch, event pipeline, topology performance, DR bidding, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Load forecasting, renewable optimizer, fault detector |

These tasks test different software engineering skills while using the same codebase.
