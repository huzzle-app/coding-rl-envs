# VertexGrid Debugging Scenarios

This directory contains realistic debugging scenarios for the VertexGrid continental balancing and dispatch optimization platform. Each scenario describes symptoms, business impact, and affected tests without revealing exact solutions.

## Scenario Overview

| File | Format | Bug Categories | Primary Modules |
|------|--------|----------------|-----------------|
| `incident_001_dispatch_deadlock.md` | Incident Report | A5, A6 (Concurrency) | dispatch, tracking |
| `incident_002_billing_precision.md` | Incident Report | F1-F8 (Financial/Numerical) | billing, routes |
| `ticket_003_notification_failures.md` | Support Ticket | A8, A9, H1, H2, C4 (Concurrency, Caching, Spring) | notifications |
| `alert_004_concurrent_modification.md` | Monitoring Alert | A3, A4 (Concurrency) | dispatch |
| `slack_005_analytics_issues.md` | Team Discussion | B4, B5, G4, K3, J1 (Memory, Logic, Observability) | analytics |

## How to Use These Scenarios

### For Debugging Practice

1. Read the scenario document carefully
2. Note the described symptoms and affected tests
3. Run the referenced tests to reproduce the failures:
   ```bash
   mvn test -Dtest=DispatchServiceTest#test_no_parallel_stream_deadlock
   ```
4. Use the symptoms to guide your investigation
5. Fix the bugs and verify tests pass

### For Understanding Production Issues

Each scenario represents patterns commonly seen in production systems:

- **Incident Reports**: Post-mortem style documents for critical outages
- **Support Tickets**: Customer-reported issues with business context
- **Monitoring Alerts**: Automated detection of anomalies
- **Team Discussions**: Informal debugging conversations

## Bug Category Reference

| Category | IDs | Scenario Coverage |
|----------|-----|-------------------|
| Concurrency | A1-A9 | Incidents 1, 4; Ticket 3 |
| Memory/Collections | B1-B8 | Slack 5 |
| Spring/Event Sourcing | C1-C5 | Ticket 3; Alert 4 |
| Distributed State | D1-D5 | (implicit in scenarios) |
| Database/JPA | E1-E8 | (implicit in scenarios) |
| Financial/Numerical | F1-F10 | Incident 2 |
| Business Logic | G1-G6 | Incident 2; Slack 5 |
| Caching | H1-H5 | Ticket 3 |
| Security | I1-I8 | (separate security audit) |
| Observability | J1-J5 | Slack 5 |
| Modern Java | K1-K5 | Slack 5 |

## Grid/Energy Domain Context

VertexGrid operates continental-scale grid balancing:

- **Dispatch Optimization**: Matching generation resources to demand
- **Load Balancing**: Real-time power flow management
- **Billing Zones**: Geographic tariff regions
- **Grid Alerts**: Critical notifications for load shedding events
- **Fleet Analytics**: Performance metrics for generation units

Understanding the domain helps contextualize why bugs have significant business impact.

## Related Documentation

- Main task description: `../TASK.md`
- Bug family reference: `../TASK.md#bug-families`
- Test execution: `mvn test` or `mvn test -q`
