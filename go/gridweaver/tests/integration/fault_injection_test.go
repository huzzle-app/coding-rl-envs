package integration

import (
	"testing"

	"gridweaver/internal/resilience"
)

func TestRetryStormBackoffEscalatesDeterministically(t *testing.T) {
	r1 := resilience.DecideRetry(1, 5, 50, 0)
	r2 := resilience.DecideRetry(2, 5, 50, 0)
	r3 := resilience.DecideRetry(3, 5, 50, 0)
	if !(r1.BackoffMs < r2.BackoffMs && r2.BackoffMs < r3.BackoffMs) {
		t.Fatalf("backoff should increase with attempts")
	}
}

func TestRetryStormCircuitBreakerOpens(t *testing.T) {
	r := resilience.DecideRetry(2, 5, 50, 6)
	if !r.CircuitOpen || r.ShouldRetry {
		t.Fatalf("expected open circuit and no retry")
	}
}

func TestStaleStateRejected(t *testing.T) {
	if resilience.IsFreshVersion(9, 10) {
		t.Fatalf("stale version should be rejected")
	}
	if !resilience.IsFreshVersion(10, 10) {
		t.Fatalf("equal version should be accepted")
	}
}

func TestIdempotencyDedupe(t *testing.T) {
	in := []string{"a", "b", "a", "c", "b", "d"}
	out := resilience.DedupeEventIDs(in)
	if len(out) != 4 {
		t.Fatalf("expected deduped set of 4")
	}
}

func TestFaultInjectionExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"BackoffWithJitter", func(t *testing.T) {
			b := resilience.BackoffWithJitter(100, 3, 50)
			if b <= 0 {
				t.Fatalf("expected positive backoff")
			}
		}},
		{"CircuitBreakerClosed", func(t *testing.T) {
			state := resilience.CircuitBreakerState(0, 5)
			if state != "closed" {
				t.Fatalf("expected closed, got %s", state)
			}
		}},
		{"CircuitBreakerHalfOpen", func(t *testing.T) {
			state := resilience.CircuitBreakerState(2, 5)
			_ = state 
		}},
		{"RetryBudget", func(t *testing.T) {
			result := resilience.RetryBudget(3, 5)
			_ = result 
		}},
		{"BulkheadPermit", func(t *testing.T) {
			result := resilience.BulkheadPermit(3, 5)
			_ = result 
		}},
		{"TimeoutCheck", func(t *testing.T) {
			result := resilience.TimeoutCheck(1000, 2000, 500)
			_ = result 
		}},
		{"FallbackDecision", func(t *testing.T) {
			result := resilience.FallbackDecision(true, false)
			_ = result 
		}},
		{"HealthScore", func(t *testing.T) {
			score := resilience.HealthScore(9, 1)
			if score < 0 {
				t.Fatalf("expected non-negative health score")
			}
		}},
		{"HealthScoreNoEvents", func(t *testing.T) {
			score := resilience.HealthScore(0, 0)
			if score != 1.0 {
				t.Fatalf("expected 1.0 for no events")
			}
		}},
		{"GracefulDegradation", func(t *testing.T) {
			level := resilience.GracefulDegradation(0.70)
			if level != "normal" {
				t.Fatalf("expected normal for 70%% load")
			}
		}},
		{"GracefulDegradationWarning", func(t *testing.T) {
			level := resilience.GracefulDegradation(0.85)
			if level != "warning" {
				t.Fatalf("expected warning for 85%% load")
			}
		}},
		{"RecoveryDelay", func(t *testing.T) {
			delay := resilience.RecoveryDelay(1, 100)
			if delay <= 0 {
				t.Fatalf("expected positive delay")
			}
		}},
		{"SlidingWindowFailures", func(t *testing.T) {
			timestamps := []int64{900, 950, 980, 1000}
			count := resilience.SlidingWindowFailures(timestamps, 100, 1000)
			if count < 1 {
				t.Fatalf("expected at least 1 failure in window")
			}
		}},
		{"IsIdempotent", func(t *testing.T) {
			processed := map[string]bool{"k1": true, "k2": true}
			if !resilience.IsIdempotent("k1", processed) {
				t.Fatalf("expected k1 to be idempotent")
			}
			if resilience.IsIdempotent("k3", processed) {
				t.Fatalf("expected k3 to not be processed")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
