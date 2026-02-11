package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/communications"
	"incidentmesh/internal/consensus"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/events"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestDomainEscalationLevelGapSeverity3(t *testing.T) {
	t.Run("Severity1MapsToLevel0", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(1)
		if level != 0 {
			t.Errorf("severity 1 should map to level 0, got %d", level)
		}
	})
	t.Run("Severity2MapsToLevel1", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(2)
		if level != 1 {
			t.Errorf("severity 2 should map to level 1, got %d", level)
		}
	})
	t.Run("Severity3MapsToLevel2", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(3)
		if level != 2 {
			t.Errorf("severity 3 should map to level 2, got %d (missing mapping)", level)
		}
	})
	t.Run("Severity4MapsToLevel3", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(4)
		if level != 3 {
			t.Errorf("severity 4 should map to level 3, got %d", level)
		}
	})
	t.Run("Severity5MapsToLevel4", func(t *testing.T) {
		level := escalation.MapSeverityToEscalationLevel(5)
		if level != 4 {
			t.Errorf("severity 5 should map to level 4, got %d", level)
		}
	})
	t.Run("MonotonicMapping", func(t *testing.T) {
		for s := 1; s < 5; s++ {
			lower := escalation.MapSeverityToEscalationLevel(s)
			upper := escalation.MapSeverityToEscalationLevel(s + 1)
			if upper <= lower {
				t.Errorf("severity %d->%d: level should increase (%d->%d)", s, s+1, lower, upper)
			}
		}
	})
}

func TestDomainResponderCountInversion(t *testing.T) {
	t.Run("HigherSeverityMoreResponders", func(t *testing.T) {
		r3 := escalation.CalculateRequiredResponders(3, 10.0)
		r4 := escalation.CalculateRequiredResponders(4, 10.0)
		r5 := escalation.CalculateRequiredResponders(5, 10.0)
		if r4 <= r3 {
			t.Errorf("severity 4 (%d responders) should need more than severity 3 (%d)", r4, r3)
		}
		if r5 <= r4 {
			t.Errorf("severity 5 (%d responders) should need more than severity 4 (%d)", r5, r4)
		}
	})
	t.Run("MonotonicWithSeverity", func(t *testing.T) {
		prev := escalation.CalculateRequiredResponders(1, 20.0)
		for s := 2; s <= 5; s++ {
			curr := escalation.CalculateRequiredResponders(s, 20.0)
			if curr < prev {
				t.Errorf("severity %d (%d) should need >= severity %d (%d)", s, curr, s-1, prev)
			}
			prev = curr
		}
	})
	t.Run("LargerAreaMoreResponders", func(t *testing.T) {
		small := escalation.CalculateRequiredResponders(3, 5.0)
		large := escalation.CalculateRequiredResponders(3, 100.0)
		if large <= small {
			t.Errorf("100sqkm (%d) should need more responders than 5sqkm (%d)", large, small)
		}
	})
	t.Run("Severity3vs4AtThreshold", func(t *testing.T) {
		r3 := escalation.CalculateRequiredResponders(3, 0)
		r4 := escalation.CalculateRequiredResponders(4, 0)
		if r4 <= r3 {
			t.Errorf("at 0 area: severity 4 (%d) must require more than severity 3 (%d)", r4, r3)
		}
	})
}

