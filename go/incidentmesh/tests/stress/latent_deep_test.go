package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/events"
	"incidentmesh/internal/resilience"
	"incidentmesh/pkg/models"
)

func TestLatentSeverityRangeBoundaries(t *testing.T) {
	incidents := []models.Incident{
		{ID: "i1", Severity: 1},
		{ID: "i2", Severity: 2},
		{ID: "i3", Severity: 3},
		{ID: "i4", Severity: 4},
		{ID: "i5", Severity: 5},
	}

	t.Run("InclusiveMinBoundary", func(t *testing.T) {
		result := models.IncidentsBySeverityRange(incidents, 3, 5)
		found := false
		for _, inc := range result {
			if inc.Severity == 3 {
				found = true
			}
		}
		if !found {
			t.Error("severity range [3,5] should include severity 3 (inclusive lower bound)")
		}
	})
	t.Run("InclusiveMaxBoundary", func(t *testing.T) {
		result := models.IncidentsBySeverityRange(incidents, 3, 5)
		found := false
		for _, inc := range result {
			if inc.Severity == 5 {
				found = true
			}
		}
		if !found {
			t.Error("severity range [3,5] should include severity 5 (inclusive upper bound)")
		}
	})
	t.Run("ExactRangeMatch", func(t *testing.T) {
		result := models.IncidentsBySeverityRange(incidents, 2, 4)
		if len(result) != 3 {
			t.Errorf("severity range [2,4] should return 3 incidents, got %d", len(result))
		}
	})
	t.Run("SingleValueRange", func(t *testing.T) {
		result := models.IncidentsBySeverityRange(incidents, 3, 3)
		if len(result) != 1 {
			t.Errorf("severity range [3,3] should return 1 incident, got %d", len(result))
		}
	})
	t.Run("FullRange", func(t *testing.T) {
		result := models.IncidentsBySeverityRange(incidents, 1, 5)
		if len(result) != 5 {
			t.Errorf("severity range [1,5] should return all 5 incidents, got %d", len(result))
		}
	})
	t.Run("EmptyResult", func(t *testing.T) {
		result := models.IncidentsBySeverityRange(incidents, 6, 10)
		if len(result) != 0 {
			t.Errorf("severity range [6,10] should return 0 incidents, got %d", len(result))
		}
	})
}

func TestLatentAveragePriorityPrecision(t *testing.T) {
	t.Run("EvenDivision", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", Priority: 10},
			{IncidentID: "b", Priority: 20},
		}
		avg := models.AveragePriority(plans)
		if math.Abs(avg-15.0) > 0.001 {
			t.Errorf("average of 10 and 20 should be 15.0, got %.3f", avg)
		}
	})
	t.Run("UnevenDivisionLosesPrecision", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", Priority: 10},
			{IncidentID: "b", Priority: 20},
			{IncidentID: "c", Priority: 30},
		}
		avg := models.AveragePriority(plans)
		if math.Abs(avg-20.0) > 0.001 {
			t.Errorf("average of 10, 20, 30 should be 20.0, got %.3f", avg)
		}
	})
	t.Run("TruncationOnNonDivisible", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", Priority: 1},
			{IncidentID: "b", Priority: 2},
			{IncidentID: "c", Priority: 3},
		}
		avg := models.AveragePriority(plans)
		if math.Abs(avg-2.0) > 0.001 {
			t.Errorf("average of 1, 2, 3 should be 2.0, got %.3f", avg)
		}
	})
	t.Run("SmallValuesLoseEntireFraction", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", Priority: 1},
			{IncidentID: "b", Priority: 2},
		}
		avg := models.AveragePriority(plans)
		if math.Abs(avg-1.5) > 0.001 {
			t.Errorf("average of 1 and 2 should be 1.5, got %.3f (integer truncation)", avg)
		}
	})
	t.Run("LargeOddCount", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", Priority: 100},
			{IncidentID: "b", Priority: 200},
			{IncidentID: "c", Priority: 200},
			{IncidentID: "d", Priority: 300},
			{IncidentID: "e", Priority: 300},
			{IncidentID: "f", Priority: 300},
			{IncidentID: "g", Priority: 400},
		}
		avg := models.AveragePriority(plans)
		expected := 1800.0 / 7.0
		if math.Abs(avg-expected) > 0.1 {
			t.Errorf("average should be %.2f, got %.2f", expected, avg)
		}
	})
}

