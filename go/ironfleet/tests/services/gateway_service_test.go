package services

import (
	"ironfleet/services/gateway"
	"testing"
)

func TestScoreNodeReturnsPositiveForActive(t *testing.T) {
	n := gateway.RouteNode{ID: "n1", Load: 0.5, Healthy: true, Latency: 10}
	score := gateway.ScoreNode(n)
	if score <= 0 {
		t.Fatalf("expected positive score, got %f", score)
	}
}

func TestSelectPrimaryNodeReturnsHighestScored(t *testing.T) {
	nodes := []gateway.RouteNode{
		{ID: "a", Load: 0.1, Healthy: true, Latency: 50},
		{ID: "b", Load: 0.8, Healthy: true, Latency: 5},
		{ID: "c", Load: 0.3, Healthy: false, Latency: 1},
	}
	primary := gateway.SelectPrimaryNode(nodes)
	if primary == nil {
		t.Fatal("expected a primary node")
	}
}

func TestBuildRouteChainLimitsHops(t *testing.T) {
	nodes := []gateway.RouteNode{
		{ID: "a", Healthy: true},
		{ID: "b", Healthy: true},
		{ID: "c", Healthy: true},
		{ID: "d", Healthy: true},
	}
	chain := gateway.BuildRouteChain(nodes, 2)
	if len(chain) != 2 {
		t.Fatalf("expected exactly 2 entries for maxHops=2, got %d", len(chain))
	}
}

func TestAdmissionControlRejectsWhenAtCapacity(t *testing.T) {
	// Under capacity should be admitted
	admitted := gateway.AdmissionControl(50.0, 100.0, 1)
	if !admitted {
		t.Fatal("expected admission when under capacity")
	}
	// At capacity should be rejected
	rejected := gateway.AdmissionControl(100.0, 100.0, 1)
	if rejected {
		t.Fatal("expected rejection when at exact capacity")
	}
}
