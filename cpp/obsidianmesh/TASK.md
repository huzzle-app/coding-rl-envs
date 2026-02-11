# ObsidianMesh - Apex-Principal Reliability Environment

ObsidianMesh is an autonomous traffic-grid command-loop system built in C++20. It manages deterministic replay correction, constrained routing, and strict safety-policy gates across 13 interconnected microservices. The codebase implements scheduling, resilience patterns (circuit breakers, checkpointing, bulkheads), security primitives (HMAC signing, token management, rate limiting), real-time telemetry, and event-driven workflow orchestration.

## Architecture

### Source Modules (14 files)

| Module | File | Lines | Description |
| Allocator | `src/allocator.cpp` | ~245 | Dispatch planning, berth allocation, cost estimation |
| Routing | `src/routing.cpp` | ~215 | Route selection, multi-leg planning, channel scoring |
| Policy | `src/policy.cpp` | ~205 | Escalation/de-escalation state machine, SLA compliance |
| Queue | `src/queue.cpp` | ~220 | Priority queue, rate limiting, load shedding |
| Security | `src/security.cpp` | ~240 | HMAC signing, token management, path sanitization |
| Resilience | `src/resilience.cpp` | ~330 | Replay, circuit breaker, checkpoint, bulkhead patterns |
| Statistics | `src/statistics.cpp` | ~240 | Percentiles, variance, EMA, heatmap generation |
| Workflow | `src/workflow.cpp` | ~315 | State machine, BFS shortest path, entity lifecycle |
| Model | `src/model.cpp` | ~155 | Dispatch model, severity classification, vessel manifest |
| Contracts | `src/contracts.cpp` | ~125 | Service definitions, topology, contract validation |
| Config | `src/config.cpp` | ~120 | Service configuration, feature flags, environment setup |
| Concurrency | `src/concurrency.cpp` | ~130 | Atomic counters, barriers, work stealing, cycle detection |
| Events | `src/events.cpp` | ~140 | Event log, time-window filtering, gap detection |
| Telemetry | `src/telemetry.cpp` | ~100 | Error rates, latency buckets, health scoring, alerting |

### Microservices (ports 8140-8147)

| Service | Port | Dependencies |
| gateway | 8140 | routing, policy |
| routing | 8141 | policy |
| policy | 8142 | (none) |
| resilience | 8143 | policy |
| analytics | 8144 | routing |
| audit | 8145 | (none) |
| notifications | 8146 | policy |
| security | 8147 | (none) |

| Category | ID Range | Count | Area | Bug Types |
| L: Setup/Config | CHM001-005 | 5 | Config defaults, validation | Wrong defaults, boundary errors |
| K: Contracts | CHM006-007, CHM010, CHM053-054, CHM115-116 | 7 | Service definitions, topology | Missing fields, wrong depth |
| I: Data Model | CHM008-009, CHM011-012, CHM045, CHM117 | 6 | Severity, vessel, dispatch | Swapped labels, wrong formulas |
| A: Concurrency | CHM013-019 | 7 | Barriers, partitioning, CAS | Wrong operators, inverted logic |
| C: Allocator | CHM020, CHM027-028, CHM061-063, CHM075 | 7 | Weighted allocation, capacity | Wrong formulas, rounding errors |
| D: Queue | CHM021-022, CHM029-030, CHM064, CHM078, CHM082 | 7 | Batch enqueue, fairness, pressure | Missing parameters, wrong denominators |
| E: Workflow | CHM023-026, CHM051-052, CHM059-060, CHM080, CHM085-086, CHM118-120 | 14 | Transitions, completion, paths | Wrong counts, unit errors |
| B: Event Ordering | CHM031-038 | 8 | Sorting, dedup, windowing | Descending sorts, boundary exclusion |
| F: Resilience | CHM039-044, CHM097-106 | 16 | Replay, circuit breaker, backoff | Missing jitter, inverted checks |
| G: Routing | CHM046-050, CHM056-058, CHM065-067, CHM079 | 12 | Scoring, failover, conversion | Wrong weights, conversion factors |
| J: Security | CHM087-096 | 10 | Token, password, HMAC, permissions | Format errors, reversed logic |
| H: Observability | CHM107-114 | 8 | Error rate, latency, health | Inverted formulas, unit errors |
| S: Statistics | CHM068-074, CHM083-084 | 9 | Weighted mean, EMA, correlation | Wrong denominators, missing operations |
| P: Policy | CHM046-047, CHM056, CHM076-077, CHM081 | 6 | Weight ordering, thresholds | Fixed values, wrong sorts |

## Getting Started

```bash
cmake -B build && cmake --build build
ctest --test-dir build --output-on-failure
```

## Constraints

- Only edit files under `src/` and `include/obsidianmesh/`
- Do **not** modify files under `tests/`
- Preserve deterministic replay and scheduling behavior
- Keep security checks, policy gates, and audit invariants intact
- All bugs are compilable logic errors (wrong operators, formulas, constants)

## Success Criteria

- Full test suite passes: `ctest --test-dir build --output-on-failure`
- All 120 `BUG(CHMxxx)` markers resolved
- Hyper-matrix (12500 scenarios) passes with 0 failures
- No regressions in existing passing tests

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that describe production incidents and issues without revealing exact fixes:

| Scenario | Type | Component | Description |
| `incident_001_auth_token_rejection.md` | P1 Incident | Security | Authentication tokens rejected after upgrade; token format and session expiry issues |
| `incident_002_event_replay_data_loss.md` | P1 Incident | Resilience | Data loss during replay recovery; boundary conditions and event eviction bugs |
| `ticket_003_statistics_billing_discrepancy.md` | Support Ticket | Statistics | Enterprise customer billing discrepancies from calculation errors |
| `alert_004_circuit_breaker_cascade.md` | Critical Alert | Resilience | Cascade failure from circuit breaker threshold and retry bugs |
| `slack_005_workflow_bottleneck.md` | Team Discussion | Workflow | Multiple workflow metric bugs affecting operational dashboards |

These scenarios present symptoms, logs, and failing tests to help practice debugging from real-world problem descriptions rather than explicit bug markers.

## Difficulty

**Apex-Principal** (5-7 days expected, 120-168h).

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-zone partitioning, queue management refactoring, routing optimization, event streaming, time-series migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Topology optimizer, health monitor, traffic shaper |

These tasks test different software engineering skills while using the same codebase.
