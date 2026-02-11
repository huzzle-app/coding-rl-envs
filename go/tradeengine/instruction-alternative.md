# TradeEngine - Alternative Tasks

## Overview

These five alternative tasks extend the TradeEngine platform with advanced trading features, architectural improvements, and operational optimizations. Each task builds on the existing codebase to implement real-world trading requirements including risk management orders, service extraction, performance optimization, portfolio analytics, and data migration.

## Environment

- **Language**: Go
- **Infrastructure**: NATS JetStream 2.10, PostgreSQL 15, Redis 7, InfluxDB 2, etcd 3.5
- **Difficulty**: Principal

## Tasks

### Task 1: Stop-Loss and Take-Profit Order Types (Feature)

Implement conditional order types (stop-loss and take-profit) that automatically trigger market orders when price targets are reached. The system must handle edge cases like gap openings, partial fills, and concurrent position updates. Include OCO (one-cancels-other) linking between paired orders and trigger event publishing to the messaging system.

**Key Requirements:**
- Trigger logic for stop and target prices
- Conversion to market orders upon trigger
- OCO order pair management
- Status transitions and event publishing
- Slippage protection with configurable tolerances

### Task 2: Order Book Service Extraction (Refactoring)

Extract the tightly-coupled order book implementation from the matching engine into a standalone microservice with a clean gRPC interface. This refactoring improves horizontal scalability and enables independent order book operations per trading pair while preserving existing price-time priority semantics.

**Key Requirements:**
- Separate order book package with no matching engine dependencies
- gRPC service definition (AddOrder, CancelOrder, GetDepth, GetBestBidAsk)
- Per-pair state isolation with independent mutex protection
- Market data snapshot generation without blocking operations
- Abstracted event publishing interface
- No regression in test coverage

### Task 3: Order Book Snapshot and Recovery Optimization (Performance)

Implement efficient snapshotting for position recovery instead of replaying entire event histories. Large accounts with thousands of trades need fast recovery after restart. Add O(log n) sequence lookups for event replay ranges and configurable retention policies for old snapshots.

**Key Requirements:**
- Automatic snapshot creation at configurable intervals
- Snapshot includes all position state (quantities, prices, P&L, versions)
- Recovery loads latest snapshot and replays only subsequent events
- Non-blocking snapshot operations
- Event log supports efficient range queries
- Recovery time under 100ms for 10,000+ event accounts

### Task 4: Portfolio Analytics API Expansion (API Extension)

Extend the portfolio manager with advanced analytics endpoints for institutional clients. Implement time-weighted return (TWR), Sharpe ratio, and beta calculations for risk reporting and performance attribution. Use decimal arithmetic for financial precision and support configurable time periods with result caching.

**Key Requirements:**
- Time-weighted return (TWR) calculation accounting for cash flows
- Sharpe ratio with configurable risk-free rate
- Beta calculation against multiple benchmark indices
- Daily/weekly/monthly/custom period support
- Decimal arithmetic for all monetary calculations
- Result caching with TTL and invalidation
- Unit tests against financial textbook test cases

### Task 5: Redis to PostgreSQL Session Migration (Migration)

Migrate session storage from Redis to PostgreSQL for operational consolidation, without service downtime. Implement dual-write mode supporting gradual rollout with feature flags, maintaining sub-5ms p99 latency. Include backfill scripts, fallback mechanisms, and rollback procedures.

**Key Requirements:**
- PostgreSQL session table schema with performance indexes
- Dual-write mode storing to Redis and PostgreSQL
- PostgreSQL reads with Redis fallback
- Backfill script for existing Redis sessions
- Feature flag control (Redis-only, dual-write, PostgreSQL-primary, PostgreSQL-only)
- Sub-5ms p99 validation latency
- TTL/cleanup job for session expiration
- Documented and tested rollback procedures

## Getting Started

```bash
go test -v ./...
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_ALTERNATIVE.md](./TASKS_ALTERNATIVE.md).
