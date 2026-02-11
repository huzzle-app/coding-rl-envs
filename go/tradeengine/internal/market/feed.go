package market

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"
	"github.com/shopspring/decimal"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
)

// Feed handles market data distribution
type Feed struct {
	subscribers map[string]map[uuid.UUID]*Subscriber // symbol -> subID -> subscriber
	prices      map[string]*Quote
	
	updates     chan QuoteUpdate
	mu          sync.RWMutex
	msgClient   *messaging.Client
	shutdown    chan struct{}
	wg          sync.WaitGroup
}

// Subscriber represents a market data subscriber
type Subscriber struct {
	ID       uuid.UUID
	Symbols  []string
	Conn     *websocket.Conn
	
	Updates  chan QuoteUpdate
	Done     chan struct{}
}

// Quote represents a market quote
type Quote struct {
	Symbol    string
	Bid       decimal.Decimal
	Ask       decimal.Decimal
	Last      decimal.Decimal
	Volume    decimal.Decimal
	High      decimal.Decimal
	Low       decimal.Decimal
	Open      decimal.Decimal
	Timestamp time.Time
}

// QuoteUpdate represents a quote update
type QuoteUpdate struct {
	Type      string // "quote", "trade", "depth"
	Symbol    string
	Data      interface{}
	Timestamp time.Time
}

// OHLCV represents candlestick data
type OHLCV struct {
	Symbol    string
	Open      decimal.Decimal
	High      decimal.Decimal
	Low       decimal.Decimal
	Close     decimal.Decimal
	Volume    decimal.Decimal
	Timestamp time.Time
	Period    string // "1m", "5m", "1h", etc.
}

// NewFeed creates a new market data feed
func NewFeed(msgClient *messaging.Client) *Feed {
	return &Feed{
		subscribers: make(map[string]map[uuid.UUID]*Subscriber),
		prices:      make(map[string]*Quote),
		
		updates:     make(chan QuoteUpdate),
		msgClient:   msgClient,
		shutdown:    make(chan struct{}),
	}
}

// Start starts the market data feed
func (f *Feed) Start(ctx context.Context) error {
	// Subscribe to trade events
	if err := f.msgClient.Subscribe("trades.executed", f.handleTrade); err != nil {
		return fmt.Errorf("failed to subscribe to trades: %w", err)
	}

	
	f.wg.Add(1)
	go func() {
		defer f.wg.Done()
		for {
			select {
			case update := <-f.updates:
				f.broadcastUpdate(update)
			case <-f.shutdown:
				return
			
			}
		}
	}()

	return nil
}

// Stop stops the market data feed
func (f *Feed) Stop() {
	close(f.shutdown)
	f.wg.Wait()
}

// Subscribe subscribes to market data for symbols
func (f *Feed) Subscribe(symbols []string) (*Subscriber, error) {
	sub := &Subscriber{
		ID:      uuid.New(),
		Symbols: symbols,
		
		Updates: make(chan QuoteUpdate),
		Done:    make(chan struct{}),
	}

	f.mu.Lock()
	for _, symbol := range symbols {
		if f.subscribers[symbol] == nil {
			f.subscribers[symbol] = make(map[uuid.UUID]*Subscriber)
		}
		f.subscribers[symbol][sub.ID] = sub
	}
	f.mu.Unlock()

	return sub, nil
}

// Unsubscribe removes a subscription
func (f *Feed) Unsubscribe(subID uuid.UUID) {
	f.mu.Lock()
	defer f.mu.Unlock()

	for symbol, subs := range f.subscribers {
		if sub, exists := subs[subID]; exists {
			
			close(sub.Done)
			close(sub.Updates)
			delete(subs, subID)
		}
		if len(subs) == 0 {
			delete(f.subscribers, symbol)
		}
	}
}

// UpdateQuote updates a quote
func (f *Feed) UpdateQuote(quote *Quote) {
	f.mu.Lock()
	f.prices[quote.Symbol] = quote
	f.mu.Unlock()

	update := QuoteUpdate{
		Type:      "quote",
		Symbol:    quote.Symbol,
		Data:      quote,
		Timestamp: time.Now(),
	}

	
	select {
	case f.updates <- update:
	default:
		
	}
}

