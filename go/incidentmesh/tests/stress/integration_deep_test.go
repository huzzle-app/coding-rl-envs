package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/communications"
	"incidentmesh/internal/consensus"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/events"
	"incidentmesh/internal/resilience"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/internal/workflow"
	"incidentmesh/pkg/models"
)

func TestIntegrationSeverityRangeToTriageSort(t *testing.T) {
	incidents := []models.Incident{
		{ID: "i1", Severity: 1, Criticality: 1},
		{ID: "i2", Severity: 2, Criticality: 3},
		{ID: "i3", Severity: 3, Criticality: 2},
		{ID: "i4", Severity: 4, Criticality: 4},
		{ID: "i5", Severity: 5, Criticality: 5},
	}

	t.Run("FilterAndSortConsistent", func(t *testing.T) {
		critical := models.IncidentsBySeverityRange(incidents, 4, 5)
		if len(critical) != 2 {
			t.Fatalf("range [4,5]: expected 2, got %d", len(critical))
		}
		sorted := triage.DeterministicTriageSort(critical)
		if sorted[0].Severity < sorted[1].Severity {
			t.Error("sorted triage should have higher severity first")
		}
	})
	t.Run("FilterPreservesAllInRange", func(t *testing.T) {
		all := models.IncidentsBySeverityRange(incidents, 1, 5)
		if len(all) != 5 {
			t.Errorf("range [1,5]: expected 5, got %d", len(all))
		}
	})
	t.Run("EmptyFilterEmptySort", func(t *testing.T) {
		empty := models.IncidentsBySeverityRange(incidents, 10, 20)
		sorted := triage.DeterministicTriageSort(empty)
		if len(sorted) != 0 {
			t.Error("empty filter should produce empty sort")
		}
	})
	t.Run("SortThenEscalation", func(t *testing.T) {
		sorted := triage.DeterministicTriageSort(incidents)
		topPriority := sorted[0].Severity*3 + sorted[0].Criticality*2
		if !triage.MeetsEscalationThreshold(topPriority, 10) {
			t.Errorf("top priority %d should meet threshold 10", topPriority)
		}
	})
}

func TestIntegrationCapacityToDistribution(t *testing.T) {
	t.Run("ScoreAndDistribute", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "H1", BedsFree: 50, ICUFree: 10, DistanceK: 2.0},
			{Name: "H2", BedsFree: 10, ICUFree: 2, DistanceK: 20.0},
		}
		s1 := capacity.WeightedCapacityScore(facilities[0])
		s2 := capacity.WeightedCapacityScore(facilities[1])
		if s2 >= s1 {
			t.Fatalf("H1 should score higher (more beds, closer): H1=%.1f, H2=%.1f", s1, s2)
		}
		dist := capacity.DistributeLoad(facilities, 60)
		if dist["H1"] <= dist["H2"] {
			t.Errorf("H1 (more capacity) should get more patients: H1=%d, H2=%d",
				dist["H1"], dist["H2"])
		}
	})
	t.Run("SurgeCheckAfterDistribution", func(t *testing.T) {
		f := capacity.Facility{Name: "Test", BedsFree: 20, ICUFree: 5}
		dist := capacity.DistributeLoad([]capacity.Facility{f}, 25)
		assigned := dist[f.Name]
		canHandleSurge := capacity.SurgeCapacityCheck(f, assigned)
		if !canHandleSurge {
			t.Errorf("facility with 25 beds getting %d patients: should handle surge", assigned)
		}
	})
	t.Run("OverloadedFacility", func(t *testing.T) {
		f := capacity.Facility{Name: "Small", BedsFree: 5, ICUFree: 1}
		if capacity.SurgeCapacityCheck(f, 10) {
			t.Error("facility with 6 beds should not handle 10 patients")
		}
	})
	t.Run("CriticalBedRatioMatters", func(t *testing.T) {
		ratio := capacity.CriticalBedRatio(10, 90)
		if math.Abs(ratio-0.1) > 0.01 {
			t.Errorf("10 ICU / 100 total: expected ratio 0.1, got %.3f", ratio)
		}
	})
}

