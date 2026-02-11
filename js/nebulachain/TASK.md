# NebulaChain - Apex-Principal Reliability Environment

NebulaChain manages global supply provenance dispatch, integrity replay, fraud policy escalation, and resilient event routing.

The codebase contains deeply coupled service, data, resilience, and security defects with long dependency chains.

## Difficulty

Apex-Principal (5-7 days expected, 120-168h).

## Objective

Fix production defects in source files only. Defects are embedded in the source code without explicit markers.

## Test Breakdown

| Category | Count |
|----------|-------|
| Unit tests (9 core modules) | 9 |
| Integration tests (3 cross-module) | 3 |
| Service contract test | 1 |
| Service tests (8 services x 4) | 32 |
| Stress: hyper-matrix | 7,000 |
| Stress: service-mesh-matrix | 2,168 |
| **Total** | **9,213** |

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production issues. These provide context for understanding how bugs manifest in real-world operations:

| Scenario | Type | Components Affected |
| `incident_001_routing_selects_congested_channels.md` | Incident Report | Routing engine channel selection |
| `incident_002_escalation_policy_stuck.md` | Incident Report | Policy escalation thresholds and cooldowns |
| `ticket_003_vessel_classification_wrong.md` | Support Ticket | Dispatch ticket models, vessel classification |
| `alert_004_replay_keeping_stale_events.md` | Monitoring Alert | Resilience replay, deduplication, circuit breaker |
| `slack_005_security_bypass_discussion.md` | Team Discussion | Security path traversal, token scope, risk scoring |

Each scenario describes symptoms, logs, and business impact without revealing exact fixes. Use them to:
- Understand how bugs affect real operations
- Trace symptoms back to defective code
- Validate fixes against realistic test cases

## Completion Criteria

- Full suite passes (`npm test`) — all 9,213 tests green.
- Deterministic replay, scheduling, routing, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Consensus Quorum Validation, Replay Strategy Pattern, Route Table Indexing, Distributed Transaction Coordinator, Event Sourcing Schema |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Smart Contract Validator, Block Explorer Backend, Token Transfer Service |

These tasks test different software engineering skills while using the same codebase.
