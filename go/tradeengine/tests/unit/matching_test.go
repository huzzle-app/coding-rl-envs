package unit

import (
	"context"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/shopspring/decimal"
	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/tradeengine/internal/matching"
	"github.com/terminal-bench/tradeengine/pkg/orderbook"
)

func TestMatchingEngineCreation(t *testing.T) {
	t.Run("should create matching engine", func(t *testing.T) {
		engine := matching.NewEngine(nil)
		assert.NotNil(t, engine)
	})
}

func TestMatchingEngineSubmitOrder(t *testing.T) {
	t.Run("should submit order successfully", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		order := &matching.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			CreatedAt: time.Now(),
		}

		err := engine.SubmitOrder(context.Background(), order)
		assert.NoError(t, err, "SubmitOrder should succeed even with nil msgClient (publish is optional)")
	})
}

func TestMatchingEngineCancelOrder(t *testing.T) {
	t.Run("should cancel existing order", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		// Submit first
		orderID := uuid.New()
		order := &matching.Order{
			ID:        orderID,
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Type:      orderbook.OrderTypeLimit,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			CreatedAt: time.Now(),
		}

		engine.SubmitOrder(context.Background(), order)

		// Cancel should succeed for existing order
		err := engine.CancelOrder(context.Background(), orderID)
		assert.NoError(t, err, "CancelOrder should succeed for an order that exists in the book")
	})

	t.Run("should fail to cancel non-existent order", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		err := engine.CancelOrder(context.Background(), uuid.New())
		assert.Error(t, err)
	})
}

func TestMatchingEngineLockOrdering(t *testing.T) {
	t.Run("should not deadlock on concurrent submit and cancel", func(t *testing.T) {
		
		// SubmitOrder: booksMu -> ordersMu
		// CancelOrder: ordersMu -> booksMu
		engine := matching.NewEngine(nil)

		done := make(chan bool)
		timeout := time.After(5 * time.Second)

		// Concurrent submits
		go func() {
			for i := 0; i < 100; i++ {
				order := &matching.Order{
					ID:        uuid.New(),
					UserID:    uuid.New(),
					Symbol:    "BTC-USD",
					Side:      orderbook.SideBuy,
					Price:     decimal.NewFromFloat(100),
					Quantity:  decimal.NewFromFloat(10),
					CreatedAt: time.Now(),
				}
				engine.SubmitOrder(context.Background(), order)
			}
			done <- true
		}()

		// Concurrent cancels
		go func() {
			for i := 0; i < 100; i++ {
				engine.CancelOrder(context.Background(), uuid.New())
			}
			done <- true
		}()

		doneCount := 0
		for doneCount < 2 {
			select {
			case <-done:
				doneCount++
			case <-timeout:
				t.Fatal("Deadlock detected!")
			}
		}
	})
}

func TestMatchingEngineGoroutineLeak(t *testing.T) {
	t.Run("should stop cleanly", func(t *testing.T) {
		
		engine := matching.NewEngine(nil)

		ctx, cancel := context.WithCancel(context.Background())
		engine.Start(ctx)

		// Cancel context
		cancel()

		// Engine should stop but BUG A3 means goroutine continues
		time.Sleep(200 * time.Millisecond)
		engine.Stop()
	})
}

func TestMatchingEngineGetOrder(t *testing.T) {
	t.Run("should get existing order", func(t *testing.T) {
		engine := matching.NewEngine(nil)
		orderID := uuid.New()

		order := &matching.Order{
			ID:        orderID,
			UserID:    uuid.New(),
			Symbol:    "BTC-USD",
			Side:      orderbook.SideBuy,
			Price:     decimal.NewFromFloat(100),
			Quantity:  decimal.NewFromFloat(10),
			CreatedAt: time.Now(),
		}

		engine.SubmitOrder(context.Background(), order)

		found, exists := engine.GetOrder(orderID)
		assert.True(t, exists)
		assert.Equal(t, orderID, found.ID)
	})

	t.Run("should return false for non-existent order", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		_, exists := engine.GetOrder(uuid.New())
		assert.False(t, exists)
	})
}

func TestMatchingEngineGetOrderBook(t *testing.T) {
	t.Run("should create order book for new symbol", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		order := &matching.Order{
			ID:        uuid.New(),
			UserID:    uuid.New(),
			Symbol:    "ETH-USD",
			Side:      orderbook.SideBuy,
			Price:     decimal.NewFromFloat(2000),
			Quantity:  decimal.NewFromFloat(5),
			CreatedAt: time.Now(),
		}

		engine.SubmitOrder(context.Background(), order)

		book, exists := engine.GetOrderBook("ETH-USD")
		assert.True(t, exists)
		assert.NotNil(t, book)
	})
}

func TestMatchingEngineStats(t *testing.T) {
	t.Run("should return engine stats", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		// Add some orders
		for i := 0; i < 5; i++ {
			order := &matching.Order{
				ID:        uuid.New(),
				UserID:    uuid.New(),
				Symbol:    "BTC-USD",
				Side:      orderbook.SideBuy,
				Price:     decimal.NewFromFloat(float64(100 + i)),
				Quantity:  decimal.NewFromFloat(10),
				CreatedAt: time.Now(),
			}
			engine.SubmitOrder(context.Background(), order)
		}

		stats := engine.GetStats()
		assert.Equal(t, 1, stats["order_books"])
		assert.Equal(t, 5, stats["orders"])
	})
}

func TestMatchingEngineConcurrentAccess(t *testing.T) {
	t.Run("should handle concurrent operations safely", func(t *testing.T) {
		engine := matching.NewEngine(nil)

		var wg sync.WaitGroup

		// Concurrent submits
		for i := 0; i < 10; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for j := 0; j < 10; j++ {
					order := &matching.Order{
						ID:        uuid.New(),
						UserID:    uuid.New(),
						Symbol:    "BTC-USD",
						Side:      orderbook.SideBuy,
						Price:     decimal.NewFromFloat(100),
						Quantity:  decimal.NewFromFloat(1),
						CreatedAt: time.Now(),
					}
					engine.SubmitOrder(context.Background(), order)
				}
			}()
		}

		// Concurrent reads
		for i := 0; i < 10; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for j := 0; j < 10; j++ {
					engine.GetStats()
					engine.GetOrderBook("BTC-USD")
				}
			}()
		}

		wg.Wait()
	})
}
