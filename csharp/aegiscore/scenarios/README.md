# AegisCore Debugging Scenarios

This directory contains realistic debugging scenarios for the AegisCore maritime dispatch platform. Each scenario represents the type of incident, ticket, or discussion that engineers encounter when investigating production issues.

## Purpose

These scenarios help you practice debugging by:
- Describing **symptoms** rather than solutions
- Providing business context and impact
- Referencing failing tests as investigation starting points
- Showing how issues manifest in real operational environments

## Scenarios

| # | File | Type | Affected Module | Bug Categories |
|---|------|------|-----------------|----------------|
| 1 | [001_dispatch_priority_inversion.md](001_dispatch_priority_inversion.md) | Incident Report | Allocator | Sort order, priority logic |
| 2 | [002_policy_escalation_premature.md](002_policy_escalation_premature.md) | JIRA Ticket | Policy | Boundary conditions, thresholds |
| 3 | [003_security_path_traversal.md](003_security_path_traversal.md) | Security Alert | Security | Input sanitization, loops |
| 4 | [004_queue_wait_time_explosion.md](004_queue_wait_time_explosion.md) | Slack Thread | QueueGuard | Operator inversion, boundary |
| 5 | [005_workflow_departed_cancellation.md](005_workflow_departed_cancellation.md) | Post-Mortem | Workflow | State machine, transitions |

## How to Use These Scenarios

1. **Read the scenario** to understand the symptoms and business impact
2. **Identify the affected module** from the scenario context
3. **Run the failing tests** mentioned in the scenario to confirm the issue
4. **Investigate the source code** to find the root cause
5. **Fix the bug** without modifying test files

## Debugging Approach

Each scenario intentionally avoids revealing the exact fix. Instead, focus on:

### 1. Understand the Symptom
- What behavior is unexpected?
- What is the expected behavior?
- What business process is affected?

### 2. Reproduce the Issue
- Run the mentioned failing tests
- Understand what the test expects vs. what it gets

### 3. Trace the Code Path
- Find the relevant source file
- Understand the logic flow
- Look for common bug patterns:
  - Off-by-one errors (`<` vs `<=`, `>` vs `>=`)
  - Operator inversion (`*` vs `/`, `+` vs `-`)
  - Sort direction (ascending vs descending)
  - Loop termination (single pass vs complete removal)
  - State machine graph (missing or extra transitions)

### 4. Verify the Fix
- Run `dotnet test` to confirm the fix
- Ensure no regressions in related tests

## Running Tests

```bash
# Run all tests
dotnet test

# Run specific test class
dotnet test --filter "FullyQualifiedName~CoreTests"

# Run with verbose output
dotnet test -v n
```

## Notes

- Do NOT modify files under `tests/`
- Each bug has a unique identifier (AGS0001-AGS0021)
- Bug IDs are mentioned in the scenarios for cross-reference
- Some scenarios cover multiple related bugs
