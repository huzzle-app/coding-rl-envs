# QuantumCore - High-Frequency Trading Platform

Debug 75 bugs in a Rust-based high-frequency trading platform with 10 microservices, NATS messaging, PostgreSQL, Redis, InfluxDB, and etcd.

## Architecture

QuantumCore is a microservices platform with 10 Rust services:

| Service | Port | Purpose |
|---------|------|---------|
| Gateway | 8000 | API Gateway, WebSocket |
| Auth | 8001 | Authentication, API keys |
| Orders | 8002 | Order management |
| Matching | 8003 | Order matching engine |
| Risk | 8004 | Risk management |
| Positions | 8005 | Position tracking |
| Market | 8006 | Market data feed |
| Portfolio | 8007 | Portfolio management |
| Ledger | 8008 | Transaction ledger |
| Alerts | 8009 | Price alerts |

## Infrastructure

| Component | Purpose |
|-----------|---------|
| NATS 2.10 | Message queue with JetStream |
| PostgreSQL 15 | Orders, positions, users |
| Redis 7 | Caching, rate limiting |
| InfluxDB 2 | Time-series market data |
| etcd 3.5 | Service discovery, distributed locks |

## Bug Categories

| Category | Count | Description |
|----------|-------|-------------|
| Setup/Configuration | 8 | NATS reconnection, runtime config, pool exhaustion, graceful shutdown, service discovery race, hot-reload crash, timezone handling, TLS validation |
| Ownership/Borrowing | 10 | Use after move, borrowed value escapes, mutable borrow in iterator, partial move, reference outlives data, double mutable borrow, moved value in async, interior mutability, self-referential struct, lifetime variance |
| Concurrency | 12 | Lock ordering deadlock, blocking in async, race conditions, Future not Send, mutex poisoning, channel backpressure, atomic ordering, spin loop, condvar spurious wakeup, thread pool exhaustion, ABA problem, memory ordering |
| Error Handling | 8 | Unwrap in production, error type conversion loss, panic in async, unhandled Result in drop, error chain truncation, missing context, catch-all hiding bugs, panic hook not set |
| Memory/Resources | 8 | Unbounded Vec growth, Arc cycle leak, file handle leak, connection pool leak, cache without eviction, string allocation in hot path, large stack allocation, buffer not released |
| Unsafe Code | 6 | UB in price conversion, uninitialized memory, invalid pointer arithmetic, data race in lock-free code, incorrect Send/Sync impl, use after free in FFI |
| Numerical/Financial | 10 | Float precision in prices, integer overflow, decimal rounding mode, currency conversion race, fee calculation truncation, P&L calculation, margin requirement overflow, price tick validation, order value calculation, tax rounding compound |
| Distributed Systems | 8 | Event ordering not guaranteed, distributed lock not released, split-brain in failover, idempotency key collision, saga compensation failure, circuit breaker state shared wrong, retry without backoff, leader election race |
| Security | 5 | JWT secret hardcoded, timing attack in comparison, SQL injection, rate limit bypass, sensitive data in logs |

**Total** | 75 bugs | 960+ tests | Difficulty: Principal (8-16h)

## Getting Started

```bash
# Start infrastructure (NATS, PostgreSQL, Redis, InfluxDB, etcd)
docker compose up -d

# Build all services
cargo build --workspace

# Run all tests
cargo test --workspace

# Run specific service tests
cargo test -p matching-engine
cargo test -p risk-service

# Run with thread sanitizer (nightly)
RUSTFLAGS="-Z sanitizer=thread" cargo +nightly test --workspace
```

## Key Notes

- **Setup bugs**: Some bugs prevent services from starting. Fix these first (L category).
- **Rust-specific bugs**: Watch for use-after-move, lifetime issues, blocking in async contexts, and lock ordering deadlocks.
- **Financial calculations**: Use `rust_decimal` for all money calculations, never `f64`.
- **Concurrency**: Lock ordering must be consistent globally. All async code must be `Send + Sync`.
- **Distributed systems**: Event ordering, idempotency, and circuit breakers are critical.
- **Security**: JWT validation, timing attacks, and injection vulnerabilities.

## Success Criteria

- All tests pass
- No compiler warnings
- `cargo clippy` clean
- No data races (TSAN clean)
- No memory leaks (Valgrind/Miri)
- < 100μs P99 order matching latency
- No financial calculation errors

## Test Output

Cargo test will show:
```
test result: ok. X passed; Y failed; Z ignored
```

Your goal is to achieve 100% pass rate (all tests passing).

## Hints

1. Start with L category - services may not start
2. Use `cargo clippy` extensively
3. Run with `RUST_BACKTRACE=1` for panic traces
4. Use `tokio-console` for async debugging
5. Financial calculations need `rust_decimal`
6. Lock ordering must be consistent globally
7. All async code should be `Send + Sync`
8. Use `parking_lot` for better mutex behavior

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Multi-leg orders, order book cache optimization, feed latency, FIX gateway, event sourcing |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Market Data Normalizer, Options Greeks Calculator, Trade Execution Reporter |

These tasks test different software engineering skills while using the same codebase.
