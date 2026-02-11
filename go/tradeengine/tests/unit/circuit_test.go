package unit

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/terminal-bench/tradeengine/pkg/circuit"
)

func TestCircuitBreakerCreation(t *testing.T) {
	t.Run("should create circuit breaker", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			Name:        "test",
			MaxFailures: 3,
			Timeout:     time.Second,
			HalfOpenMax: 2,
		})

		assert.NotNil(t, breaker)
		assert.Equal(t, circuit.StateClosed, breaker.State())
	})
}

func TestCircuitBreakerClosed(t *testing.T) {
	t.Run("should allow requests when closed", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		err := breaker.Execute(context.Background(), func() error {
			return nil
		})

		assert.NoError(t, err)
		assert.Equal(t, circuit.StateClosed, breaker.State())
	})

	t.Run("should track failures", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		assert.Equal(t, 1, breaker.Failures())
		assert.Equal(t, circuit.StateClosed, breaker.State())
	})
}

func TestCircuitBreakerOpen(t *testing.T) {
	t.Run("should open after max failures", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		for i := 0; i < 3; i++ {
			breaker.Execute(context.Background(), func() error {
				return errors.New("failure")
			})
		}

		assert.Equal(t, circuit.StateOpen, breaker.State())
	})

	t.Run("should reject requests when open", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		// Trip the breaker
		for i := 0; i < 3; i++ {
			breaker.Execute(context.Background(), func() error {
				return errors.New("failure")
			})
		}

		err := breaker.Execute(context.Background(), func() error {
			return nil
		})

		assert.Equal(t, circuit.ErrCircuitOpen, err)
	})
}

func TestCircuitBreakerHalfOpen(t *testing.T) {
	t.Run("should transition to half-open after timeout", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 3,
			Timeout:     100 * time.Millisecond,
			HalfOpenMax: 2,
		})

		// Trip the breaker
		for i := 0; i < 3; i++ {
			breaker.Execute(context.Background(), func() error {
				return errors.New("failure")
			})
		}

		assert.Equal(t, circuit.StateOpen, breaker.State())

		// Wait for timeout
		time.Sleep(150 * time.Millisecond)

		// Next request should transition to half-open
		err := breaker.Execute(context.Background(), func() error {
			return nil
		})

		assert.NoError(t, err)
		// State might be half-open or closed depending on success
	})

	t.Run("should limit half-open requests", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 1,
			Timeout:     100 * time.Millisecond,
			HalfOpenMax: 2,
		})

		// Trip the breaker
		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		// Wait for timeout
		time.Sleep(150 * time.Millisecond)

		// First two requests allowed
		err1 := breaker.Execute(context.Background(), func() error {
			time.Sleep(50 * time.Millisecond)
			return nil
		})
		assert.NoError(t, err1, "First half-open request should be allowed")

		err2 := breaker.Execute(context.Background(), func() error {
			time.Sleep(50 * time.Millisecond)
			return nil
		})
		assert.NoError(t, err2, "Second half-open request should be allowed")
	})

	t.Run("should close after successful half-open", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 1,
			Timeout:     100 * time.Millisecond,
			HalfOpenMax: 2,
		})

		// Trip the breaker
		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		time.Sleep(150 * time.Millisecond)

		// Successful requests in half-open
		for i := 0; i < 2; i++ {
			breaker.Execute(context.Background(), func() error {
				return nil
			})
		}

		// Should be closed now
		assert.Equal(t, circuit.StateClosed, breaker.State())
	})

	t.Run("should re-open on failure in half-open", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 1,
			Timeout:     100 * time.Millisecond,
			HalfOpenMax: 2,
		})

		// Trip the breaker
		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		time.Sleep(150 * time.Millisecond)

		// Fail in half-open
		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		assert.Equal(t, circuit.StateOpen, breaker.State())
	})
}

func TestCircuitBreakerReset(t *testing.T) {
	t.Run("should reset to closed", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 1,
			Timeout:     time.Second,
		})

		// Trip the breaker
		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		assert.Equal(t, circuit.StateOpen, breaker.State())

		// Reset
		breaker.Reset()

		assert.Equal(t, circuit.StateClosed, breaker.State())
		assert.Equal(t, 0, breaker.Failures())
	})
}

func TestCircuitBreakerForceOpen(t *testing.T) {
	t.Run("should force open", func(t *testing.T) {
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 10,
			Timeout:     time.Second,
		})

		breaker.ForceOpen()

		assert.Equal(t, circuit.StateOpen, breaker.State())
	})
}

func TestCircuitBreakerStateChange(t *testing.T) {
	t.Run("should call state change callback", func(t *testing.T) {
		changes := make([]circuit.State, 0)
		var mu sync.Mutex

		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 1,
			Timeout:     100 * time.Millisecond,
			OnStateChange: func(from, to circuit.State) {
				mu.Lock()
				changes = append(changes, to)
				mu.Unlock()
			},
		})

		// Trip
		breaker.Execute(context.Background(), func() error {
			return errors.New("failure")
		})

		time.Sleep(150 * time.Millisecond)

		// Recover
		breaker.Execute(context.Background(), func() error {
			return nil
		})

		mu.Lock()
		defer mu.Unlock()
		assert.Contains(t, changes, circuit.StateOpen)
	})
}

func TestCircuitBreakerConcurrency(t *testing.T) {
	t.Run("should handle concurrent requests", func(t *testing.T) {
		
		breaker := circuit.NewBreaker(circuit.Config{
			MaxFailures: 100,
			Timeout:     time.Second,
			HalfOpenMax: 10,
		})

		var wg sync.WaitGroup

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func() {
				defer wg.Done()
				breaker.Execute(context.Background(), func() error {
					if time.Now().UnixNano()%2 == 0 {
						return errors.New("failure")
					}
					return nil
				})
			}()
		}

		wg.Wait()
	})
}

func TestBreakerGroupGet(t *testing.T) {
	t.Run("should create breaker on first access", func(t *testing.T) {
		group := circuit.NewBreakerGroup(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		breaker := group.Get("service-a")
		assert.NotNil(t, breaker)
		assert.Equal(t, circuit.StateClosed, breaker.State())
	})

	t.Run("should return same breaker", func(t *testing.T) {
		group := circuit.NewBreakerGroup(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		b1 := group.Get("service-a")
		b2 := group.Get("service-a")

		assert.Same(t, b1, b2)
	})

	t.Run("should handle concurrent access", func(t *testing.T) {
		
		group := circuit.NewBreakerGroup(circuit.Config{
			MaxFailures: 3,
			Timeout:     time.Second,
		})

		var wg sync.WaitGroup
		breakers := make([]*circuit.Breaker, 100)

		for i := 0; i < 100; i++ {
			wg.Add(1)
			go func(idx int) {
				defer wg.Done()
				breakers[idx] = group.Get("service-a")
			}(i)
		}

		wg.Wait()

		// All should be the same instance
		for i := 1; i < 100; i++ {
			assert.Same(t, breakers[0], breakers[i])
		}
	})
}

func TestBreakerGroupStates(t *testing.T) {
	t.Run("should return all breaker states", func(t *testing.T) {
		group := circuit.NewBreakerGroup(circuit.Config{
			MaxFailures: 1,
			Timeout:     time.Second,
		})

		group.Get("service-a")
		group.Get("service-b")

		// Trip service-a
		group.Execute(context.Background(), "service-a", func() error {
			return errors.New("failure")
		})

		states := group.States()
		assert.Len(t, states, 2)
		assert.Equal(t, circuit.StateOpen, states["service-a"])
		assert.Equal(t, circuit.StateClosed, states["service-b"])
	})
}
