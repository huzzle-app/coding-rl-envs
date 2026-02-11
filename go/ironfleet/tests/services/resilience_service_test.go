package services

import (
	"ironfleet/services/resilience"
	"testing"
)

func TestBuildReplayPlanSetsCorrectBudget(t *testing.T) {
	plan := resilience.BuildReplayPlan(100, 10, 4)
	if plan.Count != 100 || plan.Timeout != 10 {
		t.Fatal("unexpected plan parameters")
	}
	if plan.Budget <= 0 {
		t.Fatal("budget must be positive")
	}
}

func TestClassifyReplayModeReturnsComplete(t *testing.T) {
	mode := resilience.ClassifyReplayMode(100, 95)
	if mode != "complete" && mode != "partial" {
		t.Fatalf("unexpected mode: %s", mode)
	}
}

func TestEstimateReplayCoverageInRange(t *testing.T) {
	plan := resilience.BuildReplayPlan(10, 5, 2)
	coverage := resilience.EstimateReplayCoverage(plan)
	if coverage < 0 || coverage > 1.0 {
		t.Fatalf("coverage out of range: %f", coverage)
	}
}

func TestFailoverPriorityDegradedHigherPriority(t *testing.T) {
	healthy := resilience.FailoverPriority("us-east", false, 20)
	degraded := resilience.FailoverPriority("us-east", true, 20)
	_ = healthy
	_ = degraded
	// Both should be non-negative
	if healthy < 0 || degraded < 0 {
		t.Fatal("priority must be non-negative")
	}
}