func TestDomainRegionScoreETADirection(t *testing.T) {
	t.Run("LowerETAHigherScore", func(t *testing.T) {
		fast := []models.Unit{{Region: "north", Capacity: 10, ETAmins: 5, Status: "available"}}
		slow := []models.Unit{{Region: "north", Capacity: 10, ETAmins: 60, Status: "available"}}
		scoreFast := routing.WeightedRegionScore(fast, "north")
		scoreSlow := routing.WeightedRegionScore(slow, "north")
		if scoreSlow >= scoreFast {
			t.Errorf("slow region (ETA=60) should score lower than fast (ETA=5): slow=%.1f, fast=%.1f",
				scoreSlow, scoreFast)
		}
	})
	t.Run("ETAPenaltyNotReward", func(t *testing.T) {
		unit1 := []models.Unit{{Region: "a", Capacity: 20, ETAmins: 5, Status: "available"}}
		unit2 := []models.Unit{{Region: "a", Capacity: 20, ETAmins: 100, Status: "available"}}
		score1 := routing.WeightedRegionScore(unit1, "a")
		score2 := routing.WeightedRegionScore(unit2, "a")
		if score2 > score1 {
			t.Errorf("100min ETA unit should score LOWER than 5min ETA: 100min=%.1f, 5min=%.1f",
				score2, score1)
		}
	})
	t.Run("CapacityStillMatters", func(t *testing.T) {
		highCap := []models.Unit{{Region: "r", Capacity: 100, ETAmins: 10, Status: "available"}}
		lowCap := []models.Unit{{Region: "r", Capacity: 5, ETAmins: 10, Status: "available"}}
		scoreHigh := routing.WeightedRegionScore(highCap, "r")
		scoreLow := routing.WeightedRegionScore(lowCap, "r")
		if scoreHigh <= scoreLow {
			t.Errorf("high capacity should score higher: high=%.1f, low=%.1f", scoreHigh, scoreLow)
		}
	})
	t.Run("UnavailableUnitsExcluded", func(t *testing.T) {
		units := []models.Unit{
			{Region: "r", Capacity: 50, ETAmins: 5, Status: "busy"},
			{Region: "r", Capacity: 50, ETAmins: 5, Status: "offline"},
		}
		score := routing.WeightedRegionScore(units, "r")
		if score != 0 {
			t.Errorf("no available units: expected score 0, got %.1f", score)
		}
	})
}

func TestDomainTriageThresholdBoundary(t *testing.T) {
	t.Run("ExactThresholdMeets", func(t *testing.T) {
		if !triage.MeetsEscalationThreshold(100, 100) {
			t.Error("priority 100 should meet threshold 100 (inclusive boundary)")
		}
	})
	t.Run("AboveThreshold", func(t *testing.T) {
		if !triage.MeetsEscalationThreshold(101, 100) {
			t.Error("priority 101 should meet threshold 100")
		}
	})
	t.Run("BelowThreshold", func(t *testing.T) {
		if triage.MeetsEscalationThreshold(99, 100) {
			t.Error("priority 99 should not meet threshold 100")
		}
	})
	t.Run("ZeroThreshold", func(t *testing.T) {
		if !triage.MeetsEscalationThreshold(0, 0) {
			t.Error("priority 0 should meet threshold 0")
		}
	})
}

func TestDomainNotifyAllCompleteness(t *testing.T) {
	t.Run("AllRecipientsNotified", func(t *testing.T) {
		recipients := []string{"dispatch", "command", "ems", "fire", "police"}
		delivered := communications.NotifyAll(recipients, "active shooter")
		if delivered != 5 {
			t.Errorf("5 recipients: expected 5 delivered, got %d (dropped recipients)", delivered)
		}
	})
	t.Run("SingleRecipient", func(t *testing.T) {
		delivered := communications.NotifyAll([]string{"dispatch"}, "alert")
		if delivered != 1 {
			t.Errorf("1 recipient: expected 1 delivered, got %d", delivered)
		}
	})
	t.Run("TwoRecipients", func(t *testing.T) {
		delivered := communications.NotifyAll([]string{"a", "b"}, "msg")
		if delivered != 2 {
			t.Errorf("2 recipients: expected 2 delivered, got %d", delivered)
		}
	})
	t.Run("EmptyMessage", func(t *testing.T) {
		delivered := communications.NotifyAll([]string{"a"}, "")
		if delivered != 0 {
			t.Errorf("empty message: expected 0 delivered, got %d", delivered)
		}
	})
}

