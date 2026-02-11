# ObsidianMesh Debugging Scenarios

This directory contains realistic debugging scenarios for the ObsidianMesh traffic-grid command-loop system. Each scenario presents a production incident, support ticket, monitoring alert, or team discussion that describes symptoms of bugs in the codebase.

## Purpose

These scenarios help developers practice debugging skills by:
- Starting from symptoms rather than known bugs
- Understanding how bugs manifest in production systems
- Reading realistic incident reports and support tickets
- Correlating business impact with technical issues

## Scenarios

| File | Type | Component | Summary |
|------|------|-----------|---------|
| `incident_001_auth_token_rejection.md` | Incident Report | Security | Authentication tokens rejected after security upgrade; token formatting and session expiry issues |
| `incident_002_event_replay_data_loss.md` | Incident Report | Resilience | Data loss during replay recovery; boundary conditions and eviction order bugs |
| `ticket_003_statistics_billing_discrepancy.md` | Support Ticket | Statistics | Customer billing discrepancies from weighted mean and correlation calculation errors |
| `alert_004_circuit_breaker_cascade.md` | Monitoring Alert | Resilience | Cascade failure from circuit breaker threshold, jitter, and recovery rate bugs |
| `slack_005_workflow_bottleneck.md` | Team Discussion | Workflow | Multiple workflow metric bugs affecting operational dashboards |

## How to Use

1. **Read the scenario** - Understand the symptoms, business impact, and investigation notes
2. **Run related tests** - Execute the failing tests mentioned in each scenario
3. **Investigate the code** - Use the symptoms to locate the bugs in the source files
4. **Fix and verify** - Make corrections and confirm tests pass

## Scenario Coverage

The scenarios cover bugs across multiple modules:

| Module | Scenarios |
|--------|-----------|
| `src/security.cpp` | Incident 001 |
| `src/resilience.cpp` | Incident 002, Alert 004 |
| `src/events.cpp` | Incident 002 |
| `src/statistics.cpp` | Ticket 003 |
| `src/workflow.cpp` | Slack 005 |

## Tips

- Focus on the **symptoms** described, not hunting for BUG comments
- The test failures listed provide a starting point for investigation
- Business context helps prioritize which bugs to fix first
- Some bugs have dependencies - fixing one may require fixing another first

## Running Tests

```bash
# Build the project
cmake -B build && cmake --build build

# Run all tests
ctest --test-dir build --output-on-failure

# Run specific test (example)
./build/test_obsidianmesh 2>&1 | grep -A2 "security_token_format"
```

## Note

These scenarios describe symptoms only. The actual bug fixes require code analysis and understanding of the correct behavior based on test expectations and domain logic.
