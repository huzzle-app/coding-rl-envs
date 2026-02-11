# TradeEngine Greenfield Tasks

This document contains greenfield implementation tasks for the TradeEngine platform. Each task requires implementing a new module from scratch while following existing architectural patterns.

**Test Command:** `go test -v ./...`

---

## Task 1: Market Maker Service

### Overview

Implement a Market Maker service that automatically provides liquidity by placing buy and sell orders around the current market price. The service should maintain a configurable spread and dynamically adjust quotes based on inventory risk.

### Location

Create files in: `internal/marketmaker/`

### Interface Contract

```go
package marketmaker

import (
    "context"
    "time"

    "github.com/google/uuid"
    "github.com/shopspring/decimal"
)

// MarketMaker provides automated liquidity for trading pairs
type MarketMaker interface {
    // Start begins market making for the specified symbol
    Start(ctx context.Context, symbol string) error

    // Stop halts market making for the specified symbol
    Stop(symbol string) error

    // UpdateConfig updates the market making configuration
    UpdateConfig(symbol string, config *Config) error

    // GetStatus returns the current status of a market maker
    GetStatus(symbol string) (*Status, error)

    // GetActiveSymbols returns all symbols with active market makers
    GetActiveSymbols() []string

    // GetInventory returns current inventory position for a symbol
    GetInventory(symbol string) (*Inventory, error)
}

// Config contains market making parameters for a symbol
type Config struct {
    Symbol          string          // Trading pair symbol
    SpreadBps       int             // Bid-ask spread in basis points (100 bps = 1%)
    OrderSize       decimal.Decimal // Size of each quote order
    MaxInventory    decimal.Decimal // Maximum net inventory position
    MinInventory    decimal.Decimal // Minimum net inventory (negative for short)
    RefreshInterval time.Duration   // How often to refresh quotes
    SkewFactor      decimal.Decimal // Inventory skew adjustment factor
    Enabled         bool            // Whether market making is active
}

// Status represents the current state of a market maker
type Status struct {
    Symbol          string
    State           string          // "running", "paused", "stopped", "error"
    CurrentBid      decimal.Decimal
    CurrentAsk      decimal.Decimal
    MidPrice        decimal.Decimal
    BidOrderID      uuid.UUID
    AskOrderID      uuid.UUID
    LastUpdate      time.Time
    TotalTrades     int64
    TotalVolume     decimal.Decimal
    PnL             decimal.Decimal
    ErrorMessage    string
}

// Inventory tracks the market maker's position
type Inventory struct {
    Symbol           string
    NetPosition      decimal.Decimal // Positive = long, negative = short
    TotalBought      decimal.Decimal
    TotalSold        decimal.Decimal
    AvgBuyPrice      decimal.Decimal
    AvgSellPrice     decimal.Decimal
    UnrealizedPnL    decimal.Decimal
    RealizedPnL      decimal.Decimal
    InventoryRisk    decimal.Decimal // 0.0 to 1.0 based on position vs limits
}

// QuoteUpdate represents a price quote update event
type QuoteUpdate struct {
    Symbol    string
    BidPrice  decimal.Decimal
    BidSize   decimal.Decimal
    AskPrice  decimal.Decimal
    AskSize   decimal.Decimal
    Timestamp time.Time
}
```

### Required Structs/Types

```go
// Service implements the MarketMaker interface
type Service struct {
    matching    *matching.Engine
    positions   *positions.Tracker
    msgClient   *messaging.Client
    makers      map[string]*symbolMaker  // symbol -> active maker
    mu          sync.RWMutex
    shutdown    chan struct{}
}

// symbolMaker manages market making for a single symbol
type symbolMaker struct {
    config      *Config
    status      *Status
    inventory   *Inventory
    stopCh      chan struct{}
    mu          sync.RWMutex
}

// TradeCallback is invoked when a market maker order is filled
type TradeCallback func(trade *messaging.TradeEvent)
```

### Architectural Patterns to Follow

