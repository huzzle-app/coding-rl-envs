# QuorumLedger - Hyper-Principal Distributed Treasury Platform

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic behavior of consensus, settlement, and replay logic.
- Keep security checks (hash chain integrity, token validation, permission levels) intact.

## Getting Started

```bash
go test -race -v ./...
```

Review failing tests, trace failures to source modules in `internal/`, `pkg/models/`, `shared/contracts/`, and `services/`.

## Success Criteria

- All 7,638 tests pass (`go test -race -v ./...`).
- Deterministic consensus, settlement, replay, and policy behavior remains stable.
- Security, workflow, and compliance invariants remain enforced.

## Reward Function

The environment uses 8-tier sparse rewards (Hyper-Principal):

```
Pass Rate -> Reward
< 25% -> 0.00
25-40% -> 0.05
40-55% -> 0.12
55-70% -> 0.22
70-85% -> 0.38
85-95% -> 0.55
95-100% -> 0.78
100% -> 1.00
```

Primary objective: make all tests pass with robust, production-safe fixes.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-currency netting, consensus strategies, ledger optimization, streaming reconciliation, legacy migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Cross-Ledger Bridge Service, Compliance Reporting Engine, Event Sourcing Journal |

These tasks test different software engineering skills while using the same codebase.
