# FluxRail Debugging Scenarios

This directory contains realistic debugging scenarios for the FluxRail intermodal dispatch platform. Each scenario presents symptoms, business impact, and failing tests without revealing the exact fixes.

## Scenarios

| # | Title | Format | Modules Affected | Severity |
|---|-------|--------|------------------|----------|
| 001 | [Urgent Freight Wrong Priority](./001-urgent-freight-wrong-priority.md) | Incident Report | dispatch | P1 Critical |
| 002 | [Security Access Control Failures](./002-security-access-control-failures.md) | Security Alert | security, authorization | Security Critical |
| 003 | [Capacity Shed Not Triggering](./003-capacity-shed-not-triggering.md) | Slack Thread | capacity | P1 |
| 004 | [Replay State Corruption](./004-replay-state-corruption.md) | Post-Mortem | replay, resilience | P1 |
| 005 | [SLA Breach Detection Delayed](./005-sla-breach-detection-delayed.md) | JIRA Ticket | sla, economics | High |

## How to Use These Scenarios

Each scenario describes a production issue in a format you might encounter in real-world engineering:

1. **Read the scenario** to understand the symptoms and business impact
2. **Run the referenced test suites** to see the failures
3. **Investigate the affected modules** listed in each scenario
4. **Fix the underlying bugs** without breaking other functionality

## Running Tests

To verify your fixes against a specific scenario:

```bash
# Scenario 001 - Dispatch Priority
npm test -- tests/unit/dispatch.test.js
npm test -- tests/integration/flow-orchestration.test.js

# Scenario 002 - Security
npm test -- tests/unit/security.test.js
npm test -- tests/unit/authorization.test.js
npm test -- tests/integration/security-compliance.test.js

# Scenario 003 - Capacity
npm test -- tests/unit/capacity.test.js

# Scenario 004 - Replay/Resilience
npm test -- tests/unit/replay.test.js
npm test -- tests/unit/resilience.test.js
npm test -- tests/chaos/replay-storm.test.js
npm test -- tests/integration/replay-chaos.test.js

# Scenario 005 - SLA/Economics
npm test -- tests/unit/sla.test.js
npm test -- tests/unit/economics.test.js
npm test -- tests/integration/economic-risk.test.js

# All tests
npm test
```

## Scenario Coverage

These scenarios cover the following bug categories from TASK.md:

| Category | Scenarios |
|----------|-----------|
| Dispatch | 001 |
| Security | 002 |
| Authorization | 002 |
| Capacity | 003 |
| Resilience | 004 |
| Replay | 004 |
| SLA | 005 |
| Economics | 005 |

Additional bug categories (Policy, Statistics, Workflow, Queue, Routing, Ledger, Dependency, Models) are exercised through integration and stress tests but do not have dedicated scenarios.

## Tips for Debugging

- **Look for boundary conditions**: Many bugs involve `>` vs `>=` or off-by-one errors
- **Check mathematical operations**: Addition vs subtraction, multiplication vs addition
- **Verify sort directions**: Ascending vs descending comparators
- **Examine threshold values**: Constants may be slightly off from their intended values
- **Test edge cases**: Zero values, exact boundaries, empty inputs

## Important

- Do not edit files under `tests/`
- Ensure all 8,053 tests pass before considering the work complete
- Fixing one bug may reveal others in the same module
