# PolarisCore Debugging Scenarios

This directory contains realistic debugging scenarios for the PolarisCore cold-chain logistics orchestration platform. Each scenario simulates a real-world incident that engineers might encounter in production.

## Scenario Overview

| Scenario | Type | Affected Systems | Severity |
|----------|------|------------------|----------|
| 01 - Hub Selection Incident | PagerDuty Alert | Routing, Gateway | P1 |
| 02 - Compliance Review Backlog | Ops Ticket | Policy, Audit | P2 |
| 03 - Retry Storm | Slack Thread | Resilience, Notifications | P1 |
| 04 - Signature Validation Bypass | Security Advisory | Security, Identity | P0 |
| 05 - Queue Starvation | Customer Escalation | Queue, Statistics, Economics | P2 |
| 06 - Fulfillment State Violations | Ops Escalation | Workflow, State Machine | P2 |

## How to Use These Scenarios

1. Read the scenario file to understand the incident context
2. Use `cargo test` to run the test suite and observe failures
3. Trace symptoms back to failing tests mentioned in the scenario
4. Investigate the relevant source modules
5. Fix bugs while maintaining system invariants

## Scenario Format

Each scenario includes:
- **Incident trigger**: How the issue was discovered (alert, customer complaint, audit)
- **Symptoms observed**: What operators/users are experiencing
- **Business impact**: Why this matters (revenue, compliance, SLA)
- **Affected tests**: Which test files are failing (without revealing exact fixes)
- **Timeline**: When the issue started and escalation history

## Tips for Debugging

- Start with the failing tests to understand expected behavior
- Trace data flow through the affected modules
- Look for boundary conditions, sort order, and arithmetic errors
- Consider how bugs in one module cascade to dependent services
- Run `cargo test -- --nocapture` for detailed output