func TestLatentDispatchPlanValidateMissingUnits(t *testing.T) {
	t.Run("ValidPlan", func(t *testing.T) {
		plan := models.DispatchPlan{IncidentID: "inc-1", UnitIDs: []string{"u1"}, Priority: 10}
		if !models.DispatchPlanValidate(plan) {
			t.Error("plan with valid ID, units, and priority should be valid")
		}
	})
	t.Run("EmptyUnitIDsInvalid", func(t *testing.T) {
		plan := models.DispatchPlan{IncidentID: "inc-1", UnitIDs: []string{}, Priority: 10}
		if models.DispatchPlanValidate(plan) {
			t.Error("plan with empty UnitIDs should be invalid: no responders assigned")
		}
	})
	t.Run("NilUnitIDsInvalid", func(t *testing.T) {
		plan := models.DispatchPlan{IncidentID: "inc-1", Priority: 10}
		if models.DispatchPlanValidate(plan) {
			t.Error("plan with nil UnitIDs should be invalid: cannot dispatch without units")
		}
	})
	t.Run("EmptyIncidentIDInvalid", func(t *testing.T) {
		plan := models.DispatchPlan{IncidentID: "", UnitIDs: []string{"u1"}, Priority: 10}
		if models.DispatchPlanValidate(plan) {
			t.Error("plan with empty IncidentID should be invalid")
		}
	})
}

func TestLatentPlanETATotalOffByOne(t *testing.T) {
	t.Run("SinglePlan", func(t *testing.T) {
		plans := []models.DispatchPlan{{EstimatedETA: 15}}
		total := models.PlanETATotal(plans)
		if total != 15 {
			t.Errorf("single plan ETA 15: expected total 15, got %d", total)
		}
	})
	t.Run("TwoPlans", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{EstimatedETA: 10},
			{EstimatedETA: 20},
		}
		total := models.PlanETATotal(plans)
		if total != 30 {
			t.Errorf("plans ETA 10+20: expected total 30, got %d", total)
		}
	})
	t.Run("ThreePlans", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{EstimatedETA: 5},
			{EstimatedETA: 10},
			{EstimatedETA: 15},
		}
		total := models.PlanETATotal(plans)
		if total != 30 {
			t.Errorf("plans ETA 5+10+15: expected total 30, got %d (last plan skipped?)", total)
		}
	})
	t.Run("FivePlans", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{EstimatedETA: 2},
			{EstimatedETA: 4},
			{EstimatedETA: 6},
			{EstimatedETA: 8},
			{EstimatedETA: 10},
		}
		total := models.PlanETATotal(plans)
		if total != 30 {
			t.Errorf("plans ETA 2+4+6+8+10: expected 30, got %d", total)
		}
	})
	t.Run("EmptyPlans", func(t *testing.T) {
		total := models.PlanETATotal(nil)
		if total != 0 {
			t.Errorf("empty plans: expected 0, got %d", total)
		}
	})
}

func TestLatentHighestSeverityTieBreak(t *testing.T) {
	t.Run("UniqueServerities", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "low", Severity: 1},
			{ID: "high", Severity: 5},
			{ID: "mid", Severity: 3},
		}
		best := models.HighestSeverityIncident(incidents)
		if best.ID != "high" {
			t.Errorf("expected highest severity incident 'high', got '%s'", best.ID)
		}
	})
	t.Run("TiedSeveritiesReturnsFirst", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "first-critical", Severity: 5},
			{ID: "second-critical", Severity: 5},
			{ID: "third-critical", Severity: 5},
		}
		best := models.HighestSeverityIncident(incidents)
		if best.ID != "first-critical" {
			t.Errorf("tied severity: should return first occurrence 'first-critical', got '%s'", best.ID)
		}
	})
	t.Run("TiedMaxWithLowerBetween", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "first-max", Severity: 4},
			{ID: "low", Severity: 1},
			{ID: "second-max", Severity: 4},
		}
		best := models.HighestSeverityIncident(incidents)
		if best.ID != "first-max" {
			t.Errorf("tied severity 4: should return first occurrence 'first-max', got '%s'", best.ID)
		}
	})
	t.Run("SingleIncident", func(t *testing.T) {
		incidents := []models.Incident{{ID: "only", Severity: 3}}
		best := models.HighestSeverityIncident(incidents)
		if best.ID != "only" {
			t.Errorf("single incident: expected 'only', got '%s'", best.ID)
		}
	})
	t.Run("EmptyReturnsNil", func(t *testing.T) {
		best := models.HighestSeverityIncident(nil)
		if best != nil {
			t.Error("empty input should return nil")
		}
	})
}

