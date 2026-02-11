# IncidentMesh — Global Emergency Response Coordination Platform

You are debugging a mission-critical emergency response platform built with Go microservices.
IncidentMesh coordinates dispatch centers, triage policies, geospatial routing, hospital capacity,
communications failover, consensus-based leader election, and compliance audit trails.

The codebase contains issues across 10 internal packages and 13 microservices.
All 1220+ tests must pass before the task is complete.

## Architecture

```
┌──────────┐ ┌──────────┐ ┌──────────┐
│ Gateway │→ │ Auth │→ │ Identity │
└────┬─────┘ └──────────┘ └──────────┘
 │
┌────▼─────┐ ┌──────────┐ ┌──────────┐
│ Intake │→ │ Triage │→ │Resources │
└────┬─────┘ └──────────┘ └──────────┘
 │
┌────▼─────┐ ┌──────────┐ ┌──────────┐
│ Routing │→ │ Capacity │→ │ Dispatch │
└────┬─────┘ └──────────┘ └──────────┘
 │
┌────▼──────┐ ┌───────────┐ ┌───────────┐
│Escalation │ │Compliance │ │ Analytics │
└────┬──────┘ └───────────┘ └───────────┘
 │
┌────▼───────────┐ ┌──────────────┐
│ Communications │ │ Notifications│
└────────────────┘ └──────────────┘
```

## Module Overview

### Internal Packages (`internal/`)

| Package | Description | Bugs |
| `config` | Environment variable loading, URL construction, config merge | L01-L08 |
| `triage` | Priority scoring, severity classification, triage policy | P01-P12 |
| `routing` | Geospatial routing, ETA estimation, region filtering | R01-R10 |
| `capacity` | Hospital bed ranking, capacity normalization | S15-S18 |
| `escalation` | Escalation level calculation, time-based triggers | P13-P16 |
| `security` | Authorization, token validation, rate limiting, encryption | F01-F12 |
| `workflow` | Sequential/parallel execution, safe map ops, metrics | A01-A08 |
| `concurrency` | Worker pool, fan-out, pipeline, throttle | A09-A16 |
| `communications` | Channel failover, retry delays, circuit breaker | G01-G08 |
| `compliance` | Audit trails, retention, compliance scoring | D09-D12, K01-K04 |
| `resilience` | Replay, idempotency, backoff, deduplication | D01-D08 |
| `events` | Event pipeline, windowing, filtering, correlation | H01-H06 |
| `consensus` | Leader election, lease management, split-brain detect | S01-S14 |

### Microservices (`services/`)

| `identity` | Identity resolution | — |
| `intake` | Batch command intake and queuing | A17-A18 |
| `triage` | Priority routing and classification | R13-R14 |
| `resources` | Resource allocation and pool management | A19-A20 |
| `routing` | Optimal route and weight calculation | R11-R12 |
| `capacity` | Regional capacity checking | — |
| `communications` | Message tracing and channel logging | H09-H10 |
| `escalation` | Escalation retry and backoff | G09-G10 |
| `compliance` | Audit and compliance tagging | K05-K06 |
| `notifications` | Notification dispatch and priority | G11-G12 |
| `analytics` | Event tracking and metric labels | H07-H08 |

### Shared (`shared/contracts/`, `pkg/models/`)

- `contracts.go` — IncidentCommand, IncidentEvent, AuditEntry, NotificationPayload
- `models.go` — Incident, Unit, Facility, DispatchPlan, TriageResult, AuditRecord, IncidentSnapshot

## Getting Started

```bash
# Run all tests
go test -race -v ./...

# Run specific package tests
go test -race -v ./tests/unit/...
go test -race -v ./tests/integration/...
go test -race -v ./tests/services/...
go test -race -v ./tests/stress/...

# Count passing/failing
go test -race -v ./... 2>&1 | grep -c '--- PASS:'
go test -race -v ./... 2>&1 | grep -c '--- FAIL:'
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents, audit findings, and support tickets. These describe symptoms without revealing solutions:

| Scenario | Type | Description |
| `001_ambulance_routing_chaos.md` | Incident Report | Ambulances dispatched to farthest locations instead of nearest; ETA calculations broken |
| `002_compliance_audit_failure.md` | Audit Finding | HIPAA compliance failures: missing audit fields, wrong retention, inverted policies |
| `003_leader_election_storm.md` | PagerDuty Alert | Consensus thrashing with 2,847 leader changes/hour; split-brain conditions |
| `004_triage_priority_inversion.md` | Support Ticket | Critical patients classified as low priority; severity calculations broken |
| `005_notification_blackhole.md` | Slack Discussion | Notifications failing silently; retry storms; priority inversion in alerts |

Use these scenarios to:
1. Practice production debugging workflows
2. Understand how symptoms map to code defects
3. Prioritize fixes based on business impact

## Success Criteria

- All 1220+ tests pass (`--- FAIL:` count = 0)
- Security and compliance test groups must be fully green
- Final full-suite pass rate is 100%
- Reward of 1.0 from `bash harbor/test.sh`

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-tier escalation policies, event pipeline refactoring, concurrent dispatch optimization, capacity federation API, unified routing subsystem |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Postmortem Generator, Alert Grouping Service, On-Call Schedule Manager |

These tasks test different software engineering skills while using the same codebase.
