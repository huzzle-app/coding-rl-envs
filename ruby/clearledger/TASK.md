# ClearLedger - Ultra-Principal Reliability Environment

ClearLedger is a Ruby clearing and settlement platform handling cross-jurisdiction workflows with ledger ingestion, risk-gated settlement, reconciliation replay, compliance overrides, and audit chain verification.

The codebase contains deeply coupled service, data, resilience, and security defects with dependency chains across 14 core modules.

## Difficulty

Ultra-Principal (12-24 hours expected).

## Getting Started

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Constraints

- **Do not modify files under `tests/`.**
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, compliance gates, and audit invariants intact.
- Only edit files under `lib/clearledger/`.

## Debugging Scenarios

The `scenarios/` directory contains 5 realistic debugging scenarios that describe symptoms as they would appear in production incidents. Use these to guide your investigation:

| Scenario | Type | Description |
| `001_settlement_discrepancy.md` | Incident Report | Netting ratios and health scores returning 0 due to integer division |
| `002_reconciliation_drift.md` | Engineering Ticket | Age calculations returning negative values, break counts inverted |
| `003_workflow_deadlock.md` | Slack Discussion | Terminal state checks incomplete, routing filters inverted |
| `004_compliance_override_failure.md` | Alert Runbook | Valid overrides rejected, missing audit actions, boundary errors |
| `005_window_watermark_rejection.md` | Customer Escalation | Event window checks failing, off-by-one errors, inverted failover |

These scenarios describe **symptoms only** - not solutions. Use them to understand the user impact and trace bugs through the codebase.

## Completion Criteria

- Full suite passes (`ruby -Ilib -Itests tests/run_all.rb`).
- All 1240 tests pass with zero failures.
- Settlement correctness and compliance suites remain stable.
- Security, workflow, and audit invariants remain enforced.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-currency netting, reconciliation refactor, risk optimization, compliance API, time-series migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Intercompany elimination, multi-currency translator, financial report generator |

These tasks test different software engineering skills while using the same codebase.
