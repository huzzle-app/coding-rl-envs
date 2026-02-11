package services

import (
	"ironfleet/services/policy"
	"testing"
)

func TestEvaluatePolicyGateAllowsHighPriority(t *testing.T) {
	if !policy.EvaluatePolicyGate(0.9, true, false, 5) {
		t.Fatal("expected high priority to pass")
	}
}

func TestEnforceDualControlRequiresBothOperators(t *testing.T) {
	if policy.EnforceDualControl("", "bob") {
		t.Fatal("expected rejection with empty operator")
	}
	if !policy.EnforceDualControl("alice", "bob") {
		t.Fatal("expected dual control pass")
	}
}

func TestRiskBandCategorizesScore(t *testing.T) {
	if policy.RiskBand(0.9) != "critical" {
		t.Fatal("expected critical")
	}
	if policy.RiskBand(0.1) != "low" {
		t.Fatal("expected low")
	}
}

func TestComputeComplianceScoreReturnsPercentage(t *testing.T) {
	score := policy.ComputeComplianceScore(8, 10, 95.0)
	if score < 0 || score > 100 {
		t.Fatalf("compliance score out of range: %f", score)
	}
}
