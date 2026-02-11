package stress

import (
	"math"
	"testing"

	"gridweaver/internal/consensus"
	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/internal/events"
	"gridweaver/internal/resilience"
	"gridweaver/pkg/models"
)

func TestMultiStepBugs(t *testing.T) {

	t.Run("RampSchedule_AllPositive", func(t *testing.T) {
		// RampSchedule uses RoundGeneration internally
		// Even if RoundGeneration is buggy, the schedule should have all positive values
		schedule := dispatch.RampSchedule(100, 500, 4, 2)
		if len(schedule) != 5 { // steps+1 points
			t.Fatalf("expected 5 schedule points, got %d", len(schedule))
		}
		for i, v := range schedule {
			if v < 0 {
				t.Fatalf("schedule point %d should be positive, got %.2f", i, v)
			}
		}
	})

	t.Run("RampSchedule_MonotonicallyIncreasing", func(t *testing.T) {
		schedule := dispatch.RampSchedule(200, 800, 6, 1)
		for i := 1; i < len(schedule); i++ {
			if schedule[i] < schedule[i-1] {
				t.Fatalf("ramp up should be monotonically increasing: step %d (%.1f) < step %d (%.1f)",
					i, schedule[i], i-1, schedule[i-1])
			}
		}
	})

	t.Run("RampSchedule_EndpointsCorrect", func(t *testing.T) {
		schedule := dispatch.RampSchedule(100, 500, 4, 0)
		if math.Abs(schedule[0]-100) > 1 {
			t.Fatalf("first point should be ~100, got %.1f", schedule[0])
		}
		if math.Abs(schedule[len(schedule)-1]-500) > 1 {
			t.Fatalf("last point should be ~500, got %.1f", schedule[len(schedule)-1])
		}
	})

	t.Run("MeritOrderThenDispatch_IntegrationChain", func(t *testing.T) {
		// Step 1: MeritOrder should sort by ascending cost
		units := []struct {
			ID        string
			CostPerMW float64
		}{
			{"expensive_gas", 80},
			{"cheap_solar", 10},
			{"mid_wind", 40},
		}
		order := dispatch.MeritOrder(units)
		// Step 2: First generator in merit order should be cheapest
		if order[0] != "cheap_solar" {
			t.Fatalf("merit order should list cheapest first, got %s", order[0])
		}
		// Step 3: Use the sorted order to dispatch
		// If merit order is wrong, this whole chain falls apart
		if order[len(order)-1] != "expensive_gas" {
			t.Fatalf("expensive generator should be last, got %s", order[len(order)-1])
		}
	})

	t.Run("BuildPlanThenConstraintThenMargin", func(t *testing.T) {
		// Multi-step chain: BuildPlan -> ApplyConstraint -> CapacityMargin
		plan := dispatch.BuildPlan("west", 1000, 0.12)
		// Step 1: generation should be >= demand + reserve
		if plan.GenerationMW < 1000 {
			t.Fatalf("generation should be >= demand, got %.0f", plan.GenerationMW)
		}
		// Step 2: Apply constraint
		constrained := dispatch.ApplyConstraint(plan, 5000)
		// Step 3: Calculate margin
		margin := dispatch.CapacityMargin(constrained.GenerationMW, 1000)
		// Margin should be positive if gen > demand
		if margin < 0 {
			t.Fatalf("margin should be positive when gen > demand, got %.3f", margin)
		}
	})

	t.Run("EstimateThenForecastChain", func(t *testing.T) {
		state := models.RegionState{
			Region: "west", BaseLoadMW: 800, TemperatureC: 35,
			WindPct: 10, ReservePct: 0.15, ActiveOutages: 2,
		}
		// Step 1: Estimate current load
		load := estimator.EstimateLoad(state)
		// Step 2: Use trend to forecast ahead
		readings := []float64{load * 0.9, load * 0.95, load}
		slope := estimator.TrendSlope(readings)
		// Step 3: Forecast 5 steps ahead
		forecast := estimator.LoadForecast(load, slope, 5)
		// Forecast should be > current load if trend is positive
		if slope > 0 && forecast <= load {
			t.Fatalf("positive trend should give higher forecast: load=%.1f, forecast=%.1f, slope=%.4f",
				load, forecast, slope)
		}
	})

	t.Run("EventSortThenGapDetection", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Sequence: 1},
			{ID: "e2", Sequence: 3},
			{ID: "e3", Sequence: 10},
		}
		// Step 1: Sort should give ascending order
		sorted := events.SortBySequence(evts)
		if sorted[0].Sequence > sorted[1].Sequence {
			t.Fatalf("sort should be ascending, got %d before %d", sorted[0].Sequence, sorted[1].Sequence)
		}
		// Step 2: Gap detection should find gaps
		gaps := events.SequenceGaps(evts)
		// Gaps should be: 3-1=2 (gap of 2), 10-3=7 (gap of 7)
		if len(gaps) < 1 {
			t.Fatalf("should detect sequence gaps")
		}
		foundLargeGap := false
		for _, g := range gaps {
			if g >= 5 {
				foundLargeGap = true
			}
		}
		if !foundLargeGap {
			t.Fatalf("should detect gap of ~7 between seq 3 and 10, got gaps %v", gaps)
		}
	})

	t.Run("ConsensusElectionDependsOnIncrementTerm", func(t *testing.T) {
		// RunElection uses IncrementTerm internally
		// If IncrementTerm adds 2 instead of 1, terms skip
		result := consensus.RunElection(
			[]string{"alice", "bob", "charlie"},
			[]string{"voter1", "voter2", "voter3", "voter4", "voter5"},
			5,
		)
		// With 5 voters and 3 candidates, quorum is 3
		// The election should eventually find a leader
		if !result.HasQuorum {
			t.Fatalf("election should find a leader within 5 rounds")
		}
		// Term should increment by 1 each round
		expectedMaxTerm := int64(result.Rounds)
		if result.Term > expectedMaxTerm {
			t.Fatalf("term should be <= %d (rounds), got %d (term skipping?)", expectedMaxTerm, result.Term)
		}
	})

	t.Run("ReplayThenDedupe_ChainedDependency", func(t *testing.T) {
		// Step 1: Create events with some duplicates
		evts := []resilience.DispatchEvent{
			{Version: 11, IdempotencyKey: "k1", GenerationDelta: 100, ReserveDelta: 10},
			{Version: 12, IdempotencyKey: "k2", GenerationDelta: 200, ReserveDelta: 20},
			{Version: 13, IdempotencyKey: "k1", GenerationDelta: 100, ReserveDelta: 10}, // duplicate key
		}
		// Step 2: Replay should deduplicate by idempotency key
		snap := resilience.ReplayDispatch(500, 50, 10, evts)
		// Should apply k1 and k2 only (not duplicate k1)
		if snap.Applied != 2 {
			t.Fatalf("expected 2 applied (deduped), got %d", snap.Applied)
		}
		// Step 3: Verify state is correct
		expectedGen := 500 + 100 + 200 // base + k1 + k2
		if math.Abs(snap.GenerationMW-float64(expectedGen)) > 0.01 {
			t.Fatalf("expected generation %.0f, got %.0f", float64(expectedGen), snap.GenerationMW)
		}
	})

	t.Run("CascadeDetector_UpstreamCausesDownstream", func(t *testing.T) {
		cd := resilience.NewCascadeDetector(5000, 0.5)
		// Record upstream errors
		for i := 0; i < 10; i++ {
			cd.RecordError("auth", int64(1000+i*100))
		}
		// Record downstream errors correlated with upstream
		for i := 0; i < 8; i++ {
			cd.RecordError("dispatch", int64(1050+i*100))
		}
		// Should detect cascade: downstream/upstream = 8/10 = 0.8 > 0.5
		cascade := cd.DetectCascade("auth", "dispatch", 2000)
		if !cascade {
			t.Fatalf("should detect cascade when downstream errors correlate with upstream")
		}
	})

	t.Run("CascadeDetector_WindowExclusion", func(t *testing.T) {
		cd := resilience.NewCascadeDetector(1000, 0.5)
		// Old errors outside window
		cd.RecordError("auth", 100)
		cd.RecordError("dispatch", 150)
		// Check at time 5000 - errors at 100/150 are outside 1000ms window
		cascade := cd.DetectCascade("auth", "dispatch", 5000)
		if cascade {
			t.Fatalf("should not detect cascade when errors are outside window")
		}
	})

	t.Run("MultiRegionPlanThenTotalGeneration", func(t *testing.T) {
		regions := []string{"west", "east", "central"}
		demands := map[string]float64{"west": 1000, "east": 800, "central": 600}
		// Step 1: Build plans for all regions
		plans := dispatch.MultiRegionPlan(regions, demands, 0.12)
		// Step 2: Total generation across regions
		totalGen := dispatch.TotalGeneration(plans)
		totalDemand := 1000 + 800 + 600.0
		// Generation should be >= total demand
		if totalGen < totalDemand {
			t.Fatalf("total generation (%.0f) should be >= total demand (%.0f)", totalGen, totalDemand)
		}
	})

	t.Run("RetryStateMachine_ResetAfterSuccess", func(t *testing.T) {
		rsm := resilience.NewRetryStateMachine(3, 100)
		// Fail twice
		rsm.RecordAttempt(false)
		rsm.RecordAttempt(false)
		if rsm.BackoffMs <= 100 {
			t.Fatalf("backoff should escalate after failures, got %d", rsm.BackoffMs)
		}
		// Succeed
		rsm.RecordAttempt(true)
		// After success, backoff should reset
		if rsm.CurrentAttempt != 0 {
			t.Fatalf("current attempt should reset after success, got %d", rsm.CurrentAttempt)
		}
		// Another failure should start from base backoff
		rsm.RecordAttempt(false)
		if rsm.BackoffMs > 200 {
			t.Fatalf("backoff should restart from base after success, got %d", rsm.BackoffMs)
		}
	})

	t.Run("CommitIndex_MajorityReplication", func(t *testing.T) {
		// 5-node cluster, match indices from 4 followers
		matchIndices := []int64{10, 20, 15, 25}
		commitIdx := consensus.CommitIndex(matchIndices, 5)
		// Majority of 5 = 3. The 3rd highest match index is 15
		// Sorted: [10, 15, 20, 25], majority index = 5/2 = 2, sorted[2] = 20
		if commitIdx < 15 {
			t.Fatalf("commit index should be >= median match index, got %d", commitIdx)
		}
	})
}
