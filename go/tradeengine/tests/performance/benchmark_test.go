package performance

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/shopspring/decimal"
	"github.com/stretchr/testify/assert"
)

// Test* functions for performance-critical paths

func TestOrderSubmissionLatency(t *testing.T) {
	t.Run("should submit orders within latency budget", func(t *testing.T) {
		engine := newMockMatchingEngine()

		start := time.Now()
		for i := 0; i < 1000; i++ {
			engine.SubmitOrder(context.Background(), &Order{
				UserID:   "user1",
				Symbol:   "BTC-USD",
				Side:     "buy",
				Price:    decimal.NewFromFloat(50000.0),
				Quantity: decimal.NewFromFloat(1.0),
			})
		}
		elapsed := time.Since(start)

		// 1000 orders should complete within 1 second
		assert.Less(t, elapsed, time.Second,
			"1000 order submissions should complete within 1s")
	})
}

func TestConcurrentOrderThroughput(t *testing.T) {
	t.Run("should handle concurrent submissions without data loss", func(t *testing.T) {
		engine := newMockMatchingEngine()

		var wg sync.WaitGroup
		submitted := int32(0)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				err := engine.SubmitOrder(context.Background(), &Order{
					UserID:   "user1",
					Symbol:   "BTC-USD",
					Side:     "buy",
					Price:    decimal.NewFromFloat(50000.0 + float64(idx)),
					Quantity: decimal.NewFromFloat(0.1),
				})
				if err == nil {
					atomic.AddInt32(&submitted, 1)
				}
			}(i)
		}
		wg.Wait()

		assert.Equal(t, int32(100), submitted,
			"All concurrent submissions should succeed")

		engine.mu.RLock()
		count := len(engine.orders["BTC-USD"])
		engine.mu.RUnlock()

		assert.Equal(t, 100, count,
			"All 100 orders should be in the book")
	})
}

func TestPositionTrackerConcurrency(t *testing.T) {
	t.Run("should handle concurrent position updates", func(t *testing.T) {
		tracker := newMockPositionTracker()

		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				tracker.UpdatePosition("user1", "BTC-USD", 0.01, 50000.0+float64(idx))
			}(i)
		}
		wg.Wait()

		tracker.mu.RLock()
		qty := tracker.positions["user1"]["BTC-USD"]
		tracker.mu.RUnlock()

		assert.InDelta(t, 1.0, qty, 0.001,
			"100 updates of 0.01 should sum to 1.0")
	})
}

func TestCircuitBreakerPerformance(t *testing.T) {
	t.Run("should not degrade under concurrent execution", func(t *testing.T) {
		breaker := newMockCircuitBreaker()

		var wg sync.WaitGroup
		errors := int32(0)

		start := time.Now()
		for i := 0; i < 1000; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				err := breaker.Execute(func() error { return nil })
				if err != nil {
					atomic.AddInt32(&errors, 1)
				}
			}()
		}
		wg.Wait()
		elapsed := time.Since(start)

		assert.Equal(t, int32(0), errors,
			"No errors expected when circuit is closed")
		assert.Less(t, elapsed, 2*time.Second,
			"1000 concurrent executions should complete quickly")
	})
}

func TestCachePerformance(t *testing.T) {
	t.Run("should handle concurrent reads and writes", func(t *testing.T) {
		cache := newMockCache()

		var wg sync.WaitGroup
		// Writers
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				for j := 0; j < 100; j++ {
					cache.Set("key", "value")
				}
			}(i)
		}
		// Readers
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				for j := 0; j < 100; j++ {
					cache.Get("key")
				}
			}()
		}
		wg.Wait()
	})
}

func TestAlertCheckPerformance(t *testing.T) {
	t.Run("should check 1000 alerts efficiently", func(t *testing.T) {
		engine := newMockAlertEngine()
		for i := 0; i < 1000; i++ {
			engine.CreateAlert("user1", "BTC-USD", "above", 50000.0+float64(i))
		}

		start := time.Now()
		triggered := engine.CheckPrice("BTC-USD", 55000.0)
		elapsed := time.Since(start)

		// All alerts below 55000 should trigger
		assert.Greater(t, len(triggered), 0,
			"Some alerts should trigger when price exceeds thresholds")
		assert.Less(t, elapsed, 100*time.Millisecond,
			"Checking 1000 alerts should complete within 100ms")
	})
}

func TestDecimalPrecision(t *testing.T) {
	t.Run("should maintain precision through operations", func(t *testing.T) {
		// Classic float precision test: 0.1 + 0.2 != 0.3 in float64
		a := decimal.NewFromFloat(0.1)
		b := decimal.NewFromFloat(0.2)
		expected := decimal.NewFromFloat(0.3)

		sum := a.Add(b)
		assert.True(t, sum.Equal(expected),
			"Decimal 0.1 + 0.2 should equal 0.3 exactly")
	})

	t.Run("should handle large multiplication without overflow", func(t *testing.T) {
		price := decimal.NewFromFloat(99999.99)
		qty := decimal.NewFromFloat(99999.99)

		result := price.Mul(qty)
		assert.True(t, result.IsPositive(),
			"Large decimal multiplication should not overflow")
	})
}

