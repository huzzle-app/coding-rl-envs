# GridWeaver Debugging Scenarios

This directory contains realistic debugging scenarios for the GridWeaver National Smart Grid Orchestration Platform. Each scenario presents symptoms and context that engineers would encounter in production, without revealing the underlying root causes.

## Scenario Types

| File | Type | Category | Severity |
|------|------|----------|----------|
| `01_consensus_election_failure.md` | Incident Report | Distributed State / Consensus | P1 - Critical |
| `02_dispatch_negative_generation.md` | Support Ticket | Numerical Stability / Dispatch | P2 - High |
| `03_topology_capacity_mismatch.md` | Slack Discussion | Constraint Logic / Topology | P2 - High |
| `04_event_ordering_anomaly.md` | Alert Investigation | Event Ordering / Concurrency | P1 - Critical |
| `05_resilience_cascade_failure.md` | Post-Mortem Draft | Resilience / Circuit Breaker | P1 - Critical |

## Using These Scenarios

Each scenario describes **symptoms only** - the observable behavior that indicates something is wrong. Engineers should:

1. Read the scenario to understand the symptoms and context
2. Use the symptom descriptions to guide investigation
3. Trace through the codebase to identify root causes
4. Verify fixes by ensuring the described symptoms no longer occur

## Scenario Structure

Each scenario file contains:

- **Context**: Background information about the affected system area
- **Symptoms**: Observable behaviors that indicate the problem
- **Impact**: Business or operational consequences
- **Relevant Logs/Metrics**: Sample output showing the issue
- **Investigation Hints**: Pointers to where to start looking (without revealing the fix)

## Difficulty Distribution

- Scenarios 1-2: Single root cause, localized to one package
- Scenarios 3-4: Multiple related bugs that compound the symptoms
- Scenario 5: Complex interaction between multiple subsystems
