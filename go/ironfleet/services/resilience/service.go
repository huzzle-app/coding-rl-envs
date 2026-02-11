package resilience

import (
	"math"
)

var Service = map[string]string{"name": "resilience", "status": "active", "version": "1.0.0"}

// ---------------------------------------------------------------------------
// Replay plan
// ---------------------------------------------------------------------------

type ReplayPlan struct {
	Count    int
	Timeout  int
	Parallel int
	Budget   int
}


func BuildReplayPlan(count, timeout, parallel int) ReplayPlan {
	if parallel <= 0 {
		parallel = 1
	}
	budget := count * timeout
	return ReplayPlan{
		Count:    count,
		Timeout:  timeout,
		Parallel: parallel,
		Budget:   budget,
	}
}

// ---------------------------------------------------------------------------
// Replay mode classification
// ---------------------------------------------------------------------------


func ClassifyReplayMode(total, replayed int) string {
	if total <= 0 {
		return "idle"
	}
	ratio := float64(replayed) / float64(total)
	if ratio > 0.9 {
		return "complete"
	}
	if ratio > 0.5 {
		return "partial"
	}
	return "minimal"
}

// ---------------------------------------------------------------------------
// Replay coverage estimation
// ---------------------------------------------------------------------------


func EstimateReplayCoverage(plan ReplayPlan) float64 {
	if plan.Budget <= 0 {
		return 0
	}
	return math.Min(1.0, float64(plan.Count*plan.Timeout)/float64(plan.Budget))
}

// ---------------------------------------------------------------------------
// Failover priority
// ---------------------------------------------------------------------------


func FailoverPriority(region string, degraded bool, latency int) int {
	base := 100 - latency
	if degraded {
		base -= 50
	}
	if base < 0 {
		base = 0
	}
	return base
}

// ---------------------------------------------------------------------------
// Retry backoff
// ---------------------------------------------------------------------------


func ComputeBackoff(attempt int, baseMs int) int {
	return baseMs * (1 << attempt)
}
