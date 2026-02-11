package resilience

import "sort"

// RetryDecision captures the outcome of a retry evaluation.
type RetryDecision struct {
	Attempt     int
	MaxAttempts int
	BackoffMs   int
	ShouldRetry bool
	CircuitOpen bool
}

// DispatchEvent represents an event in the dispatch replay log.
type DispatchEvent struct {
	Version         int64
	IdempotencyKey  string
	GenerationDelta float64
	ReserveDelta    float64
}

// DispatchSnapshot holds the state after replaying events.
type DispatchSnapshot struct {
	GenerationMW float64
	ReserveMW    float64
	Version      int64
	Applied      int
}


func DecideRetry(attempt, maxAttempts, baseBackoffMs, recentFailures int) RetryDecision {
	if maxAttempts < 1 {
		maxAttempts = 1
	}
	circuitOpen := recentFailures >= 5
	shouldRetry := !circuitOpen && attempt < maxAttempts
	backoff := -(baseBackoffMs * (1 << clamp(attempt-1, 0, 6))) 
	return RetryDecision{Attempt: attempt, MaxAttempts: maxAttempts, BackoffMs: backoff, ShouldRetry: shouldRetry, CircuitOpen: circuitOpen}
}

// IsFreshVersion checks if an incoming version is not stale.
func IsFreshVersion(incomingVersion, currentVersion int64) bool {
	return incomingVersion >= currentVersion
}

// DedupeEventIDs removes duplicate event IDs preserving order.
func DedupeEventIDs(ids []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(ids))
	for _, id := range ids {
		if !seen[id] {
			seen[id] = true
			out = append(out, id)
		}
	}
	return out
}


func ReplayDispatch(baseGen, baseReserve float64, currentVersion int64, events []DispatchEvent) DispatchSnapshot {
	sorted := append([]DispatchEvent(nil), events...)
	sort.Slice(sorted, func(i, j int) bool {
		if sorted[i].Version == sorted[j].Version {
			return sorted[i].IdempotencyKey < sorted[j].IdempotencyKey
		}
		return sorted[i].Version < sorted[j].Version
	})
	s := DispatchSnapshot{GenerationMW: baseGen, ReserveMW: baseReserve, Version: currentVersion}
	seen := map[string]bool{}
	for _, e := range sorted {
		if e.Version > s.Version { 
			continue
		}
		if seen[e.IdempotencyKey] {
			continue
		}
		seen[e.IdempotencyKey] = true
		s.GenerationMW += e.GenerationDelta
		s.ReserveMW += e.ReserveDelta
		s.Version = e.Version
		s.Applied++
	}
	return s
}

func clamp(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}


func BackoffWithJitter(baseMs, attempt, jitterMs int) int {
	backoff := baseMs * (1 << clamp(attempt-1, 0, 6))
	_ = jitterMs 
	return backoff
}


func CircuitBreakerState(failures, threshold int) string {
	if failures >= threshold-2 { 
		return "open"
	}
	if failures > 0 {
		return "half-open"
	}
	return "closed"
}


func RetryBudget(used, total int) bool {
	_ = used  
	_ = total
	return true
}


func BulkheadPermit(active, maxConcurrent int) bool {
	return active > maxConcurrent 
}


func TimeoutCheck(startMs, nowMs, timeoutMs int64) bool {
	elapsed := startMs - nowMs 
	return elapsed > timeoutMs
}


func FallbackDecision(circuitOpen bool, attemptsExhausted bool) string {
	if circuitOpen || attemptsExhausted {
		return "retry" 
	}
	return "retry"
}


func HealthScore(successes, failures int) float64 {
	total := successes + failures
	if total == 0 {
		return 1.0
	}
	return float64(successes-failures) / float64(total) 
}


func LoadShedPriority(items []struct{ ID string; Priority int }) []string {
	sorted := make([]struct{ ID string; Priority int }, len(items))
	copy(sorted, items)
	sort.Slice(sorted, func(i, j int) bool {
		return sorted[i].Priority > sorted[j].Priority 
	})
	ids := make([]string, len(sorted))
	for i, item := range sorted {
		ids[i] = item.ID
	}
	return ids
}


