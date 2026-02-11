# HelixOps - Apex-Principal Reliability Environment

HelixOps coordinates clinical manufacturing execution, quality-policy enforcement, deterministic replay, and distributed routing resilience.

The environment contains issues across deep dependency chains:
- **80 handcrafted core bugs** across Kotlin-specific failure families.
- **1170 expanded apex bugs** mapped onto real service test signatures.
- **12,000+ stress scenarios** (hyper-matrix pressure).

## Difficulty

Apex-Principal (5-7 days expected, 120-168h).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents:

| Scenario | Type | Description |
| `incident_001_embedding_service_crash.md` | P1 Incident | Embedding pipeline crashes with uninitialized properties, batch cancellation, and stack overflows |
| `incident_002_auth_security_vulnerability.md` | P0 Security | JWT algorithm bypass, timing attacks, and stale token cache issues |
| `ticket_003_billing_calculation_errors.md` | Support Ticket | Invoice total mismatches, tax calculation errors, and concurrent transfer failures |
| `alert_004_gateway_performance_degradation.md` | Monitoring Alert | Thread pool exhaustion, deadlocks, and security vulnerabilities in request handling |
| `slack_005_collab_and_search_issues.md` | Team Discussion | Real-time sync failures, cache stampedes, and MDC context propagation issues |

Each scenario describes symptoms, logs, and failing tests without revealing exact fixes. Use them as starting points for debugging.

## Completion Criteria

- Full suite passes (`./gradlew test`) including 12,000+ stress cases.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | API key management, unified query DSL, connection pooling, GraphQL federation, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | SSO integration, document templates, usage analytics |

These tasks test different software engineering skills while using the same codebase.
