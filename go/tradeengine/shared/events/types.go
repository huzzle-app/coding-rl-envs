package events

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// Event types
const (
	// Order events
	OrderCreated     = "order.created"
	OrderSubmitted   = "order.submitted"
	OrderAccepted    = "order.accepted"
	OrderRejected    = "order.rejected"
	OrderPartialFill = "order.partial_fill"
	OrderFilled      = "order.filled"
	OrderCancelled   = "order.cancelled"

	// Trade events
	TradeExecuted = "trade.executed"

	// Position events
	PositionOpened  = "position.opened"
	PositionUpdated = "position.updated"
	PositionClosed  = "position.closed"

	// Risk events
	RiskAlert      = "risk.alert"
	MarginCall     = "risk.margin_call"
	LimitBreached  = "risk.limit_breached"

	// Market events
	MarketOpen  = "market.open"
	MarketClose = "market.close"
	TradingHalt = "market.halt"

	// Account events
	AccountCreated  = "account.created"
	BalanceUpdated  = "account.balance_updated"
	FundsDeposited  = "account.deposit"
	FundsWithdrawn  = "account.withdrawal"
)

// BaseEvent contains common event fields
type BaseEvent struct {
	ID            uuid.UUID       `json:"id"`
	Type          string          `json:"type"`
	AggregateID   uuid.UUID       `json:"aggregate_id"`
	AggregateType string          `json:"aggregate_type"`
	Timestamp     time.Time       `json:"timestamp"`
	Version       int             `json:"version"`
	Data          json.RawMessage `json:"data"`
	Metadata      Metadata        `json:"metadata"`
}

// Metadata contains event metadata
type Metadata struct {
	CorrelationID string            `json:"correlation_id"`
	CausationID   string            `json:"causation_id"`
	UserID        string            `json:"user_id,omitempty"`
	Source        string            `json:"source"`
	TraceID       string            `json:"trace_id,omitempty"`
	SpanID        string            `json:"span_id,omitempty"`
	Extra         map[string]string `json:"extra,omitempty"`
}

// OrderData contains order event data
type OrderData struct {
	OrderID      uuid.UUID `json:"order_id"`
	UserID       uuid.UUID `json:"user_id"`
	Symbol       string    `json:"symbol"`
	Side         string    `json:"side"`
	Type         string    `json:"type"`
	TimeInForce  string    `json:"time_in_force"`
	Quantity     string    `json:"quantity"`
	Price        string    `json:"price,omitempty"`
	StopPrice    string    `json:"stop_price,omitempty"`
	FilledQty    string    `json:"filled_qty,omitempty"`
	AvgFillPrice string    `json:"avg_fill_price,omitempty"`
	Status       string    `json:"status"`
	Reason       string    `json:"reason,omitempty"`
}

// TradeData contains trade event data
type TradeData struct {
	TradeID     uuid.UUID `json:"trade_id"`
	Symbol      string    `json:"symbol"`
	BuyOrderID  uuid.UUID `json:"buy_order_id"`
	SellOrderID uuid.UUID `json:"sell_order_id"`
	BuyerID     uuid.UUID `json:"buyer_id"`
	SellerID    uuid.UUID `json:"seller_id"`
	Quantity    string    `json:"quantity"`
	Price       string    `json:"price"`
	BuyerFee    string    `json:"buyer_fee"`
	SellerFee   string    `json:"seller_fee"`
	Timestamp   time.Time `json:"timestamp"`
}

// PositionData contains position event data
type PositionData struct {
	PositionID    uuid.UUID `json:"position_id"`
	UserID        uuid.UUID `json:"user_id"`
	Symbol        string    `json:"symbol"`
	Side          string    `json:"side"`
	Quantity      string    `json:"quantity"`
	EntryPrice    string    `json:"entry_price"`
	CurrentPrice  string    `json:"current_price,omitempty"`
	UnrealizedPnL string    `json:"unrealized_pnl,omitempty"`
	RealizedPnL   string    `json:"realized_pnl,omitempty"`
}

// RiskAlertData contains risk alert data
type RiskAlertData struct {
	AlertID      uuid.UUID `json:"alert_id"`
	UserID       uuid.UUID `json:"user_id"`
	AlertType    string    `json:"alert_type"`
	Severity     string    `json:"severity"` // "info", "warning", "critical"
	Message      string    `json:"message"`
	CurrentValue string    `json:"current_value"`
	Threshold    string    `json:"threshold"`
	Metric       string    `json:"metric"`
}

// BalanceData contains balance update data
type BalanceData struct {
	AccountID uuid.UUID `json:"account_id"`
	UserID    uuid.UUID `json:"user_id"`
	Currency  string    `json:"currency"`
	Balance   string    `json:"balance"`
	Available string    `json:"available"`
	Hold      string    `json:"hold"`
	Change    string    `json:"change"`
	Reference string    `json:"reference"`
}

// NewEvent creates a new event
func NewEvent(eventType string, aggregateID uuid.UUID, aggregateType string, data interface{}, metadata Metadata) (*BaseEvent, error) {
	dataBytes, err := json.Marshal(data)
	if err != nil {
		return nil, err
	}

	return &BaseEvent{
		ID:            uuid.New(),
		Type:          eventType,
		AggregateID:   aggregateID,
		AggregateType: aggregateType,
		Timestamp:     time.Now(),
		Version:       1,
		Data:          dataBytes,
		Metadata:      metadata,
	}, nil
}

// ParseData parses event data into the given type
func (e *BaseEvent) ParseData(v interface{}) error {
	return json.Unmarshal(e.Data, v)
}

// WithCorrelation sets correlation and causation IDs
func (m *Metadata) WithCorrelation(correlationID, causationID string) *Metadata {
	m.CorrelationID = correlationID
	m.CausationID = causationID
	return m
}

// WithTracing sets trace context
func (m *Metadata) WithTracing(traceID, spanID string) *Metadata {
	m.TraceID = traceID
	m.SpanID = spanID
	return m
}