func TestOrderBookDepthPerformance(t *testing.T) {
	t.Run("should retrieve depth from large book quickly", func(t *testing.T) {
		book := newMockOrderBook("BTC-USD")
		for i := 0; i < 10000; i++ {
			book.AddOrder(&BookOrder{
				Price:    decimal.NewFromFloat(50000.0 - float64(i)),
				Quantity: decimal.NewFromFloat(1.0),
				Side:     "buy",
			})
		}

		start := time.Now()
		bids, _ := book.GetDepth(100)
		elapsed := time.Since(start)

		_ = bids
		assert.Less(t, elapsed, 50*time.Millisecond,
			"Depth retrieval from 10k-order book should be fast")
	})
}

// Benchmark tests for performance-critical paths

func BenchmarkOrderSubmission(b *testing.B) {
	// Setup
	engine := newMockMatchingEngine()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.SubmitOrder(context.Background(), &Order{
			UserID:   "user1",
			Symbol:   "BTC-USD",
			Side:     "buy",
			Price:    decimal.NewFromFloat(50000.0),
			Quantity: decimal.NewFromFloat(1.0),
		})
	}
}

func BenchmarkOrderMatching(b *testing.B) {
	engine := newMockMatchingEngine()

	// Pre-populate order book
	for i := 0; i < 1000; i++ {
		engine.SubmitOrder(context.Background(), &Order{
			UserID:   "seller1",
			Symbol:   "BTC-USD",
			Side:     "sell",
			Price:    decimal.NewFromFloat(50000.0 + float64(i)),
			Quantity: decimal.NewFromFloat(1.0),
		})
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.SubmitOrder(context.Background(), &Order{
			UserID:   "buyer1",
			Symbol:   "BTC-USD",
			Side:     "buy",
			Price:    decimal.NewFromFloat(50000.0),
			Quantity: decimal.NewFromFloat(0.1),
		})
		engine.Match("BTC-USD")
	}
}

func BenchmarkRiskCalculation(b *testing.B) {
	calc := newMockRiskCalculator()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		calc.CheckOrder("user1", "BTC-USD", "buy", 1.0, 50000.0)
	}
}

func BenchmarkPositionUpdate(b *testing.B) {
	tracker := newMockPositionTracker()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		tracker.UpdatePosition("user1", "BTC-USD", 0.01, 50000.0)
	}
}

func BenchmarkPnLCalculation(b *testing.B) {
	
	tracker := newMockPositionTracker()

	// Setup large position
	tracker.UpdatePosition("user1", "BTC-USD", 1000.0, 50000.0)

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		tracker.CalculatePnL("user1")
	}
}

func BenchmarkCircuitBreaker(b *testing.B) {
	
	breaker := newMockCircuitBreaker()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		breaker.Execute(func() error {
			return nil
		})
	}
}

func BenchmarkConcurrentOrderSubmission(b *testing.B) {
	engine := newMockMatchingEngine()

	b.ResetTimer()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			engine.SubmitOrder(context.Background(), &Order{
				UserID:   "user1",
				Symbol:   "BTC-USD",
				Side:     "buy",
				Price:    decimal.NewFromFloat(50000.0),
				Quantity: decimal.NewFromFloat(1.0),
			})
		}
	})
}

func BenchmarkOrderBookDepth(b *testing.B) {
	book := newMockOrderBook("BTC-USD")

	// Pre-populate
	for i := 0; i < 1000; i++ {
		book.AddOrder(&BookOrder{
			Price:    decimal.NewFromFloat(50000.0 - float64(i)),
			Quantity: decimal.NewFromFloat(1.0),
			Side:     "buy",
		})
		book.AddOrder(&BookOrder{
			Price:    decimal.NewFromFloat(50000.0 + float64(i)),
			Quantity: decimal.NewFromFloat(1.0),
			Side:     "sell",
		})
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		book.GetDepth(100)
	}
}

func BenchmarkMarketDataProcessing(b *testing.B) {
	feed := newMockMarketFeed()

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		feed.ProcessTick(&Tick{
			Symbol:    "BTC-USD",
			Price:     50000.0 + float64(i%100),
			Volume:    1.0,
			Timestamp: time.Now(),
		})
	}
}

func BenchmarkAlertChecking(b *testing.B) {
	engine := newMockAlertEngine()

	// Setup alerts
	for i := 0; i < 1000; i++ {
		engine.CreateAlert("user1", "BTC-USD", "above", 50000.0+float64(i))
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		engine.CheckPrice("BTC-USD", 55000.0)
	}
}

func BenchmarkCacheOperations(b *testing.B) {
	cache := newMockCache()

	b.Run("Set", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			cache.Set("key", "value")
		}
	})

	b.Run("Get", func(b *testing.B) {
		cache.Set("key", "value")
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			cache.Get("key")
		}
	})

	b.Run("GetMiss", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			cache.Get("nonexistent")
		}
	})
}

