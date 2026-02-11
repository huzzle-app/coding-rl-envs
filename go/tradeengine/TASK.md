# TradeEngine - High-Frequency Trading Platform

## Task Description

You are debugging a distributed high-frequency trading platform built with Go microservices. The system processes orders, matches trades, manages risk, tracks positions, and provides real-time market data.

## Known Issues

The codebase needs attention. Failures span configuration, service logic, and integration points.

The codebase contains issues across 10 microservices that need to be identified and fixed. All tests must pass before the task is complete.

## Getting Started

```bash
# Start all services
docker compose up -d

# Run all tests
go test ./... -v

# Run tests with race detector
go test ./... -race -v

# Run specific test categories
go test ./tests/unit/... -v
go test ./tests/integration/... -v
go test ./tests/security/... -v
go test ./tests/chaos/... -v
go test ./tests/performance/... -v
```

## Architecture

The platform consists of 10 microservices:

| Service | Port | Purpose |
| Gateway | 8000 | API Gateway, WebSocket connections |
| Auth | 8001 | Authentication, JWT, API keys |
| Orders | 8002 | Order management |
| Matching | 8003 | Order matching engine |
| Risk | 8004 | Risk management |
| Positions | 8005 | Position tracking |
| Market | 8006 | Market data feed |
| Portfolio | 8007 | Portfolio management |
| Ledger | 8008 | Transaction ledger |
| Alerts | 8009 | Price alerts |

### Infrastructure

- **NATS JetStream** - Message queue (port 4222)
- **PostgreSQL** - Persistent storage (port 5432)
- **Redis** - Caching, rate limiting (port 6379)
- **InfluxDB** - Time-series market data (port 8086)
- **etcd** - Service discovery, distributed locks (port 2379)

- L1: NATS reconnection state not synchronized
- L2: Service discovery doesn't handle failures
- L3: Health checks don't detect partial failures
- L4: Import cycle between packages
- L5: Environment variable parsing issues
- L6: Missing service dependency in docker-compose
- L7: Init order issues in main.go
- L8: Connection timeout not configured

### Concurrency
- A1: Lock ordering deadlock in matching engine
- A2: Concurrent map access without mutex
- A3: Goroutine leak in market feed
- A4: Unbuffered channel blocking in alerts
- A5: sync.WaitGroup misuse
- A6: Race condition in price tracking
- A7: atomic.Value store nil
- A8: Context cancellation not propagated
- A9: Mutex not unlocked on error path
- A10: Channel not closed on shutdown
- A11: Mutex copy (pass by value)
- A12: Goroutine leak in position tracker

### Data Structures
- B1: Heap invariant violation after Pop
- B2: Map iteration order assumption
- B3: Slice aliasing modification
- B4: Ring buffer wrap-around off-by-one
- B5: Nil map write
- B6: Slice bounds check missing
- B7: Append reallocates and breaks reference
- B8: Time bucket aggregation error

### Event Sourcing
- C1: Event ordering not guaranteed
- C2: Ledger double-entry consistency
- C3: Circuit breaker state transition race
- C4: Snapshot corruption on concurrent write
- C5: Event replay missing idempotency
- C6: Projection lag not handled
- C7: Dead letter queue not processed
- C8: Event sequence gap detection missing

### Distributed State
- D1: Race condition in risk validation
- D2: Distributed lock not renewed
- D3: Order status check and update not atomic
- D4: Split-brain scenario in matching
- D5: Leader election issues
- D6: Consensus timeout too short
- D7: Stale read from replica
- D8: Cache and DB inconsistency
- D9: Transaction isolation level wrong
- D10: Optimistic locking version mismatch

### Database
- E1: Connection pool not configured
- E2: Transaction not isolated
- E3: SQL injection in order list
- E4: No transaction - partial state on failure
- E5: rows.Close() not deferred
- E6: Prepared statement leak
- E7: N+1 query in portfolio
- E8: Index missing on frequently queried column

### Financial Calculation
- F1: float64 for money (precision loss)
- F2: Float precision in P&L calculation
- F3: Decimal string parsing loses precision
- F4: Rounding mode inconsistency
- F5: Overflow in margin calculation
- F6: Float comparison for fill completion
- F7: Division by zero in percentage calc
- F8: Incorrect max drawdown calculation
- F9: Division by zero in allocation
- F10: Float comparison without epsilon

