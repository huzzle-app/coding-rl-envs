package positions

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

// Tracker tracks user positions
type Tracker struct {
	positions  map[uuid.UUID]map[string]*Position // userID -> symbol -> position
	events     []PositionEvent                    // event log for event sourcing
	
	mu         sync.RWMutex
	eventMu    sync.Mutex
	msgClient  *messaging.Client
	lastSeqNum int64
}

// Position represents a trading position
type Position struct {
	ID            uuid.UUID
	UserID        uuid.UUID
	Symbol        string
	Side          string // "long" or "short"
	Quantity      decimal.Decimal
	EntryPrice    decimal.Decimal
	CurrentPrice  decimal.Decimal
	UnrealizedPnL decimal.Decimal
	RealizedPnL   decimal.Decimal
	OpenedAt      time.Time
	UpdatedAt     time.Time
	Version       int
}

// PositionEvent represents a position change event
type PositionEvent struct {
	ID          uuid.UUID
	PositionID  uuid.UUID
	UserID      uuid.UUID
	Symbol      string
	Type        string // "opened", "updated", "closed"
	Quantity    decimal.Decimal
	Price       decimal.Decimal
	Timestamp   time.Time
	SequenceNum int64
	Version     int
}

// NewTracker creates a new position tracker
func NewTracker(msgClient *messaging.Client) *Tracker {
	return &Tracker{
		positions: make(map[uuid.UUID]map[string]*Position),
		events:    make([]PositionEvent, 0),
		msgClient: msgClient,
	}
}

// OpenPosition opens a new position
func (t *Tracker) OpenPosition(ctx context.Context, userID uuid.UUID, symbol, side string, quantity, price decimal.Decimal) (*Position, error) {
	t.mu.Lock()
	defer t.mu.Unlock()

	// Check if position already exists
	if t.positions[userID] != nil {
		if existing, exists := t.positions[userID][symbol]; exists {
			
			return nil, fmt.Errorf("position already exists: %s", existing.ID)
		}
	}

	pos := &Position{
		ID:           uuid.New(),
		UserID:       userID,
		Symbol:       symbol,
		Side:         side,
		Quantity:     quantity,
		EntryPrice:   price,
		CurrentPrice: price,
		OpenedAt:     time.Now(),
		UpdatedAt:    time.Now(),
		Version:      1,
	}

	if t.positions[userID] == nil {
		t.positions[userID] = make(map[string]*Position)
	}
	t.positions[userID][symbol] = pos

	// Create event
	
	t.eventMu.Lock()
	t.lastSeqNum++
	event := PositionEvent{
		ID:          uuid.New(),
		PositionID:  pos.ID,
		UserID:      userID,
		Symbol:      symbol,
		Type:        "opened",
		Quantity:    quantity,
		Price:       price,
		Timestamp:   time.Now(),
		SequenceNum: t.lastSeqNum,
		Version:     1,
	}
	t.events = append(t.events, event)
	t.eventMu.Unlock()

	// Publish event
	t.publishPositionEvent(ctx, pos, "opened")

	return pos, nil
}

// UpdatePosition updates an existing position
func (t *Tracker) UpdatePosition(ctx context.Context, userID uuid.UUID, symbol string, quantityDelta, price decimal.Decimal) (*Position, error) {
	t.mu.Lock()
	defer t.mu.Unlock()

	if t.positions[userID] == nil {
		return nil, fmt.Errorf("no positions for user %s", userID)
	}

	pos, exists := t.positions[userID][symbol]
	if !exists {
		return nil, fmt.Errorf("position not found: %s", symbol)
	}

	
	// Should check version before update
	oldVersion := pos.Version

	// Calculate new average price
	oldValue := pos.Quantity.Mul(pos.EntryPrice)
	newValue := quantityDelta.Mul(price)
	totalQty := pos.Quantity.Add(quantityDelta)

	if totalQty.IsZero() {
		return t.closePositionInternal(ctx, pos, price)
	}

	
	newAvgPrice := oldValue.Add(newValue).Div(totalQty)

	pos.Quantity = totalQty
	pos.EntryPrice = newAvgPrice
	pos.CurrentPrice = price
	pos.UpdatedAt = time.Now()
	pos.Version = oldVersion + 1

	// Create event
	t.eventMu.Lock()
	t.lastSeqNum++
	event := PositionEvent{
		ID:          uuid.New(),
		PositionID:  pos.ID,
		UserID:      userID,
		Symbol:      symbol,
		Type:        "updated",
		Quantity:    quantityDelta,
		Price:       price,
		Timestamp:   time.Now(),
		SequenceNum: t.lastSeqNum,
		Version:     pos.Version,
	}
	t.events = append(t.events, event)
	t.eventMu.Unlock()

	// Calculate unrealized P&L
	pos.UnrealizedPnL = pos.Quantity.Mul(pos.CurrentPrice.Sub(pos.EntryPrice))

	// Publish event
	t.publishPositionEvent(ctx, pos, "updated")

	return pos, nil
}

