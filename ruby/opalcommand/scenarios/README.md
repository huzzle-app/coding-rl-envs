# OpalCommand Debugging Scenarios

This directory contains realistic debugging scenarios based on the bugs present in the OpalCommand codebase. Each scenario describes symptoms, business impact, and failing tests without revealing the exact fixes.

## Scenario Overview

| File | Type | Severity | Affected Components |
|------|------|----------|---------------------|
| `incident_001_settlement_replay_corruption.md` | Incident Report | P1-Critical | resilience.rb, ledger service |
| `incident_002_routing_cost_overruns.md` | Incident Report | P2-High | routing.rb, gateway service |
| `ticket_003_priority_queue_mishandling.md` | Support Ticket | High | queue.rb, intake service |
| `alert_004_security_audit_failures.md` | Security Alert | High | security.rb, auth/audit services |
| `slack_005_analytics_dashboard_issues.md` | Team Discussion | Medium | analytics/reporting services, statistics.rb |

## How to Use These Scenarios

1. **Read the scenario** - Understand the business context and symptoms
2. **Review failing tests** - Each scenario lists related test failures
3. **Investigate the code** - Use the affected component paths as starting points
4. **Fix the bugs** - Make targeted fixes based on symptoms (not revealed solutions)
5. **Verify** - Run the test suite to confirm your fixes

## Scenario Types

### Incident Reports (incident_*)
Formal post-mortem style documents with timelines, business impact, and technical details. These represent production issues requiring immediate attention.

### Support Tickets (ticket_*)
User-facing issues reported by claims supervisors and operations staff. Focus on business impact and user experience.

### Security Alerts (alert_*)
Automated security monitoring alerts highlighting authentication, authorization, and audit trail issues.

### Slack Discussions (slack_*)
Informal team conversations that reveal multiple related issues discovered during normal operations.

## Domain Context

OpalCommand manages catastrophe claims processing for an insurance company:

- **Claims** - Property damage claims from natural disasters (hurricanes, floods, etc.)
- **Settlement** - Financial resolution of claims, including adjuster assessments
- **Adjusters** - Field personnel who assess damage and recommend settlements
- **SLA** - Service Level Agreements for claim response times
- **CAT Response** - Catastrophe response operations during major events
- **Compliance** - Regulatory requirements for audit trails and reporting

## Bug Categories Covered

The scenarios collectively cover these bug categories:

- **Comparison operators** - `>` vs `>=`, `<` vs `<=`, boundary errors
- **Sort direction** - Ascending vs descending, min vs max
- **Missing validation** - Incomplete field checks, missing state validation
- **Wrong coefficients** - Incorrect multipliers, thresholds, defaults
- **Formula errors** - Wrong divisor, missing terms, precision issues
- **Security gaps** - URL encoding, case sensitivity, timing issues
- **Deduplication** - Insufficient key composition
- **State machine** - Missing transitions, terminal state handling

## Running Tests

To verify fixes, run the full test suite:

```bash
ruby -Ilib -Itests tests/run_all.rb
```

Or run specific test files:

```bash
ruby -Ilib -Itests tests/unit/resilience_test.rb
ruby -Ilib -Itests tests/services/analytics_service_test.rb
```

## Notes

- Scenarios describe SYMPTOMS, not solutions
- Business impact is realistic for an insurance claims context
- Test names map to actual tests in the `tests/` directory
- Each scenario may reference multiple related bugs
- Some bugs have dependencies - fixing one may unblock others