func TestDomainQuorumAcknowledgement(t *testing.T) {
	t.Run("MajorityOf3", func(t *testing.T) {
		if !communications.QuorumAck(2, 3) {
			t.Error("2 of 3: strict majority should be quorum")
		}
	})
	t.Run("MinorityOf3NotQuorum", func(t *testing.T) {
		if communications.QuorumAck(1, 3) {
			t.Error("1 of 3: not a majority, should not be quorum")
		}
	})
	t.Run("MajorityOf5", func(t *testing.T) {
		if !communications.QuorumAck(3, 5) {
			t.Error("3 of 5: strict majority should be quorum")
		}
	})
	t.Run("MinorityOf5NotQuorum", func(t *testing.T) {
		if communications.QuorumAck(2, 5) {
			t.Error("2 of 5: not a majority, should not be quorum")
		}
	})
	t.Run("HalfOf4NotQuorum", func(t *testing.T) {
		if communications.QuorumAck(2, 4) {
			t.Error("2 of 4: exactly half is not a strict majority, should not be quorum")
		}
	})
	t.Run("MajorityOf4", func(t *testing.T) {
		if !communications.QuorumAck(3, 4) {
			t.Error("3 of 4: strict majority should be quorum")
		}
	})
}

func TestDomainChannelPrioritySortDirection(t *testing.T) {
	t.Run("HighestFirst", func(t *testing.T) {
		channels := []string{"email", "sms", "radio"}
		scores := map[string]int{"email": 2, "sms": 5, "radio": 10}
		sorted := communications.PrioritySortChannels(channels, scores)
		if sorted[0] != "radio" {
			t.Errorf("radio (score 10) should be first, got %s", sorted[0])
		}
		if sorted[len(sorted)-1] != "email" {
			t.Errorf("email (score 2) should be last, got %s", sorted[len(sorted)-1])
		}
	})
	t.Run("DescendingOrder", func(t *testing.T) {
		channels := []string{"a", "b", "c", "d"}
		scores := map[string]int{"a": 1, "b": 4, "c": 2, "d": 3}
		sorted := communications.PrioritySortChannels(channels, scores)
		for i := 1; i < len(sorted); i++ {
			if scores[sorted[i]] > scores[sorted[i-1]] {
				t.Errorf("not descending at [%d]: %s(%d) after %s(%d)",
					i, sorted[i], scores[sorted[i]], sorted[i-1], scores[sorted[i-1]])
			}
		}
	})
	t.Run("SingleChannel", func(t *testing.T) {
		sorted := communications.PrioritySortChannels([]string{"only"}, map[string]int{"only": 5})
		if sorted[0] != "only" {
			t.Error("single channel should remain unchanged")
		}
	})
}

func TestDomainReachabilityQuorumBoundary(t *testing.T) {
	t.Run("ExactQuorumMet", func(t *testing.T) {
		if !consensus.ReachabilityQuorum(3, 5) {
			t.Error("3 of 5 reachable: quorum of 3 is met (5/2+1=3)")
		}
	})
	t.Run("BelowQuorum", func(t *testing.T) {
		if consensus.ReachabilityQuorum(2, 5) {
			t.Error("2 of 5 reachable: quorum of 3 not met")
		}
	})
	t.Run("AllReachable", func(t *testing.T) {
		if !consensus.ReachabilityQuorum(5, 5) {
			t.Error("all 5 reachable: quorum trivially met")
		}
	})
	t.Run("SingleNodeQuorum", func(t *testing.T) {
		if !consensus.ReachabilityQuorum(1, 1) {
			t.Error("1 of 1 reachable: quorum met")
		}
	})
	t.Run("TwoOfThree", func(t *testing.T) {
		if !consensus.ReachabilityQuorum(2, 3) {
			t.Error("2 of 3 reachable: quorum of 2 is met (3/2+1=2)")
		}
	})
}

