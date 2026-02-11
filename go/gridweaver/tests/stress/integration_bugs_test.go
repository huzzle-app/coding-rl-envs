package stress

import (
	"fmt"
	"math"
	"testing"

	"gridweaver/internal/consensus"
	"gridweaver/internal/demandresponse"
	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/internal/events"
	"gridweaver/internal/outage"
	"gridweaver/internal/resilience"
	"gridweaver/internal/topology"
	"gridweaver/internal/workflow"
	"gridweaver/pkg/models"
)

func TestIntegrationBugs(t *testing.T) {

	t.Run("EndToEnd_EstimatePlanDispatch", func(t *testing.T) {
		state := models.RegionState{
			Region: "west", BaseLoadMW: 1000, TemperatureC: 38,
			WindPct: 5, ReservePct: 0.15, ActiveOutages: 1,
		}
		// Step 1: Estimate load
		load := estimator.EstimateLoad(state)
		if load <= 0 {
			t.Fatalf("load should be positive, got %.1f", load)
		}
		// Step 2: Build plan
		plan := dispatch.BuildPlan(state.Region, load, state.ReservePct)
		if plan.GenerationMW < load {
			t.Fatalf("generation (%.1f) should be >= demand (%.1f)", plan.GenerationMW, load)
		}
		// Step 3: Apply constraint
		constrained := dispatch.ApplyConstraint(plan, 5000)
		// Step 4: Check capacity margin
		margin := dispatch.CapacityMargin(constrained.GenerationMW, load)
		if margin < 0 {
			t.Fatalf("margin should be positive, got %.3f", margin)
		}
		// Step 5: Verify safety
		safe := estimator.SafetyCheck(state)
		if !safe {
			t.Fatalf("state should be safe with 15%% reserves and 1 outage")
		}
	})

	t.Run("DRWithOutage_IntegrationWorkflow", func(t *testing.T) {
		// Outage increases priority
		oc := outage.OutageCase{Population: 50000, Critical: true, HoursDown: 6}
		priority := outage.PriorityScore(oc)
		if priority < 300 {
			t.Fatalf("critical outage with 50K population should have high priority, got %d", priority)
		}
		// DR program to handle curtailment
		dr := demandresponse.Program{CommittedMW: 0, MaxMW: 200}
		if !demandresponse.CanDispatch(dr, 100) {
			t.Fatalf("should be able to dispatch 100 MW")
		}
		dr = demandresponse.ApplyDispatch(dr, 100)
		remaining := demandresponse.RemainingCapacity(dr)
		if math.Abs(remaining-100) > 0.01 {
			t.Fatalf("remaining should be 100, got %.1f", remaining)
		}
	})

	t.Run("TopologyPathAndCapacity", func(t *testing.T) {
		g := topology.NewGraph()
		g.AddEdge(topology.Edge{From: "gen1", To: "sub1", CapacityMW: 500})
		g.AddEdge(topology.Edge{From: "sub1", To: "sub2", CapacityMW: 300})
		g.AddEdge(topology.Edge{From: "sub2", To: "load1", CapacityMW: 200})
		// Find path
		path := g.FindPath("gen1", "load1")
		if path == nil {
			t.Fatalf("should find path from gen1 to load1")
		}
		// Max flow should be bottleneck
		edges := []topology.Edge{
			{From: "gen1", To: "sub1", CapacityMW: 500},
			{From: "sub1", To: "sub2", CapacityMW: 300},
			{From: "sub2", To: "load1", CapacityMW: 200},
		}
		flow := topology.MaxFlowEstimate(edges)
		// Bottleneck is 200 MW
		if flow < 200 {
			t.Fatalf("max flow should be >= 200 (bottleneck), got %.0f", flow)
		}
	})

	t.Run("ConsensusElection_MultiRound", func(t *testing.T) {
		result := consensus.RunElection(
			[]string{"nodeA", "nodeB"},
			[]string{"v1", "v2", "v3"},
			10,
		)
		if !result.HasQuorum {
			t.Fatalf("2 candidates, 3 voters should find quorum")
		}
		if result.VoteCount < 2 {
			t.Fatalf("winner should have >= 2 votes (majority of 3), got %d", result.VoteCount)
		}
	})

	t.Run("ConsensusLeaderTransfer_Valid", func(t *testing.T) {
		ok, leader := consensus.SafeLeaderTransfer("nodeA", "nodeB", []string{"nodeA", "nodeB", "nodeC"})
		if !ok {
			t.Fatalf("should succeed for valid successor")
		}
		if leader != "nodeB" {
			t.Fatalf("new leader should be nodeB, got %s", leader)
		}
	})

	t.Run("ConsensusLeaderTransfer_InvalidSuccessor", func(t *testing.T) {
		ok, leader := consensus.SafeLeaderTransfer("nodeA", "nodeX", []string{"nodeA", "nodeB"})
		if ok {
			t.Fatalf("should fail for invalid successor")
		}
		if leader != "nodeA" {
			t.Fatalf("leader should remain nodeA, got %s", leader)
		}
	})

	t.Run("EventPartitioning_AllEventsPreserved", func(t *testing.T) {
		evts := make([]events.Event, 100)
		regions := []string{"west", "east", "central", "north", "south"}
		for i := range evts {
			evts[i] = events.Event{ID: fmt.Sprintf("e%d", i), Region: regions[i%5], Sequence: int64(i)}
		}
		partitions := events.PartitionEvents(evts, 5)
		if len(partitions) != 5 {
			t.Fatalf("expected 5 partitions, got %d", len(partitions))
		}
		totalEvents := 0
		for _, p := range partitions {
			totalEvents += len(p)
		}
		if totalEvents != 100 {
			t.Fatalf("total events should be 100, got %d", totalEvents)
		}
	})

	t.Run("EventPartitioning_SameRegionSamePartition", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Region: "west", Sequence: 1},
			{ID: "e2", Region: "west", Sequence: 2},
			{ID: "e3", Region: "west", Sequence: 3},
			{ID: "e4", Region: "east", Sequence: 4},
			{ID: "e5", Region: "east", Sequence: 5},
		}
		partitions := events.PartitionEvents(evts, 3)
		// All "west" events should land in the same partition
		westPartition := -1
		for i, p := range partitions {
			for _, e := range p {
				if e.Region == "west" {
					if westPartition == -1 {
						westPartition = i
					} else if i != westPartition {
						t.Fatalf("west events split across partitions %d and %d", westPartition, i)
					}
				}
			}
		}
	})

	t.Run("EventCompaction_WithDuplicates", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Sequence: 5},
			{ID: "e2", Sequence: 10},
			{ID: "e1", Sequence: 15}, // duplicate ID
			{ID: "e3", Sequence: 20},
		}
		compacted := events.CompactLog(evts, 5)
		if len(compacted) != 3 {
			t.Fatalf("should have 3 unique events after compaction, got %d", len(compacted))
		}
	})

	t.Run("MultiRegionResilience_ReplayAndCircuitBreaker", func(t *testing.T) {
		// Step 1: Replay events
		evts := []resilience.DispatchEvent{
			{Version: 11, IdempotencyKey: "k1", GenerationDelta: 50, ReserveDelta: 5},
			{Version: 12, IdempotencyKey: "k2", GenerationDelta: 100, ReserveDelta: 10},
		}
		snap := resilience.ReplayDispatch(500, 50, 10, evts)
		if snap.Applied < 2 {
			t.Fatalf("should apply 2 events, got %d", snap.Applied)
		}
		// Step 2: Circuit breaker for the replay service
		cb := resilience.NewCircuitBreaker(3, 2, 1000)
		// Simulate some failures
		cb.RecordResult(false, 100)
		cb.RecordResult(false, 200)
		if cb.State == "open" {
			t.Fatalf("should not be open after 2 failures (threshold 3)")
		}
	})

	t.Run("DispatchWithReserveSharing", func(t *testing.T) {
		// Regions with different demand levels
		regions := []struct {
			Name     string
			GenMW    float64
			DemandMW float64
			ReserveMW float64
		}{
			{"west", 1200, 900, 120},
			{"east", 800, 750, 80},
			{"central", 600, 400, 60},
		}
		totalShared, contributions := dispatch.ReserveSharing(regions)
		// west excess: 300, east excess: 50, central excess: 200
		if totalShared <= 0 {
			t.Fatalf("should have positive shared reserves")
		}
		if contributions["central"] < 190 {
			t.Fatalf("central should contribute ~200, got %.0f", contributions["central"])
		}
	})

	t.Run("EconomicDispatch_Integration", func(t *testing.T) {
		caps := []float64{300, 500, 200}
		costs := []float64{20, 50, 30}
		demand := 500.0
		alloc := dispatch.EconomicDispatch(caps, costs, demand)
		if alloc == nil {
			t.Fatalf("should return allocations")
		}
		sum := 0.0
		for _, a := range alloc {
			sum += a
			if a < 0 {
				t.Fatalf("allocation should not be negative: %.1f", a)
			}
		}
		// Allocations should be close to demand
		if math.Abs(sum-demand) > 50 {
			t.Fatalf("allocations (%.0f) should be close to demand (%.0f)", sum, demand)
		}
	})

	t.Run("CascadeDetection_MultiService", func(t *testing.T) {
		cd := resilience.NewCascadeDetector(2000, 0.7)
		// Auth service fails
		for i := 0; i < 20; i++ {
			cd.RecordError("auth", int64(1000+i*50))
		}
		// Gateway errors follow
		for i := 0; i < 18; i++ {
			cd.RecordError("gateway", int64(1020+i*50))
		}
		// Dispatch is less affected
		for i := 0; i < 5; i++ {
			cd.RecordError("dispatch", int64(1100+i*100))
		}
		// auth -> gateway cascade should be detected
		if !cd.DetectCascade("auth", "gateway", 2000) {
			t.Fatalf("should detect cascade from auth to gateway")
		}
		// auth -> dispatch: 5/20 = 0.25 < 0.7, no cascade
		if cd.DetectCascade("auth", "dispatch", 2000) {
			t.Fatalf("should not detect cascade from auth to dispatch")
		}
	})

	t.Run("FullWorkflow_WithSaga", func(t *testing.T) {
		var log []string
		steps := []workflow.SagaStep{
			{
				Name:       "estimate",
				Execute:    func() error { log = append(log, "estimate"); return nil },
				Compensate: func() error { log = append(log, "undo_estimate"); return nil },
			},
			{
				Name:       "dispatch",
				Execute:    func() error { log = append(log, "dispatch"); return nil },
				Compensate: func() error { log = append(log, "undo_dispatch"); return nil },
			},
			{
				Name:       "settle",
				Execute:    func() error { log = append(log, "settle"); return nil },
				Compensate: func() error { log = append(log, "undo_settle"); return nil },
			},
		}
		completed, err := workflow.SagaExecutor(steps)
		if err != nil {
			t.Fatalf("all steps should succeed: %v", err)
		}
		if completed != 3 {
			t.Fatalf("should complete 3 steps, got %d", completed)
		}
		if len(log) != 3 {
			t.Fatalf("should have 3 log entries, got %d", len(log))
		}
	})

	t.Run("LoadEstimationDiversity", func(t *testing.T) {
		peaks := []float64{1000, 800, 600}
		coincident := 2000.0
		diversity := estimator.RegionalDiversity(peaks, coincident)
		// sum = 2400, diversity = 2400/2000 = 1.2
		if math.Abs(diversity-1.2) > 0.01 {
			t.Fatalf("expected diversity 1.2, got %.3f", diversity)
		}
		// Use correlated estimate
		loads := []float64{1000, 800, 600}
		correlated := estimator.CorrelatedLoadEstimate(loads, 0.5)
		independent := math.Sqrt(1000*1000 + 800*800 + 600*600)
		expected := independent + 0.5*(2400-independent)
		if math.Abs(correlated-expected) > 1 {
			t.Fatalf("expected correlated estimate ~%.0f, got %.0f", expected, correlated)
		}
	})

	t.Run("TopologyWeightedPathAndTransfer", func(t *testing.T) {
		g := topology.NewGraph()
		g.AddEdge(topology.Edge{From: "A", To: "B", CapacityMW: 1000})
		g.AddEdge(topology.Edge{From: "B", To: "C", CapacityMW: 500})
		g.AddEdge(topology.Edge{From: "A", To: "C", CapacityMW: 200})
		costs := map[string]float64{
			"A->B": 5, "B->C": 5,
			"A->C": 8,
		}
		// Cheapest path A->C is direct (cost 8) vs A->B->C (cost 10)
		path, cost := g.ShortestWeightedPath("A", "C", costs)
		if path == nil {
			t.Fatalf("should find path")
		}
		if cost > 9 {
			t.Fatalf("should pick direct path (cost 8), got %.0f", cost)
		}
		// Verify transfer with loss
		received := topology.TransferWithLoss(200, []float64{3, 2})
		if received <= 0 {
			t.Fatalf("should have positive received power")
		}
	})

	t.Run("RunMultiStage_WithIntegration", func(t *testing.T) {
		stages := []func() (string, error){
			func() (string, error) {
				load := estimator.EstimateLoad(models.RegionState{
					BaseLoadMW: 500, TemperatureC: 30, WindPct: 10, ReservePct: 0.12,
				})
				return fmt.Sprintf("load=%.0f", load), nil
			},
			func() (string, error) {
				plan := dispatch.BuildPlan("west", 500, 0.12)
				return fmt.Sprintf("gen=%.0f", plan.GenerationMW), nil
			},
			func() (string, error) {
				return "complete", nil
			},
		}
		result := workflow.RunMultiStage(stages)
		if result.Error != nil {
			t.Fatalf("should not error: %v", result.Error)
		}
		if result.StagesCompleted != 3 {
			t.Fatalf("should complete 3 stages, got %d", result.StagesCompleted)
		}
	})
}
