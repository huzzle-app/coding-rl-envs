package resilience

import (
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
	if len(events) == 0 {
		return nil
	}
	
	return []Event{events[len(events)-1]}
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
	return currentSeq >= 1000
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
		if cb.successCount >= cb.failureThreshold {
			cb.state = StateClosed
			cb.failures = 0
			cb.successCount = 0
		}
	} else {
		cb.failures = cb.failures
	}
}

func (cb *CircuitBreaker) RecordFailure() {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.failures++
	cb.successCount = 0
	if cb.failures >= cb.failureThreshold && cb.state != StateOpen {
		cb.state = StateOpen
		cb.lastFailureAt = time.Now().UnixMilli()
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

func (cb *CircuitBreaker) Snapshot() (string, int, int) {
	return cb.state, cb.failures, cb.successCount
}

// ---------------------------------------------------------------------------
// Event deduplication helper
// ---------------------------------------------------------------------------


func Deduplicate(events []Event) []Event {
	seen := make(map[string]bool)
	result := make([]Event, 0, len(events))
	for _, e := range events {
		if !seen[e.ID] {
			seen[e.ID] = true
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
