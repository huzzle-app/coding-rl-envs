package integration

import (
	"context"
	"encoding/json"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Integration tests for the order flow across services

func TestOrderSubmissionFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Run("should submit order through full pipeline", func(t *testing.T) {
		ctx := context.Background()

		// 1. Submit order via Gateway
		order := map[string]interface{}{
			"user_id":  "test-user-1",
			"symbol":   "BTC-USD",
			"side":     "buy",
			"type":     "limit",
			"price":    50000.0,
			"quantity": 1.0,
		}

		orderJSON, _ := json.Marshal(order)
		assert.NotEmpty(t, orderJSON)

		// 2. Risk check should be performed
		
		riskResult := performRiskCheck(ctx, order)
		assert.True(t, riskResult.Allowed)

		// 3. Order should be added to matching engine
		// 4. Position should be updated
		// 5. P&L should be calculated
	})

	t.Run("should handle order rejection", func(t *testing.T) {
		ctx := context.Background()

		// Order exceeding limits
		order := map[string]interface{}{
			"user_id":  "test-user-1",
			"symbol":   "BTC-USD",
			"side":     "buy",
			"type":     "limit",
			"price":    50000.0,
			"quantity": 10000.0, // Exceeds limits
		}

		riskResult := performRiskCheck(ctx, order)
		assert.False(t, riskResult.Allowed)
	})

	t.Run("should match crossing orders", func(t *testing.T) {
		// Submit sell order
		sellOrder := map[string]interface{}{
			"user_id":  "seller-1",
			"symbol":   "BTC-USD",
			"side":     "sell",
			"type":     "limit",
			"price":    50000.0,
			"quantity": 1.0,
		}

		// Submit buy order that crosses
		buyOrder := map[string]interface{}{
			"user_id":  "buyer-1",
			"symbol":   "BTC-USD",
			"side":     "buy",
			"type":     "limit",
			"price":    50000.0,
			"quantity": 1.0,
		}

		err := submitOrder(sellOrder)
		assert.NoError(t, err, "Sell order submission should succeed")

		err = submitOrder(buyOrder)
		assert.NoError(t, err, "Buy order submission should succeed")

		// Both orders at same price should result in a match
	})
}

func TestOrderCancellationFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Run("should cancel pending order", func(t *testing.T) {
		// Submit order
		orderID := "order-123"
		userID := "test-user-1"

		// Cancel order
		err := cancelOrder(orderID, userID)
		assert.NoError(t, err)
	})

	t.Run("should fail to cancel filled order", func(t *testing.T) {
		orderID := "filled-order-123"
		userID := "test-user-1"

		err := cancelOrder(orderID, userID)
		assert.Error(t, err)
	})

	t.Run("should update matching engine on cancel", func(t *testing.T) {
		
		// Concurrent cancel and submit could deadlock

		done := make(chan bool)
		timeout := time.After(5 * time.Second)

		go func() {
			for i := 0; i < 10; i++ {
				cancelOrder("order-"+string(rune(i)), "user-1")
			}
			done <- true
		}()

		go func() {
			for i := 0; i < 10; i++ {
				submitOrder(map[string]interface{}{
					"user_id": "user-1",
					"symbol":  "BTC-USD",
				})
			}
			done <- true
		}()

		doneCount := 0
		for doneCount < 2 {
			select {
			case <-done:
				doneCount++
			case <-timeout:
				t.Fatal("Potential deadlock detected")
			}
		}
	})
}

func TestTradeExecutionFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Run("should update positions after trade", func(t *testing.T) {
		// Execute trade
		trade := map[string]interface{}{
			"buyer_id":  "buyer-1",
			"seller_id": "seller-1",
			"symbol":    "BTC-USD",
			"quantity":  1.0,
			"price":     50000.0,
		}

		tradeJSON, _ := json.Marshal(trade)

		
		// Position update may happen before trade is confirmed
		processTrade(tradeJSON)

		// Verify positions
		buyerPos := getPosition("buyer-1", "BTC-USD")
		assert.Equal(t, 1.0, buyerPos.Quantity)
	})

	t.Run("should update ledger after trade", func(t *testing.T) {
		trade := map[string]interface{}{
			"buyer_id":  "buyer-1",
			"seller_id": "seller-1",
			"symbol":    "BTC-USD",
			"quantity":  1.0,
			"price":     50000.0,
		}

		
		// Double-entry may not be atomic
		tradeJSON, _ := json.Marshal(trade)
		processTrade(tradeJSON)

		// Verify ledger entries - double-entry bookkeeping
		buyerBalance := getLedgerBalance("buyer-1")
		sellerBalance := getLedgerBalance("seller-1")

		assert.Greater(t, buyerBalance, 0.0,
			"Buyer's balance should be tracked after trade")
		assert.Greater(t, sellerBalance, 0.0,
			"Seller's balance should be tracked after trade")
	})
}

func TestConcurrentOrderFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Run("should handle concurrent order submissions", func(t *testing.T) {
		var wg sync.WaitGroup
		errors := make([]error, 0)
		var mu sync.Mutex

		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()

				order := map[string]interface{}{
					"user_id":  "user-1",
					"symbol":   "BTC-USD",
					"side":     "buy",
					"price":    50000.0 + float64(idx),
					"quantity": 0.1,
				}

				err := submitOrder(order)
				if err != nil {
					mu.Lock()
					errors = append(errors, err)
					mu.Unlock()
				}
			}(i)
		}

		wg.Wait()
		assert.Empty(t, errors)
	})

	t.Run("should handle concurrent matching", func(t *testing.T) {
		// Submit many orders that will match
		var wg sync.WaitGroup
		matchCount := int32(0)

		// Buyers
		for i := 0; i < 25; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				err := submitOrder(map[string]interface{}{
					"user_id":  fmt.Sprintf("buyer-%d", idx),
					"symbol":   "BTC-USD",
					"side":     "buy",
					"price":    50000.0,
					"quantity": 0.1,
				})
				if err == nil {
					atomic.AddInt32(&matchCount, 1)
				}
			}(i)
		}

		// Sellers
		for i := 0; i < 25; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				err := submitOrder(map[string]interface{}{
					"user_id":  fmt.Sprintf("seller-%d", idx),
					"symbol":   "BTC-USD",
					"side":     "sell",
					"price":    50000.0,
					"quantity": 0.1,
				})
				if err == nil {
					atomic.AddInt32(&matchCount, 1)
				}
			}(i)
		}

		wg.Wait()

		// 25 buys + 25 sells at same price should produce 25 matches
		trades := getTradeCount("BTC-USD")
		assert.Equal(t, 25, trades,
			"25 crossing buy/sell pairs should produce 25 trades")
	})
}

func TestEventSourcingFlow(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping integration test in short mode")
	}

	t.Run("should replay events to rebuild state", func(t *testing.T) {
		// Record events
		events := []map[string]interface{}{
			{"type": "order_submitted", "order_id": "1", "symbol": "BTC-USD", "quantity": 1.0},
			{"type": "order_matched", "order_id": "1", "quantity": 0.5},
			{"type": "order_matched", "order_id": "1", "quantity": 0.5},
			{"type": "order_filled", "order_id": "1"},
		}

		// Replay events
		state := replayEvents(events)

		assert.Equal(t, "filled", state.Status)
		assert.Equal(t, 1.0, state.FilledQuantity)
	})

	t.Run("should handle out-of-order events", func(t *testing.T) {
		
		events := []map[string]interface{}{
			{"seq": 3, "type": "order_filled", "order_id": "1"},
			{"seq": 1, "type": "order_submitted", "order_id": "1"},
			{"seq": 2, "type": "order_matched", "order_id": "1"},
		}

		// When C1 is fixed, replayEvents should reorder by sequence before processing
		state := replayEvents(events)
		assert.Equal(t, "filled", state.Status,
			"Even with out-of-order events, final state should be 'filled' after reordering")
	})

	t.Run("should snapshot for fast recovery", func(t *testing.T) {
		// Create snapshot
		snapshot := createSnapshot("user-1")
		require.NotNil(t, snapshot)

		// Verify snapshot contains current state
		assert.NotEmpty(t, snapshot.Timestamp)
	})
}

// Helper functions

type RiskResult struct {
	Allowed bool
	Reason  string
}

func performRiskCheck(ctx context.Context, order map[string]interface{}) RiskResult {
	// Simulated risk check
	qty := order["quantity"].(float64)
	if qty > 1000 {
		return RiskResult{Allowed: false, Reason: "exceeds position limit"}
	}
	return RiskResult{Allowed: true}
}

var cancelledOrders sync.Map

func cancelOrder(orderID, userID string) error {
	// Bug D3: no atomic check-and-update — filled orders can be "cancelled"
	if orderID == "filled-order-123" {
		return fmt.Errorf("cannot cancel filled order")
	}
	cancelledOrders.Store(orderID, true)
	return nil
}

func submitOrder(order map[string]interface{}) error {
	// Simulated submit
	return nil
}

func processTrade(tradeJSON []byte) {
	// Simulated trade processing
}

type Position struct {
	Quantity float64
}

func getPosition(userID, symbol string) Position {
	return Position{Quantity: 1.0}
}

func getLedgerBalance(userID string) float64 {
	return 100000.0
}

type State struct {
	Status         string
	FilledQuantity float64
}

func replayEvents(events []map[string]interface{}) State {
	state := State{}
	for _, e := range events {
		switch e["type"] {
		case "order_submitted":
			state.Status = "open"
		case "order_matched":
			state.FilledQuantity += 0.5
		case "order_filled":
			state.Status = "filled"
		}
	}
	return state
}

type Snapshot struct {
	Timestamp time.Time
}

func createSnapshot(userID string) *Snapshot {
	return &Snapshot{Timestamp: time.Now()}
}

// getTradeCount returns the number of trades for a symbol.
// Bug: no actual matching happens in stubs, always returns 0.
func getTradeCount(symbol string) int {
	return 0
}
