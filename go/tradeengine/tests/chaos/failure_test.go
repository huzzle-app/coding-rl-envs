package chaos

import (
	"context"
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// Chaos tests for simulating failures and testing resilience

func TestNATSFailure(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping chaos test in short mode")
	}

	t.Run("should handle NATS connection loss", func(t *testing.T) {
		

		// Simulate NATS going down
		stopNATS()

		// Try to publish message
		err := publishMessage("orders.submitted", []byte("test"))
		assert.Error(t, err, "Publishing should fail when NATS is down")

		// Restart NATS
		startNATS()

		
		time.Sleep(2 * time.Second)

		err = publishMessage("orders.submitted", []byte("test"))
		assert.NoError(t, err,
			"Publishing should succeed after NATS reconnection")
	})

	t.Run("should buffer messages during outage", func(t *testing.T) {
		// Simulate brief outage
		stopNATS()

		// Publish several messages — should be buffered
		buffered := 0
		for i := 0; i < 10; i++ {
			err := publishMessage("orders.submitted", []byte("msg"))
			if err == nil {
				buffered++
			}
		}

		startNATS()
		time.Sleep(time.Second)

		// With proper buffering, messages published during outage
		// should be queued and delivered after reconnection.
		// Bug: publishMessage silently drops during outage (returns nil),
		// so buffered==10 but none were actually queued.
		delivered := getDeliveredCount("orders.submitted")
		assert.Equal(t, 10, delivered,
			"All 10 messages buffered during outage should be delivered after reconnection")
	})
}

func TestDatabaseFailure(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping chaos test in short mode")
	}

	t.Run("should handle database connection loss", func(t *testing.T) {
		

		// Simulate database going down
		stopPostgres()

		// Try to execute query
		_, err := executeDBQuery("SELECT 1")
		assert.Error(t, err)

		// Restart database
		startPostgres()
		time.Sleep(2 * time.Second)

		// Should reconnect
		result, err := executeDBQuery("SELECT 1")
		assert.NoError(t, err)
		assert.NotNil(t, result)
	})

	t.Run("should handle connection pool exhaustion", func(t *testing.T) {

		// Open many connections — should hit pool limit
		var wg sync.WaitGroup
		errorCount := int32(0)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				conn, err := openDBConnection()
				if err != nil {
					atomic.AddInt32(&errorCount, 1)
					return
				}
				// Hold connection open
				time.Sleep(100 * time.Millisecond)
				conn.Close()
			}()
		}

		wg.Wait()

		// Bug E1: Connection pool not configured — all 100 connections succeed
		// when they should be limited (e.g., pool max = 20).
		assert.Greater(t, atomic.LoadInt32(&errorCount), int32(0),
			"Connection pool should reject connections beyond its limit")
	})
}

func TestRedisFailure(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping chaos test in short mode")
	}

	t.Run("should handle Redis connection loss", func(t *testing.T) {
		

		// Cache some data
		setCache("user:1:portfolio", "cached-data")

		// Stop Redis
		stopRedis()

		// Try to read cache
		_, err := getCache("user:1:portfolio")
		assert.Error(t, err)

		// Service should fall back to database
		data := getFromDatabase("user:1:portfolio")
		assert.NotEmpty(t, data)

		startRedis()
	})

	t.Run("should handle cache stampede", func(t *testing.T) {

		// Clear cache
		deleteCache("popular-key")

		// Simulate many concurrent requests — no stampede protection
		var wg sync.WaitGroup
		dbCalls := int32(0)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()

				// Bug H2: no singleflight — each goroutine independently
				// checks cache, sees miss, hits DB
				cacheMu.Lock()
				data := cacheStore["popular-key"]
				cacheMu.Unlock()

				if data == "" {
					// Simulate DB fetch delay that causes thundering herd
					time.Sleep(time.Millisecond)
					atomic.AddInt32(&dbCalls, 1)

					result := getFromDatabase("popular-key")
					setCache("popular-key", result)
				}
			}()
		}

		wg.Wait()

		// With thundering herd protection (singleflight), only ~1 DB call.
		// Without protection, most of the 100 goroutines see cache miss.
		t.Logf("DB calls during stampede: %d", dbCalls)
		assert.LessOrEqual(t, atomic.LoadInt32(&dbCalls), int32(5),
			"Thundering herd protection should limit DB calls to ~1, got many")
	})
}

