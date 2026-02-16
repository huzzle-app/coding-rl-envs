# TransitCore - Intermodal Dispatch and Capacity Command Platform

You are debugging a Java 21 orchestration platform for high-frequency transit dispatch:
route selection, capacity balancing, compliance controls, replay-safe state convergence,
and audit/report publication.

The codebase contains issues across core modules. All tests must pass before completion.

## Services

- Gateway
- Auth
- Intake
- Routing
- Capacity
- Dispatch
- Workflow
- Policy
- Security
- Audit
- Analytics
- Notifications
- Reporting

## Infrastructure

- PostgreSQL
- Redis
- NATS

## Bug ID Taxonomy

| ID Range | Category |
|----------|----------|
| TRN001-TRN005 | Dispatch/Routing |
| TRN006-TRN008 | Policy/Escalation |
| TRN009 | Security/Token |
| TRN010-TRN015 | Resilience/Queue |
| TRN016-TRN019 | SLA/Compliance |
| TRN020-TRN023 | Watermark/Audit |
| TRN024-TRN025 | Workflow/Statistics |
| TRN026-TRN030 | SLA/Statistics |
| TRN031-TRN032 | Audit/Hash |
| TRN033 | Watermark/Lag |
| TRN034 | Routing/Churn |
| TRN035 | Resilience/Replay |

## Success Criteria

- All 1648 tests pass.
- Capacity, policy, and resilience suites stay fully green.
- Full-suite pass rate reaches 100%.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter as an engineer on the TransitCore platform. Each scenario describes **symptoms only** - observable behavior, error messages, and operator reports - without revealing the underlying code fixes.

| Scenario | Type | Description |
| [01-slow-route-selection](scenarios/01-slow-route-selection.md) | Operations Escalation | Dispatches consistently taking longest routes, SLA breaches |
| [02-capacity-overcommit](scenarios/02-capacity-overcommit.md) | PagerDuty Incident | Fleet capacity exceeded, vehicle shedding not triggering |
| [03-escalation-failures](scenarios/03-escalation-failures.md) | Post-Mortem | Critical incidents not escalating, queue bypasses rejected |
| [04-replay-drift](scenarios/04-replay-drift.md) | Slack Discussion | State reconstruction errors after failover |
| [05-sla-reporting-anomalies](scenarios/05-sla-reporting-anomalies.md) | Dashboard Alert | SLA metrics showing incorrect breach classification |

See [scenarios/README.md](scenarios/README.md) for investigation tips and usage guidance.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-Modal Transfer Coordination, Queue Domain Extraction, Decision Caching, Telemetry API, Event Sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Passenger Info Display, Accessibility Routing, Arrival Predictor |

These tasks test different software engineering skills while using the same codebase.
