# TensorForge Debugging Scenarios

This directory contains realistic debugging scenarios for the TensorForge model-serving exchange platform. Each scenario presents symptoms of production issues without revealing the underlying fixes.

## Purpose

These scenarios simulate real-world debugging situations that engineers encounter in production ML infrastructure:

- **Incident Reports** - Formal documentation of production outages
- **Support Tickets** - Customer-reported issues escalated to engineering
- **Monitoring Alerts** - Automated system alerts indicating anomalies
- **Team Discussions** - Slack-style collaborative debugging sessions

## Scenarios

| File | Type | Primary Area | Symptoms |
|------|------|--------------|----------|
| `incident_001_inference_latency_misrouting.md` | Incident | Routing | Inference requests routed to highest-latency endpoints |
| `incident_002_authentication_bypass.md` | Incident | Security | Empty tokens accepted, auth bypass vulnerability |
| `ticket_003_allocation_cost_explosion.md` | Support Ticket | Allocator | Cost estimates 1000x too high |
| `alert_004_telemetry_health_scoring.md` | Alert | Telemetry | False positive health alerts, inverted metrics |
| `slack_005_event_ordering_replay.md` | Slack Thread | Events/Resilience | Events returned in wrong order, replay failures |

## How to Use

1. **Read the scenario** - Understand the symptoms, business impact, and failing tests
2. **Investigate the codebase** - Use the clues to locate relevant source files
3. **Run failing tests** - Verify the issue exists with `cargo test`
4. **Fix the bugs** - Correct the logic errors in the source code
5. **Verify the fix** - Ensure tests pass and behavior matches expected

## What Each Scenario Contains

- **Symptoms** - Observable incorrect behavior (logs, metrics, outputs)
- **Business Impact** - Why this matters (revenue, compliance, customers)
- **Failing Tests** - Which test cases expose the issue
- **Investigation Clues** - Hints toward the problem area (not the solution)
- **Related Issues** - Connections to other scenarios or bugs

## What Scenarios Do NOT Contain

- Exact bug locations (file:line)
- Corrected code snippets
- Step-by-step fix instructions
- Direct references to BUG comments

## Difficulty Mapping

| Scenario | Estimated Bugs | Modules Involved | Complexity |
|----------|---------------|------------------|------------|
| incident_001 | 3-5 | routing | Medium |
| incident_002 | 4-6 | security | Medium |
| ticket_003 | 5-7 | allocator | Medium-High |
| alert_004 | 8-10 | telemetry | High |
| slack_005 | 6-8 | events, resilience | High |

## Running Tests

```bash
# Run all tests
cargo test

# Run tests for a specific module
cargo test routing
cargo test security
cargo test allocator
cargo test telemetry
cargo test events
cargo test resilience

# Run with verbose output
cargo test -- --nocapture

# Run matrix scenarios (12,500 tests)
cargo test --test hyper_matrix
```

## Tips for Debugging

1. **Start with failing tests** - They pinpoint the exact incorrect behavior
2. **Look for patterns** - Many bugs are similar (inverted comparisons, wrong operators)
3. **Check edge cases** - Boundary conditions and empty inputs often reveal issues
4. **Consider dependencies** - Some bugs depend on others being fixed first
5. **Use the logs** - The anomaly messages hint at what's wrong

## Related Documentation

- [TASK.md](../TASK.md) - Full environment description and bug categories
- [instruction.md](../instruction.md) - Agent-facing task specification
- Test files in `tests/` directory for expected behavior specifications