func TestIntegrationEventMergeToGapDetection(t *testing.T) {
	t.Run("MergedNoGaps", func(t *testing.T) {
		a := []events.Event{
			{ID: "a1", Timestamp: 1},
			{ID: "a2", Timestamp: 3},
			{ID: "a3", Timestamp: 5},
		}
		b := []events.Event{
			{ID: "b1", Timestamp: 2},
			{ID: "b2", Timestamp: 4},
			{ID: "b3", Timestamp: 6},
		}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 6 {
			t.Fatalf("merge 3+3: expected 6, got %d", len(merged))
		}
		gaps := events.DetectSequenceGaps(merged)
		if len(gaps) != 0 {
			t.Errorf("consecutive merged stream: expected 0 gaps, got %d", len(gaps))
		}
	})
	t.Run("MergedWithGap", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 1}}
		b := []events.Event{{ID: "b1", Timestamp: 5}}
		merged := events.MergeEventStreams(a, b)
		gaps := events.DetectSequenceGaps(merged)
		if len(gaps) == 0 {
			t.Error("gap between 1 and 5: should detect at least one gap")
		}
	})
	t.Run("OverlappingTimestampsPreserved", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 10}, {ID: "a2", Timestamp: 20}}
		b := []events.Event{{ID: "b1", Timestamp: 10}, {ID: "b2", Timestamp: 20}}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 4 {
			t.Errorf("2+2 with overlapping timestamps: expected 4, got %d", len(merged))
		}
	})
}

func TestIntegrationQuorumToConsensus(t *testing.T) {
	t.Run("QuorumAckThenReachability", func(t *testing.T) {
		quorum := communications.QuorumAck(3, 5)
		reachable := consensus.ReachabilityQuorum(3, 5)
		if quorum != reachable {
			t.Errorf("3/5 ack quorum (%v) should match reachability quorum (%v)",
				quorum, reachable)
		}
	})
	t.Run("BothRejectMinority", func(t *testing.T) {
		ackOK := communications.QuorumAck(1, 5)
		reachOK := consensus.ReachabilityQuorum(1, 5)
		if ackOK || reachOK {
			t.Errorf("1/5 should fail both quorum checks: ack=%v, reach=%v", ackOK, reachOK)
		}
	})
	t.Run("StrongestCandidateWithQuorum", func(t *testing.T) {
		candidates := []string{"a", "b", "c"}
		weights := map[string]int{"a": 10, "b": 30, "c": 20}
		strongest := consensus.FindStrongestCandidate(candidates, weights)
		if strongest != "b" {
			t.Errorf("strongest should be 'b' (weight 30), got '%s'", strongest)
		}
	})
}

func TestIntegrationEscalationToNotification(t *testing.T) {
	t.Run("HighSeverityEscalatesAndNotifies", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(5)
		if level < 3 {
			t.Fatalf("severity 5 should be level >= 3, got %d", level)
		}
		responders := escalation.CalculateRequiredResponders(5, 20.0)
		if responders < 10 {
			t.Fatalf("severity 5 20sqkm: expected >= 10 responders, got %d", responders)
		}
		recipients := make([]string, responders)
		for i := range recipients {
			recipients[i] = "responder"
		}
		delivered := communications.NotifyAll(recipients, "active emergency")
		if delivered != responders {
			t.Errorf("all %d responders should be notified, got %d", responders, delivered)
		}
	})
	t.Run("MediumSeverityEscalatesCorrectly", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(3)
		if level != 2 {
			t.Errorf("severity 3: expected level 2, got %d", level)
		}
	})
	t.Run("EscalationThenCooldown", func(t *testing.T) {
		urgency := escalation.EscalationUrgencyScore(4, 60)
		if urgency < 30 {
			t.Errorf("severity 4 at 60min: expected urgency > 30, got %.1f", urgency)
		}
		validTransition := escalation.ValidEscalationTransition(1, 2)
		if !validTransition {
			t.Error("1->2 should be a valid escalation transition")
		}
	})
}