1. **Concurrency**: Use `sync.RWMutex` for protecting shared state (see `internal/matching/engine.go`)
2. **Event Publishing**: Publish events via `messaging.Client` for quote updates and fills
3. **Decimal Arithmetic**: Use `github.com/shopspring/decimal` for all price/quantity calculations
4. **Context Propagation**: Accept `context.Context` for cancellation and timeout handling
5. **Goroutine Management**: Use `sync.WaitGroup` for graceful shutdown (see matching engine's `Start`/`Stop`)
6. **Error Handling**: Return wrapped errors with context using `fmt.Errorf("...: %w", err)`

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/marketmaker_test.go`):
   - Test quote calculation with various spreads
   - Test inventory skew adjustments
   - Test max inventory limits enforcement
   - Test concurrent start/stop operations
   - Test configuration updates while running
   - Minimum 85% code coverage

2. **Integration Tests** (`tests/integration/marketmaker_test.go`):
   - Test quote placement and cancellation via matching engine
   - Test inventory updates on trade execution
   - Test P&L tracking across multiple trades
   - Test event publishing to NATS

3. **Integration Points**:
   - Subscribe to `market.data` events for price updates
   - Publish `marketmaker.quote` events when quotes are updated
   - Integrate with `matching.Engine` for order submission
   - Integrate with `positions.Tracker` for inventory tracking

---

## Task 2: Trade Reconciliation Engine

### Overview

Implement a Trade Reconciliation Engine that compares internal trade records with external venue/counterparty data to detect discrepancies. The service should handle trade matching, break detection, and automated resolution for simple cases.

### Location

Create files in: `internal/reconciliation/`

### Interface Contract

```go
package reconciliation

import (
    "context"
    "time"

    "github.com/google/uuid"
    "github.com/shopspring/decimal"
)

// Reconciler compares and reconciles trades between internal and external sources
type Reconciler interface {
    // Reconcile performs reconciliation for a time range
    Reconcile(ctx context.Context, req *ReconcileRequest) (*ReconcileResult, error)

    // GetBreaks returns all unresolved breaks
    GetBreaks(ctx context.Context, filter *BreakFilter) ([]*Break, error)

    // GetBreak returns a specific break by ID
    GetBreak(ctx context.Context, breakID uuid.UUID) (*Break, error)

    // ResolveBreak manually resolves a break
    ResolveBreak(ctx context.Context, breakID uuid.UUID, resolution *Resolution) error

    // AutoResolve attempts automatic resolution for eligible breaks
    AutoResolve(ctx context.Context, breakID uuid.UUID) (*Resolution, error)

    // GetStats returns reconciliation statistics
    GetStats(ctx context.Context, period string) (*Stats, error)

    // RegisterSource registers an external data source
    RegisterSource(name string, source ExternalSource) error
}

// ExternalSource provides trade data from an external venue
type ExternalSource interface {
    // FetchTrades retrieves trades from the external source
    FetchTrades(ctx context.Context, startTime, endTime time.Time) ([]*ExternalTrade, error)

    // GetSourceName returns the source identifier
    GetSourceName() string

    // HealthCheck verifies connectivity to the source
    HealthCheck(ctx context.Context) error
}

// ReconcileRequest specifies reconciliation parameters
type ReconcileRequest struct {
    StartTime     time.Time
    EndTime       time.Time
    Symbols       []string        // Empty = all symbols
    SourceName    string          // External source to reconcile against
    Tolerance     *Tolerance      // Matching tolerances
}

// Tolerance defines acceptable differences for matching
type Tolerance struct {
    PriceTolerance    decimal.Decimal // Max price difference (absolute)
    QuantityTolerance decimal.Decimal // Max quantity difference (absolute)
    TimeTolerance     time.Duration   // Max timestamp difference
}

// ReconcileResult contains the outcome of a reconciliation run
type ReconcileResult struct {
    RunID           uuid.UUID
    StartTime       time.Time
    EndTime         time.Time
    InternalCount   int
    ExternalCount   int
    MatchedCount    int
    BreakCount      int
    Breaks          []*Break
    Duration        time.Duration
    Status          string          // "completed", "partial", "failed"
}

// Break represents a reconciliation discrepancy
type Break struct {
    ID              uuid.UUID
    Type            BreakType
    InternalTrade   *InternalTrade
    ExternalTrade   *ExternalTrade
    Differences     []Difference
    Severity        string          // "critical", "major", "minor"
    Status          string          // "open", "investigating", "resolved"
    DetectedAt      time.Time
    ResolvedAt      *time.Time
    Resolution      *Resolution
    AssignedTo      string
    Notes           string
}

// BreakType categorizes the type of discrepancy
type BreakType string

const (
    BreakTypeMissing     BreakType = "missing"      // Trade exists only on one side
    BreakTypePriceDiff   BreakType = "price_diff"   // Price mismatch
    BreakTypeQuantityDiff BreakType = "qty_diff"    // Quantity mismatch
    BreakTypeTimeDiff    BreakType = "time_diff"    // Timestamp mismatch
    BreakTypeDuplicate   BreakType = "duplicate"    // Duplicate trade detected
)

// Difference describes a specific field difference
type Difference struct {
    Field         string
    InternalValue string
    ExternalValue string
    Delta         string
}

// InternalTrade represents a trade from our system
type InternalTrade struct {
    TradeID     uuid.UUID
    OrderID     uuid.UUID
    Symbol      string
    Side        string
    Quantity    decimal.Decimal
    Price       decimal.Decimal
    Fee         decimal.Decimal
    Timestamp   time.Time
    Venue       string
}

// ExternalTrade represents a trade from an external source
type ExternalTrade struct {
    ExternalID  string
    Symbol      string
    Side        string
    Quantity    decimal.Decimal
    Price       decimal.Decimal
    Fee         decimal.Decimal
    Timestamp   time.Time
    Source      string
    RawData     map[string]interface{}
}

// Resolution describes how a break was resolved
type Resolution struct {
    Method      string          // "auto", "manual", "ignored"
    Action      string          // "amended", "cancelled", "accepted", "escalated"
    Description string
    ResolvedBy  string
    ResolvedAt  time.Time
}

// BreakFilter specifies criteria for querying breaks
type BreakFilter struct {
    Status      string
    Severity    string
    BreakType   BreakType
    Symbol      string
    StartDate   time.Time
    EndDate     time.Time
    Limit       int
    Offset      int
}

// Stats contains reconciliation statistics
type Stats struct {
    Period            string
    TotalReconciled   int64
    TotalMatched      int64
    TotalBreaks       int64
    OpenBreaks        int64
    AutoResolved      int64
    ManualResolved    int64
    MatchRate         float64         // Percentage (0-100)
    AvgResolutionTime time.Duration
    BreaksByType      map[BreakType]int64
    BreaksBySeverity  map[string]int64
}
```

### Required Structs/Types

```go
// Engine implements the Reconciler interface
type Engine struct {
    db          *sql.DB
    msgClient   *messaging.Client
    sources     map[string]ExternalSource
    sourcesMu   sync.RWMutex
    matcher     *tradeMatcher
}

// tradeMatcher handles the matching logic
type tradeMatcher struct {
    tolerance *Tolerance
}

// ReconcileJob tracks a reconciliation job
type ReconcileJob struct {
    ID          uuid.UUID
    Request     *ReconcileRequest
    Status      string
    Progress    int
    StartedAt   time.Time
    CompletedAt *time.Time
}
```

### Architectural Patterns to Follow

1. **Database Access**: Use `database/sql` with context (see `internal/portfolio/manager.go`)
2. **Event Publishing**: Publish `reconciliation.break.detected` and `reconciliation.break.resolved` events
3. **Decimal Arithmetic**: Use `github.com/shopspring/decimal` for all monetary comparisons
4. **Error Wrapping**: Return wrapped errors with context
5. **Batch Processing**: Process trades in batches to handle large volumes
6. **Caching**: Consider caching matched trades to avoid reprocessing

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/reconciliation_test.go`):
   - Test trade matching with exact matches
   - Test trade matching with tolerances
   - Test break detection for each break type
   - Test auto-resolution logic
   - Test statistics calculation
   - Minimum 85% code coverage

