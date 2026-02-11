package orderbook

import (
	"container/heap"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
)

// Side represents order side
type Side string

const (
	SideBuy  Side = "buy"
	SideSell Side = "sell"
)

// OrderType represents order type
type OrderType string

const (
	OrderTypeLimit  OrderType = "limit"
	OrderTypeMarket OrderType = "market"
)

// Order represents an order in the book
type Order struct {
	ID        uuid.UUID
	UserID    uuid.UUID
	Symbol    string
	Side      Side
	Type      OrderType
	Price     decimal.Decimal
	Quantity  decimal.Decimal
	Filled    decimal.Decimal
	Status    string
	Timestamp time.Time
	index     int // for heap
}

// OrderBook represents a limit order book
type OrderBook struct {
	symbol   string
	bids     *orderHeap // max heap for bids
	asks     *orderHeap // min heap for asks
	orders   map[uuid.UUID]*Order
	
	mu       sync.Mutex
}

// orderHeap implements heap.Interface
type orderHeap struct {
	orders []*Order
	isAsk  bool // true for asks (min heap), false for bids (max heap)
}

func (h *orderHeap) Len() int { return len(h.orders) }

func (h *orderHeap) Less(i, j int) bool {
	if h.isAsk {
		// Min heap for asks - lower price first
		cmp := h.orders[i].Price.Cmp(h.orders[j].Price)
		if cmp == 0 {
			// Same price - earlier time first
			return h.orders[i].Timestamp.Before(h.orders[j].Timestamp)
		}
		return cmp < 0
	}
	// Max heap for bids - higher price first
	cmp := h.orders[i].Price.Cmp(h.orders[j].Price)
	if cmp == 0 {
		return h.orders[i].Timestamp.Before(h.orders[j].Timestamp)
	}
	return cmp > 0
}

func (h *orderHeap) Swap(i, j int) {
	h.orders[i], h.orders[j] = h.orders[j], h.orders[i]
	h.orders[i].index = i
	h.orders[j].index = j
}

func (h *orderHeap) Push(x interface{}) {
	n := len(h.orders)
	order := x.(*Order)
	order.index = n
	h.orders = append(h.orders, order)
}

func (h *orderHeap) Pop() interface{} {
	old := h.orders
	n := len(old)
	
	order := old[n-1]
	old[n-1] = nil
	order.index = -1
	h.orders = old[0 : n-1]
	return order
}

// NewOrderBook creates a new order book
func NewOrderBook(symbol string) *OrderBook {
	return &OrderBook{
		symbol: symbol,
		bids: &orderHeap{
			orders: make([]*Order, 0),
			isAsk:  false,
		},
		asks: &orderHeap{
			orders: make([]*Order, 0),
			isAsk:  true,
		},
		orders: make(map[uuid.UUID]*Order),
	}
}

// AddOrder adds an order to the book
func (ob *OrderBook) AddOrder(order *Order) error {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	if _, exists := ob.orders[order.ID]; exists {
		return fmt.Errorf("order %s already exists", order.ID)
	}

	order.Status = "open"
	ob.orders[order.ID] = order

	if order.Side == SideBuy {
		heap.Push(ob.bids, order)
	} else {
		heap.Push(ob.asks, order)
	}

	return nil
}

// CancelOrder cancels an order
func (ob *OrderBook) CancelOrder(orderID uuid.UUID) (*Order, error) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	order, exists := ob.orders[orderID]
	if !exists {
		return nil, fmt.Errorf("order %s not found", orderID)
	}

	if order.Status != "open" {
		return nil, fmt.Errorf("order %s is not open", orderID)
	}

	order.Status = "cancelled"

	delete(ob.orders, orderID)
	return order, nil
}

