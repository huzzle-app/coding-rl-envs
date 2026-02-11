Fix production defects in ClearLedger by editing source code only.

ClearLedger is an Ultra-Principal Ruby clearing platform and **tests** focused on settlement correctness, reconciliation replay, risk gating, compliance overrides, and audit chain integrity.

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and settlement behavior.
- Keep security checks, compliance gates, and audit invariants intact.
- Only edit files under `lib/clearledger/`.

## Running Tests

```bash
ruby -Ilib -Itests tests/run_all.rb
```

## Reward Thresholds (8-tier Ultra-Principal)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.00 |
| >= 0.95 | 0.78 |
| >= 0.85 | 0.55 |
| >= 0.70 | 0.38 |
| >= 0.55 | 0.22 |
| >= 0.40 | 0.12 |
| >= 0.25 | 0.05 |
| < 0.25 | 0.00 |

## Success Criteria

Make the full test suite pass (`ruby -Ilib -Itests tests/run_all.rb`) with production-safe changes. All tests should pass with zero failures.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-currency netting, reconciliation refactor, risk optimization, compliance API, time-series migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Intercompany elimination, multi-currency translator, financial report generator |

These tasks test different software engineering skills while using the same codebase.
