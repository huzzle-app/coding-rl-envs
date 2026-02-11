package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/communications"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/events"
	"incidentmesh/internal/resilience"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestMultiStepSeverityRangeToTriage(t *testing.T) {
	incidents := []models.Incident{
		{ID: "i1", Severity: 1, Criticality: 1},
		{ID: "i2", Severity: 2, Criticality: 2},
		{ID: "i3", Severity: 3, Criticality: 3},
		{ID: "i4", Severity: 4, Criticality: 4},
		{ID: "i5", Severity: 5, Criticality: 5},
	}

	t.Run("FilterThenSort", func(t *testing.T) {
		filtered := models.IncidentsBySeverityRange(incidents, 3, 5)
		if len(filtered) != 3 {
			t.Fatalf("filter [3,5]: expected 3 incidents, got %d", len(filtered))
		}
		sorted := triage.DeterministicTriageSort(filtered)
		first := sorted[0]
		expected := first.Severity*3 + first.Criticality*2
		for _, inc := range sorted[1:] {
			score := inc.Severity*3 + inc.Criticality*2
			if score > expected {
				t.Errorf("sort after filter: not descending (%d after %d)", score, expected)
			}
			expected = score
		}
	})
	t.Run("FilterBoundarySev3Included", func(t *testing.T) {
		filtered := models.IncidentsBySeverityRange(incidents, 3, 5)
		foundSev3 := false
		for _, inc := range filtered {
			if inc.Severity == 3 {
				foundSev3 = true
			}
		}
		if !foundSev3 {
			t.Error("severity 3 should be included in [3,5] range for triage")
		}
	})
	t.Run("FilterBoundarySev5Included", func(t *testing.T) {
		filtered := models.IncidentsBySeverityRange(incidents, 3, 5)
		foundSev5 := false
		for _, inc := range filtered {
			if inc.Severity == 5 {
				foundSev5 = true
			}
		}
		if !foundSev5 {
			t.Error("severity 5 should be included in [3,5] range for triage")
		}
	})
}

func TestMultiStepPlanValidateToMerge(t *testing.T) {
	t.Run("InvalidPlanFilteredBeforeMerge", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "inc-1", UnitIDs: []string{"u1"}, Priority: 100},
			{IncidentID: "inc-2", UnitIDs: nil, Priority: 50},
			{IncidentID: "inc-3", UnitIDs: []string{"u3"}, Priority: 75},
		}
		var valid []models.DispatchPlan
		for _, p := range plans {
			if models.DispatchPlanValidate(p) && len(p.UnitIDs) > 0 {
				valid = append(valid, p)
			}
		}
		if len(valid) != 2 {
			t.Fatalf("expected 2 valid plans (with units), got %d", len(valid))
		}
	})
	t.Run("ValidateThenAverage", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", UnitIDs: []string{"u1"}, Priority: 10},
			{IncidentID: "b", UnitIDs: []string{"u2"}, Priority: 20},
		}
		avg := models.AveragePriority(plans)
		if math.Abs(avg-15.0) > 0.5 {
			t.Errorf("average priority of 10 and 20: expected 15.0, got %.1f", avg)
		}
	})
}

func TestMultiStepETASumToRouting(t *testing.T) {
	t.Run("TotalETADeterminesUrgency", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{EstimatedETA: 10}, {EstimatedETA: 20}, {EstimatedETA: 30},
		}
		totalETA := models.PlanETATotal(plans)
		if totalETA != 60 {
			t.Fatalf("total ETA 10+20+30: expected 60, got %d", totalETA)
		}
		units := []models.Unit{
			{ID: "u1", ETAmins: 5, Region: "north"},
			{ID: "u2", ETAmins: 50, Region: "north"},
		}
		selected := routing.SelectUnitsInTimeWindow(units, 0, totalETA)
		if len(selected) != 2 {
			t.Errorf("window [0, %d]: expected 2 units, got %d", totalETA, len(selected))
		}
	})
	t.Run("PartialETAMisses", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{EstimatedETA: 5}, {EstimatedETA: 10}, {EstimatedETA: 15},
		}
		totalETA := models.PlanETATotal(plans)
		if totalETA != 30 {
			t.Fatalf("total ETA: expected 30, got %d (last plan missing?)", totalETA)
		}
	})
}

func TestMultiStepEscalationMappingToResponders(t *testing.T) {
	t.Run("Severity3MappedCorrectly", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(3)
		if level != 2 {
			t.Fatalf("severity 3 should map to level 2, got %d", level)
		}
		responders := escalation.CalculateRequiredResponders(3, 10.0)
		if responders < 6 {
			t.Errorf("severity 3 with 10sqkm: expected >= 6 responders, got %d", responders)
		}
	})
	t.Run("Severity4MoreThan3", func(t *testing.T) {
		r3 := escalation.CalculateRequiredResponders(3, 10.0)
		r4 := escalation.CalculateRequiredResponders(4, 10.0)
		if r4 <= r3 {
			t.Errorf("severity 4 (%d) should need more responders than severity 3 (%d)", r4, r3)
		}
	})
	t.Run("MappingChainMonotonic", func(t *testing.T) {
		for s := 1; s < 5; s++ {
			l1 := escalation.MapSeverityToEscalationLevel(s)
			l2 := escalation.MapSeverityToEscalationLevel(s + 1)
			r1 := escalation.CalculateRequiredResponders(s, 20.0)
			r2 := escalation.CalculateRequiredResponders(s+1, 20.0)
			if l2 <= l1 {
				t.Errorf("level chain: sev %d (level %d) should be < sev %d (level %d)", s, l1, s+1, l2)
			}
			if r2 < r1 {
				t.Errorf("responder chain: sev %d (%d) should be <= sev %d (%d)", s, r1, s+1, r2)
			}
		}
	})
}

