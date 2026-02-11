# SignalDock Debugging Scenarios

This directory contains realistic debugging scenarios for the SignalDock maritime dispatch system. Each scenario presents symptoms, impact, and context without revealing the underlying bugs.

## Scenario Overview

| ID | Title | Type | Subsystem |
|----|-------|------|-----------|
| 001 | Low-Priority Vessels Getting Berth Allocation | Incident Report | Scheduling |
| 002 | External Services Never Recovering After Failures | Slack Thread | Resilience |
| 003 | Disaster Recovery Replay Produces Inconsistent State | Post-Incident Review | Resilience/Replay |
| 004 | Unauthenticated Requests Bypassing Origin Validation | Security Alert | Security |
| 005 | Monitoring Dashboard Shows Impossible Metrics | Support Ticket | Statistics/Queue |

## How to Use These Scenarios

1. **Read the scenario** to understand the reported symptoms and business impact
2. **Identify the affected subsystem(s)** from the clues provided
3. **Investigate the codebase** to find the root cause
4. **Fix the bugs** and verify your fixes with the test suite

## Scenario Formats

The scenarios use different formats to simulate real-world debugging contexts:

- **Incident Report**: Formal P1/P2 incident with timeline and technical details
- **Slack Thread**: Informal engineering discussion with real-time troubleshooting
- **Post-Incident Review (PIR)**: Structured analysis after an outage
- **Security Alert**: SOC notification with evidence and risk assessment
- **Support Ticket**: Customer-reported issue with business impact

## Tips for Investigation

- Each scenario may involve multiple bugs
- Symptoms often mask the true root cause
- Look for off-by-one errors, inverted logic, and wrong operators
- Consider how bugs in one module might cascade to others
- The test suite (`npm test`) will validate your fixes

## Covered Bug Categories

These scenarios cover bugs in:

- **Scheduling**: Berth allocation, priority ordering, time window management
- **Routing**: Channel selection, latency calculations, route optimization
- **Resilience**: Circuit breakers, event replay, checkpoint management
- **Security**: Origin validation, path sanitization, digest generation
- **Policy**: Escalation thresholds, operational state checks
- **Queue**: Priority queue sizing, rate limiting, health metrics
- **Statistics**: Percentile calculations, mean/variance, utilization
- **Workflow**: State transitions, terminal state detection, active counts