func TestServicePartition(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping chaos test in short mode")
	}

	t.Run("should handle network partition between services", func(t *testing.T) {
		

		// Partition matching service from risk service
		partitionServices("matching", "risk")

		// Submit order (goes to matching)
		order := submitOrderToMatching(map[string]interface{}{
			"user_id":  "user1",
			"symbol":   "BTC-USD",
			"quantity": 1.0,
		})

		// Risk check may not happen due to partition
		
		assert.Nil(t, order,
			"Order should not be executed without risk check during network partition")

		// Heal partition
		healPartition("matching", "risk")

		// System should reconcile
		time.Sleep(2 * time.Second)
	})

	t.Run("should handle etcd leader failure", func(t *testing.T) {
		

		// Simulate etcd leader failure
		killEtcdLeader()

		// Wait for re-election
		time.Sleep(5 * time.Second)

		// Distributed locks may be in inconsistent state
		
		err := acquireDistributedLock("critical-lock")
		assert.NoError(t, err,
			"Distributed lock should be acquirable after etcd leader re-election")

		restoreEtcdCluster()
	})
}

func TestHighLoad(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping chaos test in short mode")
	}

	t.Run("should handle order spike", func(t *testing.T) {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()

		var wg sync.WaitGroup
		orderCount := int32(0)

		// Submit 1000 orders in 1 second
		for i := 0; i < 1000; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()

				err := submitOrder(ctx, map[string]interface{}{
					"user_id":  "user1",
					"symbol":   "BTC-USD",
					"quantity": 0.001,
				})

				if err == nil {
					atomic.AddInt32(&orderCount, 1)
				}
			}(i)
		}

		wg.Wait()

		t.Logf("Successfully processed %d/1000 orders under load", orderCount)
		// All 1000 succeed because submitOrder is a no-op stub.
		// Under real load, back-pressure should reject some.
		assert.Less(t, atomic.LoadInt32(&orderCount), int32(1000),
			"Back-pressure should reject some orders under spike load")
	})

	t.Run("should handle memory pressure", func(t *testing.T) {
		// Simulate memory pressure by creating large order books
		for i := 0; i < 100; i++ {
			symbol := fmt.Sprintf("TEST-%d-USD", i)
			for j := 0; j < 1000; j++ {
				addToOrderBook(symbol, map[string]interface{}{
					"price":    float64(j),
					"quantity": 1.0,
				})
			}
		}

		// System should still function under memory pressure
		err := submitOrder(context.Background(), map[string]interface{}{
			"symbol":   "BTC-USD",
			"quantity": 1.0,
		})
		assert.NoError(t, err)

		// Verify order books track the data
		count := getOrderBookCount()
		assert.Greater(t, count, 0,
			"Order books should track entries under memory pressure")

		// Clean up
		clearOrderBooks()
	})
}

func TestContextCancellation(t *testing.T) {
	if testing.Short() {
		t.Skip("Skipping chaos test in short mode")
	}

	t.Run("should respect context cancellation", func(t *testing.T) {
		

		ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
		defer cancel()

		// Start long-running operation
		done := make(chan bool)
		go func() {
			_ = longRunningOperation(ctx)
			done <- true
		}()

		// Wait for timeout
		select {
		case <-done:
			// Operation completed or cancelled
		case <-time.After(5 * time.Second):
			t.Error("Long operation did not respect context cancellation")
		}
	})

	t.Run("should clean up goroutines on cancel", func(t *testing.T) {

		ctx, cancel := context.WithCancel(context.Background())

		// Start market feed — returns a channel that closes when stopped
		stopped := startMarketFeedWithSignal(ctx)

		// Cancel context
		cancel()

		// Allow cleanup time
		select {
		case <-stopped:
			// goroutine cleaned up properly
		case <-time.After(2 * time.Second):
			t.Fatal("Market feed goroutine leaked: did not stop after context cancel")
		}
	})
}

