# TradeEngine Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and engineering discussions. Each scenario describes symptoms without revealing solutions.

## Scenario Format

Each scenario is presented as one of:
- **Incident Report**: PagerDuty/Opsgenie-style alerts with runbook sections
- **Support Ticket**: Customer-reported issues with reproduction steps
- **Slack Thread**: Engineering discussion of observed behavior
- **Alert Dashboard**: Monitoring system alerts with metrics
- **Post-Mortem Draft**: Initial investigation of a past incident

## Using These Scenarios

1. Read the scenario carefully, noting all symptoms and context
2. Use the described symptoms to guide your investigation
3. The scenario describes WHAT is happening, not WHY
4. Multiple bugs may contribute to a single scenario
5. Some scenarios are interconnected

## Scenarios

| File | Type | Summary |
|------|------|---------|
| `001_deadlock_matching.md` | Incident | Matching engine hangs under load |
| `002_money_precision.md` | Support Ticket | Portfolio values incorrect by small amounts |
| `003_stale_portfolio.md` | Slack Thread | Portfolio not updating after trades |
| `004_alert_floods.md` | Alert Dashboard | Price alerts triggering incorrectly or not at all |
| `005_auth_security.md` | Post-Mortem Draft | Security audit findings on authentication |

## Difficulty Indicators

- **Scenario 001**: Concurrency (A category bugs)
- **Scenario 002**: Financial calculations (F category bugs)
- **Scenario 003**: Caching (H category bugs)
- **Scenario 004**: Concurrency + float precision (A, F category bugs)
- **Scenario 005**: Security (I category bugs)
