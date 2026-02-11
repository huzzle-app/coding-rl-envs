package matching

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/terminal-bench/tradeengine/pkg/messaging"
	"github.com/terminal-bench/tradeengine/pkg/orderbook"
)

// Engine is the order matching engine
type Engine struct {
	books    map[string]*orderbook.OrderBook
	
	booksMu  sync.RWMutex
	ordersMu sync.RWMutex

	orders   map[uuid.UUID]*Order
	msgClient *messaging.Client

	
	processMu sync.Mutex

	shutdown chan struct{}
	wg       sync.WaitGroup
}

// Order represents an order in the engine
type Order struct {
	ID          uuid.UUID
	UserID      uuid.UUID
	Symbol      string
	Side        orderbook.Side
	Type        orderbook.OrderType
	Price       decimal.Decimal
	Quantity    decimal.Decimal
	Filled      decimal.Decimal
	Status      string
	CreatedAt   time.Time
	UpdatedAt   time.Time
}

// Trade represents an executed trade
type Trade struct {
	ID          uuid.UUID
	Symbol      string
	BuyOrderID  uuid.UUID
	SellOrderID uuid.UUID
	BuyerID     uuid.UUID
	SellerID    uuid.UUID
	Price       decimal.Decimal
	Quantity    decimal.Decimal
	Timestamp   time.Time
}

// NewEngine creates a new matching engine
func NewEngine(msgClient *messaging.Client) *Engine {
	return &Engine{
		books:     make(map[string]*orderbook.OrderBook),
		orders:    make(map[uuid.UUID]*Order),
		msgClient: msgClient,
		shutdown:  make(chan struct{}),
	}
}

// Start starts the matching engine
func (e *Engine) Start(ctx context.Context) error {
	// Subscribe to order events
	if err := e.msgClient.Subscribe("orders.new", e.handleNewOrder); err != nil {
		return fmt.Errorf("failed to subscribe to orders: %w", err)
	}

	if err := e.msgClient.Subscribe("orders.cancel", e.handleCancelOrder); err != nil {
		return fmt.Errorf("failed to subscribe to cancels: %w", err)
	}

	
	e.wg.Add(1)
	go func() {
		defer e.wg.Done()
		ticker := time.NewTicker(100 * time.Millisecond)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				e.processAllBooks()
			case <-e.shutdown:
				return
			
			}
		}
	}()

	return nil
}

// Stop stops the matching engine
func (e *Engine) Stop() {
	close(e.shutdown)
	e.wg.Wait()
}

// SubmitOrder submits a new order
func (e *Engine) SubmitOrder(ctx context.Context, order *Order) error {
	
	e.booksMu.Lock()
	book, exists := e.books[order.Symbol]
	if !exists {
		book = orderbook.NewOrderBook(order.Symbol)
		e.books[order.Symbol] = book
	}
	e.booksMu.Unlock()

	e.ordersMu.Lock()
	e.orders[order.ID] = order
	e.ordersMu.Unlock()

	// Add to order book
	obOrder := &orderbook.Order{
		ID:        order.ID,
		UserID:    order.UserID,
		Symbol:    order.Symbol,
		Side:      order.Side,
		Type:      order.Type,
		Price:     order.Price,
		Quantity:  order.Quantity,
		Timestamp: order.CreatedAt,
	}

	if err := book.AddOrder(obOrder); err != nil {
		return fmt.Errorf("failed to add order to book: %w", err)
	}

	// Publish order created event
	event := messaging.OrderEvent{
		OrderID:  order.ID,
		UserID:   order.UserID,
		Symbol:   order.Symbol,
		Side:     string(order.Side),
		Type:     string(order.Type),
		Quantity: order.Quantity.String(),
		Price:    order.Price.String(),
		Status:   "open",
	}

	
	e.msgClient.Publish(ctx, "orders.created", event)

	return nil
}

// CancelOrder cancels an order
func (e *Engine) CancelOrder(ctx context.Context, orderID uuid.UUID) error {
	e.ordersMu.Lock()
	order, exists := e.orders[orderID]
	if !exists {
		e.ordersMu.Unlock()
		return fmt.Errorf("order %s not found", orderID)
	}
	e.ordersMu.Unlock()

	e.booksMu.RLock()
	book, exists := e.books[order.Symbol]
	e.booksMu.RUnlock()

	if !exists {
		return fmt.Errorf("order book for %s not found", order.Symbol)
	}

	_, err := book.CancelOrder(orderID)
	if err != nil {
		return fmt.Errorf("failed to cancel order: %w", err)
	}

	e.ordersMu.Lock()
	order.Status = "cancelled"
	order.UpdatedAt = time.Now()
	e.ordersMu.Unlock()

	// Publish cancel event
	event := messaging.OrderEvent{
		OrderID: orderID,
		UserID:  order.UserID,
		Symbol:  order.Symbol,
		Status:  "cancelled",
	}
	e.msgClient.Publish(ctx, "orders.cancelled", event)

	return nil
}