func TestLatentDistributeIgnoresCapacity(t *testing.T) {
	t.Run("CapacityProportionalDistribution", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "small", BedsFree: 10},
			{Name: "large", BedsFree: 90},
		}
		dist := capacity.DistributeLoad(facilities, 100)
		if dist["large"] <= dist["small"] {
			t.Errorf("facility with 90 beds should get more patients than one with 10: large=%d, small=%d",
				dist["large"], dist["small"])
		}
	})
	t.Run("ZeroCapacityGetsNone", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "full", BedsFree: 0},
			{Name: "available", BedsFree: 50},
		}
		dist := capacity.DistributeLoad(facilities, 10)
		if dist["full"] > 0 {
			t.Errorf("facility with 0 beds should get 0 patients, got %d", dist["full"])
		}
	})
	t.Run("ProportionalSplit", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "a", BedsFree: 25},
			{Name: "b", BedsFree: 75},
		}
		dist := capacity.DistributeLoad(facilities, 20)
		if dist["a"] != 5 || dist["b"] != 15 {
			t.Errorf("25:75 ratio with 20 patients: expected a=5, b=15, got a=%d, b=%d",
				dist["a"], dist["b"])
		}
	})
	t.Run("ThreeFacilitiesProportional", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "a", BedsFree: 10},
			{Name: "b", BedsFree: 20},
			{Name: "c", BedsFree: 70},
		}
		dist := capacity.DistributeLoad(facilities, 100)
		if dist["a"] != 10 {
			t.Errorf("10%% capacity should get 10 patients, got %d", dist["a"])
		}
		if dist["c"] != 70 {
			t.Errorf("70%% capacity should get 70 patients, got %d", dist["c"])
		}
	})
}

func TestLatentBackoffCapWrongVariable(t *testing.T) {
	t.Run("FirstAttemptBaseDelay", func(t *testing.T) {
		delay := resilience.ExponentialBackoffWithCap(0, 100, 5000)
		if delay != 100 {
			t.Errorf("attempt 0: expected 100ms, got %d", delay)
		}
	})
	t.Run("ExponentialGrowth", func(t *testing.T) {
		d1 := resilience.ExponentialBackoffWithCap(1, 100, 50000)
		d2 := resilience.ExponentialBackoffWithCap(2, 100, 50000)
		if d1 != 200 {
			t.Errorf("attempt 1: expected 200ms, got %d", d1)
		}
		if d2 != 400 {
			t.Errorf("attempt 2: expected 400ms, got %d", d2)
		}
	})
	t.Run("CappedAtMax", func(t *testing.T) {
		delay := resilience.ExponentialBackoffWithCap(10, 100, 5000)
		if delay > 5000 {
			t.Errorf("attempt 10: expected capped at 5000ms, got %d (cap not applied)", delay)
		}
	})
	t.Run("HighAttemptsStayCapped", func(t *testing.T) {
		delay := resilience.ExponentialBackoffWithCap(20, 100, 3000)
		if delay > 3000 {
			t.Errorf("attempt 20: expected capped at 3000ms, got %d", delay)
		}
	})
	t.Run("SmallCapRespected", func(t *testing.T) {
		delay := resilience.ExponentialBackoffWithCap(5, 100, 500)
		if delay > 500 {
			t.Errorf("attempt 5 with 500ms cap: expected <= 500, got %d", delay)
		}
	})
}

func TestLatentCascadeLinearVsExponential(t *testing.T) {
	t.Run("SingleDepthSame", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(10, 1, 0.5)
		if math.Abs(impact-15.0) > 0.01 {
			t.Errorf("depth 1, factor 0.5: expected 15.0, got %.2f", impact)
		}
	})
	t.Run("MultipleLevelsExponential", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(10, 3, 0.5)
		expected := 10.0 * math.Pow(1.5, 3)
		if math.Abs(impact-expected) > 0.5 {
			t.Errorf("depth 3, factor 0.5: expected exponential %.2f, got %.2f (linear underestimate)", expected, impact)
		}
	})
	t.Run("DeepCascadeExponential", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(10, 5, 1.0)
		expected := 10.0 * math.Pow(2.0, 5)
		if math.Abs(impact-expected) > 1.0 {
			t.Errorf("depth 5, factor 1.0: expected %.0f, got %.0f", expected, impact)
		}
	})
	t.Run("ZeroDepthNoGrowth", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(10, 0, 0.5)
		if math.Abs(impact-10.0) > 0.01 {
			t.Errorf("depth 0: expected 10.0 (no cascade), got %.2f", impact)
		}
	})
}

