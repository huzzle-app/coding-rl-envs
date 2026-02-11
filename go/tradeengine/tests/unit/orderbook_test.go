package unit

import (
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/terminal-bench/tradeengine/pkg/orderbook"
)

func TestOrderBookCreation(t *testing.T) {
	t.Run("should create order book", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")
		assert.NotNil(t, book)
	})
}

func TestOrderBookAddOrder(t *testing.T) {
	t.Run("should add buy order", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		order := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}

		err := book.AddOrder(order)
		assert.NoError(t, err)

		// Verify best bid
		price, qty, exists := book.GetBestBid()
		assert.True(t, exists)
		assert.True(t, price.Equal(decimal.NewFromFloat(100)))
		assert.True(t, qty.Equal(decimal.NewFromFloat(10)))
	})

	t.Run("should add sell order", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		order := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideSell,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(110),
			Quantity:  decimal.NewFromFloat(5),
			Timestamp: time.Now(),
		}

		err := book.AddOrder(order)
		assert.NoError(t, err)

		// Verify best ask
		price, qty, exists := book.GetBestAsk()
		assert.True(t, exists)
		assert.True(t, price.Equal(decimal.NewFromFloat(110)))
		assert.True(t, qty.Equal(decimal.NewFromFloat(5)))
	})

	t.Run("should reject duplicate order", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")
		orderID := uuid.New()

		order := &orderbook.Order{
			ID:        orderID,
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}

		err := book.AddOrder(order)
		assert.NoError(t, err)

		// Try to add same order again
		err = book.AddOrder(order)
		assert.Error(t, err)
	})
}

func TestOrderBookMatching(t *testing.T) {
	t.Run("should match crossing orders", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		// Add sell order at 100
		sellOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideSell,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(sellOrder)

		// Add buy order at 100 (crosses)
		buyOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(5),
			Timestamp: time.Now(),
		}
		book.AddOrder(buyOrder)

		// Match
		trades := book.Match()
		require.Len(t, trades, 1)

		assert.True(t, trades[0].Quantity.Equal(decimal.NewFromFloat(5)))
		assert.True(t, trades[0].Price.Equal(decimal.NewFromFloat(100)))
	})

	t.Run("should not match non-crossing orders", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		// Add sell at 110
		sellOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideSell,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(110),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(sellOrder)

		// Add buy at 100 (doesn't cross)
		buyOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(buyOrder)

		// Match
		trades := book.Match()
		assert.Len(t, trades, 0)
	})

	t.Run("should handle partial fills", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		// Add sell for 10
		sellOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideSell,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(sellOrder)

		// Add buy for 3
		buyOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(3),
			Timestamp: time.Now(),
		}
		book.AddOrder(buyOrder)

		trades := book.Match()
		require.Len(t, trades, 1)
		assert.True(t, trades[0].Quantity.Equal(decimal.NewFromFloat(3)))

		// Sell order should still be in book with 7 remaining
		_, qty, exists := book.GetBestAsk()
		assert.True(t, exists)
		assert.True(t, qty.Equal(decimal.NewFromFloat(7)))
	})
}

func TestOrderBookCancelOrder(t *testing.T) {
	t.Run("should cancel order", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")
		orderID := uuid.New()

		order := &orderbook.Order{
			ID:        orderID,
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(order)

		cancelled, err := book.CancelOrder(orderID)
		assert.NoError(t, err)
		assert.Equal(t, "cancelled", cancelled.Status)
	})

	t.Run("should fail to cancel non-existent order", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		_, err := book.CancelOrder(uuid.New())
		assert.Error(t, err)
	})

	t.Run("should not match cancelled order", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")
		sellID := uuid.New()

		// Add and cancel sell
		sellOrder := &orderbook.Order{
			ID:        sellID,
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideSell,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(sellOrder)
		book.CancelOrder(sellID)

		// Add crossing buy
		buyOrder := &orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		}
		book.AddOrder(buyOrder)

		// Should not match cancelled order
		
		trades := book.Match()
		assert.Len(t, trades, 0)
	})
}

func TestOrderBookPriceTimePriority(t *testing.T) {
	t.Run("should prioritize by price for bids", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		// Add lower bid first
		book.AddOrder(&orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Side:      orderbook.SideBuy,
			Price:     decimal.NewFromFloat(99),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		})

		// Add higher bid
		book.AddOrder(&orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Side:      orderbook.SideBuy,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		})

		// Best bid should be 100
		price, _, _ := book.GetBestBid()
		assert.True(t, price.Equal(decimal.NewFromFloat(100)))
	})

	t.Run("should prioritize by time for same price", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		firstOrderID := uuid.New()
		book.AddOrder(&orderbook.Order{
			ID:        firstOrderID,
			UserID:    uuid.New(),
			Side:      orderbook.SideBuy,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now().Add(-time.Hour),
		})

		book.AddOrder(&orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Side:      orderbook.SideBuy,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			Timestamp: time.Now(),
		})

		// Add matching sell
		book.AddOrder(&orderbook.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Side:      orderbook.SideSell,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(5),
			Timestamp: time.Now(),
		})

		trades := book.Match()
		require.Len(t, trades, 1)
		// First order should be filled first
		assert.Equal(t, firstOrderID, trades[0].BuyOrder)
	})
}

func TestOrderBookDepth(t *testing.T) {
	t.Run("should return order book depth", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		// Add multiple buy orders
		for i := 0; i < 5; i++ {
			book.AddOrder(&orderbook.Order{
				ID:        uuid.New(),
				UserID:    uuid.New(),
				Side:      orderbook.SideBuy,
				Price:     decimal.NewFromFloat(float64(100 - i)),
				Quantity:  decimal.NewFromFloat(10),
				Timestamp: time.Now(),
			})
		}

		// Add multiple sell orders
		for i := 0; i < 5; i++ {
			book.AddOrder(&orderbook.Order{
				ID:        uuid.New(),
				UserID:    uuid.New(),
				Side:      orderbook.SideSell,
				Price:     decimal.NewFromFloat(float64(105 + i)),
				Quantity:  decimal.NewFromFloat(10),
				Timestamp: time.Now(),
			})
		}

		bids, asks := book.GetDepth(3)

		
		// Depth levels may not be sorted correctly
		assert.LessOrEqual(t, len(bids), 3)
		assert.LessOrEqual(t, len(asks), 3)
	})
}

func TestOrderBookConcurrency(t *testing.T) {
	t.Run("should handle concurrent operations", func(t *testing.T) {
		book := orderbook.NewOrderBook("BTC-USD")

		
		// Run with -race flag to detect
		done := make(chan bool)

		// Concurrent adds
		go func() {
			for i := 0; i < 100; i++ {
				book.AddOrder(&orderbook.Order{
					ID:        uuid.New(),
					UserID:    uuid.New(),
					Side:      orderbook.SideBuy,
					Price:     decimal.NewFromFloat(float64(100 + i%10)),
					Quantity:  decimal.NewFromFloat(1),
					Timestamp: time.Now(),
				})
			}
			done <- true
		}()

		// Concurrent matching
		go func() {
			for i := 0; i < 100; i++ {
				book.Match()
			}
			done <- true
		}()

		<-done
		<-done
	})
}
