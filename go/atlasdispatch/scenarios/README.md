# AtlasDispatch Debugging Scenarios

This directory contains realistic debugging scenarios for the AtlasDispatch maritime dispatch system. Each scenario describes symptoms observed in production without revealing the underlying root cause.

## Scenario Format

Each scenario is written as a realistic production incident:
- **Incident reports** from on-call engineers
- **Support tickets** from operations teams
- **Alert notifications** from monitoring systems
- **Slack discussions** between team members

## How to Use These Scenarios

1. Read the scenario to understand the symptoms
2. Use the symptoms to guide your investigation
3. Search the codebase for related functionality
4. Run tests to identify failing cases
5. Fix the underlying bugs

## Scenario Index

| File | Type | Domain Area | Severity |
|------|------|-------------|----------|
| `01_urgent_cargo_delays.md` | Incident Report | Allocator, Queue | P1 |
| `02_route_selection_anomaly.md` | Support Ticket | Routing | P2 |
| `03_security_audit_findings.md` | Security Alert | Security | P1 |
| `04_replay_divergence.md` | Slack Discussion | Resilience | P2 |
| `05_workflow_stuck_orders.md` | PagerDuty Alert | Workflow, Policy | P1 |

## Tips for Debugging

- Symptoms often indicate multiple related bugs
- Off-by-one errors are common in sorting and threshold logic
- Inverted comparisons can cause subtle behavioral issues
- Missing edge case handling affects boundary conditions
- Cross-module interactions may compound individual bugs
