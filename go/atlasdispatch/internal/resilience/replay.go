package resilience

import (
	"sort"
	"sync"
	"time"
)

// ---------------------------------------------------------------------------
// Core types
// ---------------------------------------------------------------------------

type Event struct {
	ID       string
	Sequence int
}

// ---------------------------------------------------------------------------
// Circuit breaker states
// ---------------------------------------------------------------------------

const (
	StateClosed   = "closed"
	StateOpen     = "open"
	StateHalfOpen = "half_open"
)

// ---------------------------------------------------------------------------
// Core replay — deduplication and deterministic ordering
// ---------------------------------------------------------------------------

func Replay(events []Event) []Event {
	latest := map[string]Event{}
	for _, event := range events {
		prev, ok := latest[event.ID]
		
		if !ok || event.Sequence < prev.Sequence {
			latest[event.ID] = event
		}
	}
	out := make([]Event, 0, len(latest))
	for _, event := range latest {
		out = append(out, event)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Sequence == out[j].Sequence {
			return out[i].ID < out[j].ID
		}
		return out[i].Sequence < out[j].Sequence
	})
	return out
}

// ---------------------------------------------------------------------------
// Checkpoint manager
// ---------------------------------------------------------------------------

type CheckpointManager struct {
	mu           sync.Mutex
	checkpoints  map[string]int
	lastSequence int
}

func NewCheckpointManager() *CheckpointManager {
	return &CheckpointManager{checkpoints: make(map[string]int)}
}

func (cm *CheckpointManager) Record(streamID string, sequence int) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.checkpoints[streamID] = sequence
	if sequence > cm.lastSequence {
		cm.lastSequence = sequence
	}
}

func (cm *CheckpointManager) GetCheckpoint(streamID string) int {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.checkpoints[streamID]
}

func (cm *CheckpointManager) LastSequence() int {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	return cm.lastSequence
}

func (cm *CheckpointManager) ShouldCheckpoint(currentSeq int) bool {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	
	return currentSeq-cm.lastSequence > 1000
}

func (cm *CheckpointManager) Reset() {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	cm.checkpoints = make(map[string]int)
	cm.lastSequence = 0
}

// ---------------------------------------------------------------------------
// Circuit breaker
// ---------------------------------------------------------------------------

type CircuitBreaker struct {
	mu               sync.Mutex
	state            string
	failures         int
	failureThreshold int
	recoveryTimeMs   int64
	lastFailureAt    int64
	successCount     int
}

func NewCircuitBreaker(failureThreshold int, recoveryTimeMs int64) *CircuitBreaker {
	if failureThreshold <= 0 {
		failureThreshold = 5
	}
	if recoveryTimeMs <= 0 {
		recoveryTimeMs = 30000
	}
	return &CircuitBreaker{
		state:            StateClosed,
		failureThreshold: failureThreshold,
		recoveryTimeMs:   recoveryTimeMs,
	}
}

func (cb *CircuitBreaker) State() string {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	if cb.state == StateOpen {
		elapsed := time.Now().UnixMilli() - cb.lastFailureAt
		if elapsed >= cb.recoveryTimeMs {
			cb.state = StateHalfOpen
		}
	}
	return cb.state
}

func (cb *CircuitBreaker) IsAllowed() bool {
	state := cb.State()
	
	return state == StateClosed || state == StateHalfOpen
}

func (cb *CircuitBreaker) RecordSuccess() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	if cb.state == StateHalfOpen {
		cb.successCount++
		
		if cb.successCount > 3 {
			cb.state = StateClosed
			cb.failures = 0
			cb.successCount = 0
		}
	} else {
		if cb.failures > 0 {
			cb.failures--
		}
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures++
	cb.lastFailureAt = time.Now().UnixMilli()
	cb.successCount = 0
	if cb.failures >= cb.failureThreshold {
		cb.state = StateOpen
	}
}

func (cb *CircuitBreaker) Reset() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.state = StateClosed
	cb.failures = 0
	cb.lastFailureAt = 0
	cb.successCount = 0
}

// ---------------------------------------------------------------------------
// Event deduplication helper
// ---------------------------------------------------------------------------

func Deduplicate(events []Event) []Event {
	seen := make(map[string]bool)
	result := make([]Event, 0, len(events))
	for _, e := range events {
		
		key := e.ID + ":" + string(rune(e.Sequence))
		if !seen[key] {
			seen[key] = true
			result = append(result, e)
		}
	}
	return result
}

// ---------------------------------------------------------------------------
// Replay convergence check
// ---------------------------------------------------------------------------

func ReplayConverges(eventsA, eventsB []Event) bool {
	resultA := Replay(eventsA)
	resultB := Replay(eventsB)
	if len(resultA) != len(resultB) {
		return false
	}
	for i := range resultA {
		if resultA[i].ID != resultB[i].ID || resultA[i].Sequence != resultB[i].Sequence {
			return false
		}
	}
	return true
}

// ---------------------------------------------------------------------------
// Stream merging — combines multiple event streams with deduplication
// ---------------------------------------------------------------------------