func TestLatentSequenceGapDetection(t *testing.T) {
	t.Run("NoGaps", func(t *testing.T) {
		evts := []events.Event{
			{Timestamp: 1}, {Timestamp: 2}, {Timestamp: 3}, {Timestamp: 4},
		}
		gaps := events.DetectSequenceGaps(evts)
		if len(gaps) != 0 {
			t.Errorf("consecutive sequence should have 0 gaps, got %d", len(gaps))
		}
	})
	t.Run("SingleGapDetected", func(t *testing.T) {
		evts := []events.Event{
			{Timestamp: 1}, {Timestamp: 3},
		}
		gaps := events.DetectSequenceGaps(evts)
		if len(gaps) != 1 {
			t.Errorf("gap between 1 and 3: expected 1 gap, got %d", len(gaps))
		}
	})
	t.Run("GapOfTwo", func(t *testing.T) {
		evts := []events.Event{
			{Timestamp: 10}, {Timestamp: 12},
		}
		gaps := events.DetectSequenceGaps(evts)
		if len(gaps) != 1 {
			t.Errorf("gap of 2 between 10 and 12: expected 1 gap detected, got %d", len(gaps))
		}
	})
	t.Run("MultipleGaps", func(t *testing.T) {
		evts := []events.Event{
			{Timestamp: 1}, {Timestamp: 5}, {Timestamp: 10},
		}
		gaps := events.DetectSequenceGaps(evts)
		if len(gaps) != 2 {
			t.Errorf("gaps between 1-5 and 5-10: expected 2 gaps, got %d", len(gaps))
		}
	})
}

func TestLatentCriticalBedRatioDenominator(t *testing.T) {
	t.Run("EqualBeds", func(t *testing.T) {
		ratio := capacity.CriticalBedRatio(50, 50)
		if math.Abs(ratio-0.5) > 0.001 {
			t.Errorf("50 ICU / 100 total: expected 0.5, got %.3f", ratio)
		}
	})
	t.Run("AllICU", func(t *testing.T) {
		ratio := capacity.CriticalBedRatio(100, 0)
		if math.Abs(ratio-1.0) > 0.001 {
			t.Errorf("100 ICU / 0 general = 100 total: expected 1.0, got %.3f", ratio)
		}
	})
	t.Run("MostlyGeneral", func(t *testing.T) {
		ratio := capacity.CriticalBedRatio(10, 90)
		if math.Abs(ratio-0.1) > 0.001 {
			t.Errorf("10 ICU / 100 total: expected 0.1, got %.3f", ratio)
		}
	})
	t.Run("SmallICUFraction", func(t *testing.T) {
		ratio := capacity.CriticalBedRatio(5, 95)
		if math.Abs(ratio-0.05) > 0.001 {
			t.Errorf("5 ICU / 100 total: expected 0.05, got %.3f", ratio)
		}
	})
}

func TestLatentWeightedCapacityICUWeight(t *testing.T) {
	t.Run("ICUBedsShouldWeighMore", func(t *testing.T) {
		highICU := capacity.Facility{BedsFree: 10, ICUFree: 20, DistanceK: 5.0}
		highGeneral := capacity.Facility{BedsFree: 20, ICUFree: 10, DistanceK: 5.0}
		scoreICU := capacity.WeightedCapacityScore(highICU)
		scoreGeneral := capacity.WeightedCapacityScore(highGeneral)
		if scoreICU <= scoreGeneral {
			t.Errorf("facility with more ICU beds should score higher: ICU=%.1f, general=%.1f", scoreICU, scoreGeneral)
		}
	})
	t.Run("ICUWeightAtLeast2x", func(t *testing.T) {
		onlyICU := capacity.Facility{BedsFree: 0, ICUFree: 10, DistanceK: 0}
		onlyGeneral := capacity.Facility{BedsFree: 10, ICUFree: 0, DistanceK: 0}
		scoreICU := capacity.WeightedCapacityScore(onlyICU)
		scoreGeneral := capacity.WeightedCapacityScore(onlyGeneral)
		if scoreICU < scoreGeneral*2.0 {
			t.Errorf("ICU beds should have >= 2x weight vs general: ICU=%.1f, general=%.1f", scoreICU, scoreGeneral)
		}
	})
	t.Run("DistancePenaltyApplied", func(t *testing.T) {
		near := capacity.Facility{BedsFree: 10, ICUFree: 5, DistanceK: 1.0}
		far := capacity.Facility{BedsFree: 10, ICUFree: 5, DistanceK: 50.0}
		if capacity.WeightedCapacityScore(near) <= capacity.WeightedCapacityScore(far) {
			t.Error("closer facility should score higher than farther one")
		}
	})
}

