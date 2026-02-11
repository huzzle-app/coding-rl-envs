# ClearLedger Debugging Scenarios

This directory contains realistic debugging scenarios for the ClearLedger clearing and settlement platform. Each scenario describes symptoms as they would appear in a production incident, without revealing the underlying cause.

## Scenario Overview

| File | Type | Severity | Affected Modules |
|------|------|----------|------------------|
| `001_settlement_discrepancy.md` | Incident Report | P1 | Settlement, Risk, Statistics |
| `002_reconciliation_drift.md` | Engineering Ticket | P2 | Reconciliation, Resilience, Audit |
| `003_workflow_deadlock.md` | Slack Discussion | P1 | Workflow, Routing, Queue |
| `004_compliance_override_failure.md` | Alert Runbook | P2 | Compliance, Authz, SLA |
| `005_window_watermark_rejection.md` | Customer Escalation | P3 | LedgerWindow, Routing, Statistics |

## How to Use These Scenarios

1. Read the scenario to understand the reported symptoms
2. Investigate the codebase to identify potential root causes
3. Write failing tests that reproduce the issue
4. Fix the underlying bugs in the affected modules
5. Verify the fix resolves all described symptoms

## Scenario Format

Each scenario uses a realistic format:
- **Incident Reports**: Production alerts with metrics and timeline
- **Engineering Tickets**: JIRA-style tickets with acceptance criteria
- **Slack Discussions**: Team conversations during debugging sessions
- **Alert Runbooks**: Automated alert with playbook steps
- **Customer Escalations**: Support tickets with customer impact

## Tips for Debugging

- Symptoms often span multiple modules due to bug dependency chains
- Integer division and boundary conditions are common issue patterns
- Pay attention to edge cases in filter logic and comparisons
- Check that terminal states and validation logic are complete
