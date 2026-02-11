# IonVeil Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production issues in the IonVeil planetary emergency command platform. Each scenario describes symptoms and context without revealing solutions.

## Scenario Overview

| File | Format | Primary Bug Area | Affected Module |
|------|--------|------------------|-----------------|
| `incident_001_replay_ordering.md` | Incident Report | Event replay sequence handling | `ionveil/resilience.py` |
| `incident_002_policy_escalation.md` | Incident Report | Policy state machine thresholds | `ionveil/policy.py` |
| `ticket_003_route_selection.md` | Support Ticket | Route sorting/selection logic | `ionveil/routing.py` |
| `alert_004_config_precedence.md` | Monitoring Alert | Configuration loading order | `shared/config.py` |
| `slack_005_dispatch_priority.md` | Team Discussion | Dispatch ordering/sorting | `ionveil/dispatch.py` |

## How to Use These Scenarios

1. **Read the scenario** to understand the symptoms and business context
2. **Run the referenced tests** to reproduce the failures
3. **Investigate the affected modules** using the symptoms as clues
4. **Fix the underlying bugs** in the source code
5. **Verify your fix** by re-running the tests

## Scenario Categories

### Incident Reports (INC-*)
Formal incident documentation following ITIL-style format. These include:
- Executive summary
- Detailed timeline
- Log excerpts
- Business impact assessment
- Stakeholder information

### Support Tickets
Customer-facing bug reports with:
- Reproduction steps
- Expected vs actual behavior
- Environment details
- Workaround attempts

### Monitoring Alerts
Production alerting scenarios with:
- Alert configuration
- Metric discrepancies
- Cascading failure analysis
- Runbook references

### Team Discussions
Informal Slack-style conversations showing:
- Real-time debugging collaboration
- Multiple perspectives on the issue
- Investigation breadcrumbs
- Cross-team impact discovery

## Testing Commands

Run specific tests referenced in scenarios:

```bash
# Unit tests for individual modules
python -m pytest tests/unit/resilience_test.py -v
python -m pytest tests/unit/policy_test.py -v
python -m pytest tests/unit/routing_test.py -v
python -m pytest tests/unit/dispatch_test.py -v

# Stress tests (large-scale validation)
python -m pytest tests/stress/hyper_matrix_test.py -v

# Full test suite
python tests/run_all.py
```

## Related Documentation

- [TASK.md](../TASK.md) - Environment overview and bug categories
- [instruction.md](../instruction.md) - Getting started guide
- `tests/` - Test files that validate fixes

## Notes for Debugging

- Scenarios describe **symptoms**, not solutions
- Multiple bugs may contribute to a single scenario
- Some issues have dependency chains (fixing A may reveal B)
- Pay attention to test assertion messages for exact expectations
- Log excerpts show runtime behavior, not necessarily bug locations