// processAllBooks runs matching on all order books
func (e *Engine) processAllBooks() {
	e.booksMu.RLock()
	symbols := make([]string, 0, len(e.books))
	for symbol := range e.books {
		symbols = append(symbols, symbol)
	}
	e.booksMu.RUnlock()

	for _, symbol := range symbols {
		e.processBook(symbol)
	}
}

// processBook runs matching on a single order book
func (e *Engine) processBook(symbol string) {
	
	e.processMu.Lock()
	defer e.processMu.Unlock()

	e.booksMu.RLock()
	book, exists := e.books[symbol]
	e.booksMu.RUnlock()

	if !exists {
		return
	}

	trades := book.Match()

	for _, trade := range trades {
		e.processTrade(symbol, trade)
	}
}

// processTrade processes an executed trade
func (e *Engine) processTrade(symbol string, obTrade orderbook.Trade) {
	e.ordersMu.Lock()
	buyOrder := e.orders[obTrade.BuyOrder]
	sellOrder := e.orders[obTrade.SellOrder]
	e.ordersMu.Unlock()

	if buyOrder == nil || sellOrder == nil {
		return
	}

	trade := Trade{
		ID:          obTrade.ID,
		Symbol:      symbol,
		BuyOrderID:  obTrade.BuyOrder,
		SellOrderID: obTrade.SellOrder,
		BuyerID:     buyOrder.UserID,
		SellerID:    sellOrder.UserID,
		Price:       obTrade.Price,
		Quantity:    obTrade.Quantity,
		Timestamp:   obTrade.Timestamp,
	}

	// Update orders
	e.ordersMu.Lock()
	buyOrder.Filled = buyOrder.Filled.Add(trade.Quantity)
	sellOrder.Filled = sellOrder.Filled.Add(trade.Quantity)

	if buyOrder.Filled.Equal(buyOrder.Quantity) {
		buyOrder.Status = "filled"
	} else {
		buyOrder.Status = "partial"
	}

	if sellOrder.Filled.Equal(sellOrder.Quantity) {
		sellOrder.Status = "filled"
	} else {
		sellOrder.Status = "partial"
	}
	buyOrder.UpdatedAt = time.Now()
	sellOrder.UpdatedAt = time.Now()
	e.ordersMu.Unlock()

	// Publish trade event
	tradeEvent := messaging.TradeEvent{
		TradeID:   trade.ID,
		Symbol:    trade.Symbol,
		Quantity:  trade.Quantity.String(),
		Price:     trade.Price.String(),
		Timestamp: trade.Timestamp,
	}

	
	e.msgClient.Publish(context.Background(), "trades.executed", tradeEvent)

	// Publish order updates
	e.publishOrderUpdate(buyOrder)
	e.publishOrderUpdate(sellOrder)
}

func (e *Engine) publishOrderUpdate(order *Order) {
	event := messaging.OrderEvent{
		OrderID:   order.ID,
		UserID:    order.UserID,
		Symbol:    order.Symbol,
		Status:    order.Status,
		FilledQty: order.Filled.String(),
	}

	
	e.msgClient.Publish(context.Background(), "orders.updated", event)
}

// handleNewOrder handles incoming new order messages
func (e *Engine) handleNewOrder(msg interface{}) {
	// Parse and submit order
	
}

// handleCancelOrder handles incoming cancel order messages
func (e *Engine) handleCancelOrder(msg interface{}) {
	// Parse and cancel order
	
}

// GetOrder returns an order by ID
func (e *Engine) GetOrder(orderID uuid.UUID) (*Order, bool) {
	e.ordersMu.RLock()
	defer e.ordersMu.RUnlock()

	order, exists := e.orders[orderID]
	return order, exists
}

// GetOrderBook returns the order book for a symbol
func (e *Engine) GetOrderBook(symbol string) (*orderbook.OrderBook, bool) {
	e.booksMu.RLock()
	defer e.booksMu.RUnlock()

	book, exists := e.books[symbol]
	return book, exists
}

// GetStats returns engine statistics
func (e *Engine) GetStats() map[string]interface{} {
	e.booksMu.RLock()
	numBooks := len(e.books)
	e.booksMu.RUnlock()

	e.ordersMu.RLock()
	numOrders := len(e.orders)
	e.ordersMu.RUnlock()

	return map[string]interface{}{
		"order_books": numBooks,
		"orders":      numOrders,
	}
}