2. **Integration Tests** (`tests/integration/reconciliation_test.go`):
   - Test full reconciliation workflow
   - Test with mock external source
   - Test break persistence and retrieval
   - Test event publishing on break detection

3. **Integration Points**:
   - Query trades from ledger service via database
   - Publish events to NATS for break notifications
   - Support multiple external source adapters

---

## Task 3: Price Alert System

### Overview

Implement an enhanced Price Alert System that supports complex alert conditions beyond simple price thresholds. The system should support percentage changes, multi-condition alerts, and rate-of-change triggers with proper notification delivery.

### Location

Create files in: `internal/pricealerts/`

**Note**: This is a more sophisticated replacement for the basic alerts in `internal/alerts/`. The new system should coexist and can import types from the existing package if needed.

### Interface Contract

```go
package pricealerts

import (
    "context"
    "time"

    "github.com/google/uuid"
    "github.com/shopspring/decimal"
)

// AlertService manages price alerts with complex conditions
type AlertService interface {
    // CreateAlert creates a new price alert
    CreateAlert(ctx context.Context, req *CreateAlertRequest) (*Alert, error)

    // GetAlert retrieves an alert by ID
    GetAlert(ctx context.Context, alertID uuid.UUID) (*Alert, error)

    // GetUserAlerts returns all alerts for a user
    GetUserAlerts(ctx context.Context, userID uuid.UUID, filter *AlertFilter) ([]*Alert, error)

    // UpdateAlert modifies an existing alert
    UpdateAlert(ctx context.Context, alertID uuid.UUID, update *AlertUpdate) (*Alert, error)

    // DeleteAlert removes an alert
    DeleteAlert(ctx context.Context, alertID uuid.UUID) error

    // PauseAlert temporarily disables an alert
    PauseAlert(ctx context.Context, alertID uuid.UUID) error

    // ResumeAlert re-enables a paused alert
    ResumeAlert(ctx context.Context, alertID uuid.UUID) error

    // GetTriggeredAlerts returns recently triggered alerts
    GetTriggeredAlerts(ctx context.Context, userID uuid.UUID, since time.Time) ([]*TriggeredAlert, error)
}

// AlertEngine processes price updates and evaluates alerts
type AlertEngine interface {
    // Start begins processing price updates
    Start(ctx context.Context) error

    // Stop halts the alert engine
    Stop() error

    // ProcessPrice evaluates a price update against all relevant alerts
    ProcessPrice(ctx context.Context, update *PriceUpdate) error

    // GetStats returns engine statistics
    GetStats() *EngineStats
}

// CreateAlertRequest contains parameters for creating an alert
type CreateAlertRequest struct {
    UserID          uuid.UUID
    Symbol          string
    Name            string          // User-friendly name
    Condition       *Condition      // Alert trigger condition
    NotifyChannels  []string        // "push", "email", "webhook"
    WebhookURL      string          // For webhook notifications
    Expiry          *time.Time      // Optional expiration
    Recurring       bool            // Trigger multiple times vs once
    Cooldown        time.Duration   // Minimum time between triggers (for recurring)
    Metadata        map[string]string
}

// Condition defines when an alert should trigger
type Condition struct {
    Type            ConditionType
    Operator        Operator
    Value           decimal.Decimal
    SecondaryValue  decimal.Decimal // For range conditions
    TimeWindow      time.Duration   // For rate-of-change conditions
    SubConditions   []*Condition    // For compound conditions (AND/OR)
    LogicalOperator string          // "AND" or "OR" for compound
}

// ConditionType specifies the type of condition
type ConditionType string

const (
    ConditionPrice         ConditionType = "price"          // Absolute price
    ConditionPercentChange ConditionType = "percent_change" // % change from reference
    ConditionPriceRange    ConditionType = "price_range"    // Price enters/exits range
    ConditionRateOfChange  ConditionType = "rate_of_change" // Price velocity
    ConditionVolume        ConditionType = "volume"         // Volume threshold
    ConditionSpread        ConditionType = "spread"         // Bid-ask spread
    ConditionCompound      ConditionType = "compound"       // Multiple conditions
)

// Operator specifies comparison operation
type Operator string

const (
    OpGreaterThan      Operator = "gt"
    OpGreaterOrEqual   Operator = "gte"
    OpLessThan         Operator = "lt"
    OpLessOrEqual      Operator = "lte"
    OpEquals           Operator = "eq"
    OpCrosses          Operator = "crosses"      // Price crosses value
    OpCrossesAbove     Operator = "crosses_above"
    OpCrossesBelow     Operator = "crosses_below"
    OpEntersRange      Operator = "enters_range"
    OpExitsRange       Operator = "exits_range"
    OpIncreasesBy      Operator = "increases_by" // For percent change
    OpDecreasesBy      Operator = "decreases_by"
)

// Alert represents a configured price alert
type Alert struct {
    ID              uuid.UUID
    UserID          uuid.UUID
    Symbol          string
    Name            string
    Condition       *Condition
    Status          AlertStatus
    NotifyChannels  []string
    WebhookURL      string
    Expiry          *time.Time
    Recurring       bool
    Cooldown        time.Duration
    TriggerCount    int
    LastTriggered   *time.Time
    CreatedAt       time.Time
    UpdatedAt       time.Time
    Metadata        map[string]string
}

// AlertStatus represents the current state of an alert
type AlertStatus string

const (
    StatusActive    AlertStatus = "active"
    StatusPaused    AlertStatus = "paused"
    StatusTriggered AlertStatus = "triggered"  // For non-recurring
    StatusExpired   AlertStatus = "expired"
    StatusDeleted   AlertStatus = "deleted"
)

// AlertUpdate contains fields that can be updated
type AlertUpdate struct {
    Name            *string
    Condition       *Condition
    NotifyChannels  []string
    WebhookURL      *string
    Expiry          *time.Time
    Recurring       *bool
    Cooldown        *time.Duration
}

// AlertFilter specifies criteria for querying alerts
type AlertFilter struct {
    Symbol      string
    Status      AlertStatus
    Limit       int
    Offset      int
}

// PriceUpdate contains current price data
type PriceUpdate struct {
    Symbol      string
    Bid         decimal.Decimal
    Ask         decimal.Decimal
    Last        decimal.Decimal
    Volume24h   decimal.Decimal
    Timestamp   time.Time
}

// TriggeredAlert contains details of an alert trigger event
type TriggeredAlert struct {
    AlertID         uuid.UUID
    Alert           *Alert
    TriggerPrice    decimal.Decimal
    TriggerTime     time.Time
    ConditionMet    string          // Human-readable condition that triggered
    NotificationsSent []NotificationResult
}

// NotificationResult tracks delivery status
type NotificationResult struct {
    Channel     string
    Success     bool
    Error       string
    SentAt      time.Time
}

// EngineStats contains alert engine metrics
type EngineStats struct {
    ActiveAlerts     int64
    AlertsProcessed  int64
    AlertsTriggered  int64
    PriceUpdates     int64
    AvgProcessTime   time.Duration
    LastProcessed    time.Time
}
```

