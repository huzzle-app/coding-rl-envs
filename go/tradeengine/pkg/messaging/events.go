package messaging

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// Event types
const (
	EventTypeOrderCreated     = "order.created"
	EventTypeOrderUpdated     = "order.updated"
	EventTypeOrderCancelled   = "order.cancelled"
	EventTypeOrderFilled      = "order.filled"
	EventTypeOrderPartialFill = "order.partial_fill"
	EventTypeOrderRejected    = "order.rejected"

	EventTypeTradeExecuted = "trade.executed"

	EventTypePositionOpened  = "position.opened"
	EventTypePositionUpdated = "position.updated"
	EventTypePositionClosed  = "position.closed"

	EventTypeMarketData     = "market.data"
	EventTypeMarketTrade    = "market.trade"
	EventTypeMarketDepth    = "market.depth"

	EventTypeRiskAlert      = "risk.alert"
	EventTypeMarginCall     = "risk.margin_call"
	EventTypeLimitBreached  = "risk.limit_breached"

	EventTypeLedgerEntry    = "ledger.entry"
	EventTypeLedgerTransfer = "ledger.transfer"

	EventTypePriceAlert     = "alert.price"
)

// Event is the base event structure
type Event struct {
	ID          uuid.UUID       `json:"id"`
	Type        string          `json:"type"`
	AggregateID uuid.UUID       `json:"aggregate_id"`
	Timestamp   time.Time       `json:"timestamp"`
	Version     int             `json:"version"`
	Data        json.RawMessage `json:"data"`
	Metadata    EventMetadata   `json:"metadata"`
}

// EventMetadata contains event metadata
type EventMetadata struct {
	CorrelationID string `json:"correlation_id"`
	CausationID   string `json:"causation_id"`
	UserID        string `json:"user_id,omitempty"`
	Source        string `json:"source"`
}

// OrderEvent contains order-related event data
type OrderEvent struct {
	OrderID     uuid.UUID `json:"order_id"`
	UserID      uuid.UUID `json:"user_id"`
	Symbol      string    `json:"symbol"`
	Side        string    `json:"side"`
	Type        string    `json:"type"`
	Quantity    string    `json:"quantity"`
	Price       string    `json:"price,omitempty"`
	FilledQty   string    `json:"filled_qty,omitempty"`
	AvgPrice    string    `json:"avg_price,omitempty"`
	Status      string    `json:"status"`
	Reason      string    `json:"reason,omitempty"`
}

// TradeEvent contains trade execution data
type TradeEvent struct {
	TradeID     uuid.UUID `json:"trade_id"`
	OrderID     uuid.UUID `json:"order_id"`
	Symbol      string    `json:"symbol"`
	Side        string    `json:"side"`
	Quantity    string    `json:"quantity"`
	Price       string    `json:"price"`
	Fee         string    `json:"fee"`
	Timestamp   time.Time `json:"timestamp"`
}

// PositionEvent contains position data
type PositionEvent struct {
	PositionID  uuid.UUID `json:"position_id"`
	UserID      uuid.UUID `json:"user_id"`
	Symbol      string    `json:"symbol"`
	Side        string    `json:"side"`
	Quantity    string    `json:"quantity"`
	EntryPrice  string    `json:"entry_price"`
	CurrentPrice string   `json:"current_price,omitempty"`
	UnrealizedPnL string  `json:"unrealized_pnl,omitempty"`
	RealizedPnL string    `json:"realized_pnl,omitempty"`
}

// MarketDataEvent contains market data
type MarketDataEvent struct {
	Symbol    string    `json:"symbol"`
	Bid       string    `json:"bid"`
	Ask       string    `json:"ask"`
	Last      string    `json:"last"`
	Volume    string    `json:"volume"`
	High      string    `json:"high"`
	Low       string    `json:"low"`
	Open      string    `json:"open"`
	Close     string    `json:"close"`
	Timestamp time.Time `json:"timestamp"`
}

// RiskAlertEvent contains risk alert data
type RiskAlertEvent struct {
	AlertID     uuid.UUID `json:"alert_id"`
	UserID      uuid.UUID `json:"user_id"`
	Type        string    `json:"type"`
	Severity    string    `json:"severity"`
	Message     string    `json:"message"`
	CurrentValue string   `json:"current_value"`
	Threshold   string    `json:"threshold"`
}

// LedgerEntryEvent contains ledger entry data
type LedgerEntryEvent struct {
	EntryID     uuid.UUID `json:"entry_id"`
	AccountID   uuid.UUID `json:"account_id"`
	Type        string    `json:"type"`
	Amount      string    `json:"amount"`
	Currency    string    `json:"currency"`
	Balance     string    `json:"balance"`
	Reference   string    `json:"reference"`
	Description string    `json:"description"`
}

// NewEvent creates a new event
func NewEvent(eventType string, aggregateID uuid.UUID, data interface{}, metadata EventMetadata) (*Event, error) {
	dataBytes, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	return &Event{
		ID:          uuid.New(),
		Type:        eventType,
		AggregateID: aggregateID,
		Timestamp:   time.Now(),
		Version:     1,
		Data:        dataBytes,
		Metadata:    metadata,
	}, nil
}

// ParseEventData parses event data into the specified type
func ParseEventData[T any](event *Event) (*T, error) {
	var data T
	if err := json.Unmarshal(event.Data, &data); err != nil {
		return nil, err
	}
	return &data, nil
}

// EventStore interface for event sourcing
type EventStore interface {
	Append(ctx interface{}, aggregateID uuid.UUID, events []Event, expectedVersion int) error
	Load(ctx interface{}, aggregateID uuid.UUID) ([]Event, error)
	LoadFrom(ctx interface{}, aggregateID uuid.UUID, fromVersion int) ([]Event, error)
}

// EventBus interface for publishing events
type EventBus interface {
	Publish(ctx interface{}, event Event) error
	Subscribe(eventType string, handler func(Event) error) error
}

// Snapshot represents an aggregate snapshot
type Snapshot struct {
	AggregateID uuid.UUID       `json:"aggregate_id"`
	Version     int             `json:"version"`
	State       json.RawMessage `json:"state"`
	Timestamp   time.Time       `json:"timestamp"`
}
