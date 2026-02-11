# NebulaChain Debugging Scenarios

This directory contains realistic debugging scenarios based on the production defects in the NebulaChain supply provenance platform. Each scenario presents symptoms, logs, and business impact without revealing the exact fixes.

## Scenario Overview

| File | Type | Component | Summary |
|------|------|-----------|---------|
| `incident_001_*.md` | Incident Report | Routing Engine | Routes selecting highest-latency channels instead of lowest |
| `incident_002_*.md` | Incident Report | Policy Engine | Escalation thresholds and cooldowns misconfigured |
| `ticket_003_*.md` | Support Ticket | Dispatch Models | Vessel classification and urgency scoring errors |
| `alert_004_*.md` | Monitoring Alert | Resilience System | Replay deduplication keeping stale events |
| `slack_005_*.md` | Team Discussion | Security Service | Path traversal bypass and scope validation issues |

## How to Use These Scenarios

These scenarios simulate real-world debugging situations. Use them to:

1. **Identify the affected code** - Each scenario references specific modules and test files
2. **Trace symptoms to root causes** - Logs and error messages point toward defects
3. **Validate fixes** - Referenced tests will pass once the underlying bugs are fixed

## Scenario Categories

### Incident Reports (incident_*.md)
Formal incident reports following standard SRE practices. Include:
- Executive summary and business impact
- Detailed timeline of events
- Log excerpts showing the problematic behavior
- Affected test suites

### Support Tickets (ticket_*.md)
Customer-reported issues with specific examples. Include:
- Customer message with concrete examples
- Internal investigation notes
- API response samples
- Contract/specification references

### Monitoring Alerts (alert_*.md)
Automated monitoring system alerts. Include:
- Metric thresholds and current values
- Dashboard snapshots
- Detailed observations with timestamps
- Runbook references

### Team Discussions (slack_*.md)
Collaborative debugging conversations. Include:
- Multiple engineer perspectives
- Code snippets and examples
- Prioritization decisions
- Related ticket/issue references

## Related Test Suites

The scenarios reference tests across multiple categories:

- **Unit tests**: `tests/unit/*.test.js` - Core module behavior
- **Service tests**: `tests/services/*.service.test.js` - Service layer logic
- **Integration tests**: `tests/integration/*.test.js` - Cross-module flows
- **Stress tests**: `tests/stress/hyper-matrix.test.js` - 7,000 parameterized cases
- **Service mesh**: `tests/stress/service-mesh-matrix.test.js` - 2,168 service scenarios

## Debugging Approach

For each scenario:

1. **Read the symptoms** - Understand what is happening from the user/operator perspective
2. **Study the logs** - Identify patterns in the observed vs. expected behavior
3. **Locate the code** - Find the referenced modules in `src/core/` or `services/`
4. **Find BUG comments** - Each defect is marked with `// BUG:` describing the issue
5. **Run the tests** - Use `npm test` to verify fixes

## Supply Chain Domain Glossary

| Term | Definition |
|------|------------|
| Dispatch Ticket | A work order for moving cargo through the supply chain |
| Provenance | The chain of custody and origin verification for shipments |
| Berth | A designated location where vessels dock for loading/unloading |
| Channel | A routing path between origin and destination (e.g., Suez, Cape) |
| Escalation Policy | Rules for elevating response level based on failure patterns |
| Replay | Re-processing events after a failure to restore consistent state |
| Circuit Breaker | A pattern to prevent cascading failures by stopping requests |
| SLA | Service Level Agreement - contractual delivery time guarantees |