### Risk Logic
- G1: Margin calculation using floats
- G2: Position limits checked with race
- G3: Daily loss limit not reset
- G4: Leverage calculation overflow
- G5: VaR calculation incorrect
- G6: Exposure aggregation error

### Caching
- H1: Cache invalidation not triggered
- H2: Thundering herd on invalidation
- H3: In-memory cache not updated from Redis
- H4: No TTL on Redis cache
- H5: N+1 queries due to cache miss pattern

### Security
- I1: Weak default JWT secret
- I2: No email validation
- I3: Timing attack in login
- I4: API key generated with math/rand
- I5: SHA256 for passwords instead of bcrypt
- I6: Permission injection via comma-separated string

### Observability
- J1: Context not propagated for tracing
- J2: Metric cardinality explosion
- J3: Trace sampling drops important spans
- J4: Log levels not configurable

## Key Files to Examine

## Test Categories

| Category | Tests | Focus |
| Unit | ~180 | Individual functions, edge cases |
| Integration | ~120 | Service interactions, message flow |
| Security | ~50 | Authentication, authorization, injection |
| Chaos | ~40 | Failure scenarios, resilience |
| Performance | ~40 | Latency, throughput, memory |
| Race | ~50 | Run with `-race` flag |
| System | ~30 | End-to-end workflows |

## Expected Behavior

### Order Flow
1. Client submits order via Gateway
2. Auth validates JWT/API key
3. Risk service checks position limits
4. Order stored in Orders service
5. Order sent to Matching engine
6. Matching engine matches crossing orders
7. Trade executed and published
8. Positions updated
9. Ledger entries created
10. Portfolio cache invalidated

### Position Tracking
- Positions are event-sourced
- Events must be processed in order
- Snapshots created periodically
- P&L calculated in real-time

### Risk Management
- Position limits enforced
- Daily loss limits tracked
- Margin requirements calculated
- Circuit breakers on failures

## Success Criteria

- All 510+ tests pass
- No race conditions detected with `-race`
- No goroutine leaks
- No memory leaks
- All security vulnerabilities fixed
- Financial calculations use proper decimal arithmetic

## Hints

1. Start with setup bugs (L category) - services may not start correctly
2. Race detector will catch many concurrency bugs
3. Float precision bugs are subtle - look for `float64` in financial code
4. Channel bugs often manifest as hangs or goroutine leaks
5. SQL injection is in a string interpolation - look for `fmt.Sprintf` with SQL
6. The matching engine has a classic lock ordering bug
7. Event ordering bugs are in the position tracker
8. Cache invalidation issues are in the portfolio service

## Debugging Scenarios

The `scenarios/` directory contains realistic debugging scenarios that simulate production incidents. These provide context for understanding how bugs manifest in real-world situations.

| Scenario | Type | Description |
| [001_deadlock_matching.md](scenarios/001_deadlock_matching.md) | Incident Report | Matching engine hangs under high load with mutex deadlock |
| [002_money_precision.md](scenarios/002_money_precision.md) | Support Ticket | Portfolio values drifting from expected values |
| [003_stale_portfolio.md](scenarios/003_stale_portfolio.md) | Slack Thread | Portfolio not updating after trades execute |
| [004_alert_floods.md](scenarios/004_alert_floods.md) | Alert Dashboard | Price alerts triggering incorrectly or not at all |
| [005_auth_security.md](scenarios/005_auth_security.md) | Security Audit | Authentication vulnerabilities identified |

Each scenario describes **symptoms only**, not solutions. Use them to understand how the bugs affect system behavior.

## Code Style

- Go 1.21+
- Standard library preferred
- Use `context.Context` for cancellation
- Use `sync.Mutex` or `sync.RWMutex` for concurrent access
- Use `github.com/shopspring/decimal` for financial math
- Use `github.com/stretchr/testify` for assertions

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Stop-Loss/Take-Profit Orders, Order Book Service Extraction, Snapshot Recovery, Portfolio Analytics, Session Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Market Maker Service, Trade Reconciliation Engine, Price Alert System |

These tasks test different software engineering skills while using the same codebase.
