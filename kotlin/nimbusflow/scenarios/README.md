# NimbusFlow Debugging Scenarios

This directory contains realistic debugging scenarios that mirror production incidents in the NimbusFlow maritime dispatch system. Each scenario describes symptoms, user reports, and observability data without revealing the underlying root cause.

## Scenario Index

| File | Type | Affected Systems |
|------|------|------------------|
| `001_tanker_priority_incident.md` | PagerDuty Incident | Allocator, Dispatch Planning |
| `002_route_cost_anomaly.md` | Finance Audit Report | Routing, Cost Estimation |
| `003_policy_escalation_chaos.md` | Slack Thread | Policy Engine, Escalation |
| `004_security_path_traversal.md` | Security Alert | Security, Path Sanitization |
| `005_replay_state_divergence.md` | Ops Postmortem | Resilience, Event Replay |

## How to Use

These scenarios are designed for debugging practice. Each presents:

1. **Context** - What the system should do
2. **Symptoms** - What users/operators observed
3. **Data** - Logs, metrics, or traces that hint at the problem
4. **Impact** - Business consequences of the issue

Your task is to investigate the codebase, identify the root cause, and propose a fix. The scenarios do NOT reveal which file or function contains the bug.

## Difficulty

These scenarios correspond to bugs in a Hyper-Principal tier environment. Expect cross-module interactions, subtle boundary conditions, and incorrect business logic.
