package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/events"
	"incidentmesh/internal/resilience"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

// Latent bugs: only manifest under specific conditions that simple tests miss.

func TestLatentPriorityDrift(t *testing.T) {
	// ApplyPriorityAdjustments compounds on running total instead of base.
	// Single adjustment: base*(1+adj) == base + base*adj — both give same result.
	// Multiple adjustments diverge: compound gives base*(1+adj)^n, linear gives base*(1+n*adj).

	t.Run("SingleAdjustmentIdentical", func(t *testing.T) {
		// With one adjustment, compound and linear are identical — this should PASS
		result := triage.ApplyPriorityAdjustments(100.0, []float64{0.1})
		if math.Abs(result-110.0) > 0.01 {
			t.Errorf("single 10%% adjustment: expected 110.0, got %.2f", result)
		}
	})
	t.Run("ThreeAdjustmentsDiverge", func(t *testing.T) {
		// Linear: 100 + 3*10 = 130. Compound: 100*1.1^3 = 133.1. Difference = 3.1
		result := triage.ApplyPriorityAdjustments(100.0, []float64{0.1, 0.1, 0.1})
		if math.Abs(result-130.0) > 0.01 {
			t.Errorf("three 10%% adjustments should give 130.0 (linear), got %.2f (compound drift)", result)
		}
	})
	t.Run("FiveAdjustmentsSignificantDrift", func(t *testing.T) {
		// Linear: 200 + 5*10 = 250. Compound: 200*1.05^5 = 255.26
		result := triage.ApplyPriorityAdjustments(200.0, []float64{0.05, 0.05, 0.05, 0.05, 0.05})
		if math.Abs(result-250.0) > 0.01 {
			t.Errorf("five 5%% adjustments on 200: expected 250.0, got %.2f", result)
		}
	})
	t.Run("NegativeAdjustmentsDrift", func(t *testing.T) {
		// Linear: 100 + 2*(-10) = 80. Compound: 100*0.9^2 = 81. Difference = 1
		result := triage.ApplyPriorityAdjustments(100.0, []float64{-0.1, -0.1})
		if math.Abs(result-80.0) > 0.01 {
			t.Errorf("two -10%% adjustments: expected 80.0, got %.2f", result)
		}
	})
	t.Run("MixedAdjustmentsShouldCancel", func(t *testing.T) {
		// Linear: 100 + 20 + (-20) = 100. Compound: 100*1.2*0.8 = 96
		result := triage.ApplyPriorityAdjustments(100.0, []float64{0.2, -0.2})
		if math.Abs(result-100.0) > 0.01 {
			t.Errorf("+20%%/-20%% should cancel to 100.0, got %.2f (compound asymmetry)", result)
		}
	})
}

func TestLatentFacilityUtilizationFormula(t *testing.T) {
	// FacilityUtilization divides by (totalBeds + occupiedBeds) instead of totalBeds.
	// This under-reports utilization, making full facilities appear to have capacity.

	t.Run("HalfOccupied", func(t *testing.T) {
		// Correct: 50/100 = 0.5. Buggy: 50/150 = 0.333
		util := capacity.FacilityUtilization(50, 100)
		if math.Abs(util-0.5) > 0.001 {
			t.Errorf("50 occupied of 100 total: expected 0.500 utilization, got %.3f", util)
		}
	})
	t.Run("NearlyFullMisleading", func(t *testing.T) {
		// Correct: 95/100 = 0.95. Buggy: 95/195 = 0.487
		// A facility at 95% utilization appears to be at ~49% — dangerously misleading
		util := capacity.FacilityUtilization(95, 100)
		if util < 0.9 {
			t.Errorf("95/100 occupied should show >= 0.9 utilization, got %.3f (under-reported)", util)
		}
	})
	t.Run("FullFacilityNotReported", func(t *testing.T) {
		// Correct: 100/100 = 1.0. Buggy: 100/200 = 0.5
		util := capacity.FacilityUtilization(100, 100)
		if math.Abs(util-1.0) > 0.001 {
			t.Errorf("fully occupied facility should show 1.0 utilization, got %.3f", util)
		}
	})
}

func TestLatentICUAdmissionDomainViolation(t *testing.T) {
	// CanAdmitCritical uses BedsFree + ICUFree instead of just ICUFree.
	// A critical patient MUST go to ICU. General beds are irrelevant.

	t.Run("GeneralBedsCannotSubstituteICU", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 50, ICUFree: 3, Region: "north"}
		// All 3 ICU beds occupied — should not admit regardless of 50 general beds
		canAdmit := capacity.CanAdmitCritical(f, 3)
		if canAdmit {
			t.Error("all ICU beds occupied (3/3): should not admit critical patient even with 50 general beds free")
		}
	})
	t.Run("ICUAvailableAdmits", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 0, ICUFree: 5, Region: "east"}
		canAdmit := capacity.CanAdmitCritical(f, 2)
		if !canAdmit {
			t.Error("3 ICU beds free: should admit critical patient even with 0 general beds")
		}
	})
	t.Run("ExactICUCapacityBoundary", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 100, ICUFree: 5, Region: "west"}
		// Exactly at capacity — should NOT admit
		canAdmit := capacity.CanAdmitCritical(f, 5)
		if canAdmit {
			t.Error("ICU at exact capacity (5/5 occupied): should not admit")
		}
	})
}

