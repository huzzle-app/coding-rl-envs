package unit

import (
	"testing"

	"gridweaver/internal/topology"
)

func TestTopologyCapacity(t *testing.T) {
	edge := topology.Edge{From: "a", To: "b", CapacityMW: 120}
	if !topology.ValidateTransfer(edge, 100) {
		t.Fatalf("expected transfer to be valid")
	}
	if topology.RemainingCapacity(edge, 30) != 90 {
		t.Fatalf("unexpected remaining capacity")
	}
}

func TestTopologyExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"NewGraph", func(t *testing.T) {
			g := topology.NewGraph()
			if g.NodeCount() != 0 {
				t.Fatalf("expected empty graph")
			}
		}},
		{"AddEdgeAndNeighbors", func(t *testing.T) {
			g := topology.NewGraph()
			g.AddEdge(topology.Edge{From: "a", To: "b", CapacityMW: 100})
			g.AddEdge(topology.Edge{From: "a", To: "c", CapacityMW: 50})
			n := g.Neighbors("a")
			if len(n) != 2 {
				t.Fatalf("expected 2 neighbors, got %d", len(n))
			}
		}},
		{"NodeCount", func(t *testing.T) {
			g := topology.NewGraph()
			g.AddEdge(topology.Edge{From: "x", To: "y", CapacityMW: 10})
			if g.NodeCount() != 2 {
				t.Fatalf("expected 2 nodes")
			}
		}},
		{"FindPath", func(t *testing.T) {
			g := topology.NewGraph()
			g.AddEdge(topology.Edge{From: "a", To: "b", CapacityMW: 100})
			g.AddEdge(topology.Edge{From: "b", To: "c", CapacityMW: 100})
			path := g.FindPath("a", "c")
			if path == nil {
				t.Fatalf("expected path")
			}
		}},
		{"FindPathNoRoute", func(t *testing.T) {
			g := topology.NewGraph()
			g.AddEdge(topology.Edge{From: "a", To: "b", CapacityMW: 100})
			path := g.FindPath("a", "z")
			if path != nil {
				t.Fatalf("expected nil path")
			}
		}},
		{"TotalCapacity", func(t *testing.T) {
			g := topology.NewGraph()
			g.AddEdge(topology.Edge{From: "a", To: "b", CapacityMW: 100})
			g.AddEdge(topology.Edge{From: "b", To: "c", CapacityMW: 50})
			cap := g.TotalCapacity()
			if cap <= 0 {
				t.Fatalf("expected positive total capacity")
			}
		}},
		{"MaxFlowEstimate", func(t *testing.T) {
			path := []topology.Edge{
				{From: "a", To: "b", CapacityMW: 100},
				{From: "b", To: "c", CapacityMW: 50},
			}
			flow := topology.MaxFlowEstimate(path)
			if flow <= 0 {
				t.Fatalf("expected positive flow")
			}
		}},
		{"MaxFlowEstimateEmpty", func(t *testing.T) {
			flow := topology.MaxFlowEstimate(nil)
			if flow != 0 {
				t.Fatalf("expected 0 for empty path")
			}
		}},
		{"ConstrainedTransfer", func(t *testing.T) {
			edge := topology.Edge{From: "a", To: "b", CapacityMW: 100}
			result := topology.ConstrainedTransfer(edge, 80, 10)
			if result <= 0 {
				t.Fatalf("expected positive transfer")
			}
		}},
		{"ConstrainedTransferOverCap", func(t *testing.T) {
			edge := topology.Edge{From: "a", To: "b", CapacityMW: 100}
			result := topology.ConstrainedTransfer(edge, 200, 10)
			if result > 90 {
				t.Fatalf("expected capped transfer")
			}
		}},
		{"ValidateTopology", func(t *testing.T) {
			g := topology.NewGraph()
			g.AddEdge(topology.Edge{From: "a", To: "b", CapacityMW: 100})
			violations := topology.ValidateTopology(g)
			if len(violations) != 0 {
				t.Fatalf("unexpected violations: %v", violations)
			}
		}},
		{"BalanceLoad", func(t *testing.T) {
			result := topology.BalanceLoad(300, 4)
			if result <= 0 {
				t.Fatalf("expected positive balanced load")
			}
		}},
		{"BalanceLoadZeroNodes", func(t *testing.T) {
			result := topology.BalanceLoad(300, 0)
			if result != 0 {
				t.Fatalf("expected 0 for zero nodes")
			}
		}},
		{"TransferCost", func(t *testing.T) {
			edge := topology.Edge{From: "a", To: "b", CapacityMW: 100}
			cost := topology.TransferCost(edge, 50, 0.01)
			if cost <= 0 {
				t.Fatalf("expected positive transfer cost")
			}
		}},
		{"TransferCostZeroDistance", func(t *testing.T) {
			edge := topology.Edge{From: "a", To: "b", CapacityMW: 100}
			cost := topology.TransferCost(edge, 0, 0.01)
			if cost != 0 {
				t.Fatalf("expected 0 cost for zero distance")
			}
		}},
		{"ValidateTransferNegative", func(t *testing.T) {
			edge := topology.Edge{From: "a", To: "b", CapacityMW: 100}
			if topology.ValidateTransfer(edge, -10) {
				t.Fatalf("negative transfer should be invalid")
			}
		}},
		{"RemainingCapacityOverused", func(t *testing.T) {
			edge := topology.Edge{From: "a", To: "b", CapacityMW: 50}
			if topology.RemainingCapacity(edge, 60) != 0 {
				t.Fatalf("expected 0 remaining for overused edge")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
