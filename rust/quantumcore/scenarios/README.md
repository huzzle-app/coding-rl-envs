# QuantumCore Debugging Scenarios

This directory contains realistic debugging scenarios that simulate production incidents, support tickets, and operational alerts you might encounter as an engineer on the QuantumCore trading platform team.

## How to Use These Scenarios

Each scenario describes **symptoms only** - the observable behavior, error messages, metrics, and user reports. Your task is to:

1. Reproduce the issue (if possible)
2. Investigate root cause
3. Identify the buggy code
4. Implement a fix
5. Verify the fix doesn't cause regressions

## Scenario Index

| Scenario | Type | Severity | Primary Symptoms |
|----------|------|----------|------------------|
| [01-matching-engine-deadlock.md](./01-matching-engine-deadlock.md) | PagerDuty Incident | Critical | Order matching frozen, latency spikes to infinity |
| [02-financial-calculation-discrepancies.md](./02-financial-calculation-discrepancies.md) | Compliance Alert | High | P&L reports showing incorrect values, margin miscalculations |
| [03-market-data-feed-leak.md](./03-market-data-feed-leak.md) | Grafana Alert | Critical | Memory growth, goroutine count explosion, stale quotes |
| [04-security-audit-findings.md](./04-security-audit-findings.md) | Security Report | High | Pentest findings, authentication vulnerabilities |
| [05-position-state-corruption.md](./05-position-state-corruption.md) | Customer Escalation | High | Position data inconsistencies, failed reconciliation |

## Difficulty Progression

These scenarios are ordered roughly by investigation complexity:

- **Scenario 1-2**: Clear symptoms pointing to specific subsystems (matching engine, risk service)
- **Scenario 3-4**: Requires understanding async patterns and security fundamentals
- **Scenario 5**: Cross-cutting concerns spanning multiple components with race conditions

## Tips for Investigation

1. **Run tests with sanitizers**: `RUSTFLAGS="-Z sanitizer=thread" cargo +nightly test`
2. **Use cargo clippy**: `cargo clippy --workspace -- -W clippy::all`
3. **Check for deadlocks**: Use `tokio-console` for async task debugging
4. **Profile memory**: Use `heaptrack` or Valgrind to identify memory leaks
5. **Search for patterns**: `grep -rn "BUG" services/` (in development mode)
6. **Review financial code**: All money calculations should use `rust_decimal`, not `f64`

## Related Documentation

- [TASK.md](../TASK.md) - Full bug category documentation
- Test files in `tests/` directory contain assertions that exercise these bugs
