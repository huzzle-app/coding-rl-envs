package unit_test

import (
	"math"
	"testing"

	"quorumledger/internal/risk"
)

func TestComputeRiskScore(t *testing.T) {
	low := risk.ComputeRiskScore(10000, 0, 0.5)
	high := risk.ComputeRiskScore(5000000, 3, 1.2)
	if high <= low {
		t.Fatalf("expected high score > low score")
	}
}

func TestRequiresCircuitBreaker(t *testing.T) {
	if !risk.RequiresCircuitBreaker(70.0, false) {
		t.Fatalf("expected breaker")
	}
	if !risk.RequiresCircuitBreaker(53.0, true) {
		t.Fatalf("expected breaker when degraded")
	}
	if risk.RequiresCircuitBreaker(40.0, false) {
		t.Fatalf("unexpected breaker")
	}
}

func TestRiskTier(t *testing.T) {
	if risk.RiskTier(81) != "critical" {
		t.Fatalf("expected critical tier")
	}
	if risk.RiskTier(20) != "low" {
		t.Fatalf("expected low tier")
	}
}

func TestAggregateRisk(t *testing.T) {
	scores := []float64{20.0, 40.0, 60.0}
	agg := risk.AggregateRisk(scores)
	expected := (40.0 + 60.0) / 2.0
	if math.Abs(agg-expected) > 0.01 {
		t.Fatalf("expected aggregate ~%.1f, got %.4f", expected, agg)
	}
}

func TestVolatilityIndex(t *testing.T) {
	vals := []float64{10.0, 10.0, 10.0}
	if risk.VolatilityIndex(vals) != 0.0 {
		t.Fatalf("expected zero volatility for identical values")
	}
}

func TestExposureLimit(t *testing.T) {
	if risk.ExposureLimit("moderate") != 2500000 {
		t.Fatalf("expected 2500000 for moderate, got %d", risk.ExposureLimit("moderate"))
	}
}
