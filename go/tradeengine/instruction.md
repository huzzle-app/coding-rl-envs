# TradeEngine - Go High-Frequency Trading Platform

 in a high-frequency trading platform with 10 Go microservices, NATS JetStream, PostgreSQL, Redis, InfluxDB, and etcd.

## Architecture

The platform consists of 10 microservices:

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

## Known Issues

Current state: most tests broken. Areas of concern include API endpoints, background processing, and database operations.

## Getting Started

1. Read `TASK.md` for detailed bug descriptions, dependencies, and testing instructions
2. Start services: `docker compose up -d`
3. Run tests: `go test -race -v ./...`
4. Fix bugs to increase test pass rate

## Success Criteria

- All tests passing
- No race conditions detected with `-race` flag
- No goroutine leaks
- No memory leaks
- All security vulnerabilities fixed
- Financial calculations use proper decimal arithmetic
- All distributed state operations properly synchronized

Estimated time: 8-16 hours (Principal difficulty)

---

## Related Tasks

This environment supports additional task types beyond debugging:

| Task File | Type | Tasks | Description |
|-----------|------|-------|-------------|
| [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md) | Feature/Refactor/Optimize | 5 | Stop-Loss/Take-Profit Orders, Order Book Service Extraction, Snapshot Recovery, Portfolio Analytics, Session Migration |
| [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md) | Greenfield Implementation | 3 | Market Maker Service, Trade Reconciliation Engine, Price Alert System |

These tasks test different software engineering skills while using the same codebase.