func TestIntegrationRegionScoreToRouting(t *testing.T) {
	t.Run("HighScoreRegionBetterRoute", func(t *testing.T) {
		units := []models.Unit{
			{ID: "n1", Region: "north", Capacity: 10, ETAmins: 30, Status: "available"},
			{ID: "s1", Region: "south", Capacity: 10, ETAmins: 5, Status: "available"},
		}
		northScore := routing.WeightedRegionScore(units, "north")
		southScore := routing.WeightedRegionScore(units, "south")
		if northScore >= southScore {
			t.Errorf("south (ETA=5) should score higher than north (ETA=30): south=%.1f, north=%.1f",
				southScore, northScore)
		}
	})
	t.Run("TimeWindowAndRegionCombined", func(t *testing.T) {
		units := []models.Unit{
			{ID: "u1", ETAmins: 5, Region: "east", Status: "available"},
			{ID: "u2", ETAmins: 15, Region: "east", Status: "available"},
			{ID: "u3", ETAmins: 25, Region: "east", Status: "available"},
		}
		inWindow := routing.SelectUnitsInTimeWindow(units, 5, 25)
		if len(inWindow) != 3 {
			t.Errorf("window [5,25]: expected 3 units, got %d", len(inWindow))
		}
	})
	t.Run("CrossRegionPenaltyApplied", func(t *testing.T) {
		samePenalty := routing.CrossRegionPenalty("north", "north")
		diffPenalty := routing.CrossRegionPenalty("north", "south")
		if samePenalty != 0 {
			t.Errorf("same region penalty should be 0, got %.1f", samePenalty)
		}
		if diffPenalty <= 0 {
			t.Errorf("cross region penalty should be > 0, got %.1f", diffPenalty)
		}
	})
}

func TestIntegrationBackoffToRetry(t *testing.T) {
	t.Run("BackoffWithinBudget", func(t *testing.T) {
		delay := resilience.ExponentialBackoffWithCap(2, 100, 5000)
		if delay > 5000 {
			t.Errorf("backoff should be capped at 5000, got %d", delay)
		}
		allowed := resilience.RetryBudgetCheck(2, 5, 1000, 1500, 2000)
		if !allowed {
			t.Error("2/5 budget within window: should allow")
		}
	})
	t.Run("ExhaustedBudgetDenied", func(t *testing.T) {
		allowed := resilience.RetryBudgetCheck(5, 5, 1000, 1500, 2000)
		if allowed {
			t.Error("5/5 budget within window: should deny")
		}
	})
	t.Run("CascadeToBackoff", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(10, 3, 0.5)
		expectedImpact := 10.0 * math.Pow(1.5, 3)
		if math.Abs(impact-expectedImpact) > 1.0 {
			t.Errorf("cascade: expected ~%.1f, got %.1f", expectedImpact, impact)
		}
		delay := resilience.ExponentialBackoffWithCap(5, 200, 10000)
		if delay > 10000 {
			t.Errorf("capped backoff: expected <= 10000, got %d", delay)
		}
	})
}

func TestIntegrationDispatchPlanPipeline(t *testing.T) {
	t.Run("ValidateSortMerge", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", UnitIDs: []string{"u1"}, Priority: 50, EstimatedETA: 10},
			{IncidentID: "b", UnitIDs: []string{"u2"}, Priority: 100, EstimatedETA: 5},
			{IncidentID: "c", Priority: 75, EstimatedETA: 15},
		}
		var valid []models.DispatchPlan
		for _, p := range plans {
			if models.DispatchPlanValidate(p) && len(p.UnitIDs) > 0 {
				valid = append(valid, p)
			}
		}
		if len(valid) != 2 {
			t.Fatalf("expected 2 valid plans, got %d", len(valid))
		}
		sorted := models.SortPlansByPriority(valid)
		if sorted[0].Priority != 100 {
			t.Errorf("highest priority should be first: got %d", sorted[0].Priority)
		}
		totalETA := models.PlanETATotal(sorted)
		if totalETA != 15 {
			t.Errorf("total ETA 10+5: expected 15, got %d", totalETA)
		}
	})
	t.Run("AveragePriorityOfValid", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", UnitIDs: []string{"u1"}, Priority: 10},
			{IncidentID: "b", UnitIDs: []string{"u2"}, Priority: 30},
		}
		avg := models.AveragePriority(plans)
		if math.Abs(avg-20.0) > 0.5 {
			t.Errorf("average of 10 and 30: expected 20.0, got %.1f", avg)
		}
	})
}

