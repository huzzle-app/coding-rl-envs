package concurrency

import (
	"atlasdispatch/internal/resilience"
	"atlasdispatch/internal/statistics"
	"fmt"
	"sync"
	"testing"
)

// ---------------------------------------------------------------------------
// Concurrency Bug: ConcurrentTracker.Snapshot reads without lock
// ---------------------------------------------------------------------------

func TestConcurrentTrackerRace(t *testing.T) {
	for i := 0; i < 50; i++ {
		i := i
		t.Run(fmt.Sprintf("tracker_race_%05d", i), func(t *testing.T) {
			ct := statistics.NewConcurrentTracker()
			var wg sync.WaitGroup
			for g := 0; g < 20; g++ {
				wg.Add(2)
				go func(v float64) {
					defer wg.Done()
					ct.Record(v)
				}(float64(g + i*20))
				go func() {
					defer wg.Done()
					_ = ct.Snapshot()
				}()
			}
			wg.Wait()
		})
	}
}

// ---------------------------------------------------------------------------
// Concurrency Bug: CheckpointManager.StreamSequences reads without lock
// ---------------------------------------------------------------------------

func TestCheckpointManagerRace(t *testing.T) {
	for i := 0; i < 50; i++ {
		i := i
		t.Run(fmt.Sprintf("checkpoint_race_%05d", i), func(t *testing.T) {
			cm := resilience.NewCheckpointManager()
			var wg sync.WaitGroup
			for g := 0; g < 20; g++ {
				wg.Add(2)
				go func(seq int) {
					defer wg.Done()
					cm.Record(fmt.Sprintf("stream-%d", seq%5), seq)
				}(g + i*20)
				go func() {
					defer wg.Done()
					_ = cm.StreamSequences()
				}()
			}
			wg.Wait()
		})
	}
}

// ---------------------------------------------------------------------------
// Complex Concurrency: CircuitBreakerPool.Get has a TOCTOU race.
// The read lock is released before the write lock is acquired. Between
// the two, another goroutine can create the same breaker. The second
// creator overwrites the first's state, silently resetting accumulated
// failure counts. A service that should have its circuit open may get
// its counter reset by a concurrent Get call.
// ---------------------------------------------------------------------------

func TestCircuitBreakerPoolRace(t *testing.T) {
	for i := 0; i < 100; i++ {
		i := i
		t.Run(fmt.Sprintf("cbpool_%05d", i), func(t *testing.T) {
			pool := resilience.NewCircuitBreakerPool(resilience.CircuitBreakerConfig{
				FailureThreshold: 3,
				RecoveryTimeMs:   60000,
			})

			service := fmt.Sprintf("svc-%d", i)
			var wg sync.WaitGroup
			for g := 0; g < 10; g++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					pool.RecordResult(service, false)
				}()
			}
			wg.Wait()

			states := pool.ServiceStates()
			state := states[service]
			if state != "open" {
				t.Fatalf("case %d: after 10 failures (threshold=3), expected circuit 'open', got '%s'", i, state)
			}
		})
	}
}
