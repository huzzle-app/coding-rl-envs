# ChronoMesh Debugging Scenarios

This directory contains realistic debugging scenarios based on production incidents, support tickets, and operational alerts from the ChronoMesh maritime dispatch platform.

## Scenario Index

| File | Type | Primary Area | Severity |
|------|------|--------------|----------|
| `01_dispatch_priority_incident.md` | Incident Report | Allocator, Queue | P1 - Critical |
| `02_routing_cost_anomaly.md` | Analytics Alert | Routing, Contracts | P2 - High |
| `03_vessel_workflow_stuck.md` | Support Ticket | Workflow, Model | P2 - High |
| `04_security_bypass_postmortem.md` | Security Postmortem | Security, Resilience | P0 - Critical |
| `05_statistics_sla_drift.md` | Ops Alert + Slack | Statistics, Policy | P2 - High |

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable problems that operators, users, or automated systems would notice. They do not reveal the underlying bugs or solutions.

When debugging:
1. Read the scenario to understand the reported symptoms
2. Reproduce the issue using the test suite or manual testing
3. Trace through the relevant code paths
4. Identify root causes by examining the logic in `src/` files
5. Fix the bugs while preserving the intended behavior

## Scenario Format

Each scenario follows a realistic format:
- **Incident Reports**: Timestamp, severity, impact, timeline, symptoms
- **Support Tickets**: Customer report, steps to reproduce, expected vs actual
- **Alerts**: Metric thresholds, triggered conditions, recent changes
- **Slack Discussions**: Team conversations with observations and theories
- **Postmortems**: Root cause analysis requests, impact assessments

## Connection to Test Failures

These scenarios correlate with test failures in the test suite. Running:

```bash
cmake --build build && ctest --test-dir build --output-on-failure
```

Will surface test failures that manifest the symptoms described in these scenarios.