func TestIntegrationVersionedMergeToWorkflow(t *testing.T) {
	t.Run("MergeThenCompensate", func(t *testing.T) {
		a := map[string]int64{"step1": 3, "step2": 7}
		b := map[string]int64{"step1": 5, "step2": 2}
		merged := workflow.MergeVersionedResults(a, b)
		if merged["step1"] != 5 {
			t.Errorf("step1: expected version 5 (higher), got %d", merged["step1"])
		}
		if merged["step2"] != 7 {
			t.Errorf("step2: expected version 7 (higher), got %d", merged["step2"])
		}
	})
	t.Run("EmptyMerge", func(t *testing.T) {
		a := map[string]int64{}
		b := map[string]int64{"key": 1}
		merged := workflow.MergeVersionedResults(a, b)
		if merged["key"] != 1 {
			t.Errorf("empty merge: expected key=1, got %d", merged["key"])
		}
	})
}

func TestIntegrationTriageToDispatchDecision(t *testing.T) {
	t.Run("HighSeverityGetsEscalation", func(t *testing.T) {
		inc := models.Incident{ID: "critical", Severity: 5, Criticality: 5, Region: "north"}
		priority := triage.PriorityScore(inc)
		required := triage.RequiredUnits(inc)
		if !triage.MeetsEscalationThreshold(priority, 100) {
			t.Errorf("critical incident priority %d: should meet escalation threshold 100", priority)
		}
		if required < 3 {
			t.Errorf("critical incident: expected >= 3 required units, got %d", required)
		}
	})
	t.Run("LowSeverityNoEscalation", func(t *testing.T) {
		inc := models.Incident{Severity: 1, Criticality: 1}
		priority := triage.PriorityScore(inc)
		if triage.MeetsEscalationThreshold(priority, 100) {
			t.Errorf("low priority %d should not meet threshold 100", priority)
		}
	})
}

func TestIntegrationEndToEndIncidentResponse(t *testing.T) {
	t.Run("FullResponsePipeline", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "fire-1", Severity: 5, Criticality: 4, Region: "north"},
			{ID: "minor-1", Severity: 1, Criticality: 1, Region: "south"},
			{ID: "med-1", Severity: 3, Criticality: 3, Region: "north"},
		}

		critical := models.IncidentsBySeverityRange(incidents, 3, 5)
		if len(critical) != 2 {
			t.Fatalf("severity [3,5] filter: expected 2, got %d", len(critical))
		}

		sorted := triage.DeterministicTriageSort(critical)
		topScore := sorted[0].Severity*3 + sorted[0].Criticality*2
		if topScore < 10 {
			t.Fatalf("top priority score should be >= 10, got %d", topScore)
		}

		units := []models.Unit{
			{ID: "u1", Region: "north", ETAmins: 5, Capacity: 10, Status: "available"},
			{ID: "u2", Region: "north", ETAmins: 15, Capacity: 20, Status: "available"},
		}
		selected := routing.SelectUnitsInTimeWindow(units, 0, 20)
		if len(selected) != 2 {
			t.Errorf("window [0,20]: expected 2 units, got %d", len(selected))
		}
	})
}

func TestIntegrationHealthScoreComponents(t *testing.T) {
	t.Run("AverageScore", func(t *testing.T) {
		scores := []float64{0.8, 0.9, 1.0}
		avg := resilience.HealthScore(scores)
		expected := 0.9
		if math.Abs(avg-expected) > 0.01 {
			t.Errorf("average health [0.8, 0.9, 1.0]: expected %.1f, got %.2f", expected, avg)
		}
	})
	t.Run("EmptyDefaultsToHealthy", func(t *testing.T) {
		score := resilience.HealthScore(nil)
		if score != 1.0 {
			t.Errorf("no components: expected 1.0 (healthy default), got %.2f", score)
		}
	})
}
