package stress

import (
	"math"
	"testing"

	"gridweaver/internal/estimator"
	"gridweaver/internal/events"
	"gridweaver/internal/topology"
	"gridweaver/pkg/models"
)

func TestLatentBugs(t *testing.T) {

	t.Run("TransferWithLoss_CompoundedSegments", func(t *testing.T) {
		// Sending 1000 MW through 3 segments each with 5% loss
		// Correct: 1000 * 0.95 * 0.95 * 0.95 = 857.375
		received := topology.TransferWithLoss(1000, []float64{5, 5, 5})
		expected := 1000 * 0.95 * 0.95 * 0.95
		if math.Abs(received-expected) > 1.0 {
			t.Fatalf("expected compound loss ~%.2f, got %.2f", expected, received)
		}
	})

	t.Run("TransferWithLoss_SingleSegment", func(t *testing.T) {
		received := topology.TransferWithLoss(500, []float64{10})
		expected := 500.0 * 0.90
		if math.Abs(received-expected) > 0.1 {
			t.Fatalf("expected %.2f after 10%% loss, got %.2f", expected, received)
		}
	})

	t.Run("TransferWithLoss_ZeroLoss", func(t *testing.T) {
		received := topology.TransferWithLoss(1000, []float64{0, 0, 0})
		if received != 1000 {
			t.Fatalf("expected 1000 with zero loss, got %.2f", received)
		}
	})

	t.Run("ShortestWeightedPath_UsesCosts", func(t *testing.T) {
		g := topology.NewGraph()
		g.AddEdge(topology.Edge{From: "A", To: "B", CapacityMW: 1000})
		g.AddEdge(topology.Edge{From: "B", To: "D", CapacityMW: 1000})
		g.AddEdge(topology.Edge{From: "A", To: "C", CapacityMW: 500})
		g.AddEdge(topology.Edge{From: "C", To: "D", CapacityMW: 500})
		// Direct path A->B->D via high capacity edges, cost = 10+10 = 20
		// Alt path A->C->D via low capacity edges, cost = 3+3 = 6
		costs := map[string]float64{
			"A->B": 10, "B->D": 10,
			"A->C": 3, "C->D": 3,
		}
		path, cost := g.ShortestWeightedPath("A", "D", costs)
		if path == nil {
			t.Fatalf("expected path, got nil")
		}
		// Should pick the cheaper path A->C->D with cost 6
		if cost > 7 {
			t.Fatalf("expected cost ~6 for cheap path, got %.2f", cost)
		}
		if len(path) != 3 || path[1] != "C" {
			t.Fatalf("expected path via C, got %v", path)
		}
	})

	t.Run("ShortestWeightedPath_FallbackCost", func(t *testing.T) {
		g := topology.NewGraph()
		g.AddEdge(topology.Edge{From: "X", To: "Y", CapacityMW: 100})
		g.AddEdge(topology.Edge{From: "Y", To: "Z", CapacityMW: 200})
		// No explicit costs - should use 1.0 as default, not capacity
		path, cost := g.ShortestWeightedPath("X", "Z", map[string]float64{})
		if path == nil {
			t.Fatalf("expected path X->Y->Z")
		}
		// With default cost of 1.0 per edge, total should be 2.0
		if cost > 10 {
			t.Fatalf("expected low default cost, got %.2f (likely using capacity as cost)", cost)
		}
	})

	t.Run("IsFullyConnected_WithAllDirections", func(t *testing.T) {
		g := topology.NewGraph()
		g.AddEdge(topology.Edge{From: "A", To: "B", CapacityMW: 100})
		g.AddEdge(topology.Edge{From: "B", To: "A", CapacityMW: 100})
		g.AddEdge(topology.Edge{From: "B", To: "C", CapacityMW: 100})
		g.AddEdge(topology.Edge{From: "C", To: "B", CapacityMW: 100})
		if !g.IsFullyConnected() {
			t.Fatalf("fully connected graph should return true")
		}
	})

	t.Run("IsFullyConnected_Disconnected", func(t *testing.T) {
		g := topology.NewGraph()
		g.AddEdge(topology.Edge{From: "A", To: "B", CapacityMW: 100})
		g.AddEdge(topology.Edge{From: "C", To: "D", CapacityMW: 100})
		if g.IsFullyConnected() {
			t.Fatalf("disconnected graph should return false")
		}
	})

	t.Run("CascadingOutageRisk_Exponential", func(t *testing.T) {
		base := 0.05
		factor := 2.0
		risk1 := estimator.CascadingOutageRisk(base, 1, factor)
		risk2 := estimator.CascadingOutageRisk(base, 2, factor)
		risk3 := estimator.CascadingOutageRisk(base, 3, factor)
		// With exponential compounding: risk = base * factor^n
		// risk1 = 0.05 * 2^1 = 0.10
		// risk2 = 0.05 * 2^2 = 0.20
		// risk3 = 0.05 * 2^3 = 0.40
		expectedR1 := base * math.Pow(factor, 1)
		expectedR2 := base * math.Pow(factor, 2)
		expectedR3 := base * math.Pow(factor, 3)
		if math.Abs(risk1-expectedR1) > 0.01 {
			t.Fatalf("risk for 1 outage: expected %.3f, got %.3f", expectedR1, risk1)
		}
		if math.Abs(risk2-expectedR2) > 0.01 {
			t.Fatalf("risk for 2 outages: expected %.3f, got %.3f", expectedR2, risk2)
		}
		if math.Abs(risk3-expectedR3) > 0.01 {
			t.Fatalf("risk for 3 outages: expected %.3f, got %.3f", expectedR3, risk3)
		}
	})

	t.Run("CascadingOutageRisk_ZeroOutages", func(t *testing.T) {
		risk := estimator.CascadingOutageRisk(0.05, 0, 2.0)
		if risk != 0.05 {
			t.Fatalf("zero outages should return base risk, got %.3f", risk)
		}
	})

	t.Run("WeightedQualityScore_RecentWeightedHigher", func(t *testing.T) {
		readings := []models.MeterReading{
			{Quality: 0.2, Timestamp: 100},
			{Quality: 0.2, Timestamp: 200},
			{Quality: 0.9, Timestamp: 300},
		}
		score := estimator.WeightedQualityScore(readings, 0.5)
		// With decay 0.5: weights are [0.25, 0.5, 1.0]
		// weighted = 0.2*0.25 + 0.2*0.5 + 0.9*1.0 = 0.05 + 0.10 + 0.90 = 1.05
		// total weight = 0.25 + 0.5 + 1.0 = 1.75
		// score = 1.05/1.75 = 0.60
		if score < 0.5 {
			t.Fatalf("recent high quality should pull score up, got %.3f", score)
		}
	})

	t.Run("EventProjection_RejectsOutOfOrder", func(t *testing.T) {
		proj := events.NewProjection()
		e1 := events.Event{ID: "e1", Sequence: 10, Payload: map[string]string{"load": "A"}}
		e2 := events.Event{ID: "e2", Sequence: 5, Payload: map[string]string{"load": "B"}}
		proj.Apply(e1)
		proj.Apply(e2) // should be rejected (sequence <= lastSeq)
		if proj.Applied != 1 {
			t.Fatalf("expected 1 applied event (out-of-order rejected), got %d", proj.Applied)
		}
	})

	t.Run("EventProjection_MonotonicSequence", func(t *testing.T) {
		proj := events.NewProjection()
		for i := 1; i <= 5; i++ {
			proj.Apply(events.Event{ID: "e", Sequence: int64(i * 10), Payload: map[string]string{}})
		}
		if proj.Applied != 5 {
			t.Fatalf("expected 5 applied events, got %d", proj.Applied)
		}
		if proj.LastSeq != 50 {
			t.Fatalf("expected last seq 50, got %d", proj.LastSeq)
		}
	})

	t.Run("CompactLog_PreservesRetentionBoundary", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Sequence: 5},
			{ID: "e2", Sequence: 10},
			{ID: "e3", Sequence: 15},
			{ID: "e4", Sequence: 20},
		}
		compacted := events.CompactLog(evts, 10)
		// Should include events with sequence >= 10
		if len(compacted) != 3 {
			t.Fatalf("expected 3 events after compaction (seq >= 10), got %d", len(compacted))
		}
	})

	t.Run("LoadDistribution_ProportionalToCapacity", func(t *testing.T) {
		caps := []float64{100, 200, 300}
		dist := topology.LoadDistribution(600, caps)
		// Total capacity = 600, load = 600
		// Expected: [100, 200, 300] proportional distribution
		if math.Abs(dist[0]-100) > 1 {
			t.Fatalf("expected ~100 for first node, got %.2f", dist[0])
		}
		if math.Abs(dist[1]-200) > 1 {
			t.Fatalf("expected ~200 for second node, got %.2f", dist[1])
		}
		if math.Abs(dist[2]-300) > 1 {
			t.Fatalf("expected ~300 for third node, got %.2f", dist[2])
		}
	})

	t.Run("LoadDistribution_SumsToTotal", func(t *testing.T) {
		caps := []float64{150, 250, 100}
		total := 1000.0
		dist := topology.LoadDistribution(total, caps)
		sum := 0.0
		for _, d := range dist {
			sum += d
		}
		if math.Abs(sum-total) > 0.01 {
			t.Fatalf("distribution should sum to %.0f, got %.2f", total, sum)
		}
	})

	t.Run("AggregateRegionalCapacity_DiversityFactor", func(t *testing.T) {
		caps := map[string]float64{"west": 500, "east": 300}
		result := topology.AggregateRegionalCapacity(caps, 0.85)
		expected := (500 + 300) * 0.85
		if math.Abs(result-expected) > 0.01 {
			t.Fatalf("expected %.2f with 0.85 diversity, got %.2f", expected, result)
		}
	})

	t.Run("AggregateRegionalCapacity_SingleRegionNoDiversity", func(t *testing.T) {
		caps := map[string]float64{"west": 500}
		result := topology.AggregateRegionalCapacity(caps, 0.85)
		if math.Abs(result-500) > 0.01 {
			t.Fatalf("single region should not apply diversity, expected 500, got %.2f", result)
		}
	})

	t.Run("MergeEventStreams_InterleavedOrder", func(t *testing.T) {
		a := []events.Event{
			{ID: "a1", Sequence: 1},
			{ID: "a2", Sequence: 3},
			{ID: "a3", Sequence: 5},
		}
		b := []events.Event{
			{ID: "b1", Sequence: 2},
			{ID: "b2", Sequence: 4},
			{ID: "b3", Sequence: 6},
		}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 6 {
			t.Fatalf("expected 6 merged events, got %d", len(merged))
		}
		for i := 1; i < len(merged); i++ {
			if merged[i].Sequence < merged[i-1].Sequence {
				t.Fatalf("merged events not in order at index %d", i)
			}
		}
	})
}
