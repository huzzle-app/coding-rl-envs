Fix production defects in StrataGuard by editing source code only.

StrataGuard is an Apex-Principal C# reliability platform and **tests** focused on workflow replay, queue backpressure, routing policy, cargo operations, and security hardening.

## Constraints

- Do not modify files under `tests/`.
- Preserve deterministic replay and scheduling behavior.
- Keep security checks, policy gates, and audit invariants intact.
- Only edit files under `src/StrataGuard/`.

## Running Tests

```bash
dotnet test --verbosity normal
```

## Reward Thresholds (10-tier Apex)

| Pass Rate | Reward |
|-----------|--------|
| >= 1.00 | 1.00 |
| >= 0.99 | 0.85 |
| >= 0.96 | 0.66 |
| >= 0.90 | 0.47 |
| >= 0.80 | 0.31 |
| >= 0.67 | 0.19 |
| >= 0.52 | 0.11 |
| >= 0.36 | 0.05 |
| >= 0.22 | 0.015 |
| >= 0.10 | 0.00 |

## Success Criteria

Make the full test suite pass (`dotnet test`) with production-safe changes. All tests should pass with zero failures.

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-Tier Queue, Policy State Machine, Route Optimization, Checkpoint API, Distributed Cache |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Intrusion Detection Service, Compliance Audit Logger, Security Policy Evaluator |

These tasks test different software engineering skills while using the same codebase.