func TestLatentCorrelationChainTemporalInversion(t *testing.T) {
	// BuildCorrelationChain sorts events DESCENDING by timestamp.
	// A correlation chain must be chronological (ascending) for replay to work.
	// This bug causes events to be processed in reverse order.

	t.Run("ReplayOrderMatters", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Type: "priority_set", Timestamp: 100, Data: map[string]string{"inc": "A"}},
			{ID: "e2", Type: "escalate", Timestamp: 300, Data: map[string]string{"inc": "A"}},
			{ID: "e3", Type: "dispatch", Timestamp: 200, Data: map[string]string{"inc": "A"}},
		}
		chains := events.BuildCorrelationChain(evts, "inc")
		chain := chains["A"]
		if len(chain) != 3 {
			t.Fatalf("expected 3 events in chain, got %d", len(chain))
		}
		// Chain must be chronological: 100 → 200 → 300
		for i := 1; i < len(chain); i++ {
			if chain[i].Timestamp < chain[i-1].Timestamp {
				t.Errorf("chain not chronological at [%d]: timestamp %d follows %d",
					i, chain[i].Timestamp, chain[i-1].Timestamp)
			}
		}
	})
	t.Run("MultipleCorrelationsAllOrdered", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Timestamp: 500, Data: map[string]string{"k": "X"}},
			{ID: "e2", Timestamp: 100, Data: map[string]string{"k": "X"}},
			{ID: "e3", Timestamp: 300, Data: map[string]string{"k": "Y"}},
			{ID: "e4", Timestamp: 50, Data: map[string]string{"k": "Y"}},
		}
		chains := events.BuildCorrelationChain(evts, "k")
		for key, chain := range chains {
			for i := 1; i < len(chain); i++ {
				if chain[i].Timestamp < chain[i-1].Timestamp {
					t.Errorf("chain %q index %d: %d < %d (not chronological)", key, i, chain[i].Timestamp, chain[i-1].Timestamp)
				}
			}
		}
	})
}

func TestLatentEventAggregationGhostCounts(t *testing.T) {
	// AggregateByType initializes count to 1 then increments, double-counting
	// the first event of each type. Total count = actual + unique_type_count.

	t.Run("SingleTypeSingleEvent", func(t *testing.T) {
		evts := []events.Event{{ID: "e1", Type: "alert"}}
		counts := events.AggregateByType(evts)
		if counts["alert"] != 1 {
			t.Errorf("1 alert event: expected count 1, got %d", counts["alert"])
		}
	})
	t.Run("TotalCountMatchesInputSize", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Type: "alert"},
			{ID: "e2", Type: "dispatch"},
			{ID: "e3", Type: "alert"},
			{ID: "e4", Type: "resolve"},
			{ID: "e5", Type: "dispatch"},
		}
		counts := events.AggregateByType(evts)
		total := 0
		for _, c := range counts {
			total += c
		}
		if total != 5 {
			t.Errorf("5 events should produce total count 5, got %d (ghost counts from init bug)", total)
		}
	})
	t.Run("PerTypeAccuracy", func(t *testing.T) {
		evts := []events.Event{
			{ID: "e1", Type: "A"}, {ID: "e2", Type: "A"}, {ID: "e3", Type: "A"},
			{ID: "e4", Type: "B"}, {ID: "e5", Type: "B"},
		}
		counts := events.AggregateByType(evts)
		if counts["A"] != 3 {
			t.Errorf("3 type-A events: expected 3, got %d", counts["A"])
		}
		if counts["B"] != 2 {
			t.Errorf("2 type-B events: expected 2, got %d", counts["B"])
		}
	})
}

func TestLatentCircuitBreakerOffByOne(t *testing.T) {
	// AdvancedCircuitBreaker requires recoveryThreshold+1 successes to close.
	// The +1 is an off-by-one: reaching the threshold should be enough.

	t.Run("ExactThresholdShouldClose", func(t *testing.T) {
		state := resilience.AdvancedCircuitBreaker(10, 5, 5, 5)
		if state != "closed" {
			t.Errorf("5 successes at threshold 5 should close circuit, got %s", state)
		}
	})
	t.Run("OneOverThresholdCloses", func(t *testing.T) {
		state := resilience.AdvancedCircuitBreaker(10, 6, 5, 5)
		if state != "closed" {
			t.Errorf("6 successes above threshold 5 should close circuit, got %s", state)
		}
	})
}

