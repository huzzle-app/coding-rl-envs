# HelixOps Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and team discussions. Each scenario describes symptoms and business impact without revealing exact fixes.

## Scenario Overview

| File | Type | Affected Modules | Bug Categories |
|------|------|------------------|----------------|
| `incident_001_embedding_service_crash.md` | Incident Report | embeddings | A7, B4, F5, K3 |
| `incident_002_auth_security_vulnerability.md` | Security Incident | auth, gateway | D3, G1, I4, I5 |
| `ticket_003_billing_calculation_errors.md` | Support Ticket | billing | B5, C6, E5, E6, K5 |
| `alert_004_gateway_performance_degradation.md` | Monitoring Alert | gateway | A1, A2, D1, D2, I1, I2, I3 |
| `slack_005_collab_and_search_issues.md` | Team Discussion | collab, search, graph, analytics | A6, A8, B3, C3, C4, C5, F2, F3, F4, G2, G3, H1, H2, H3, J1, K1, K4 |

## How to Use These Scenarios

### For Debugging Practice

1. Read a scenario to understand the symptoms
2. Identify which modules and tests are affected
3. Run the relevant tests to confirm failures
4. Investigate the source code to find root causes
5. Apply fixes without breaking other functionality

### Running Tests

Each scenario references specific test failures. Run tests with:

```bash
# All tests
./gradlew test

# Module-specific tests
./gradlew :embeddings:test
./gradlew :auth:test
./gradlew :billing:test
./gradlew :gateway:test
./gradlew :collab:test
./gradlew :search:test
./gradlew :graph:test
./gradlew :analytics:test
```

## Scenario Types

### Incident Reports (INC-*)
Formal incident documentation following standard incident management practices. Includes timeline, impact assessment, and logs.

### Support Tickets (SUPPORT-*)
Customer-reported issues with business context. Includes customer impact, reproduction steps, and workaround attempts.

### Monitoring Alerts (ALT-*)
System-generated alerts with metrics, thresholds, and dashboard snapshots. Includes Grafana/Prometheus data and Kubernetes pod status.

### Team Discussions (Slack)
Informal engineering conversations that explore multiple related issues. Captures the collaborative debugging process.

## Bug Category Reference

| Category | Description | Scenarios |
|----------|-------------|-----------|
| A* | Coroutines | 1, 4, 5 |
| B* | Null Safety | 1, 3, 5 |
| C* | Data Classes/Sealed | 3, 5 |
| D* | Ktor Pipeline | 2, 4 |
| E* | Exposed ORM | 3, 5 |
| F* | Serialization | 1, 5 |
| G* | Delegation | 2, 5 |
| H* | Caching | 5 |
| I* | Security | 2, 4 |
| J* | Observability | 5 |
| K* | Modern Kotlin | 1, 3, 5 |

## Notes

- Scenarios describe **symptoms**, not solutions
- Log snippets and error messages are realistic but sanitized
- Test names indicate which functionality is broken
- Business impact helps prioritize debugging efforts
- Some bugs have dependencies - fixing one may unblock others
