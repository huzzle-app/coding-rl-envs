# AetherOps Debugging Scenarios

This directory contains realistic debugging scenarios that simulate the types of issues you might encounter when investigating production problems in the AetherOps orbital operations platform.

## Overview

Each scenario represents a real-world debugging situation presented through different formats:
- Incident reports
- Jira tickets
- PagerDuty alerts
- Slack discussions
- Post-mortem documents

The scenarios describe **symptoms and business impact** without revealing the exact code changes needed. Your task is to investigate the codebase, identify the root causes, and implement fixes.

## Scenarios

| # | Title | Format | Affected Module | Severity |
|---|-------|--------|-----------------|----------|
| 01 | [Suboptimal Burn Window Selection](scenario_01_orbital_burn_window.md) | Incident Report | orbit.py | High |
| 02 | [Circuit Breaker Fails to Trip](scenario_02_circuit_breaker_timing.md) | Slack Thread | resilience.py | Medium |
| 03 | [Critical Alerts Missing Pager](scenario_03_critical_alert_pager.md) | Jira Ticket | notifications/service.py | Critical |
| 04 | [SLA Calculation 10x Too Low](scenario_04_sla_calculation_wrong.md) | PagerDuty Alert | policy.py | High |
| 05 | [Queue Priority Inversion](scenario_05_queue_priority_inversion.md) | Post-Mortem | queue.py | SEV-1 |

## How to Use These Scenarios

1. **Read the scenario** - Understand the reported symptoms and business impact
2. **Review referenced tests** - Look at the failing test cases mentioned in each scenario
3. **Investigate the codebase** - Trace through the affected modules and functions
4. **Identify root causes** - Find the bugs causing the described behavior
5. **Implement fixes** - Make targeted changes to resolve the issues
6. **Verify with tests** - Run the test suite to confirm your fixes work

## Key Investigation Areas

### Scenario 01: Orbital Burn Window Selection
- File: `aetherops/orbit.py`
- Function: `optimal_window()`
- Concept: Selection criteria for delta-v efficiency

### Scenario 02: Circuit Breaker Timing
- File: `aetherops/resilience.py`
- Class: `CircuitBreaker`
- Concept: Boundary conditions and comparison operators

### Scenario 03: Critical Alert Channels
- File: `services/notifications/service.py`
- Class: `NotificationPlanner`
- Concept: Channel routing for different severity levels

### Scenario 04: SLA Compliance Calculation
- File: `aetherops/policy.py`
- Function: `sla_percentage()`
- Concept: Percentage calculations and multipliers

### Scenario 05: Queue Priority Ordering
- File: `aetherops/queue.py`
- Class: `PriorityQueue`
- Concept: Priority semantics (higher = more urgent)

## Running Tests

To verify your fixes, run the test suite:

```bash
python tests/run_all.py
```

Individual test files can be run with:

```bash
python -m pytest tests/unit/queue_test.py -v
python -m pytest tests/unit/resilience_test.py -v
```

## Notes

- These scenarios represent a small subset of the 940 bugs in the full environment
- Each scenario may involve multiple related bugs in the same module
- The scenarios are designed to be realistic examples of production debugging
- Focus on understanding the domain (orbital mechanics, mission control, resilience patterns) to reason about correct behavior
