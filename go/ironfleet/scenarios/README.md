# IronFleet Debugging Scenarios

This directory contains realistic debugging scenarios that simulate how production issues would be reported and investigated in the IronFleet autonomous convoy fleet management system.

## Purpose

These scenarios are designed to:
- Present bugs as they would appear in production (symptoms, not solutions)
- Reference actual failing tests from the test suite
- Show realistic operational and business impact
- Include authentic logs, metrics, and alert configurations
- Help developers practice debugging in a domain-appropriate context

## Scenario Index

| File | Format | Domain Area | Key Symptoms |
|------|--------|-------------|--------------|
| `incident_001_mission_prioritization.md` | Incident Report | Mission Allocator | Low-urgency convoys dispatched before high-urgency |
| `incident_002_signature_verification.md` | Security Incident | Security Module | All command signatures rejected |
| `ticket_003_convoy_routing.md` | Support Ticket | Routing | Highest-latency routes selected |
| `alert_004_fleet_health.md` | Prometheus Alert | Analytics | Negative health scores |
| `slack_005_replay_convergence.md` | Slack Discussion | Resilience | Event replay losing data |

## Using These Scenarios

1. **Read the scenario** to understand the reported symptoms
2. **Identify failing tests** mentioned in the scenario
3. **Run the test suite** to confirm the failures: `go test -race -v ./...`
4. **Investigate the affected components** listed in each scenario
5. **Fix the underlying bugs** in the source files
6. **Verify the fix** by re-running the tests

## Scenario Formats

### Incident Reports (INC-*)
Formal post-incident documentation format used for P0/P1 issues. Includes timeline, impact assessment, and metrics.

### Support Tickets (FLEET-SUP-*)
User-reported issues with reproduction steps, expected vs actual behavior, and workaround attempts.

### Prometheus Alerts
Alert definitions with current firing values, dashboard context, and runbook actions.

### Slack Discussions
Real-time team debugging conversations showing collaborative investigation.

## Test Reference

Scenarios reference tests from:
- `tests/unit/core_test.go` - Core module unit tests
- `tests/chaos/replay_test.go` - Chaos engineering tests
- `tests/services/*_service_test.go` - Service layer tests
- `tests/stress/hyper_matrix_test.go` - Parameterized stress tests (7,000+ cases)

## Note

These scenarios describe **symptoms only**. They intentionally do not reveal the exact code fix required. The goal is to practice the full debugging workflow from symptom observation through root cause identification.
