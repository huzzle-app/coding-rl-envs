package unit

import (
	"context"
	"encoding/json"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/tradeengine/internal/positions"
)

func TestTrackerCreation(t *testing.T) {
	t.Run("should create tracker with config", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{
			SnapshotInterval: time.Minute * 5,
			MaxEventsBuffer:  1000,
		})

		assert.NotNil(t, tracker)
	})
}

func TestPositionTracking(t *testing.T) {
	t.Run("should track new position", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)

		pos, exists := tracker.GetPosition("user1", "BTC-USD")
		assert.True(t, exists)
		assert.Equal(t, 1.0, pos.Quantity)
		assert.Equal(t, 50000.0, pos.AvgPrice)
	})

	t.Run("should update existing position", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		// First trade: Buy 1 BTC at $50000
		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)

		// Second trade: Buy 1 BTC at $52000
		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 52000.0)

		pos, exists := tracker.GetPosition("user1", "BTC-USD")
		assert.True(t, exists)
		assert.Equal(t, 2.0, pos.Quantity)
		// Average: (50000 + 52000) / 2 = 51000
		assert.InDelta(t, 51000.0, pos.AvgPrice, 0.01)
	})

	t.Run("should handle sell reducing position", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		// Buy 2 BTC
		tracker.UpdatePosition("user1", "BTC-USD", 2.0, 50000.0)

		// Sell 1 BTC
		tracker.UpdatePosition("user1", "BTC-USD", -1.0, 52000.0)

		pos, exists := tracker.GetPosition("user1", "BTC-USD")
		assert.True(t, exists)
		assert.Equal(t, 1.0, pos.Quantity)
	})

	t.Run("should close position when quantity reaches zero", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)
		tracker.UpdatePosition("user1", "BTC-USD", -1.0, 52000.0)

		pos, exists := tracker.GetPosition("user1", "BTC-USD")
		if exists {
			// If position still exists, quantity should be zero
			assert.Equal(t, 0.0, pos.Quantity,
				"Position that was fully closed should have quantity 0")
		}
		// If !exists, that is also correct (position was deleted)
	})
}

func TestPnLCalculation(t *testing.T) {
	t.Run("should calculate unrealized P&L", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		// Buy at $50000
		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)

		// Current price is $55000
		tracker.UpdateMarketPrice("BTC-USD", 55000.0)

		
		pnl := tracker.CalculatePnL("user1")

		// Unrealized P&L: (55000 - 50000) * 1 = 5000
		assert.InDelta(t, 5000.0, pnl.Unrealized, 0.01)
	})

	t.Run("should calculate realized P&L", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		// Buy at $50000
		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)

		// Sell at $55000
		tracker.RecordTrade("user1", "BTC-USD", -1.0, 55000.0)

		pnl := tracker.CalculatePnL("user1")
		// Realized P&L: (55000 - 50000) * 1 = 5000
		assert.InDelta(t, 5000.0, pnl.Realized, 0.01)
	})

	t.Run("should handle multiple symbols", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)
		tracker.UpdatePosition("user1", "ETH-USD", 10.0, 3000.0)

		tracker.UpdateMarketPrice("BTC-USD", 52000.0)
		tracker.UpdateMarketPrice("ETH-USD", 3200.0)

		pnl := tracker.CalculatePnL("user1")
		// BTC: (52000-50000)*1 = 2000
		// ETH: (3200-3000)*10 = 2000
		// Total: 4000
		assert.InDelta(t, 4000.0, pnl.Unrealized, 0.01)
	})
}

