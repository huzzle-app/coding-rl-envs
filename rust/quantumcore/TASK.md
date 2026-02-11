# QuantumCore - High-Frequency Trading Platform

## Task Description

You are debugging a high-frequency trading platform built with Rust microservices. The platform handles order matching, risk management, market data, and portfolio tracking with microsecond latency requirements.

The codebase contains issues across 10 microservices that need to be identified and fixed. All 510+ tests must pass before the task is complete.

## Getting Started

```bash
# Start infrastructure services
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

### Infrastructure

| Component | Purpose |
|-----------|---------|
| NATS 2.10 | Message queue with JetStream |
| PostgreSQL 15 | Orders, positions, users |
| Redis 7 | Caching, rate limiting |
| InfluxDB 2 | Time-series market data |
| etcd 3.5 | Service discovery, distributed locks |

## Bug Categories

### Setup/Configuration

| Bug | Description | Service |
|-----|-------------|---------|
| L1 | NATS connection not handling reconnection | shared |
| L2 | Tokio runtime misconfigured for CPU-bound work | matching |
| L3 | Database pool exhaustion under load | orders |
| L4 | Missing graceful shutdown | gateway |
| L5 | Service discovery race condition | shared |
| L6 | Configuration hot-reload causes crash | risk |
| L7 | Timezone handling in timestamps | market |
| L8 | TLS certificate validation disabled | auth |

### Ownership/Borrowing

| Bug | Description | Service |
|-----|-------------|---------|
| A1 | Use after move in order processing | orders |
| A2 | Borrowed value escapes closure | matching |
| A3 | Mutable borrow in iterator | positions |
| A4 | Partial move out of Option | risk |
| A5 | Reference outlives data | market |
| A6 | Double mutable borrow | portfolio |
| A7 | Moved value in async block | ledger |
| A8 | Borrow checker vs interior mutability | alerts |
| A9 | Self-referential struct | matching |
| A10 | Lifetime variance issue | shared |

### Concurrency

| Bug | Description | Service |
|-----|-------------|---------|
| B1 | Lock ordering deadlock | matching |
| B2 | Blocking in async context | orders |
| B3 | Race condition in order book | matching |
| B4 | Future not Send | gateway |
| B5 | Mutex poisoning not handled | risk |
| B6 | Channel backpressure ignored | market |
| B7 | Atomic ordering too weak | positions |
| B8 | Spin loop in async | ledger |
| B9 | Condvar spurious wakeup | alerts |
| B10 | Thread pool exhaustion | gateway |
| B11 | Lock-free queue ABA problem | matching |
| B12 | Memory ordering in price updates | market |

### Error Handling

| Bug | Description | Service |
|-----|-------------|---------|
| C1 | Unwrap in production code | orders |
| C2 | Error type conversion loss | risk |
| C3 | Panic in async task | matching |
| C4 | Unhandled Result in drop | positions |
| C5 | Error chain truncation | ledger |
| C6 | Missing error context | portfolio |
| C7 | Catch-all error hiding bugs | auth |
| C8 | Panic hook not set | gateway |

### Memory/Resources

| Bug | Description | Service |
|-----|-------------|---------|
| D1 | Unbounded Vec growth | orders |
| D2 | Memory leak from Arc cycle | positions |
| D3 | File handle leak | ledger |
| D4 | Connection pool leak | market |
| D5 | Cache without eviction | risk |
| D6 | String allocation in hot path | matching |
| D7 | Large stack allocation | portfolio |
| D8 | Buffer not released | gateway |

### Unsafe Code

| Bug | Description | Service |
|-----|-------------|---------|
| E1 | Undefined behavior in price conversion | matching |
| E2 | Uninitialized memory read | market |
| E3 | Invalid pointer arithmetic | ledger |
| E4 | Data race in lock-free code | matching |
| E5 | Incorrect Send/Sync impl | shared |
| E6 | Use after free in FFI | market |

### Numerical/Financial

| Bug | Description | Service |
|-----|-------------|---------|
| F1 | Float precision in prices | orders |
| F2 | Integer overflow in quantity | matching |
| F3 | Decimal rounding mode | ledger |
| F4 | Currency conversion race | portfolio |
| F5 | Fee calculation truncation | orders |
| F6 | P&L calculation wrong | positions |
| F7 | Margin requirement overflow | risk |
| F8 | Price tick validation | matching |
| F9 | Order value calculation | orders |
| F10 | Tax rounding compound | ledger |

### Distributed Systems

| Bug | Description | Service |
|-----|-------------|---------|
| G1 | Event ordering not guaranteed | shared |
| G2 | Distributed lock not released | positions |
| G3 | Split-brain in failover | matching |
| G4 | Idempotency key collision | orders |
| G5 | Saga compensation failure | ledger |
| G6 | Circuit breaker state shared wrong | gateway |
| G7 | Retry without backoff | shared |
| G8 | Leader election race | matching |

### Security

| Bug | Description | Service |
|-----|-------------|---------|
| H1 | JWT secret hardcoded | auth |
| H2 | Timing attack in comparison | auth |
| H3 | SQL injection | orders |
| H4 | Rate limit bypass | gateway |
| H5 | Sensitive data in logs | shared |

## Key Files by Service

### Matching Engine
| File | Bugs |
|------|------|
| `src/engine.rs` | B1, B3, E1, E4 |
| `src/orderbook.rs` | A2, A9, B11, F8 |
| `src/priority_queue.rs` | D6, F2 |

### Orders Service
| File | Bugs |
|------|------|
| `src/handler.rs` | A1, C1, H3 |
| `src/processor.rs` | B2, D1, F1, F5, F9, G4 |

### Risk Service
| File | Bugs |
|------|------|
| `src/calculator.rs` | A4, B5, F7 |
| `src/config.rs` | L6, D5 |

### Positions Service
| File | Bugs |
|------|------|
| `src/tracker.rs` | A3, B7, D2, F6 |
| `src/lock.rs` | G2 |

### Market Data Service
| File | Bugs |
|------|------|
| `src/feed.rs` | A5, B6, B12, E2, E6 |
| `src/aggregator.rs` | L7, D4 |

### Shared Library
| File | Bugs |
|------|------|
| `src/nats.rs` | L1, G1 |
| `src/discovery.rs` | L5, E5 |
| `src/http.rs` | G7 |
| `src/logger.rs` | H5 |
| `src/types.rs` | A10 |

## Test Categories

| Category | Tests | Focus |
|----------|-------|-------|
| Unit | 180 | Individual functions |
| Integration | 120 | Service interactions |
| Concurrency | 60 | Race conditions, deadlocks |
| Performance | 50 | Latency, throughput |
| Security | 50 | Auth, injection |
| Chaos | 30 | Failure scenarios |
| E2E | 20 | Full order lifecycle |

## Success Criteria

- All 510+ tests pass
- No compiler warnings
- `cargo clippy` clean
- No data races (TSAN clean)
- No memory leaks (Valgrind/Miri)
- < 100μs P99 order matching latency
- No financial calculation errors

## Rust HFT Patterns to Watch

```rust
// Lock ordering deadlock (BUG)
let order_book = order_books.get(&symbol).lock();
let risk_state = risk_states.get(&account).lock(); // Opposite order elsewhere!

