# PolarisCore - Hyper-Principal Logistics Orchestration Environment

You are debugging a Rust cold-chain logistics control plane coordinating shipment allocation,
routing, policy risk gates, security checks, and replay/failover resilience across 13 services.

The codebase contains issues across coupled modules with deep dependency chains.

## Difficulty

Hyper-Principal (70-140h expected).

## Services

Gateway, Identity, Intake, Routing, Allocator, Policy, Resilience, Security, Audit, Analytics, Notifications, Reporting, Fulfillment.

## Success Criteria

- All tests pass via `cargo test`.
- Replay/failover chaos paths remain stable.
- Security and compliance gates stay intact through optimization fixes.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios simulating production incidents:

| Scenario | Description | Severity |
| [01 - Hub Selection Incident](scenarios/01_hub_selection_incident.md) | Shipments routed to blocked hubs during maintenance | P1 |
| [02 - Compliance Review Backlog](scenarios/02_compliance_review_backlog.md) | Risk scores underreported, compliance tiers miscalculated | P2 |
| [03 - Retry Storm](scenarios/03_retry_storm.md) | Exponential backoff and replay budget causing infrastructure overload | P1 |
| [04 - Signature Validation Bypass](scenarios/04_signature_validation_bypass.md) | Security vulnerability in cryptographic signature validation | P0 |
| [05 - Queue Starvation](scenarios/05_queue_starvation.md) | Priority inversion, SLA miscalculation, economics errors | P2 |

Each scenario includes:
- Incident details (alerts, tickets, Slack threads)
- Observed symptoms and business impact
- Affected test files for investigation
- Resolution criteria (without revealing exact fixes)

Use these scenarios to practice incident-driven debugging: start from symptoms, trace to failing tests, investigate source modules, and fix root causes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-zone scheduling, risk refactoring, queue optimization, tracking API, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Weather Impact Assessor, Cold Chain Monitor, Expedition Cost Estimator |

These tasks test different software engineering skills while using the same codebase.