func TestEventOrdering(t *testing.T) {
	t.Run("should process events in order", func(t *testing.T) {
		
		tracker := positions.NewTracker(positions.TrackerConfig{
			MaxEventsBuffer: 100,
		})

		// Simulate ordered events
		events := []struct {
			seq    int
			qty    float64
			price  float64
		}{
			{1, 1.0, 50000.0},
			{2, 0.5, 51000.0},
			{3, -0.5, 52000.0},
		}

		for _, e := range events {
			tradeJSON, _ := json.Marshal(map[string]interface{}{
				"sequence": e.seq,
				"user_id":  "user1",
				"symbol":   "BTC-USD",
				"quantity": e.qty,
				"price":    e.price,
			})
			tracker.ProcessTrade(tradeJSON)
		}

		pos, _ := tracker.GetPosition("user1", "BTC-USD")
		assert.Equal(t, 1.0, pos.Quantity)
	})

	t.Run("should handle out-of-order events", func(t *testing.T) {
		
		tracker := positions.NewTracker(positions.TrackerConfig{})

		// Events arrive out of order
		outOfOrder := []struct {
			seq    int
			qty    float64
			price  float64
		}{
			{3, -0.5, 52000.0}, // Arrives first but should be processed third
			{1, 1.0, 50000.0},  // Should be first
			{2, 0.5, 51000.0},  // Should be second
		}

		for _, e := range outOfOrder {
			tradeJSON, _ := json.Marshal(map[string]interface{}{
				"sequence": e.seq,
				"user_id":  "user1",
				"symbol":   "BTC-USD",
				"quantity": e.qty,
				"price":    e.price,
			})
			
			tracker.ProcessTrade(tradeJSON)
		}
	})
}

func TestConcurrentPositionUpdates(t *testing.T) {
	t.Run("should handle concurrent updates safely", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		var wg sync.WaitGroup

		// Concurrent position updates
		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				tracker.UpdatePosition("user1", "BTC-USD", 0.01, 50000.0+float64(idx))
			}(i)
		}

		wg.Wait()

		// Position should have all updates
		pos, exists := tracker.GetPosition("user1", "BTC-USD")
		assert.True(t, exists)
		assert.InDelta(t, 1.0, pos.Quantity, 0.01) // 100 * 0.01 = 1.0
	})
}

func TestSnapshotting(t *testing.T) {
	t.Run("should create periodic snapshots", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{
			SnapshotInterval: 100 * time.Millisecond,
		})

		ctx, cancel := context.WithCancel(context.Background())
		tracker.Start(ctx)

		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)

		// Wait for snapshot
		time.Sleep(200 * time.Millisecond)

		// Verify snapshot was created
		snapshots := tracker.GetSnapshots("user1")
		assert.GreaterOrEqual(t, len(snapshots), 1)

		cancel()
	})

	t.Run("should restore from snapshot", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		// Create snapshot
		snapshot := positions.Snapshot{
			UserID:    "user1",
			Timestamp: time.Now(),
			Positions: map[string]*positions.Position{
				"BTC-USD": {
					Symbol:   "BTC-USD",
					Quantity: 2.0,
					AvgPrice: 48000.0,
				},
			},
		}

		tracker.RestoreFromSnapshot(&snapshot)

		pos, exists := tracker.GetPosition("user1", "BTC-USD")
		assert.True(t, exists)
		assert.Equal(t, 2.0, pos.Quantity)
	})
}

func TestGetAllPositions(t *testing.T) {
	t.Run("should return all positions for user", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		tracker.UpdatePosition("user1", "BTC-USD", 1.0, 50000.0)
		tracker.UpdatePosition("user1", "ETH-USD", 10.0, 3000.0)
		tracker.UpdatePosition("user1", "SOL-USD", 100.0, 150.0)

		positions := tracker.GetPositions("user1")
		assert.Len(t, positions, 3)
	})

	t.Run("should return empty for unknown user", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		positions := tracker.GetPositions("unknown")
		assert.Len(t, positions, 0)
	})
}

func TestMarketValueCalculation(t *testing.T) {
	t.Run("should calculate market value", func(t *testing.T) {
		tracker := positions.NewTracker(positions.TrackerConfig{})

		tracker.UpdatePosition("user1", "BTC-USD", 2.0, 50000.0)
		tracker.UpdateMarketPrice("BTC-USD", 55000.0)

		
		marketValue := tracker.GetMarketValue("user1", "BTC-USD")
		// 2 * 55000 = 110000
		assert.InDelta(t, 110000.0, marketValue, 0.01)
	})
}
