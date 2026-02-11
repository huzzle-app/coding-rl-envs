package stress

import (
	"fmt"
	"testing"

	"gridweaver/internal/concurrency"
	"gridweaver/internal/resilience"
)

func TestConcurrencyMatrix(t *testing.T) {

	// ParallelReduce with different sizes and initial values
	sizes := []int{0, 1, 5, 10, 50}
	initials := []int{0, 100}
	for _, sz := range sizes {
		for _, init := range initials {
			name := fmt.Sprintf("ParallelReduce/sz%d_init%d", sz, init)
			t.Run(name, func(t *testing.T) {
				items := make([]int, sz)
				expectedSum := init
				for i := range items {
					items[i] = i + 1
					expectedSum += i + 1
				}
				result := concurrency.ParallelReduce(items,
					func(v int) int { return v },
					func(a, b int) int { return a + b },
					init,
				)
				if result != expectedSum {
					t.Fatalf("expected sum %d, got %d", expectedSum, result)
				}
			})
		}
	}

	// BoundedBuffer with varying capacities and fill levels
	bufCaps := []int{1, 5, 10, 50}
	fillPcts := []float64{0.0, 0.5, 1.0}
	for _, cap := range bufCaps {
		for _, pct := range fillPcts {
			fill := int(float64(cap) * pct)
			name := fmt.Sprintf("BoundedBuffer/cap%d_fill%d", cap, fill)
			t.Run(name, func(t *testing.T) {
				buf := concurrency.NewBoundedBuffer(cap)
				for i := 0; i < fill; i++ {
					ok := buf.Put(fmt.Sprintf("item_%d", i))
					if !ok {
						t.Fatalf("put should succeed for item %d (cap=%d)", i, cap)
					}
				}
				if buf.Size() != fill {
					t.Fatalf("expected size %d, got %d", fill, buf.Size())
				}
				// Try to get all items back
				for i := 0; i < fill; i++ {
					v, ok := buf.Get()
					if !ok {
						t.Fatalf("get should succeed for item %d", i)
					}
					expected := fmt.Sprintf("item_%d", i)
					if v != expected {
						t.Fatalf("expected '%s', got '%s'", expected, v)
					}
				}
			})
		}
	}

	// Circuit breaker with varying thresholds and probe limits
	thresholds := []int{1, 3, 5}
	probeLimits := []int{1, 2, 5}
	for _, thresh := range thresholds {
		for _, probe := range probeLimits {
			name := fmt.Sprintf("CircuitBreaker/thresh%d_probe%d", thresh, probe)
			t.Run(name, func(t *testing.T) {
				cb := resilience.NewCircuitBreaker(thresh, probe, 1000)
				// Trip it
				for i := 0; i < thresh; i++ {
					cb.RecordResult(false, int64(i*100))
				}
				if cb.State != "open" {
					t.Fatalf("should be open after %d failures, got %s", thresh, cb.State)
				}
				// Wait for timeout
				cb.RecordResult(true, int64(thresh*100+1100))
				if cb.State != "half-open" {
					t.Fatalf("should be half-open after timeout, got %s", cb.State)
				}
				// All probes succeed -> close
				for i := 0; i < probe; i++ {
					cb.RecordResult(true, int64(thresh*100+1200+i*100))
				}
				if cb.State != "closed" {
					t.Fatalf("should be closed after %d successful probes, got %s", probe, cb.State)
				}
			})
		}
	}

	// ConcurrentSet with varying sizes
	setCounts := []int{1, 10, 50, 100}
	for _, count := range setCounts {
		name := fmt.Sprintf("ConcurrentSet/n%d", count)
		t.Run(name, func(t *testing.T) {
			set := concurrency.NewConcurrentSet()
			for i := 0; i < count; i++ {
				set.Add(fmt.Sprintf("k%d", i))
			}
			if set.Size() != count {
				t.Fatalf("expected size %d, got %d", count, set.Size())
			}
			items := set.Items()
			if len(items) != count {
				t.Fatalf("expected %d items, got %d", count, len(items))
			}
		})
	}

	// RetryStateMachine with varying max attempts
	maxAttempts := []int{1, 3, 5, 10}
	baseBOs := []int{50, 100, 500}
	for _, ma := range maxAttempts {
		for _, bo := range baseBOs {
			name := fmt.Sprintf("RetryStateMachine/max%d_bo%d", ma, bo)
			t.Run(name, func(t *testing.T) {
				rsm := resilience.NewRetryStateMachine(ma, bo)
				for i := 0; i < ma; i++ {
					if !rsm.ShouldRetry() {
						t.Fatalf("should allow retry at attempt %d (max=%d)", i, ma)
					}
					rsm.RecordAttempt(false)
				}
				if rsm.TotalRetries != ma {
					t.Fatalf("expected %d total retries, got %d", ma, rsm.TotalRetries)
				}
			})
		}
	}

	// AdvancedCircuitBreaker AllowRequest matrix
	for _, thresh := range thresholds {
		name := fmt.Sprintf("CB_AllowRequest/thresh%d", thresh)
		t.Run(name, func(t *testing.T) {
			cb := resilience.NewCircuitBreaker(thresh, 2, 500)
			// Should allow in closed state
			if !cb.AllowRequest(0) {
				t.Fatalf("closed should allow")
			}
			// Trip it
			for i := 0; i < thresh; i++ {
				cb.RecordResult(false, int64(i*10))
			}
			// Should block in open state (before timeout)
			if cb.AllowRequest(int64(thresh * 10 + 100)) {
				t.Fatalf("open should block before timeout")
			}
			// Should allow after timeout
			if !cb.AllowRequest(int64(thresh*10 + 600)) {
				t.Fatalf("should allow after timeout")
			}
		})
	}
}