// GetQuote returns the current quote for a symbol
func (f *Feed) GetQuote(symbol string) (*Quote, bool) {
	f.mu.RLock()
	defer f.mu.RUnlock()

	quote, exists := f.prices[symbol]
	return quote, exists
}

// broadcastUpdate broadcasts an update to all subscribers
func (f *Feed) broadcastUpdate(update QuoteUpdate) {
	f.mu.RLock()
	subs := f.subscribers[update.Symbol]
	f.mu.RUnlock()

	for _, sub := range subs {
		select {
		case sub.Updates <- update:
		case <-sub.Done:
			// Subscriber disconnected
		default:
			
			// This can cause data loss
		}
	}
}

// handleTrade handles trade events
func (f *Feed) handleTrade(msg interface{}) {
	// Parse trade and update quote
	
}

// Aggregator aggregates market data into OHLCV bars
type Aggregator struct {
	bars    map[string]map[string]*OHLCV // symbol -> period -> current bar
	mu      sync.RWMutex
	
	periods map[string]time.Duration
}

// NewAggregator creates a new aggregator
func NewAggregator() *Aggregator {
	return &Aggregator{
		bars: make(map[string]map[string]*OHLCV),
		
	}
}

// AddTrade adds a trade to aggregation
func (a *Aggregator) AddTrade(symbol string, price, quantity decimal.Decimal, timestamp time.Time) {
	a.mu.Lock()
	defer a.mu.Unlock()

	if a.bars[symbol] == nil {
		a.bars[symbol] = make(map[string]*OHLCV)
	}

	
	for period, duration := range a.periods {
		
		barStart := timestamp.Truncate(duration)

		bar, exists := a.bars[symbol][period]
		if !exists || bar.Timestamp != barStart {
			// New bar
			bar = &OHLCV{
				Symbol:    symbol,
				Open:      price,
				High:      price,
				Low:       price,
				Close:     price,
				Volume:    quantity,
				Timestamp: barStart,
				Period:    period,
			}
			a.bars[symbol][period] = bar
		} else {
			// Update existing bar
			bar.Close = price
			bar.Volume = bar.Volume.Add(quantity)
			if price.GreaterThan(bar.High) {
				bar.High = price
			}
			if price.LessThan(bar.Low) {
				bar.Low = price
			}
		}
	}
}

// GetBar returns the current bar for a symbol and period
func (a *Aggregator) GetBar(symbol, period string) (*OHLCV, bool) {
	a.mu.RLock()
	defer a.mu.RUnlock()

	if a.bars[symbol] == nil {
		return nil, false
	}

	bar, exists := a.bars[symbol][period]
	return bar, exists
}

// GetHistory returns historical bars
func (a *Aggregator) GetHistory(symbol, period string, limit int) []*OHLCV {
	// In a real implementation, this would query historical data
	return []*OHLCV{}
}

// WebSocketHandler handles WebSocket connections for market data
type WebSocketHandler struct {
	feed     *Feed
	upgrader websocket.Upgrader
}

// NewWebSocketHandler creates a new WebSocket handler
func NewWebSocketHandler(feed *Feed) *WebSocketHandler {
	return &WebSocketHandler{
		feed: feed,
		upgrader: websocket.Upgrader{
			ReadBufferSize:  1024,
			WriteBufferSize: 1024,
		},
	}
}

// ServeWS handles a WebSocket connection
func (h *WebSocketHandler) ServeWS(ctx context.Context, conn *websocket.Conn, symbols []string) {
	sub, err := h.feed.Subscribe(symbols)
	if err != nil {
		conn.WriteMessage(websocket.CloseMessage, []byte("failed to subscribe"))
		conn.Close()
		return
	}
	sub.Conn = conn

	defer func() {
		h.feed.Unsubscribe(sub.ID)
		conn.Close()
	}()

	// Read messages (for ping/pong and unsubscribe)
	go func() {
		for {
			_, _, err := conn.ReadMessage()
			if err != nil {
				close(sub.Done)
				return
			}
		}
	}()

	// Write updates
	for {
		select {
		case update := <-sub.Updates:
			data, err := json.Marshal(update)
			if err != nil {
				continue
			}
			
			if err := conn.WriteMessage(websocket.TextMessage, data); err != nil {
				return
			}
		case <-sub.Done:
			return
		case <-ctx.Done():
			return
		}
	}
}
