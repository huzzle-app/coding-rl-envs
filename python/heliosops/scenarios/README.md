# HeliosOps Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and on-call alerts encountered by the HeliosOps emergency dispatch operations platform.

## Purpose

These scenarios are designed to:
1. Provide realistic context for debugging exercises
2. Describe **symptoms** rather than root causes or solutions
3. Mirror actual incident reports, Slack discussions, and ticket formats
4. Test an engineer's ability to diagnose issues from user-reported symptoms

## Scenario Format

Each scenario file uses a realistic format:
- **Incident reports**: PagerDuty-style alerts with metrics and timelines
- **Support tickets**: Customer-reported issues with reproduction steps
- **Slack threads**: Team discussions capturing live debugging sessions
- **Postmortem drafts**: Incomplete postmortems awaiting root cause analysis

## Scenarios

| File | Type | Primary Symptom Domain |
|------|------|------------------------|
| `01_eta_mismatch_incident.md` | Incident Report | Dispatch ETA calculations wildly inaccurate |
| `02_rate_limit_bypass_ticket.md` | Security Ticket | Rate limiting ineffective behind load balancer |
| `03_shift_boundary_slack.md` | Slack Thread | Units disappearing from availability at shift edges |
| `04_consensus_split_brain.md` | Incident Report | Cluster consensus failures during node scaling |
| `05_memory_leak_postmortem.md` | Postmortem Draft | Gradual memory growth and eventual OOM kills |

## Usage

Read each scenario and identify the underlying bugs in the HeliosOps codebase. The symptoms described correspond to actual defects in the source files. Multiple bugs may contribute to a single scenario.

## Note

These scenarios describe symptoms only. Do not treat the user's hypothesis or debugging attempts as authoritative -- the actual root cause may differ from initial assumptions.