### Required Structs/Types

```go
// Service implements AlertService and AlertEngine
type Service struct {
    db              *sql.DB
    msgClient       *messaging.Client
    redis           *redis.Client
    alerts          map[string][]*Alert  // symbol -> alerts
    priceHistory    map[string]*priceRing // symbol -> price history for ROC
    mu              sync.RWMutex
    priceChannel    chan *PriceUpdate
    stopCh          chan struct{}
    wg              sync.WaitGroup
    stats           *EngineStats
    statsMu         sync.Mutex
}

// priceRing is a ring buffer for price history
type priceRing struct {
    prices    []pricePoint
    size      int
    head      int
    count     int
    mu        sync.RWMutex
}

// pricePoint stores a historical price
type pricePoint struct {
    price     decimal.Decimal
    timestamp time.Time
}

// NotificationSender handles alert delivery
type NotificationSender interface {
    Send(ctx context.Context, alert *Alert, trigger *TriggeredAlert) error
}
```

### Architectural Patterns to Follow

1. **Concurrency**: Use buffered channels for price processing (see existing alerts engine)
2. **Database Access**: Persist alerts in PostgreSQL with proper transactions
3. **Caching**: Use Redis for active alert lookup optimization
4. **Event Publishing**: Publish `alert.triggered` events via NATS
5. **Decimal Comparison**: Use `decimal.Decimal.Cmp()` instead of float comparison
6. **Graceful Shutdown**: Implement proper cleanup with `sync.WaitGroup`