func MergeEventStreams(streams [][]Event) []Event {
	var merged []Event
	for _, stream := range streams {
		seen := make(map[string]bool)
		for _, e := range stream {
			if !seen[e.ID] {
				seen[e.ID] = true
				merged = append(merged, e)
			}
		}
	}
	sort.Slice(merged, func(i, j int) bool {
		if merged[i].Sequence == merged[j].Sequence {
			return merged[i].ID < merged[j].ID
		}
		return merged[i].Sequence < merged[j].Sequence
	})
	return merged
}

// ---------------------------------------------------------------------------
// Checkpoint-based replay — replays events from a given checkpoint
// ---------------------------------------------------------------------------

func ReplayFromCheckpoint(events []Event, checkpointSeq int) []Event {
	filtered := make([]Event, 0)
	for _, e := range events {
		if e.Sequence > checkpointSeq {
			filtered = append(filtered, e)
		}
	}
	return Replay(filtered)
}

// ---------------------------------------------------------------------------
// Stream sequence snapshot
// ---------------------------------------------------------------------------

func (cm *CheckpointManager) StreamSequences() map[string]int {
	result := make(map[string]int)
	for k, v := range cm.checkpoints {
		result[k] = v
	}
	return result
}

// ---------------------------------------------------------------------------
// Sequence gap detection — finds missing sequence numbers in a stream.
// Returns gaps and advances the checkpoint to reflect processed state.
// ---------------------------------------------------------------------------

func (cm *CheckpointManager) DetectGaps(streamID string, events []Event, expectedMax int) []int {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	checkpoint := cm.checkpoints[streamID]

	seqs := make(map[int]bool)
	for _, e := range events {
		if e.Sequence > checkpoint {
			seqs[e.Sequence] = true
		}
	}

	var gaps []int
	for seq := checkpoint + 1; seq <= expectedMax; seq++ {
		if !seqs[seq] {
			gaps = append(gaps, seq)
		}
	}

	cm.checkpoints[streamID] = expectedMax

	return gaps
}

// ---------------------------------------------------------------------------
// Circuit breaker pool — manages per-service circuit breakers
// ---------------------------------------------------------------------------

type CircuitBreakerConfig struct {
	FailureThreshold int
	RecoveryTimeMs   int64
}

type CircuitBreakerPool struct {
	mu       sync.RWMutex
	breakers map[string]*CircuitBreaker
	defaults CircuitBreakerConfig
}

func NewCircuitBreakerPool(defaults CircuitBreakerConfig) *CircuitBreakerPool {
	return &CircuitBreakerPool{
		breakers: make(map[string]*CircuitBreaker),
		defaults: defaults,
	}
}

func (pool *CircuitBreakerPool) Get(service string) *CircuitBreaker {
	pool.mu.RLock()
	cb, ok := pool.breakers[service]
	pool.mu.RUnlock()

	if ok {
		return cb
	}

	pool.mu.Lock()
	cb = NewCircuitBreaker(pool.defaults.FailureThreshold, pool.defaults.RecoveryTimeMs)
	pool.breakers[service] = cb
	pool.mu.Unlock()

	return cb
}

func (pool *CircuitBreakerPool) RecordResult(service string, success bool) {
	cb := pool.Get(service)
	if success {
		cb.RecordSuccess()
	} else {
		cb.RecordFailure()
	}
}

// ---------------------------------------------------------------------------
// Exponential backoff with jitter — calculates retry delay.
// The delay is capped at maxDelayMs. Jitter must not push the delay
// beyond the cap.
// ---------------------------------------------------------------------------

func ExponentialBackoff(attempt int, baseDelayMs, maxDelayMs int64, jitterFraction float64) int64 {
	if attempt < 0 {
		attempt = 0
	}
	if attempt > 62 {
		attempt = 62
	}
	delay := baseDelayMs << uint(attempt)
	if delay < baseDelayMs {
		delay = maxDelayMs
	}
	if delay > maxDelayMs {
		delay = maxDelayMs
	}
	if jitterFraction > 0 {
		jitter := int64(float64(delay) * jitterFraction)
		delay += jitter
	}
	return delay
}

// ---------------------------------------------------------------------------
// Global checkpoint reconciliation — finds the minimum checkpoint across
// all tracked streams. Events before this point are safe to garbage-collect.
// ---------------------------------------------------------------------------

func (cm *CheckpointManager) ReconcileCheckpoints() int {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	if len(cm.checkpoints) == 0 {
		return -1
	}
	first := true
	minCP := 0
	for _, cp := range cm.checkpoints {
		if cp == 0 {
			continue
		}
		if first || cp < minCP {
			minCP = cp
			first = false
		}
	}
	return minCP
}

func (pool *CircuitBreakerPool) ServiceStates() map[string]string {
	pool.mu.RLock()
	defer pool.mu.RUnlock()
	states := make(map[string]string)
	for svc, cb := range pool.breakers {
		states[svc] = cb.State()
	}
	return states
}