func TestDomainStrongestCandidateWithNegativeWeights(t *testing.T) {
	t.Run("PositiveWeights", func(t *testing.T) {
		candidates := []string{"a", "b", "c"}
		weights := map[string]int{"a": 10, "b": 30, "c": 20}
		best := consensus.FindStrongestCandidate(candidates, weights)
		if best != "b" {
			t.Errorf("node b (weight 30) should be strongest, got %s", best)
		}
	})
	t.Run("ZeroWeights", func(t *testing.T) {
		candidates := []string{"a", "b"}
		weights := map[string]int{"a": 0, "b": 0}
		best := consensus.FindStrongestCandidate(candidates, weights)
		if best != "a" {
			t.Errorf("equal zero weights: should return first candidate 'a', got '%s'", best)
		}
	})
	t.Run("NegativeWeights", func(t *testing.T) {
		candidates := []string{"a", "b", "c"}
		weights := map[string]int{"a": -5, "b": -3, "c": -1}
		best := consensus.FindStrongestCandidate(candidates, weights)
		if best != "c" {
			t.Errorf("negative weights: 'c' (weight -1) is highest, got '%s'", best)
		}
	})
	t.Run("SingleCandidate", func(t *testing.T) {
		best := consensus.FindStrongestCandidate([]string{"only"}, map[string]int{"only": 42})
		if best != "only" {
			t.Errorf("single candidate should return 'only', got '%s'", best)
		}
	})
}

func TestDomainDeliveryConfirmationBoundary(t *testing.T) {
	t.Run("WithinTimeout", func(t *testing.T) {
		if !communications.DeliveryConfirmation(1000, 1500, 1000) {
			t.Error("500ms elapsed with 1000ms timeout: should be confirmed")
		}
	})
	t.Run("ExactTimeoutBoundary", func(t *testing.T) {
		if !communications.DeliveryConfirmation(1000, 2000, 1000) {
			t.Error("exactly at timeout boundary (1000ms): should still be valid")
		}
	})
	t.Run("PastTimeout", func(t *testing.T) {
		if communications.DeliveryConfirmation(1000, 3000, 1000) {
			t.Error("2000ms elapsed with 1000ms timeout: should be expired")
		}
	})
}

func TestDomainTimeWindowRouteExclusive(t *testing.T) {
	units := []models.Unit{
		{ID: "u1", ETAmins: 5},
		{ID: "u2", ETAmins: 10},
		{ID: "u3", ETAmins: 15},
		{ID: "u4", ETAmins: 20},
	}

	t.Run("InclusiveEndBoundary", func(t *testing.T) {
		selected := routing.SelectUnitsInTimeWindow(units, 5, 15)
		ids := map[string]bool{}
		for _, u := range selected {
			ids[u.ID] = true
		}
		if !ids["u3"] {
			t.Error("unit with ETA=15 should be included in window [5,15] (inclusive end)")
		}
	})
	t.Run("InclusiveStartBoundary", func(t *testing.T) {
		selected := routing.SelectUnitsInTimeWindow(units, 5, 20)
		ids := map[string]bool{}
		for _, u := range selected {
			ids[u.ID] = true
		}
		if !ids["u1"] {
			t.Error("unit with ETA=5 should be included in window [5,20] (inclusive start)")
		}
	})
	t.Run("ExactMatch", func(t *testing.T) {
		selected := routing.SelectUnitsInTimeWindow(units, 10, 10)
		if len(selected) != 1 {
			t.Errorf("window [10,10] should match exactly 1 unit (ETA=10), got %d", len(selected))
		}
	})
	t.Run("AllInWindow", func(t *testing.T) {
		selected := routing.SelectUnitsInTimeWindow(units, 5, 20)
		if len(selected) != 4 {
			t.Errorf("window [5,20] should include all 4 units, got %d", len(selected))
		}
	})
}