// Helper functions - simulate service behavior including bugs

var (
	natsDown    bool
	pgDown      bool
	redisDown   bool
	cacheStore  = make(map[string]string)
	cacheMu     sync.Mutex
	partitioned = make(map[string]bool)
)

func stopNATS()  { natsDown = true }
func startNATS() { natsDown = false }

func publishMessage(subject string, data []byte) error {
	if natsDown {
		// Bug L1: doesn't return error on disconnected state
		return nil
	}
	return nil
}

func stopPostgres()  { pgDown = true }
func startPostgres() { pgDown = false }

func executeDBQuery(query string) (interface{}, error) {
	if pgDown {
		return nil, fmt.Errorf("connection refused")
	}
	return "result", nil
}

func openDBConnection() (*DBConnChaos, error) {
	if pgDown {
		return nil, fmt.Errorf("cannot connect to database")
	}
	return &DBConnChaos{}, nil
}

func stopRedis()  { redisDown = true }
func startRedis() { redisDown = false }

func setCache(key, value string) {
	if redisDown {
		return
	}
	cacheMu.Lock()
	cacheStore[key] = value
	cacheMu.Unlock()
}

func getCache(key string) (string, error) {
	if redisDown {
		return "", fmt.Errorf("redis: connection refused")
	}
	cacheMu.Lock()
	v, ok := cacheStore[key]
	cacheMu.Unlock()
	if !ok {
		return "", nil
	}
	return v, nil
}

func deleteCache(key string) {
	cacheMu.Lock()
	delete(cacheStore, key)
	cacheMu.Unlock()
}

func getFromDatabase(key string) string { return "data-from-db" }

func partitionServices(svc1, svc2 string) {
	partitioned[svc1+":"+svc2] = true
}
func healPartition(svc1, svc2 string) {
	delete(partitioned, svc1+":"+svc2)
}

func submitOrderToMatching(order map[string]interface{}) interface{} {
	// Bug D4: allows order execution even when risk service is partitioned
	if partitioned["matching:risk"] {
		// Should return nil (order rejected) but bug lets it through
		return order
	}
	return order
}

func killEtcdLeader()    {}
func restoreEtcdCluster() {}

func acquireDistributedLock(key string) error {
	// Bug D2: lock not properly renewed - may fail after leader change
	return nil
}

func submitOrder(ctx context.Context, order map[string]interface{}) error {
	select {
	case <-ctx.Done():
		return ctx.Err()
	default:
		return nil
	}
}

var (
	orderBookStore   = make(map[string]int)
	orderBookStoreMu sync.Mutex
)

func addToOrderBook(symbol string, order map[string]interface{}) {
	orderBookStoreMu.Lock()
	orderBookStore[symbol]++
	orderBookStoreMu.Unlock()
}

func getOrderBookCount() int {
	orderBookStoreMu.Lock()
	defer orderBookStoreMu.Unlock()
	total := 0
	for _, c := range orderBookStore {
		total += c
	}
	return total
}

func clearOrderBooks() {
	orderBookStoreMu.Lock()
	orderBookStore = make(map[string]int)
	orderBookStoreMu.Unlock()
}

// getDeliveredCount returns messages delivered after reconnection.
// Bug: no message buffering exists, so always returns 0.
func getDeliveredCount(subject string) int {
	return 0
}

func longRunningOperation(ctx context.Context) error {
	// Bug A8: should respect context cancellation but may not
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-time.After(10 * time.Second):
		return nil
	}
}

func startMarketFeed(ctx context.Context) {}

// startMarketFeedWithSignal starts a feed that should stop on cancel.
// Bug A3/A12: goroutine does not listen on ctx.Done(), so it leaks.
func startMarketFeedWithSignal(_ context.Context) <-chan struct{} {
	stopped := make(chan struct{})
	go func() {
		defer close(stopped)
		ticker := time.NewTicker(50 * time.Millisecond)
		defer ticker.Stop()
		for range ticker.C {
			// process tick — never exits because ctx is not checked
		}
	}()
	return stopped
}

type DBConnChaos struct{}

func (c *DBConnChaos) Close() {}
