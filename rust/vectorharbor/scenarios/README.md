# VectorHarbor Debugging Scenarios

This directory contains realistic debugging scenarios for the VectorHarbor maritime orchestration platform. Each scenario describes symptoms observed in production without revealing the underlying cause.

## Scenario Files

| File | Type | Primary Modules Affected |
|------|------|--------------------------|
| `scenario_01_priority_dispatch.md` | Incident Report | Allocator, Models |
| `scenario_02_berth_scheduling.md` | Support Ticket | Allocator, Queue |
| `scenario_03_security_audit.md` | Security Alert | Security |
| `scenario_04_policy_escalation.md` | Slack Discussion | Policy, Resilience |
| `scenario_05_analytics_drift.md` | Dashboard Alert | Statistics, Routing |

## How to Use

1. Read the scenario description to understand the observed symptoms
2. Use `cargo test` to run the test suite and identify failing tests
3. Correlate test failures with the symptoms described
4. Investigate the source files mentioned in the scenarios
5. Fix the underlying bugs without modifying test files

## Scenario Difficulty

Each scenario may involve multiple interrelated bugs across different modules. The symptoms described are emergent behaviors that result from subtle defects in the codebase.

## Tips

- Pay attention to boundary conditions and off-by-one errors
- Check comparison operators carefully (`<` vs `<=`, `>` vs `>=`)
- Verify arithmetic operations match the intended semantics
- Consider edge cases at threshold boundaries