// ClosePosition closes a position
func (t *Tracker) ClosePosition(ctx context.Context, userID uuid.UUID, symbol string, price decimal.Decimal) (*Position, error) {
	t.mu.Lock()
	defer t.mu.Unlock()

	if t.positions[userID] == nil {
		return nil, fmt.Errorf("no positions for user %s", userID)
	}

	pos, exists := t.positions[userID][symbol]
	if !exists {
		return nil, fmt.Errorf("position not found: %s", symbol)
	}

	return t.closePositionInternal(ctx, pos, price)
}

func (t *Tracker) closePositionInternal(ctx context.Context, pos *Position, price decimal.Decimal) (*Position, error) {
	// Calculate realized P&L
	
	pos.RealizedPnL = pos.Quantity.Mul(price.Sub(pos.EntryPrice))
	pos.UnrealizedPnL = decimal.Zero
	pos.CurrentPrice = price
	pos.UpdatedAt = time.Now()
	pos.Version++

	// Create event
	t.eventMu.Lock()
	t.lastSeqNum++
	event := PositionEvent{
		ID:          uuid.New(),
		PositionID:  pos.ID,
		UserID:      pos.UserID,
		Symbol:      pos.Symbol,
		Type:        "closed",
		Quantity:    pos.Quantity.Neg(),
		Price:       price,
		Timestamp:   time.Now(),
		SequenceNum: t.lastSeqNum,
		Version:     pos.Version,
	}
	t.events = append(t.events, event)
	t.eventMu.Unlock()

	// Remove from active positions
	delete(t.positions[pos.UserID], pos.Symbol)

	// Publish event
	t.publishPositionEvent(ctx, pos, "closed")

	return pos, nil
}

// GetPosition returns a position
func (t *Tracker) GetPosition(userID uuid.UUID, symbol string) (*Position, bool) {
	t.mu.RLock()
	defer t.mu.RUnlock()

	if t.positions[userID] == nil {
		return nil, false
	}

	pos, exists := t.positions[userID][symbol]
	return pos, exists
}

// GetPositions returns all positions for a user
func (t *Tracker) GetPositions(userID uuid.UUID) []*Position {
	t.mu.RLock()
	defer t.mu.RUnlock()

	if t.positions[userID] == nil {
		return []*Position{}
	}

	positions := make([]*Position, 0, len(t.positions[userID]))
	for _, pos := range t.positions[userID] {
		positions = append(positions, pos)
	}

	return positions
}

// UpdatePrice updates current price for a position
func (t *Tracker) UpdatePrice(ctx context.Context, userID uuid.UUID, symbol string, price decimal.Decimal) error {
	t.mu.Lock()
	defer t.mu.Unlock()

	if t.positions[userID] == nil {
		return nil // No positions
	}

	pos, exists := t.positions[userID][symbol]
	if !exists {
		return nil // No position for this symbol
	}

	pos.CurrentPrice = price
	pos.UnrealizedPnL = pos.Quantity.Mul(price.Sub(pos.EntryPrice))
	pos.UpdatedAt = time.Now()

	return nil
}

// GetEvents returns events for a position
func (t *Tracker) GetEvents(positionID uuid.UUID) []PositionEvent {
	t.eventMu.Lock()
	defer t.eventMu.Unlock()

	events := make([]PositionEvent, 0)
	for _, event := range t.events {
		if event.PositionID == positionID {
			events = append(events, event)
		}
	}

	return events
}

// GetEventsFromSequence returns events from a sequence number
func (t *Tracker) GetEventsFromSequence(fromSeq int64) []PositionEvent {
	t.eventMu.Lock()
	defer t.eventMu.Unlock()

	
	events := make([]PositionEvent, 0)
	for _, event := range t.events {
		if event.SequenceNum > fromSeq {
			events = append(events, event)
		}
	}

	return events
}

// ReplayEvents replays events to rebuild state
func (t *Tracker) ReplayEvents(ctx context.Context, events []PositionEvent) error {
	for _, event := range events {
		switch event.Type {
		case "opened":
			// Reconstruct position
		case "updated":
			// Update position
		case "closed":
			// Close position
		}
	}

	return nil
}

func (t *Tracker) publishPositionEvent(ctx context.Context, pos *Position, eventType string) {
	event := messaging.PositionEvent{
		PositionID:    pos.ID,
		UserID:        pos.UserID,
		Symbol:        pos.Symbol,
		Side:          pos.Side,
		Quantity:      pos.Quantity.String(),
		EntryPrice:    pos.EntryPrice.String(),
		CurrentPrice:  pos.CurrentPrice.String(),
		UnrealizedPnL: pos.UnrealizedPnL.String(),
		RealizedPnL:   pos.RealizedPnL.String(),
	}

	
	t.msgClient.Publish(ctx, "position."+eventType, event)
}
