# MercuryLedger Debugging Scenarios

This directory contains realistic debugging scenarios for the MercuryLedger maritime settlement platform. Each scenario presents symptoms, business impact, and failing test references without revealing specific fixes.

## Scenario Overview

| Scenario | Type | Severity | Primary Modules |
|----------|------|----------|-----------------|
| [001 - Berth Capacity Crisis](./001_berth_capacity_crisis.md) | Incident Report | P1 | Dispatch, Order |
| [002 - Circuit Breaker Cascade](./002_circuit_breaker_cascading_failure.md) | Slack Thread | P1 | Resilience |
| [003 - Security Bypass](./003_security_bypass_pentest_findings.md) | Pentest Report | High | Security |
| [004 - Routing Optimization](./004_routing_optimization_failure.md) | JIRA Ticket | High | Routing, Gateway |
| [005 - Workflow State Machine](./005_workflow_state_machine_audit.md) | Audit Report | Critical | Workflow, Statistics |

## How to Use These Scenarios

1. **Read the scenario** to understand the symptoms and business context
2. **Run the test suite** to identify failing tests: `ruby -Ilib -Itests tests/run_all.rb`
3. **Investigate the referenced modules** based on the scenario hints
4. **Fix the underlying bugs** in source files only (do not modify tests)
5. **Verify your fixes** by re-running the test suite

## Scenario Types

### Incident Reports (001)
Production incidents with timeline, symptoms, and customer impact. Focus on operational urgency and real-world consequences.

### Slack Threads (002)
Team discussions during an active incident. Multiple perspectives and incremental discovery of related issues.

### Penetration Test Reports (003)
Security assessment findings with vulnerability classifications, proof-of-concept descriptions, and CVSS scores.

### JIRA Tickets (004)
Standard bug reports with reproduction steps, expected vs actual behavior, and acceptance criteria.

### Audit Reports (005)
Compliance and regulatory findings with formal requirement references and remediation timelines.

## Tips for Debugging

- **Follow the symptoms** - Each scenario describes observable behavior, not root causes
- **Cross-reference tests** - Failing test names often indicate which functions are affected
- **Check related modules** - Many bugs span multiple files (e.g., core module + service layer)
- **Read the BUG comments** - Source files contain `# BUG:` annotations explaining each defect
- **Verify determinism** - Maritime systems require deterministic behavior; watch for unstable sorts and race conditions

## Module Quick Reference

| Module | Path | Description |
|--------|------|-------------|
| Dispatch | `lib/mercuryledger/core/dispatch.rb` | Berth allocation, capacity checking |
| Order | `lib/mercuryledger/core/order.rb` | Severity, SLA, urgency scoring |
| Resilience | `lib/mercuryledger/core/resilience.rb` | Circuit breaker, replay, checkpoints |
| Security | `lib/mercuryledger/core/security.rb` | Path sanitization, token validation |
| Routing | `lib/mercuryledger/core/routing.rb` | Corridor selection, channel scoring |
| Workflow | `lib/mercuryledger/core/workflow.rb` | State machine, transitions |
| Statistics | `lib/mercuryledger/core/statistics.rb` | Percentile, variance, averages |
| Gateway Svc | `services/gateway/service.rb` | Node scoring, admission control |
| Routing Svc | `services/routing/service.rb` | Path optimization, risk scoring |
| Security Svc | `services/security/service.rb` | Command auth, rate limiting |