func TestLatentSurgeCapacityBoundary(t *testing.T) {
	t.Run("ExactCapacitySufficient", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 10, ICUFree: 5}
		if !capacity.SurgeCapacityCheck(f, 15) {
			t.Error("facility with 15 available beds should handle 15 patients (exact match)")
		}
	})
	t.Run("BelowCapacity", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 20, ICUFree: 10}
		if !capacity.SurgeCapacityCheck(f, 15) {
			t.Error("facility with 30 available should handle 15 patients")
		}
	})
	t.Run("AboveCapacity", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 5, ICUFree: 5}
		if capacity.SurgeCapacityCheck(f, 15) {
			t.Error("facility with 10 available should not handle 15 patients")
		}
	})
}

func TestLatentEventStreamMergeDuplicateTimestamp(t *testing.T) {
	t.Run("NoOverlap", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 1}, {ID: "a2", Timestamp: 3}}
		b := []events.Event{{ID: "b1", Timestamp: 2}, {ID: "b2", Timestamp: 4}}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 4 {
			t.Errorf("merging 2+2 non-overlapping: expected 4, got %d", len(merged))
		}
	})
	t.Run("SameTimestampBothKept", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 100}}
		b := []events.Event{{ID: "b1", Timestamp: 100}}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 2 {
			t.Errorf("two events at same timestamp: expected 2 in merged, got %d (event dropped)", len(merged))
		}
	})
	t.Run("MultipleOverlaps", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 1}, {ID: "a2", Timestamp: 3}, {ID: "a3", Timestamp: 5}}
		b := []events.Event{{ID: "b1", Timestamp: 1}, {ID: "b2", Timestamp: 3}, {ID: "b3", Timestamp: 5}}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 6 {
			t.Errorf("3+3 with all timestamps matching: expected 6, got %d", len(merged))
		}
	})
	t.Run("AllEventsPreserved", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 10}, {ID: "a2", Timestamp: 20}}
		b := []events.Event{{ID: "b1", Timestamp: 10}, {ID: "b2", Timestamp: 15}}
		merged := events.MergeEventStreams(a, b)
		ids := map[string]bool{}
		for _, e := range merged {
			ids[e.ID] = true
		}
		for _, expected := range []string{"a1", "a2", "b1", "b2"} {
			if !ids[expected] {
				t.Errorf("event %s missing from merged result", expected)
			}
		}
	})
	t.Run("EmptyStreams", func(t *testing.T) {
		merged := events.MergeEventStreams(nil, nil)
		if len(merged) != 0 {
			t.Errorf("merging empty streams: expected 0, got %d", len(merged))
		}
	})
}

func TestLatentUrgencyBucketBoundaries(t *testing.T) {
	t.Run("ExactBoundary100", func(t *testing.T) {
		bucket := models.IncidentUrgencyBucket(100)
		if bucket != "immediate" {
			t.Errorf("score 100 should be 'immediate', got '%s'", bucket)
		}
	})
	t.Run("ExactBoundary60", func(t *testing.T) {
		bucket := models.IncidentUrgencyBucket(60)
		if bucket != "urgent" {
			t.Errorf("score 60 should be 'urgent', got '%s'", bucket)
		}
	})
	t.Run("ExactBoundary30", func(t *testing.T) {
		bucket := models.IncidentUrgencyBucket(30)
		if bucket != "delayed" {
			t.Errorf("score 30 should be 'delayed', got '%s'", bucket)
		}
	})
	t.Run("AboveImmediate", func(t *testing.T) {
		bucket := models.IncidentUrgencyBucket(150)
		if bucket != "immediate" {
			t.Errorf("score 150 should be 'immediate', got '%s'", bucket)
		}
	})
	t.Run("BelowMinimal", func(t *testing.T) {
		bucket := models.IncidentUrgencyBucket(0)
		if bucket != "minimal" {
			t.Errorf("score 0 should be 'minimal', got '%s'", bucket)
		}
	})
}
