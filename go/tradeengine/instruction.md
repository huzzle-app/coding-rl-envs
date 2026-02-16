# TradeEngine - Go High-Frequency Trading Platform

Debug a distributed high-frequency trading platform with 10 Go microservices, NATS JetStream, PostgreSQL, Redis, InfluxDB, and etcd.

**Difficulty**: Principal | **Language**: Go | **Bugs**: 87 | **Tests**: ~359

## Bug Categories

| Category | Count | Description |
|----------|-------|-------------|
| L: Setup/Infrastructure | 8 | NATS state, service discovery, health checks, import cycles |
| A: Concurrency | 12 | Deadlocks, race conditions, goroutine leaks |
| B: Data Structures | 8 | Heap invariants, slice aliasing, bounds checks |
| C: Event Sourcing | 8 | Event ordering, idempotency, circuit breakers |
| D: Distributed State | 10 | Race conditions, distributed locks, split-brain |
| E: Database | 8 | Connection pools, SQL injection, N+1 queries |
| F: Financial Calculation | 10 | Float64 precision, rounding, overflow |
| G: Risk Logic | 6 | Margin calculations, position limits |
| H: Caching | 5 | Invalidation, thundering herd, TTL |
| I: Security | 6 | Weak JWT secrets, timing attacks, SHA256 passwords |
| J: Observability | 4 | Context propagation, metric cardinality |

## Architecture

| Service | Port | Purpose |
|---------|------|---------|
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

## Infrastructure

- **NATS JetStream 2.10** - Message queue (port 4222)
- **PostgreSQL 15** - Persistent storage (port 5432)
- **Redis 7** - Caching, rate limiting (port 6379)
- **InfluxDB 2** - Time-series market data (port 8086)
- **etcd 3.5** - Service discovery, distributed locks (port 2379)

## Getting Started

```bash
# Start infrastructure
docker compose up -d

# Run all tests
go test -race -v ./...

# Run specific categories
go test ./tests/unit/... -v
go test ./tests/integration/... -v
go test ./tests/security/... -v
go test ./tests/chaos/... -v
```

## Success Criteria

- All tests passing with no race conditions (`-race` flag)
- No goroutine leaks or memory leaks
- Financial calculations use proper decimal arithmetic
- All distributed state operations properly synchronized
- Security vulnerabilities fixed (bcrypt, crypto/rand, constant-time comparison)
