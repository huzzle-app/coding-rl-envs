# HeliosOps - Hyper-Principal Orbital Response Reliability Environment

HeliosOps coordinates mission dispatch, route control, replay recovery, and security policy gates.

The codebase contains issues spanning 15 categories with deep dependency chains across scheduling, replay, routing, policy, security, and infrastructure layers.

## Difficulty

Hyper-Principal (70-140h expected).

## Objective

Fix production defects in source files only.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that simulate production incidents. Each describes symptoms observed by operations teams, security auditors, or on-call engineers. Use these as entry points for investigation.

| Scenario | Type | Domain |
| `01_eta_mismatch_incident.md` | Incident Report | Dispatch ETA calculations wildly inaccurate |
| `02_rate_limit_bypass_ticket.md` | Security Ticket | Rate limiting ineffective behind load balancer |
| `03_shift_boundary_slack.md` | Slack Thread | Units disappearing from availability at shift edges |
| `04_consensus_split_brain.md` | Incident Report | Cluster consensus failures during node scaling |
| `05_memory_leak_postmortem.md` | Postmortem Draft | Gradual memory growth and eventual OOM kills |

These scenarios describe **symptoms only** -- the actual root causes must be found in the source code.

## Completion Criteria

- Full suite passes (`python tests/run_all.py`) with **9,200+ scenarios**.
- Routing, queue, policy, and replay behavior remain deterministic.
- Security and workflow invariants remain enforced.
- Do not edit files under `tests/`.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Conjunction alert system, contact window consolidation, telemetry optimization, command auth API, TLE migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Constellation Coordinator, Health Monitor, Ground Station Scheduler |

These tasks test different software engineering skills while using the same codebase.
