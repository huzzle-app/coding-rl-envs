# TradeEngine - Alternative Tasks

These alternative tasks provide different ways to engage with the TradeEngine codebase beyond bug fixing. Each task focuses on a specific aspect of trading platform development.

---

## Task 1: Stop-Loss and Take-Profit Order Types (Feature Development)

### Description

TradeEngine currently supports only basic limit and market orders. Modern trading platforms require advanced conditional order types to help traders manage risk and automate exit strategies. This task involves implementing stop-loss and take-profit order functionality.

A stop-loss order becomes active when the market price reaches a specified trigger price, automatically executing a sell order to limit losses. A take-profit order similarly triggers when price reaches a favorable level, securing profits. Both order types need to integrate with the existing matching engine and respect the price-time priority rules already in place.

The implementation must handle edge cases such as gap openings where the trigger price is breached significantly, partial fills on the resulting market order, and concurrent updates to the same position. The system should also support OCO (one-cancels-other) linking between stop-loss and take-profit orders on the same position.

### Acceptance Criteria

- Stop-loss orders trigger when market price falls to or below the stop price for sell orders, or rises to or above for buy orders
- Take-profit orders trigger when market price reaches the target profit level
- Triggered orders are converted to market orders and processed through the standard matching engine
- OCO pairs automatically cancel the counterpart order when one is triggered or filled
- Trigger events are published to the messaging system for position tracking integration
- Order status transitions are tracked: pending -> triggered -> filled/cancelled
- Slippage protection with configurable maximum deviation from trigger price
- All existing order flow tests continue to pass

### Test Command

```bash
go test -v ./...
```

---

## Task 2: Order Book Service Extraction (Refactoring)

### Description

The current order book implementation is tightly coupled within the matching engine package, making it difficult to scale horizontally or deploy as an independent service. This task involves refactoring the order book into a standalone service with a clean gRPC interface.

The extraction should preserve the existing price-time priority matching semantics while introducing a clear separation between the order book state management and the matching algorithm. The new service architecture should support running multiple order book instances for different trading pairs, with each instance managing its own state independently.

This refactoring enables future improvements such as order book snapshotting, real-time market data streaming, and independent scaling of order book services per trading pair volume.

### Acceptance Criteria

- Order book logic is extracted into a separate internal service package with no direct dependencies on the matching engine
- gRPC service definition for order book operations: AddOrder, CancelOrder, GetDepth, GetBestBidAsk
- Order book state is isolated per trading pair with independent mutex protection
- Market data snapshots can be generated without blocking matching operations
- Event publishing is abstracted through an interface to support multiple messaging backends
- Integration tests verify order book operations work correctly through the gRPC interface
- Matching engine uses the new order book service interface instead of direct struct access
- No regression in existing test coverage

### Test Command

```bash
go test -v ./...
```

---

## Task 3: Order Book Snapshot and Recovery Optimization (Performance Optimization)

### Description

The position tracker currently uses event sourcing for state recovery, but replaying all events becomes prohibitively slow as the event log grows. Large accounts with thousands of historical trades can take minutes to recover after service restart, causing unacceptable delays in position visibility.

This task focuses on implementing an efficient snapshotting mechanism that periodically captures position state, allowing recovery to start from the most recent snapshot rather than replaying the entire event history. The snapshot system must maintain consistency with the event log to handle partial replays correctly.

Additionally, the current event log storage uses a simple slice with linear search for sequence lookups. This should be optimized to support efficient range queries for event replay operations.

### Acceptance Criteria

- Position snapshots are created automatically at configurable intervals (by event count or time)
- Snapshots include all position state: quantities, entry prices, unrealized P&L, and version numbers
- Recovery process loads the latest snapshot and replays only subsequent events
- Snapshot creation does not block normal position update operations
- Event log supports O(log n) sequence number lookups for replay range queries
- Memory usage is bounded with configurable retention policy for old snapshots
- Recovery time for accounts with 10,000+ events is under 100ms from snapshot
- Benchmark tests demonstrate performance improvement over full event replay

### Test Command

```bash
go test -v ./...
```

---

## Task 4: Portfolio Analytics API Expansion (API Extension)

### Description

The portfolio manager currently provides basic portfolio value and position information, but institutional clients require more sophisticated analytics for risk reporting and performance attribution. This task extends the portfolio API with advanced analytics endpoints.

The new endpoints should provide time-weighted return (TWR) calculations that account for cash flows, Sharpe ratio for risk-adjusted performance measurement, and beta calculations against configurable benchmark indices. These metrics are essential for regulatory reporting and investor communications.

All calculations must use proper decimal arithmetic to avoid floating-point precision issues that can accumulate in financial calculations. The analytics should support configurable time periods and be cacheable for repeated access patterns.

### Acceptance Criteria

- Time-weighted return (TWR) endpoint calculates performance adjusted for deposits and withdrawals
- Sharpe ratio endpoint with configurable risk-free rate parameter
- Beta calculation endpoint supporting multiple benchmark indices (configurable)
- Daily, weekly, monthly, and custom period support for all analytics endpoints
- All calculations use decimal arithmetic (not float64) for monetary values
- Results are cached with configurable TTL and invalidation on position changes
- API documentation describes calculation methodology for each metric
- Unit tests verify calculations against known test cases from financial textbooks

### Test Command

```bash
go test -v ./...
```

---

## Task 5: Redis to PostgreSQL Session Migration (Migration)

### Description

The authentication service currently stores session data in Redis for fast access, but this has created operational complexity with session state being separate from the main PostgreSQL database. The operations team wants to consolidate on PostgreSQL for simplified backup, recovery, and compliance auditing.

This task involves migrating session storage from Redis to PostgreSQL while maintaining the performance characteristics required for authentication flows. Sessions must still be validated within 5ms p99 latency to avoid impacting trading operations.

The migration must be performed without service downtime, supporting a gradual rollout with the ability to fall back to Redis if issues are discovered. Existing sessions should continue to work throughout the migration period.

### Acceptance Criteria

- New PostgreSQL session table schema with appropriate indexes for lookup performance
- Dual-write mode that stores sessions in both Redis and PostgreSQL during migration
- Session validation reads from PostgreSQL with Redis fallback for cache misses
- Migration script to backfill existing Redis sessions to PostgreSQL
- Feature flag to control the rollout: Redis-only, dual-write, PostgreSQL-primary, PostgreSQL-only
- Session validation p99 latency remains under 5ms with PostgreSQL backend
- Session expiration is handled via database TTL or background cleanup job
- Rollback procedure documented and tested for reverting to Redis-only mode

### Test Command

```bash
go test -v ./...
```