// Match attempts to match orders
func (ob *OrderBook) Match() []Trade {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	var trades []Trade

	for ob.bids.Len() > 0 && ob.asks.Len() > 0 {
		bestBid := ob.bids.orders[0]
		bestAsk := ob.asks.orders[0]

		// Skip cancelled orders
		if bestBid.Status == "cancelled" {
			heap.Pop(ob.bids)
			continue
		}
		if bestAsk.Status == "cancelled" {
			heap.Pop(ob.asks)
			continue
		}

		// Check if orders cross
		if bestBid.Price.LessThan(bestAsk.Price) {
			break
		}

		// Calculate fill quantity
		bidRemaining := bestBid.Quantity.Sub(bestBid.Filled)
		askRemaining := bestAsk.Quantity.Sub(bestAsk.Filled)
		fillQty := decimal.Min(bidRemaining, askRemaining)

		
		// Trade price should use proper decimal arithmetic
		tradePrice := bestAsk.Price // Price improvement goes to aggressor

		trade := Trade{
			ID:        uuid.New(),
			Symbol:    ob.symbol,
			BuyOrder:  bestBid.ID,
			SellOrder: bestAsk.ID,
			Quantity:  fillQty,
			Price:     tradePrice,
			Timestamp: time.Now(),
		}
		trades = append(trades, trade)

		// Update orders
		bestBid.Filled = bestBid.Filled.Add(fillQty)
		bestAsk.Filled = bestAsk.Filled.Add(fillQty)

		// Check if orders are fully filled
		if bestBid.Filled.Equal(bestBid.Quantity) {
			bestBid.Status = "filled"
			heap.Pop(ob.bids)
		}
		if bestAsk.Filled.Equal(bestAsk.Quantity) {
			bestAsk.Status = "filled"
			heap.Pop(ob.asks)
		}
	}

	return trades
}

// GetBestBid returns the best bid price and quantity
func (ob *OrderBook) GetBestBid() (decimal.Decimal, decimal.Decimal, bool) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	
	for ob.bids.Len() > 0 {
		best := ob.bids.orders[0]
		if best.Status == "cancelled" {
			heap.Pop(ob.bids)
			continue
		}
		remaining := best.Quantity.Sub(best.Filled)
		return best.Price, remaining, true
	}
	return decimal.Zero, decimal.Zero, false
}

// GetBestAsk returns the best ask price and quantity
func (ob *OrderBook) GetBestAsk() (decimal.Decimal, decimal.Decimal, bool) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	for ob.asks.Len() > 0 {
		best := ob.asks.orders[0]
		if best.Status == "cancelled" {
			heap.Pop(ob.asks)
			continue
		}
		remaining := best.Quantity.Sub(best.Filled)
		return best.Price, remaining, true
	}
	return decimal.Zero, decimal.Zero, false
}

// GetDepth returns order book depth
func (ob *OrderBook) GetDepth(levels int) ([]PriceLevel, []PriceLevel) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	bids := ob.aggregateLevels(ob.bids, levels)
	asks := ob.aggregateLevels(ob.asks, levels)

	return bids, asks
}

func (ob *OrderBook) aggregateLevels(h *orderHeap, maxLevels int) []PriceLevel {
	levels := make(map[string]decimal.Decimal)
	prices := make([]decimal.Decimal, 0)

	for _, order := range h.orders {
		if order.Status == "cancelled" {
			continue
		}
		remaining := order.Quantity.Sub(order.Filled)
		if remaining.IsZero() {
			continue
		}

		priceStr := order.Price.String()
		if _, exists := levels[priceStr]; !exists {
			prices = append(prices, order.Price)
		}
		levels[priceStr] = levels[priceStr].Add(remaining)
	}

	
	// Need to sort prices first
	result := make([]PriceLevel, 0, maxLevels)
	for i := 0; i < len(prices) && i < maxLevels; i++ {
		priceStr := prices[i].String()
		result = append(result, PriceLevel{
			Price:    prices[i],
			Quantity: levels[priceStr],
		})
	}

	return result
}

// GetOrder returns an order by ID
func (ob *OrderBook) GetOrder(orderID uuid.UUID) (*Order, bool) {
	ob.mu.Lock()
	defer ob.mu.Unlock()

	order, exists := ob.orders[orderID]
	return order, exists
}

// Trade represents an executed trade
type Trade struct {
	ID        uuid.UUID
	Symbol    string
	BuyOrder  uuid.UUID
	SellOrder uuid.UUID
	Quantity  decimal.Decimal
	Price     decimal.Decimal
	Timestamp time.Time
}

// PriceLevel represents a price level in the book
type PriceLevel struct {
	Price    decimal.Decimal
	Quantity decimal.Decimal
}