func TestMultiStepCapacityToDistribution(t *testing.T) {
	t.Run("HighCapacityGetsMore", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "small", BedsFree: 10, ICUFree: 2, DistanceK: 5.0, Region: "north"},
			{Name: "large", BedsFree: 90, ICUFree: 20, DistanceK: 3.0, Region: "north"},
		}
		scoreSmall := capacity.RankScore(facilities[0])
		scoreLarge := capacity.RankScore(facilities[1])
		if scoreLarge <= scoreSmall {
			t.Fatalf("large facility should score higher: small=%.1f, large=%.1f", scoreSmall, scoreLarge)
		}
		dist := capacity.DistributeLoad(facilities, 100)
		if dist["large"] <= dist["small"] {
			t.Errorf("large facility should get more patients: small=%d, large=%d",
				dist["small"], dist["large"])
		}
	})
}

func TestMultiStepEventMergeToSequence(t *testing.T) {
	t.Run("MergedStreamHasNoGaps", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 1}, {ID: "a2", Timestamp: 3}}
		b := []events.Event{{ID: "b1", Timestamp: 2}, {ID: "b2", Timestamp: 4}}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 4 {
			t.Fatalf("merge 2+2: expected 4 events, got %d", len(merged))
		}
		gaps := events.DetectSequenceGaps(merged)
		if len(gaps) != 0 {
			t.Errorf("merged consecutive stream should have 0 gaps, got %d", len(gaps))
		}
	})
	t.Run("OverlappingTimestampsPreserved", func(t *testing.T) {
		a := []events.Event{{ID: "a1", Timestamp: 10}}
		b := []events.Event{{ID: "b1", Timestamp: 10}}
		merged := events.MergeEventStreams(a, b)
		if len(merged) != 2 {
			t.Errorf("same timestamp: both events should be preserved, got %d", len(merged))
		}
	})
}

func TestMultiStepNotifyToQuorum(t *testing.T) {
	t.Run("AllNotifiedQuorumReached", func(t *testing.T) {
		recipients := []string{"a", "b", "c", "d", "e"}
		delivered := communications.NotifyAll(recipients, "emergency")
		if delivered != 5 {
			t.Fatalf("expected all 5 notified, got %d", delivered)
		}
		quorum := communications.QuorumAck(delivered, 5)
		if !quorum {
			t.Error("all 5 acked out of 5: quorum should be reached")
		}
	})
	t.Run("PartialDeliveryNoQuorum", func(t *testing.T) {
		recipients := []string{"a", "b", "c", "d", "e"}
		delivered := communications.NotifyAll(recipients, "emergency")
		partialAck := delivered / 3
		if communications.QuorumAck(partialAck, 5) {
			t.Errorf("%d acks out of 5 should not be quorum", partialAck)
		}
	})
}

func TestMultiStepCascadeToBackoff(t *testing.T) {
	t.Run("CascadeImpactDeterminesRetry", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(10, 3, 0.5)
		expected := 10.0 * math.Pow(1.5, 3)
		if math.Abs(impact-expected) > 1.0 {
			t.Fatalf("cascade impact: expected %.1f (exponential), got %.1f", expected, impact)
		}
		retryDelay := resilience.ExponentialBackoffWithCap(3, 100, 5000)
		if retryDelay > 5000 {
			t.Errorf("backoff should be capped at 5000, got %d", retryDelay)
		}
	})
	t.Run("HighCascadeHighBackoff", func(t *testing.T) {
		impact := resilience.CascadeImpactEstimate(100, 5, 1.0)
		if impact < 1000 {
			t.Fatalf("deep cascade: expected > 1000 impact, got %.0f", impact)
		}
		d5 := resilience.ExponentialBackoffWithCap(5, 200, 10000)
		if d5 > 10000 {
			t.Errorf("backoff at attempt 5: expected <= 10000, got %d", d5)
		}
	})
}

func TestMultiStepTriageThresholdToEscalation(t *testing.T) {
	t.Run("PriorityAtThresholdEscalates", func(t *testing.T) {
		inc := models.Incident{Severity: 4, Criticality: 3}
		priority := triage.PriorityScore(inc)
		threshold := priority
		if !triage.MeetsEscalationThreshold(priority, threshold) {
			t.Errorf("priority %d at threshold %d: should trigger escalation (inclusive)", priority, threshold)
		}
	})
	t.Run("PriorityAboveThresholdEscalates", func(t *testing.T) {
		inc := models.Incident{Severity: 5, Criticality: 5}
		priority := triage.PriorityScore(inc)
		if !triage.MeetsEscalationThreshold(priority, 100) {
			t.Errorf("priority %d at threshold 100: should escalate", priority)
		}
	})
}

func TestMultiStepRegionScoreToRoute(t *testing.T) {
	t.Run("BestRegionSelectedForRouting", func(t *testing.T) {
		units := []models.Unit{
			{ID: "n1", Region: "north", Capacity: 20, ETAmins: 30, Status: "available"},
			{ID: "n2", Region: "north", Capacity: 10, ETAmins: 60, Status: "available"},
			{ID: "s1", Region: "south", Capacity: 20, ETAmins: 5, Status: "available"},
			{ID: "s2", Region: "south", Capacity: 10, ETAmins: 10, Status: "available"},
		}
		northScore := routing.WeightedRegionScore(units, "north")
		southScore := routing.WeightedRegionScore(units, "south")
		if northScore >= southScore {
			t.Errorf("south (faster ETA) should score higher: north=%.1f, south=%.1f", northScore, southScore)
		}
	})
}
