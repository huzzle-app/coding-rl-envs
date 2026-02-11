# IncidentMesh

A Go-based global emergency response coordination platform with issues across 10 internal
packages and 13 microservices.

## Architecture

13 microservices (gateway, auth, identity, intake, triage, resources, routing, capacity,
communications, escalation, compliance, notifications, analytics) communicate through
shared contracts (IncidentCommand → IncidentEvent). Internal packages provide core logic
for config, triage, routing, capacity, escalation, security, workflow, concurrency,
communications, compliance, resilience, events, and consensus.

## Getting Started

```bash
# Run all tests (verbose, race detector)
go test -race -v ./...

# Verify with Harbor
bash harbor/test.sh
```

## Reward Thresholds (8-tier)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.00 |
| >= 0.95 | 0.78 |
| >= 0.85 | 0.55 |
| >= 0.70 | 0.38 |
| >= 0.55 | 0.22 |
| >= 0.40 | 0.12 |
| >= 0.25 | 0.05 |
| < 0.25 | 0.00 |

## Constraints

- Do not modify test files (`tests/` directory)
- Do not modify environment files (`environment/` directory)
- All bugs are embedded in the source codes in the source
- Fix bugs by correcting the logic, not by removing the marker comments
- A submission is correct when Harbor writes reward `1.0`

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-tier escalation policies, event pipeline refactoring, concurrent dispatch optimization, capacity federation API, unified routing subsystem |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Postmortem Generator, Alert Grouping Service, On-Call Schedule Manager |

These tasks test different software engineering skills while using the same codebase.