func TestDomainDeterministicTriageTieOrder(t *testing.T) {
	t.Run("TiedPrioritiesAlphabetical", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "charlie", Severity: 3, Criticality: 2},
			{ID: "alpha", Severity: 3, Criticality: 2},
			{ID: "bravo", Severity: 3, Criticality: 2},
		}
		sorted := triage.DeterministicTriageSort(incidents)
		if sorted[0].ID != "alpha" {
			t.Errorf("equal priority: 'alpha' should be first (alphabetical), got '%s'", sorted[0].ID)
		}
		if sorted[1].ID != "bravo" {
			t.Errorf("equal priority: 'bravo' should be second, got '%s'", sorted[1].ID)
		}
		if sorted[2].ID != "charlie" {
			t.Errorf("equal priority: 'charlie' should be third, got '%s'", sorted[2].ID)
		}
	})
	t.Run("HighPriorityFirstThenAlphabetical", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "z-low", Severity: 1, Criticality: 1},
			{ID: "b-high", Severity: 5, Criticality: 5},
			{ID: "a-high", Severity: 5, Criticality: 5},
		}
		sorted := triage.DeterministicTriageSort(incidents)
		if sorted[0].ID != "a-high" {
			t.Errorf("highest priority + alphabetical first: expected 'a-high', got '%s'", sorted[0].ID)
		}
	})
	t.Run("StableSortPreservesOrder", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "first", Severity: 2, Criticality: 2},
			{ID: "second", Severity: 2, Criticality: 2},
		}
		sorted := triage.DeterministicTriageSort(incidents)
		if sorted[0].ID != "first" {
			t.Errorf("deterministic: 'first' should come before 'second' (alphabetical), got '%s'", sorted[0].ID)
		}
	})
}

func TestDomainCrossRegionPenalty(t *testing.T) {
	t.Run("SameRegionNoPenalty", func(t *testing.T) {
		penalty := routing.CrossRegionPenalty("north", "north")
		if penalty != 0.0 {
			t.Errorf("same region should have 0 penalty, got %.1f", penalty)
		}
	})
	t.Run("DifferentRegionHasPenalty", func(t *testing.T) {
		penalty := routing.CrossRegionPenalty("north", "south")
		if penalty <= 0.0 {
			t.Errorf("different regions should have positive penalty, got %.1f", penalty)
		}
	})
}

func TestDomainEscalationUrgencyTimeBoost(t *testing.T) {
	t.Run("HigherSeverityHigherScore", func(t *testing.T) {
		s3 := escalation.EscalationUrgencyScore(3, 30)
		s5 := escalation.EscalationUrgencyScore(5, 30)
		if s5 <= s3 {
			t.Errorf("severity 5 (%.1f) should score higher than severity 3 (%.1f)", s5, s3)
		}
	})
	t.Run("LongerTimeHigherScore", func(t *testing.T) {
		early := escalation.EscalationUrgencyScore(3, 10)
		late := escalation.EscalationUrgencyScore(3, 200)
		if late <= early {
			t.Errorf("200min elapsed (%.1f) should score higher than 10min (%.1f)", late, early)
		}
	})
	t.Run("OverTwoHoursBoost", func(t *testing.T) {
		at119 := escalation.EscalationUrgencyScore(3, 119)
		at121 := escalation.EscalationUrgencyScore(3, 121)
		timeDiff := at121 - at119
		if timeDiff < 0.5 {
			t.Errorf("crossing 120min should trigger time boost: 119min=%.1f, 121min=%.1f", at119, at121)
		}
	})
}

