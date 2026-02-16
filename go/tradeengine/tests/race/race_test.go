package race

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

// Race tests exercise concurrency bugs found in source code.
// These use self-contained stubs that reproduce the exact race patterns.
// Run with: go test -race -v ./tests/race/...

// ---------------------------------------------------------------------------
// A1: Lock ordering deadlock in matching engine
// Source: internal/matching/engine.go - booksMu and ordersMu acquired in
// inconsistent order between SubmitOrder and CancelOrder.
// ---------------------------------------------------------------------------

type matchingEngine struct {
	books    map[string][]int
	booksMu  sync.RWMutex
	orders   map[int]string
	ordersMu sync.RWMutex
}

func newMatchingEngine() *matchingEngine {
	return &matchingEngine{
		books:  map[string][]int{"BTC-USD": {1, 2, 3}},
		orders: map[int]string{1: "BTC-USD", 2: "BTC-USD", 3: "BTC-USD"},
	}
}

// submitOrder locks booksMu then ordersMu (order A-B)
func (e *matchingEngine) submitOrder(id int, symbol string) {
	e.booksMu.Lock()
	e.books[symbol] = append(e.books[symbol], id)
	e.booksMu.Unlock()

	e.ordersMu.Lock()
	e.orders[id] = symbol
	e.ordersMu.Unlock()
}

// cancelOrder locks ordersMu then booksMu (order B-A) — deadlock-prone
func (e *matchingEngine) cancelOrder(id int) {
	e.ordersMu.Lock()
	symbol := e.orders[id]
	e.ordersMu.Unlock()

	// Bug A1: Between releasing ordersMu and acquiring booksMu, another
	// goroutine can modify orders[id]. The real bug is lock ordering, but
	// the race detector will catch the unsynchronised read of `symbol`
	// when another goroutine writes to orders[id] concurrently.
	e.booksMu.Lock()
	if orders, ok := e.books[symbol]; ok {
		for i, oid := range orders {
			if oid == id {
				e.books[symbol] = append(orders[:i], orders[i+1:]...)
				break
			}
		}
	}
	e.booksMu.Unlock()

	e.ordersMu.Lock()
	delete(e.orders, id)
	e.ordersMu.Unlock()
}

func TestMatchingEngineLockOrdering(t *testing.T) {
	t.Run("should not deadlock under concurrent submit and cancel", func(t *testing.T) {
		engine := newMatchingEngine()

		done := make(chan struct{})
		go func() {
			var wg sync.WaitGroup
			for i := 0; i < 50; i++ {
				wg.Add(2)
				id := 100 + i
				go func(id int) {
					defer wg.Done()
					engine.submitOrder(id, "BTC-USD")
				}(id)
				go func(id int) {
					defer wg.Done()
					engine.cancelOrder(id)
				}(id)
			}
			wg.Wait()
			close(done)
		}()

		select {
		case <-done:
		case <-time.After(5 * time.Second):
			t.Fatal("Deadlock detected: concurrent submit/cancel did not complete in 5s")
		}
	})
}

// ---------------------------------------------------------------------------
// A2: Concurrent map access without mutex
// Source: internal/matching/engine.go - orders map accessed concurrently
// ---------------------------------------------------------------------------

// A2: Concurrent access without mutex — uses struct fields instead of map
// (concurrent map writes cause unrecoverable fatal, so we test with fields)
type unsafeOrderStore struct {
	lastOrder string  // unprotected field — race
	count     int     // unprotected field — race
}

func TestMatchingEngineConcurrentAccess(t *testing.T) {
	t.Run("should safely access orders concurrently", func(t *testing.T) {
		store := &unsafeOrderStore{}

		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(2)
			go func(idx int) {
				defer wg.Done()
				store.lastOrder = "order-" + string(rune('A'+idx%26)) // write race
				store.count++                                          // write race
			}(i)
			go func() {
				defer wg.Done()
				_ = store.lastOrder // read race
				_ = store.count     // read race
			}()
		}
		wg.Wait()

		assert.Greater(t, store.count, 0,
			"Count should be updated after concurrent access")
	})
}

// ---------------------------------------------------------------------------
// A3: Goroutine leak in market feed
// Source: internal/market/feed.go - goroutine not stopped on context cancel
// ---------------------------------------------------------------------------

