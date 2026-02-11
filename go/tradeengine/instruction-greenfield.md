# TradeEngine - Greenfield Tasks

## Overview

These three greenfield implementation tasks add entirely new capabilities to the TradeEngine platform. Each requires building a new module from scratch while following established architectural patterns. Tasks test system design, concurrency management, and integration with existing infrastructure.

## Environment

- **Language**: Go
- **Infrastructure**: NATS JetStream 2.10, PostgreSQL 15, Redis 7, etcd 3.5
- **Difficulty**: Principal

## Tasks

### Task 1: Market Maker Service (Greenfield Implementation)

Implement an automated market making service that maintains two-sided quotes around the current market price. The service must dynamically adjust spreads based on inventory risk, enforce position limits, and track P&L across multiple symbols.

**Location:** `internal/marketmaker/`

**Interface Highlights:**
- `MarketMaker` service with Start/Stop/UpdateConfig operations per symbol
- `Config` type controlling spread, order size, max inventory, refresh interval, skew factor
- `Status` tracking active quotes, last update, trade counts, P&L
- `Inventory` tracking net position, buy/sell history, realized/unrealized P&L

**Key Requirements:**
- Multi-symbol market making with independent configuration
- Inventory-based spread skew (higher skew for larger positions)
- Position limit enforcement (MaxInventory, MinInventory)
- Quote refresh at configurable intervals
- Integration with matching engine for order submission
- Position tracker integration for inventory updates
- Event publishing for quote updates (`marketmaker.quote`)
- 85%+ code coverage with unit and integration tests

**Architectural Patterns:**
- Concurrency via `sync.RWMutex` (see `internal/matching/engine.go`)
- Event publishing through `messaging.Client`
- Decimal arithmetic using `github.com/shopspring/decimal`
- Goroutine lifecycle management with `sync.WaitGroup`
- Context propagation for cancellation and timeouts

---

### Task 2: Trade Reconciliation Engine (Greenfield Implementation)

Implement a trade reconciliation system that compares internal trade records against external venue data. The system must detect discrepancies (breaks), classify break types (missing, price diff, quantity diff, etc.), and support both automatic and manual resolution.

**Location:** `internal/reconciliation/`

**Interface Highlights:**
- `Reconciler` service with Reconcile, GetBreaks, ResolveBreak operations
- `ExternalSource` interface for pluggable venue adapters
- `Break` types: Missing, PriceDiff, QuantityDiff, TimeDiff, Duplicate
- `Tolerance` struct for configurable matching thresholds
- `ReconcileResult` containing break count, matched count, duration
- `Resolution` tracking how breaks were resolved (auto/manual/ignored)

**Key Requirements:**
- Trade matching with configurable tolerances (price, quantity, time)
- Break detection for each break type
- Severity classification (critical, major, minor)
- Auto-resolution logic for simple cases
- Break persistence and retrieval with filtering
- Statistics API (match rates, break counts by type/severity)
- Reconciliation jobs with progress tracking
- 85%+ code coverage with unit and integration tests
- Event publishing for break detection/resolution

**Architectural Patterns:**
- Database access via `database/sql` with context (see `internal/portfolio/manager.go`)
- Decimal comparisons using `decimal.Decimal.Cmp()`
- Batch processing for large trade volumes
- Break caching to avoid reprocessing
- Event publishing via NATS for break notifications

---

### Task 3: Price Alert System (Greenfield Implementation)

Implement an enhanced price alert system supporting complex multi-condition alerts beyond simple price thresholds. System must handle percentage changes, rate-of-change triggers, price crossing detection, and multi-condition compound logic with proper cooldown and expiration handling.

**Location:** `internal/pricealerts/`

**Interface Highlights:**
- `AlertService` for CRUD operations on alerts
- `AlertEngine` processing price updates against active alerts
- `Condition` types: Price, PercentChange, PriceRange, RateOfChange, Volume, Spread, Compound
- `Operator` types: GreaterThan, LessThan, Equals, Crosses, CrossesAbove, CrossesBelow, EntersRange, ExitsRange, IncreasesBy, DecreasesBy
- `Alert` with status tracking (Active, Paused, Triggered, Expired, Deleted)
- `TriggeredAlert` with notification delivery tracking
- `EngineStats` for monitoring active alerts, trigger counts, processing times

**Key Requirements:**
- Simple and compound alert conditions (AND/OR logic)
- Price crossing detection (crossing, crossing-above, crossing-below)
- Percentage change alerts from reference price
- Rate-of-change (ROC) calculation over time windows
- Price range enter/exit detection
- One-time and recurring alerts with cooldown periods
- Alert expiration by time
- Notification delivery to multiple channels (push, email, webhook)
- Persistent storage with recovery on restart
- Redis caching for active alert lookup
- Price history ring buffer for ROC calculations
- 85%+ code coverage with unit and integration tests
- Event publishing for triggered alerts (`alert.triggered`)

**Architectural Patterns:**
- Buffered channels for price processing (see existing alerts engine)
- Database persistence in PostgreSQL with transactions
- Redis caching for active alert sets
- Decimal comparison using `decimal.Decimal.Cmp()`
- Ring buffer for price history with O(1) insertion
- Graceful shutdown with `sync.WaitGroup`
- Subscription to `market.data` events for price updates

---

## Implementation Guidelines

### Code Organization

Each module should follow:
```
internal/<module>/
    service.go      # Main service implementation
    types.go        # Type definitions (if complex)
    repository.go   # Database access layer (if applicable)
    events.go       # Event handlers and publishers
```

### Testing Structure

```
tests/
    unit/<module>_test.go        # Unit tests with mocks
    integration/<module>_test.go # Integration tests with real dependencies
```

### Common Dependencies

All modules must use:
- `github.com/google/uuid` for UUIDs
- `github.com/shopspring/decimal` for financial calculations
- `context.Context` for cancellation propagation
- `sync.Mutex`/`sync.RWMutex` for concurrency

### Error Handling

Use sentinel errors for common cases:
```go
var (
    ErrNotFound      = errors.New("resource not found")
    ErrAlreadyExists = errors.New("resource already exists")
    ErrInvalidInput  = errors.New("invalid input")
    ErrUnauthorized  = errors.New("unauthorized")
)
```

### Metrics and Logging

- Structured logging using `log/slog` or similar
- Expose metrics for monitoring (counts, latencies, error rates)
- Use correlation IDs from context for distributed tracing

## Getting Started

```bash
go test -v ./...
```

## Success Criteria

Implementation meets the acceptance criteria defined in [TASKS_GREENFIELD.md](./TASKS_GREENFIELD.md).