func BenchmarkDecimalOperations(b *testing.B) {
	

	b.Run("Float64Multiply", func(b *testing.B) {
		price := 50000.123456
		qty := 1.234567
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			_ = price * qty
		}
	})

	b.Run("DecimalMultiply", func(b *testing.B) {
		price := decimal.NewFromFloat(50000.123456)
		qty := decimal.NewFromFloat(1.234567)
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			_ = price.Mul(qty)
		}
	})
}

func BenchmarkLockContention(b *testing.B) {
	
	var mu sync.RWMutex
	data := make(map[string]int)

	b.Run("WriteContention", func(b *testing.B) {
		b.RunParallel(func(pb *testing.PB) {
			for pb.Next() {
				mu.Lock()
				data["key"]++
				mu.Unlock()
			}
		})
	})

	b.Run("ReadContention", func(b *testing.B) {
		b.RunParallel(func(pb *testing.PB) {
			for pb.Next() {
				mu.RLock()
				_ = data["key"]
				mu.RUnlock()
			}
		})
	})
}

// Mock types and helpers

type Order struct {
	UserID   string
	Symbol   string
	Side     string
	Price    decimal.Decimal
	Quantity decimal.Decimal
}

type BookOrder struct {
	Price    decimal.Decimal
	Quantity decimal.Decimal
	Side     string
}

type Tick struct {
	Symbol    string
	Price     float64
	Volume    float64
	Timestamp time.Time
}

type MockMatchingEngine struct {
	orders map[string][]*Order
	mu     sync.RWMutex
}

func newMockMatchingEngine() *MockMatchingEngine {
	return &MockMatchingEngine{
		orders: make(map[string][]*Order),
	}
}

func (e *MockMatchingEngine) SubmitOrder(ctx context.Context, order *Order) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.orders[order.Symbol] = append(e.orders[order.Symbol], order)
	return nil
}

func (e *MockMatchingEngine) Match(symbol string) []interface{} {
	return nil
}

type MockRiskCalculator struct{}

func newMockRiskCalculator() *MockRiskCalculator {
	return &MockRiskCalculator{}
}

func (c *MockRiskCalculator) CheckOrder(userID, symbol, side string, qty, price float64) bool {
	return qty*price < 1000000
}

type MockPositionTracker struct {
	positions map[string]map[string]float64
	mu        sync.RWMutex
}

func newMockPositionTracker() *MockPositionTracker {
	return &MockPositionTracker{
		positions: make(map[string]map[string]float64),
	}
}

func (t *MockPositionTracker) UpdatePosition(userID, symbol string, qty, price float64) {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.positions[userID] == nil {
		t.positions[userID] = make(map[string]float64)
	}
	t.positions[userID][symbol] += qty
}

func (t *MockPositionTracker) CalculatePnL(userID string) float64 {
	t.mu.RLock()
	defer t.mu.RUnlock()
	return 0.0
}

type MockCircuitBreaker struct {
	state int32
}

func newMockCircuitBreaker() *MockCircuitBreaker {
	return &MockCircuitBreaker{}
}

func (b *MockCircuitBreaker) Execute(fn func() error) error {
	return fn()
}

type MockOrderBook struct {
	bids []*BookOrder
	asks []*BookOrder
	mu   sync.RWMutex
}

func newMockOrderBook(symbol string) *MockOrderBook {
	return &MockOrderBook{}
}

func (b *MockOrderBook) AddOrder(order *BookOrder) {
	b.mu.Lock()
	defer b.mu.Unlock()
	if order.Side == "buy" {
		b.bids = append(b.bids, order)
	} else {
		b.asks = append(b.asks, order)
	}
}

func (b *MockOrderBook) GetDepth(levels int) ([][2]float64, [][2]float64) {
	b.mu.RLock()
	defer b.mu.RUnlock()
	return nil, nil
}

type MockMarketFeed struct{}

func newMockMarketFeed() *MockMarketFeed {
	return &MockMarketFeed{}
}

func (f *MockMarketFeed) ProcessTick(tick *Tick) {}

type MockAlertEngine struct {
	alerts map[string][]float64
}

func newMockAlertEngine() *MockAlertEngine {
	return &MockAlertEngine{alerts: make(map[string][]float64)}
}

func (e *MockAlertEngine) CreateAlert(userID, symbol, condition string, price float64) {
	e.alerts[symbol] = append(e.alerts[symbol], price)
}

func (e *MockAlertEngine) CheckPrice(symbol string, price float64) []int {
	return nil
}

type MockCache struct {
	data map[string]string
	mu   sync.RWMutex
}

func newMockCache() *MockCache {
	return &MockCache{data: make(map[string]string)}
}

func (c *MockCache) Set(key, value string) {
	c.mu.Lock()
	c.data[key] = value
	c.mu.Unlock()
}

func (c *MockCache) Get(key string) (string, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	v, ok := c.data[key]
	return v, ok
}