func TestDomainPlanSortByPriority(t *testing.T) {
	t.Run("DescendingOrder", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "low", Priority: 10},
			{IncidentID: "high", Priority: 100},
			{IncidentID: "mid", Priority: 50},
		}
		sorted := models.SortPlansByPriority(plans)
		if sorted[0].IncidentID != "high" {
			t.Errorf("highest priority should be first, got %s (priority %d)", sorted[0].IncidentID, sorted[0].Priority)
		}
		if sorted[2].IncidentID != "low" {
			t.Errorf("lowest priority should be last, got %s", sorted[2].IncidentID)
		}
	})
	t.Run("AlreadySorted", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "a", Priority: 100},
			{IncidentID: "b", Priority: 50},
			{IncidentID: "c", Priority: 10},
		}
		sorted := models.SortPlansByPriority(plans)
		for i := 1; i < len(sorted); i++ {
			if sorted[i].Priority > sorted[i-1].Priority {
				t.Errorf("not descending at [%d]: %d after %d", i, sorted[i].Priority, sorted[i-1].Priority)
			}
		}
	})
}

func TestDomainHealthScoreAverage(t *testing.T) {
	t.Run("AllHealthy", func(t *testing.T) {
		score := capacity.RankScore(capacity.Facility{BedsFree: 20, ICUFree: 5, DistanceK: 2.0})
		if score <= 0 {
			t.Error("healthy facility should have positive score")
		}
	})
	t.Run("TermDistanceCorrect", func(t *testing.T) {
		dist := consensus.TermDistance(10, 7)
		if dist != 3 {
			t.Errorf("term distance 10-7 should be 3, got %d", dist)
		}
	})
	t.Run("TermDistanceFollowerAhead", func(t *testing.T) {
		dist := consensus.TermDistance(5, 10)
		if dist != 0 {
			t.Errorf("follower ahead of leader: distance should be 0, got %d", dist)
		}
	})
}

func TestDomainSurgeCapacityExactBoundary(t *testing.T) {
	for _, tc := range []struct {
		name       string
		beds, icu  int
		patients   int
		shouldPass bool
	}{
		{"AboveCapacity", 5, 5, 20, false},
		{"ExactMatch", 10, 5, 15, true},
		{"BelowCapacity", 20, 10, 15, true},
		{"OneOver", 10, 5, 16, false},
		{"OneUnder", 10, 5, 14, true},
	} {
		t.Run(tc.name, func(t *testing.T) {
			f := capacity.Facility{BedsFree: tc.beds, ICUFree: tc.icu}
			result := capacity.SurgeCapacityCheck(f, tc.patients)
			if result != tc.shouldPass {
				t.Errorf("beds=%d icu=%d patients=%d: expected %v, got %v",
					tc.beds, tc.icu, tc.patients, tc.shouldPass, result)
			}
		})
	}
}

func TestDomainGroupByCategory(t *testing.T) {
	t.Run("MultipleCategories", func(t *testing.T) {
		results := []models.TriageResult{
			{Category: "critical"}, {Category: "moderate"}, {Category: "critical"},
			{Category: "low"}, {Category: "critical"},
		}
		groups := triage.TriageGroupByCategory(results)
		if groups["critical"] != 3 {
			t.Errorf("expected 3 critical, got %d", groups["critical"])
		}
		if groups["moderate"] != 1 {
			t.Errorf("expected 1 moderate, got %d", groups["moderate"])
		}
	})
}

func TestDomainEventRate(t *testing.T) {
	t.Run("EvenDistribution", func(t *testing.T) {
		var evts []events.Event
		for i := int64(0); i < 100; i++ {
			evts = append(evts, events.Event{ID: "e", Timestamp: i * 10})
		}
		rates := events.EventRatePerWindow(evts, 100)
		for _, count := range rates {
			if count < 9 || count > 11 {
				t.Errorf("evenly distributed events: expected ~10 per window, got %d", count)
			}
		}
	})
}

func TestDomainHaversineNearbyAccurate(t *testing.T) {
	t.Run("NearbyPointsAccurate", func(t *testing.T) {
		dist := routing.HaversineApprox(40.7128, -74.0060, 40.7580, -73.9855)
		if math.Abs(dist-5.3) > 2.0 {
			t.Errorf("NYC to Central Park: expected ~5.3km, got %.1f km", dist)
		}
	})
}