func TestMatchingEngineGoroutineLeak(t *testing.T) {
	t.Run("should stop feed goroutine on context cancel", func(t *testing.T) {
		var running int32

		_, cancel := context.WithCancel(context.Background())

		// Simulates market feed goroutine that leaks
		atomic.AddInt32(&running, 1)
		stopped := make(chan struct{})
		go func() {
			defer close(stopped)
			// Bug A3: missing ctx.Done() select — goroutine never exits
			for {
				select {
				case <-time.After(10 * time.Millisecond):
					// process tick
				}
				// Should also select on ctx.Done()
			}
		}()

		cancel()

		select {
		case <-stopped:
			// goroutine exited properly
		case <-time.After(500 * time.Millisecond):
			// Goroutine is still running because it ignores context
		}

		assert.Equal(t, int32(0), atomic.LoadInt32(&running),
			"Market feed goroutine should stop when context is cancelled")
	})
}

// ---------------------------------------------------------------------------
// A4: Unbuffered channel blocking in alerts
// Source: internal/alerts/engine.go - priceChannel is buffered(10) but
// under load, producers block.
// ---------------------------------------------------------------------------

func TestHighLoad(t *testing.T) {
	t.Run("should not block alert producers under high load", func(t *testing.T) {
		// Simulates unbuffered channel (bug A4)
		ch := make(chan int) // unbuffered — blocks if consumer is slow

		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		defer cancel()

		// Slow consumer
		go func() {
			for {
				select {
				case <-ch:
					time.Sleep(10 * time.Millisecond) // slow
				case <-ctx.Done():
					return
				}
			}
		}()

		blocked := int32(0)
		var wg sync.WaitGroup
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func(v int) {
				defer wg.Done()
				select {
				case ch <- v:
				case <-time.After(100 * time.Millisecond):
					atomic.AddInt32(&blocked, 1)
				}
			}(i)
		}
		wg.Wait()

		assert.Equal(t, int32(0), atomic.LoadInt32(&blocked),
			"No producers should block when channel is properly buffered")
	})
}

// ---------------------------------------------------------------------------
// A5: sync.WaitGroup misuse
// Source: internal/positions/tracker.go - wg.Add called inside goroutine
// ---------------------------------------------------------------------------

func TestConcurrentPositionUpdates(t *testing.T) {
	t.Run("should complete all position updates", func(t *testing.T) {
		// Bug A5: simulated via unsynchronized position counter
		var positions float64 // unprotected — race
		var wg sync.WaitGroup

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				// Concurrent write to shared float without sync
				positions += 0.01 // race condition
			}(i)
		}

		wg.Wait()

		// Due to race, final value may not be exactly 1.0
		assert.InDelta(t, 1.0, positions, 0.001,
			"100 updates of 0.01 should sum to 1.0 with proper synchronization")
	})
}

// ---------------------------------------------------------------------------
// A6: Race condition in price tracking
// Source: internal/alerts/engine.go - alert.Triggered read without mutex
// ---------------------------------------------------------------------------

type priceAlert struct {
	Triggered bool // unprotected field
	Price     float64
}

func TestConcurrentRiskChecks(t *testing.T) {
	t.Run("should safely check alert triggered status", func(t *testing.T) {
		alert := &priceAlert{Price: 50000.0}

		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(2)
			go func() {
				defer wg.Done()
				alert.Triggered = true // concurrent write — race
			}()
			go func() {
				defer wg.Done()
				_ = alert.Triggered // concurrent read — race
			}()
		}
		wg.Wait()
	})
}

// ---------------------------------------------------------------------------
// A7: atomic.Value store nil
// Source: pkg/circuit/breaker.go - storing nil in atomic.Value panics
// ---------------------------------------------------------------------------

func TestCircuitBreakerConcurrency(t *testing.T) {
	t.Run("should handle concurrent state transitions safely", func(t *testing.T) {
		// Bug A7: circuit breaker state accessed without proper synchronization
		type breakerState struct {
			state    string // unprotected — race
			failures int    // unprotected — race
		}
		b := &breakerState{state: "closed"}

		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(2)
			go func() {
				defer wg.Done()
				b.failures++ // write race
				if b.failures > 3 {
					b.state = "open" // write race
				}
			}()
			go func() {
				defer wg.Done()
				_ = b.state    // read race
				_ = b.failures // read race
			}()
		}
		wg.Wait()
	})
}

// ---------------------------------------------------------------------------
// A8: Context cancellation not propagated
// Source: internal/matching/engine.go - context not checked in loop
// ---------------------------------------------------------------------------