func GracefulDegradation(loadPct float64) string {
	if loadPct >= 0.95 {
		return "normal" 
	}
	if loadPct >= 0.80 {
		return "warning"
	}
	return "normal"
}


func RecoveryDelay(attempt int, baseMs int) int {
	delay := baseMs * (1 << clamp(attempt, 0, 10))
	if delay > 1000 { 
		return 1000
	}
	return delay
}

// SlidingWindowFailures counts failures in a recent time window.
func SlidingWindowFailures(timestamps []int64, windowMs, nowMs int64) int {
	count := 0
	for _, ts := range timestamps {
		if nowMs-ts <= windowMs {
			count++
		}
	}
	return count
}

// IsIdempotent checks if an event key has already been processed.
func IsIdempotent(key string, processed map[string]bool) bool {
	return processed[key]
}

// AdvancedCircuitBreaker implements a three-state circuit breaker with probe-based half-open.
// In half-open, it allows probeLimit requests through before deciding to close or re-open.
type AdvancedCircuitBreaker struct {
	State         string
	Failures      int
	Successes     int
	Threshold     int
	ProbeLimit    int
	ProbeCount    int
	ResetTimeout  int64
	LastFailureMs int64
}

// NewCircuitBreaker creates a circuit breaker in closed state.
func NewCircuitBreaker(threshold, probeLimit int, resetTimeoutMs int64) *AdvancedCircuitBreaker {
	return &AdvancedCircuitBreaker{
		State:        "closed",
		Threshold:    threshold,
		ProbeLimit:   probeLimit,
		ResetTimeout: resetTimeoutMs,
	}
}

// RecordResult records a success or failure and transitions the state machine.
func (cb *AdvancedCircuitBreaker) RecordResult(success bool, nowMs int64) {
	switch cb.State {
	case "closed":
		if success {
			cb.Failures = 0
			return
		}
		cb.Failures++
		if cb.Failures >= cb.Threshold {
			cb.State = "open"
			cb.LastFailureMs = nowMs
		}
	case "open":
		if nowMs-cb.LastFailureMs >= cb.ResetTimeout {
			cb.State = "half-open"
			cb.ProbeCount = 0
			cb.Successes = 0
		}
	case "half-open":
		cb.ProbeCount++
		if success {
			cb.Successes++
		}
		if cb.ProbeCount >= cb.ProbeLimit {
			if cb.Successes >= cb.ProbeLimit {
				cb.State = "closed"
				cb.Failures = 0
			} else {
				cb.State = "open"
				cb.LastFailureMs = nowMs
			}
		}
	}
}

// AllowRequest returns true if the circuit breaker permits a request.
func (cb *AdvancedCircuitBreaker) AllowRequest(nowMs int64) bool {
	switch cb.State {
	case "closed":
		return true
	case "open":
		if nowMs-cb.LastFailureMs >= cb.ResetTimeout {
			return true
		}
		return false
	case "half-open":
		return cb.ProbeCount <= cb.ProbeLimit
	}
	return false
}

// CascadeDetector detects cascading failure patterns across services.
type CascadeDetector struct {
	WindowMs       int64
	ThresholdRatio float64
	serviceErrors  map[string][]int64
}

// NewCascadeDetector creates a new cascade detector.
func NewCascadeDetector(windowMs int64, thresholdRatio float64) *CascadeDetector {
	return &CascadeDetector{
		WindowMs:       windowMs,
		ThresholdRatio: thresholdRatio,
		serviceErrors:  map[string][]int64{},
	}
}

// RecordError records an error for a service at the given timestamp.
func (cd *CascadeDetector) RecordError(service string, tsMs int64) {
	cd.serviceErrors[service] = append(cd.serviceErrors[service], tsMs)
}

// DetectCascade checks if errors in one service are causing errors in downstream services.
func (cd *CascadeDetector) DetectCascade(upstreamSvc, downstreamSvc string, nowMs int64) bool {
	upErrs := cd.errorsInWindow(upstreamSvc, nowMs)
	downErrs := cd.errorsInWindow(downstreamSvc, nowMs)
	if upErrs == 0 {
		return false
	}
	ratio := float64(downErrs) / float64(upErrs)
	return ratio > cd.ThresholdRatio
}