### Acceptance Criteria

1. **Unit Tests** (`tests/unit/pricealerts_test.go`):
   - Test each condition type evaluation
   - Test compound conditions (AND/OR)
   - Test price crossing detection
   - Test rate-of-change calculation
   - Test cooldown enforcement
   - Test alert expiry
   - Minimum 85% code coverage

2. **Integration Tests** (`tests/integration/pricealerts_test.go`):
   - Test alert lifecycle (create, trigger, resolve)
   - Test notification delivery
   - Test persistence and recovery
   - Test concurrent price updates

3. **Integration Points**:
   - Subscribe to `market.data` events for price updates
   - Publish `alert.triggered` events to NATS
   - Integrate with notification service for delivery
   - Store alert history in database

---

## General Implementation Notes

### Code Organization

Each module should follow this structure:
```
internal/<module>/
    service.go      # Main service implementation
    types.go        # Type definitions (if complex)
    repository.go   # Database access layer
    events.go       # Event handlers and publishers
```

### Testing Structure

```
tests/
    unit/<module>_test.go        # Unit tests with mocks
    integration/<module>_test.go # Integration tests with real dependencies
```

### Common Dependencies

All modules should use:
- `github.com/google/uuid` for UUIDs
- `github.com/shopspring/decimal` for financial calculations
- `github.com/terminal-bench/tradeengine/pkg/messaging` for NATS messaging
- `context.Context` for cancellation propagation

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

- Add structured logging using `log/slog` or similar
- Expose metrics for monitoring (counts, latencies, error rates)
- Use correlation IDs from context for distributed tracing