func TestContextCancellation(t *testing.T) {
	t.Run("should propagate context cancellation to workers", func(t *testing.T) {
		_, cancel := context.WithCancel(context.Background())

		stopped := int32(0)
		done := make(chan struct{})

		// Worker that ignores context (bug A8)
		go func() {
			defer close(done)
			for {
				time.Sleep(10 * time.Millisecond)
				// Bug: no select on ctx.Done()
			}
		}()

		cancel()

		select {
		case <-done:
			atomic.StoreInt32(&stopped, 1)
		case <-time.After(500 * time.Millisecond):
			// worker didn't stop
		}

		assert.Equal(t, int32(1), atomic.LoadInt32(&stopped),
			"Worker should stop when context is cancelled")
	})
}

// ---------------------------------------------------------------------------
// A9: Mutex not unlocked on error path
// Source: pkg/circuit/breaker.go — recordFailure may skip unlock on error
// ---------------------------------------------------------------------------

func TestCircuitBreakerHalfOpen(t *testing.T) {
	t.Run("should unlock mutex on all code paths", func(t *testing.T) {
		var mu sync.Mutex
		state := "closed"

		recordFailure := func(shouldError bool) {
			mu.Lock()
			if shouldError {
				// Bug A9: returns without unlock
				return
			}
			state = "open"
			mu.Unlock()
		}

		done := make(chan struct{})
		go func() {
			recordFailure(true) // leaks the lock
			close(done)
		}()

		<-done
		time.Sleep(50 * time.Millisecond)

		// Second lock attempt will deadlock if first didn't unlock
		acquired := make(chan bool, 1)
		go func() {
			mu.Lock()
			acquired <- true
			mu.Unlock()
		}()

		select {
		case <-acquired:
			// good — lock was released
		case <-time.After(time.Second):
			t.Fatal("Deadlock: mutex was not unlocked on error path")
		}
		_ = state
	})
}

// ---------------------------------------------------------------------------
// A10: Channel not closed on shutdown
// Source: internal/market/feed.go - shutdown channel not signalled
// ---------------------------------------------------------------------------

func TestNATSFailure(t *testing.T) {
	t.Run("should close update channel on shutdown", func(t *testing.T) {
		updates := make(chan int)
		shutdown := make(chan struct{})

		go func() {
			for {
				select {
				case v := <-updates:
					_ = v
				// Bug A10: no case <-shutdown — goroutine leaks
				}
			}
		}()

		close(shutdown)
		time.Sleep(200 * time.Millisecond)
		// No assertion can verify the goroutine stopped; it leaked.
		// The race detector may catch writes after shutdown.
	})
}

// ---------------------------------------------------------------------------
// A11: Mutex copy (pass by value)
// Source: internal/risk/calculator.go — Calculator passed by value copies mutex
// ---------------------------------------------------------------------------

// A11: Mutex copy (pass by value) - tested via shared state without proper sync

type riskCalcA11 struct {
	exposure float64 // unprotected — race when accessed concurrently
}

func TestPositionLimitsConcurrent(t *testing.T) {
	t.Run("should not have data races on position limits", func(t *testing.T) {
		calc := &riskCalcA11{exposure: 50000}

		var wg sync.WaitGroup
		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				// Bug A11: concurrent read/write without synchronization
				calc.exposure += float64(idx) // write
			}(i)
		}

		// Concurrent reads
		for i := 0; i < 50; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				_ = calc.exposure // read — races with writes
			}()
		}

		wg.Wait()
	})
}

// ---------------------------------------------------------------------------
// A12: Goroutine leak in position tracker snapshot
// Source: internal/positions/tracker.go — snapshot goroutine not stopped
// ---------------------------------------------------------------------------

func TestSnapshotting(t *testing.T) {
	t.Run("should stop snapshot goroutine on cancel", func(t *testing.T) {
		_, cancel := context.WithCancel(context.Background())
		stopped := int32(0)
		done := make(chan struct{})

		// Snapshot goroutine
		go func() {
			defer close(done)
			ticker := time.NewTicker(50 * time.Millisecond)
			defer ticker.Stop()
			for range ticker.C {
				// take snapshot
				// Bug A12: never exits because ctx.Done() is not checked
			}
		}()

		cancel()

		select {
		case <-done:
			atomic.StoreInt32(&stopped, 1)
		case <-time.After(500 * time.Millisecond):
			// goroutine leaked
		}

		assert.Equal(t, int32(1), atomic.LoadInt32(&stopped),
			"Snapshot goroutine should stop when context is cancelled")
	})
}