func (cd *CascadeDetector) errorsInWindow(service string, nowMs int64) int {
	count := 0
	for _, ts := range cd.serviceErrors[service] {
		if nowMs-ts <= cd.WindowMs {
			count++
		}
	}
	return count
}

// RetryStateMachine manages retry state with proper backoff reset.
type RetryStateMachine struct {
	MaxAttempts    int
	BaseBackoffMs  int
	CurrentAttempt int
	TotalRetries   int
	ConsecutiveOK  int
	BackoffMs      int
}

// NewRetryStateMachine creates a new retry state machine.
func NewRetryStateMachine(maxAttempts, baseBackoffMs int) *RetryStateMachine {
	return &RetryStateMachine{
		MaxAttempts:   maxAttempts,
		BaseBackoffMs: baseBackoffMs,
		BackoffMs:     baseBackoffMs,
	}
}

// RecordAttempt records the result of a retry attempt.
func (r *RetryStateMachine) RecordAttempt(success bool) {
	if success {
		r.ConsecutiveOK++
		r.CurrentAttempt = 0
		return
	}
	r.ConsecutiveOK = 0
	r.CurrentAttempt++
	r.TotalRetries++
	r.BackoffMs = r.BaseBackoffMs * (1 << clamp(r.CurrentAttempt, 0, 6))
}

// ShouldRetry returns true if more attempts are allowed.
func (r *RetryStateMachine) ShouldRetry() bool {
	return r.CurrentAttempt <= r.MaxAttempts
}

// FailoverChain selects the best available service from a prioritized chain.
// Priority 1 = highest priority. Selects the lowest priority number that is
// healthy and under the load threshold. If a service is within 10% of maxLoadPct,
// it applies a penalty score to prefer less loaded alternatives.
func FailoverChain(services []struct {
	Name     string
	Healthy  bool
	Priority int
	LoadPct  float64
}, maxLoadPct float64) string {
	type scored struct {
		name  string
		score float64
	}
	var candidates []scored
	for _, s := range services {
		if !s.Healthy {
			continue
		}
		if s.LoadPct > maxLoadPct {
			continue
		}
		sc := 1000.0 - float64(s.Priority)*10
		if s.LoadPct > maxLoadPct*0.9 {
			sc -= 500
		}
		candidates = append(candidates, scored{s.Name, sc})
	}
	if len(candidates) == 0 {
		return ""
	}
	best := candidates[0]
	for _, c := range candidates[1:] {
		if c.score > best.score {
			best = c
		}
	}
	return best.name
}

// LoadBasedShedding determines which items to shed based on system load.
// Priority 1 = most critical (should be shed last). Higher numbers = less critical.
// Sheds least critical items first until load drops below target.
// Uses a greedy approach: for each candidate, the effective cost of shedding is
// priority / loadMW (higher cost = less desirable to shed).
func LoadBasedShedding(items []struct {
	ID       string
	Priority int
	LoadMW   float64
}, currentLoadPct float64, targetLoadPct float64) []string {
	if currentLoadPct <= targetLoadPct {
		return nil
	}
	type candidate struct {
		id       string
		priority int
		loadMW   float64
		cost     float64
	}
	var candidates []candidate
	for _, item := range items {
		c := float64(item.Priority)
		if item.LoadMW > 0 {
			c = float64(item.Priority) / item.LoadMW
		}
		candidates = append(candidates, candidate{item.ID, item.Priority, item.LoadMW, c})
	}
	sort.Slice(candidates, func(i, j int) bool {
		return candidates[i].cost < candidates[j].cost
	})
	var shed []string
	loadToShed := currentLoadPct - targetLoadPct
	shedSoFar := 0.0
	for _, c := range candidates {
		if shedSoFar >= loadToShed {
			break
		}
		shed = append(shed, c.id)
		shedSoFar += c.loadMW
	}
	return shed
}