func TestLatentRetryBudgetWindowInversion(t *testing.T) {
	// RetryBudgetCheck allows unlimited retries WITHIN window and checks budget AFTER.
	// Correct: check budget within window, reset on expiry.

	t.Run("BudgetEnforcedWithinWindow", func(t *testing.T) {
		// 5/5 retries used, within window — should be DENIED
		allowed := resilience.RetryBudgetCheck(5, 5, 1000, 1500, 2000)
		if allowed {
			t.Error("within window with exhausted budget (5/5): should deny retry")
		}
	})
	t.Run("BudgetAvailableWithinWindow", func(t *testing.T) {
		allowed := resilience.RetryBudgetCheck(2, 5, 1000, 1500, 2000)
		if !allowed {
			t.Error("within window with available budget (2/5): should allow retry")
		}
	})
	t.Run("ExpiredWindowResetsAllowsRetry", func(t *testing.T) {
		// Window expired — budget should reset, retry allowed regardless of used count
		allowed := resilience.RetryBudgetCheck(5, 5, 1000, 5000, 2000)
		if !allowed {
			t.Error("expired window: should reset budget and allow retry")
		}
	})
}

func TestLatentRegionalCapacitySumVsAverage(t *testing.T) {
	// RegionalCapacitySummary returns sum instead of average per region.
	// With 1 facility per region, sum == average (bug is invisible).
	// With 2+ facilities, sum > average — region appears to have more capacity.

	t.Run("SingleFacilityPerRegionIdentical", func(t *testing.T) {
		// Sum == average when N=1 — this should PASS
		facilities := []capacity.Facility{
			{Name: "H1", BedsFree: 10, ICUFree: 2, DistanceK: 5.0, Region: "north"},
		}
		summary := capacity.RegionalCapacitySummary(facilities)
		expected := capacity.RankScore(facilities[0])
		if math.Abs(summary["north"]-expected) > 0.01 {
			t.Errorf("single facility: expected %.2f, got %.2f", expected, summary["north"])
		}
	})
	t.Run("TwoFacilitiesMustAverage", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "H1", BedsFree: 10, ICUFree: 2, DistanceK: 5.0, Region: "north"},
			{Name: "H2", BedsFree: 20, ICUFree: 4, DistanceK: 3.0, Region: "north"},
		}
		summary := capacity.RegionalCapacitySummary(facilities)
		s1 := capacity.RankScore(facilities[0])
		s2 := capacity.RankScore(facilities[1])
		expected := (s1 + s2) / 2.0
		if math.Abs(summary["north"]-expected) > 0.01 {
			t.Errorf("two facilities: expected average %.2f, got %.2f (sum=%.2f)", expected, summary["north"], s1+s2)
		}
	})
	t.Run("ThreeFacilitiesInflatedScore", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "H1", BedsFree: 10, ICUFree: 1, DistanceK: 2.0, Region: "east"},
			{Name: "H2", BedsFree: 20, ICUFree: 2, DistanceK: 3.0, Region: "east"},
			{Name: "H3", BedsFree: 30, ICUFree: 3, DistanceK: 1.0, Region: "east"},
		}
		summary := capacity.RegionalCapacitySummary(facilities)
		s1, s2, s3 := capacity.RankScore(facilities[0]), capacity.RankScore(facilities[1]), capacity.RankScore(facilities[2])
		expected := (s1 + s2 + s3) / 3.0
		if math.Abs(summary["east"]-expected) > 0.01 {
			t.Errorf("three facilities: expected average %.2f, got %.2f", expected, summary["east"])
		}
	})
}

func TestLatentMergeDispatchPlansInvertedDedup(t *testing.T) {
	// MergeDispatchPlans has inverted dedup: keeps duplicates from b, drops unique entries.
	// This means unique new plans are silently lost.

	t.Run("UniqueEntriesFromBAreLost", func(t *testing.T) {
		a := []models.DispatchPlan{{IncidentID: "inc-1", UnitIDs: []string{"u1"}}}
		b := []models.DispatchPlan{{IncidentID: "inc-2", UnitIDs: []string{"u2"}}}
		merged := models.MergeDispatchPlans(a, b)
		if len(merged) != 2 {
			t.Errorf("merging [inc-1] + [inc-2]: expected 2 plans, got %d", len(merged))
		}
		found := map[string]bool{}
		for _, p := range merged {
			found[p.IncidentID] = true
		}
		if !found["inc-2"] {
			t.Error("inc-2 unique to list b should be in merged result but was dropped")
		}
	})
	t.Run("DuplicatesNotDoubled", func(t *testing.T) {
		a := []models.DispatchPlan{{IncidentID: "inc-1", UnitIDs: []string{"u1"}, Priority: 100}}
		b := []models.DispatchPlan{
			{IncidentID: "inc-1", UnitIDs: []string{"u2"}, Priority: 200},
			{IncidentID: "inc-3", UnitIDs: []string{"u3"}},
		}
		merged := models.MergeDispatchPlans(a, b)
		count := 0
		for _, p := range merged {
			if p.IncidentID == "inc-1" {
				count++
			}
		}
		if count > 1 {
			t.Errorf("duplicate inc-1 should appear once, found %d times", count)
		}
	})
}
