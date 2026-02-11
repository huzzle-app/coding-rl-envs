# IncidentMesh Debugging Scenarios

This directory contains realistic debugging scenarios for the IncidentMesh emergency response coordination platform. Each scenario describes symptoms observed in production or staging environments without revealing the root cause.

## Scenario Index

| File | Type | Severity | Primary Domain |
|------|------|----------|----------------|
| `001_ambulance_routing_chaos.md` | Incident Report | P1/Critical | Routing, Dispatch |
| `002_compliance_audit_failure.md` | Audit Finding | P2/High | Compliance, Data Integrity |
| `003_leader_election_storm.md` | Alert/PagerDuty | P1/Critical | Consensus, Distributed State |
| `004_triage_priority_inversion.md` | Support Ticket | P2/High | Triage, Policy |
| `005_notification_blackhole.md` | Slack Discussion | P2/High | Communications, Resilience |

## How to Use These Scenarios

1. Read the scenario description carefully
2. Identify the affected components based on symptoms
3. Write test cases to reproduce the behavior
4. Use `go test -race -v ./...` to validate hypotheses
5. Fix bugs incrementally, checking test pass rates

## Scenario Format

Each scenario includes:
- **Context**: Background on when/how the issue was discovered
- **Symptoms**: Observable behaviors and error patterns
- **Impact**: Business/operational consequences
- **Investigation Notes**: What was already tried (if applicable)
- **Affected Timeframe**: When the issue started/was noticed

Scenarios do NOT include:
- Root cause analysis
- Specific code locations
- Solutions or fixes

The goal is to simulate realistic debugging work where engineers must investigate symptoms and discover root causes through code analysis and testing.
