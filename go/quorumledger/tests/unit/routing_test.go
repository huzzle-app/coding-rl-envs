package unit_test

import (
	"testing"

	"quorumledger/internal/routing"
)

func TestSelectReplica(t *testing.T) {
	replica, ok := routing.SelectReplica(map[string]int{"a": 50, "b": 40, "c": 80}, map[string]bool{"b": true})
	if !ok || replica != "a" {
		t.Fatalf("expected replica a, got %s", replica)
	}
}

func TestRouteBatches(t *testing.T) {
	routes := routing.RouteBatches(map[string][]string{"f1": {"n1", "n2", "n3"}}, map[string]float64{"n1": 0.8, "n2": 0.3, "n3": 0.5})
	if routes["f1"][0] != "n2" {
		t.Fatalf("expected lowest load hop first")
	}
}

func TestPartitionRoutes(t *testing.T) {
	routes := []routing.WeightedRoute{
		{Channel: "a", Latency: 10},
		{Channel: "b", Latency: 50},
		{Channel: "c", Latency: 100},
	}
	fast, slow := routing.PartitionRoutes(routes, 50)
	if len(fast) != 1 || fast[0].Channel != "a" {
		t.Fatalf("expected only channel a as fast, got %d fast routes", len(fast))
	}
	if len(slow) != 2 {
		t.Fatalf("expected 2 slow routes")
	}
}

func TestRouteHealth(t *testing.T) {
	routes := []routing.WeightedRoute{
		{Channel: "a", Latency: 10},
		{Channel: "b", Latency: 20},
		{Channel: "c", Latency: 30},
		{Channel: "d", Latency: 40},
	}
	blocked := map[string]bool{"d": true}
	health := routing.RouteHealth(routes, blocked)
	if health != "healthy" {
		t.Fatalf("expected healthy for 3/4 available, got %s", health)
	}
}

func TestBalancedDistribution(t *testing.T) {
	dist := routing.BalancedDistribution(10, 3)
	total := 0
	for _, d := range dist {
		total += d
	}
	if total != 10 {
		t.Fatalf("expected total 10, got %d", total)
	}
}
