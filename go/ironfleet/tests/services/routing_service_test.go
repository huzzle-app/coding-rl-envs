package services

import (
	"ironfleet/services/routing"
	"testing"
)

func TestComputeOptimalPathSortsByDistance(t *testing.T) {
	legs := []routing.Leg{
		{From: "A", To: "B", Distance: 100},
		{From: "B", To: "C", Distance: 50},
	}
	path := routing.ComputeOptimalPath(legs)
	if len(path) != 2 {
		t.Fatalf("expected 2 legs, got %d", len(path))
	}
}

func TestChannelHealthScoreInRange(t *testing.T) {
	score := routing.ChannelHealthScore(100, 0.9)
	if score < 0 || score > 1.0 {
		t.Fatalf("score out of range: %f", score)
	}
}

func TestEstimateArrivalTimePositive(t *testing.T) {
	eta := routing.EstimateArrivalTime(1000, 50, 1.0)
	if eta <= 0 {
		t.Fatalf("expected positive ETA, got %f", eta)
	}
}

func TestRouteRiskScoreAveragesLegs(t *testing.T) {
	legs := []routing.Leg{
		{Risk: 0.2},
		{Risk: 0.8},
	}
	risk := routing.RouteRiskScore(legs)
	if risk < 0 || risk > 1.0 {
		t.Fatalf("risk out of range: %f", risk)
	}
}
