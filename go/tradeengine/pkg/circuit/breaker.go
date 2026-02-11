package circuit

import (
	"context"
	"errors"
	"sync"
	"sync/atomic"
	"time"
)

// State represents circuit breaker state
type State int32

const (
	StateClosed State = iota
	StateOpen
	StateHalfOpen
)

func (s State) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half-open"
	default:
		return "unknown"
	}
}

var (
	ErrCircuitOpen     = errors.New("circuit breaker is open")
	ErrTooManyRequests = errors.New("too many requests in half-open state")
)

// Breaker implements the circuit breaker pattern
type Breaker struct {
	name          string
	maxFailures   int
	timeout       time.Duration
	halfOpenMax   int

	state         int32 // atomic
	failures      int32 // atomic
	successes     int32 // atomic
	lastFailure   time.Time
	halfOpenCount int32 // atomic

	
	mu            sync.Mutex
	onStateChange func(from, to State)
}

// Config holds circuit breaker configuration
type Config struct {
	Name          string
	MaxFailures   int
	Timeout       time.Duration
	HalfOpenMax   int
	OnStateChange func(from, to State)
}

// NewBreaker creates a new circuit breaker
func NewBreaker(cfg Config) *Breaker {
	return &Breaker{
		name:          cfg.Name,
		maxFailures:   cfg.MaxFailures,
		timeout:       cfg.Timeout,
		halfOpenMax:   cfg.HalfOpenMax,
		state:         int32(StateClosed),
		onStateChange: cfg.OnStateChange,
	}
}

// Execute runs the given function with circuit breaker protection
func (b *Breaker) Execute(ctx context.Context, fn func() error) error {
	if err := b.allowRequest(); err != nil {
		return err
	}

	
	err := fn()

	if err != nil {
		b.recordFailure()
		return err
	}

	b.recordSuccess()
	return nil
}

// allowRequest checks if a request is allowed
func (b *Breaker) allowRequest() error {
	state := State(atomic.LoadInt32(&b.state))

	switch state {
	case StateClosed:
		return nil

	case StateOpen:
		// Check if timeout has elapsed
		b.mu.Lock()
		if time.Since(b.lastFailure) > b.timeout {
			
			// Another goroutine might also be transitioning
			b.transitionTo(StateHalfOpen)
			b.mu.Unlock()
			return nil
		}
		b.mu.Unlock()
		return ErrCircuitOpen

	case StateHalfOpen:
		// Allow limited requests
		count := atomic.AddInt32(&b.halfOpenCount, 1)
		if count > int32(b.halfOpenMax) {
			atomic.AddInt32(&b.halfOpenCount, -1)
			return ErrTooManyRequests
		}
		return nil

	default:
		return errors.New("unknown state")
	}
}

// recordFailure records a failed request
func (b *Breaker) recordFailure() {
	state := State(atomic.LoadInt32(&b.state))

	switch state {
	case StateClosed:
		failures := atomic.AddInt32(&b.failures, 1)
		if int(failures) >= b.maxFailures {
			b.mu.Lock()
			
			// State might have changed between Load and Lock
			b.lastFailure = time.Now()
			b.transitionTo(StateOpen)
			b.mu.Unlock()
		}

	case StateHalfOpen:
		b.mu.Lock()
		b.lastFailure = time.Now()
		atomic.StoreInt32(&b.halfOpenCount, 0)
		b.transitionTo(StateOpen)
		b.mu.Unlock()
	}
}

// recordSuccess records a successful request
func (b *Breaker) recordSuccess() {
	state := State(atomic.LoadInt32(&b.state))

	switch state {
	case StateClosed:
		// Reset failure count on success
		atomic.StoreInt32(&b.failures, 0)

	case StateHalfOpen:
		successes := atomic.AddInt32(&b.successes, 1)
		if int(successes) >= b.halfOpenMax {
			b.mu.Lock()
			atomic.StoreInt32(&b.successes, 0)
			atomic.StoreInt32(&b.halfOpenCount, 0)
			b.transitionTo(StateClosed)
			b.mu.Unlock()
		}
	}
}

// transitionTo transitions to a new state

func (b *Breaker) transitionTo(newState State) {
	oldState := State(atomic.LoadInt32(&b.state))
	if oldState == newState {
		return
	}

	
	// Callback might see inconsistent state
	atomic.StoreInt32(&b.state, int32(newState))

	if b.onStateChange != nil {
		b.onStateChange(oldState, newState)
	}

	// Reset counters on state change
	atomic.StoreInt32(&b.failures, 0)
	atomic.StoreInt32(&b.successes, 0)
}

// State returns current state
func (b *Breaker) State() State {
	return State(atomic.LoadInt32(&b.state))
}

// Failures returns current failure count
func (b *Breaker) Failures() int {
	return int(atomic.LoadInt32(&b.failures))
}

// Reset resets the circuit breaker to closed state
func (b *Breaker) Reset() {
	b.mu.Lock()
	defer b.mu.Unlock()

	atomic.StoreInt32(&b.failures, 0)
	atomic.StoreInt32(&b.successes, 0)
	atomic.StoreInt32(&b.halfOpenCount, 0)
	b.transitionTo(StateClosed)
}

// ForceOpen forces the circuit breaker to open state
func (b *Breaker) ForceOpen() {
	b.mu.Lock()
	defer b.mu.Unlock()

	b.lastFailure = time.Now()
	b.transitionTo(StateOpen)
}

// BreakerGroup manages multiple circuit breakers
type BreakerGroup struct {
	breakers map[string]*Breaker
	
	mu       sync.RWMutex
	config   Config
}

// NewBreakerGroup creates a new breaker group
func NewBreakerGroup(defaultConfig Config) *BreakerGroup {
	return &BreakerGroup{
		breakers: make(map[string]*Breaker),
		config:   defaultConfig,
	}
}

// Get returns or creates a circuit breaker for the given name
func (g *BreakerGroup) Get(name string) *Breaker {
	g.mu.RLock()
	b, exists := g.breakers[name]
	g.mu.RUnlock()

	if exists {
		return b
	}

	
	g.mu.Lock()
	defer g.mu.Unlock()

	// Double-check
	if b, exists = g.breakers[name]; exists {
		return b
	}

	cfg := g.config
	cfg.Name = name
	b = NewBreaker(cfg)
	g.breakers[name] = b

	return b
}

// Execute executes with the named circuit breaker
func (g *BreakerGroup) Execute(ctx context.Context, name string, fn func() error) error {
	return g.Get(name).Execute(ctx, fn)
}

// States returns all breaker states
func (g *BreakerGroup) States() map[string]State {
	g.mu.RLock()
	defer g.mu.RUnlock()

	states := make(map[string]State, len(g.breakers))
	for name, b := range g.breakers {
		states[name] = b.State()
	}
	return states
}