// Float precision in prices (BUG)
let price: f64 = 100.10;
let qty: f64 = 0.001;
let value = price * qty; // Precision loss!

// Integer overflow in quantity (BUG)
let total_qty: u64 = qty1.checked_add(qty2).unwrap(); // Panics on overflow!

// Atomic ordering too weak (BUG)
let price = LAST_PRICE.load(Ordering::Relaxed); // May see stale value!

// Use Decimal for money:
use rust_decimal::Decimal;
let price = Decimal::from_str("100.10").unwrap();
```

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents you might encounter. Each scenario describes symptoms without revealing fixes - use them to practice real-world debugging.

| Scenario | Type | Severity | Focus Area |
|----------|------|----------|------------|
| [01-matching-engine-deadlock](scenarios/01-matching-engine-deadlock.md) | PagerDuty Incident | Critical | Lock ordering, concurrency |
| [02-financial-calculation-discrepancies](scenarios/02-financial-calculation-discrepancies.md) | Compliance Alert | High | Float precision, Decimal usage |
| [03-market-data-feed-leak](scenarios/03-market-data-feed-leak.md) | Grafana Alert | Critical | Task lifecycle, async cleanup |
| [04-security-audit-findings](scenarios/04-security-audit-findings.md) | Security Report | High | JWT, timing attacks, secrets |
| [05-position-state-corruption](scenarios/05-position-state-corruption.md) | Customer Escalation | High | Race conditions, event sourcing |

See [scenarios/README.md](scenarios/README.md) for detailed usage instructions.

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
