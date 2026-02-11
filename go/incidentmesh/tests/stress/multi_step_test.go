package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/escalation"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

// Multi-step bugs: fixing one component reveals a bug in the next downstream component.

func TestMultiStepTriageToRouting(t *testing.T) {
	// Step 1: MultiIncidentSort produces wrong order (ascending instead of descending).
	// Step 2: RouteWithFallback returns first match (not best ETA) for primary region.
	// Combined: worst incident gets triaged last AND gets slow unit.

	t.Run("HighPriorityTriagedFirstGetsFastestUnit", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "minor", Severity: 1, Criticality: 1, Region: "north"},
			{ID: "critical", Severity: 5, Criticality: 5, Region: "north"},
			{ID: "moderate", Severity: 3, Criticality: 2, Region: "north"},
		}
		sorted := triage.MultiIncidentSort(incidents)
		if sorted[0].ID != "critical" {
			t.Fatalf("triage: critical should be first, got %s", sorted[0].ID)
		}

		units := []models.Unit{
			{ID: "u-slow", Region: "north", ETAmins: 30, Status: "available"},
			{ID: "u-fast", Region: "north", ETAmins: 5, Status: "available"},
		}
		best := routing.RouteWithFallback(units, sorted[0].Region, "south")
		if best == nil {
			t.Fatal("should find unit")
		}
		if best.ETAmins != 5 {
			t.Errorf("critical incident should get fastest unit (5min), got %dmin", best.ETAmins)
		}
	})
}

func TestMultiStepEscalationWithCooldown(t *testing.T) {
	// Step 1: ValidEscalationTransition allows level skipping (0→3 valid).
	// Step 2: CooldownExpired compares ms to seconds (always says expired).
	// Combined: escalation jumps multiple levels AND cooldown never blocks.

	t.Run("SkippedEscalationBlockedByCooldown", func(t *testing.T) {
		validTransition := escalation.ValidEscalationTransition(1, 2)
		if !validTransition {
			t.Fatal("1→2 should be valid")
		}
		// Only 2 seconds (2000ms) since last escalation, cooldown is 5 seconds
		cooldownDone := escalation.CooldownExpired(50000, 52000, 5)
		if cooldownDone {
			t.Error("2000ms elapsed with 5-second cooldown: should NOT be expired")
		}
	})
	t.Run("ValidTransitionAfterCooldown", func(t *testing.T) {
		validTransition := escalation.ValidEscalationTransition(1, 2)
		if !validTransition {
			t.Fatal("1→2 should be valid")
		}
		// 6 seconds (6000ms) since last escalation, cooldown is 5 seconds
		cooldownDone := escalation.CooldownExpired(50000, 56000, 5)
		if !cooldownDone {
			t.Error("6000ms elapsed with 5-second cooldown: should be expired")
		}
	})
}

func TestMultiStepCapacityToAdmission(t *testing.T) {
	// Step 1: FacilityUtilization under-reports (divides by total+occupied).
	// Step 2: CanAdmitCritical uses general+ICU beds for ICU admission.
	// Combined: facility appears to have capacity AND ICU check is wrong.

	t.Run("HighUtilizationMasksICUShortage", func(t *testing.T) {
		f := capacity.Facility{BedsFree: 100, ICUFree: 2, DistanceK: 5.0, Region: "east"}

		// Check utilization first — 90% occupied should be alarming
		util := capacity.FacilityUtilization(90, 100)
		if util < 0.85 {
			t.Fatalf("90/100 utilization should be >= 0.85, got %.3f (under-reported)", util)
		}

		// All ICU beds taken — should NOT admit critical patient
		canAdmit := capacity.CanAdmitCritical(f, 2)
		if canAdmit {
			t.Error("all ICU beds occupied: should not admit critical patient even with general beds free")
		}
	})
}

func TestMultiStepPriorityAdjustmentToEscalation(t *testing.T) {
	// Step 1: ApplyPriorityAdjustments compounds (gives wrong adjusted priority).
	// Step 2: Adjusted priority feeds into ShouldEscalate.
	// If adjustment is wrong, escalation decision may be wrong.

	t.Run("AdjustedPriorityDeterminesEscalation", func(t *testing.T) {
		base := 100.0
		adjs := []float64{0.1, 0.1, 0.1}
		adjusted := triage.ApplyPriorityAdjustments(base, adjs)

		// Linear: 130. Compound: 133.1. Difference matters for borderline escalation.
		expectedAdjusted := 130.0
		if math.Abs(adjusted-expectedAdjusted) > 0.5 {
			t.Fatalf("base 100 + three 10%% adjustments: expected ~130, got %.1f", adjusted)
		}

		shouldEsc := escalation.ShouldEscalate(int(adjusted), 2, 5)
		if !shouldEsc {
			t.Errorf("priority %d with 2/5 responders should escalate", int(adjusted))
		}
	})
}

func TestMultiStepHaversineToRouting(t *testing.T) {
	// HaversineApprox uses cos(lat1)^2 instead of cos(lat1)*cos(lat2).
	// This breaks distance symmetry: distance(A→B) ≠ distance(B→A).
	// Routing decisions based on asymmetric distances are incorrect.

	t.Run("CloserPointSmallerDistance", func(t *testing.T) {
		dist1 := routing.HaversineApprox(40.0, -74.0, 40.1, -74.0)
		dist2 := routing.HaversineApprox(40.0, -74.0, 41.0, -74.0)
		if dist1 >= dist2 {
			t.Errorf("0.1° should be shorter than 1.0°: %.2f >= %.2f", dist1, dist2)
		}
	})
	t.Run("DistanceSymmetric", func(t *testing.T) {
		d1 := routing.HaversineApprox(0.0, 0.0, 60.0, 10.0)
		d2 := routing.HaversineApprox(60.0, 10.0, 0.0, 0.0)
		if math.Abs(d1-d2) > 1.0 {
			t.Errorf("distance must be symmetric: A→B=%.1f, B→A=%.1f (diff=%.1f)",
				d1, d2, math.Abs(d1-d2))
		}
	})
}

func TestMultiStepAutoResolveAfterEscalation(t *testing.T) {
	// AutoResolveEligible bug allows severity 5 to auto-resolve.
	// After escalation, a critical incident should NEVER auto-resolve.

	t.Run("EscalatedCriticalCannotAutoResolve", func(t *testing.T) {
		priority := triage.PriorityScore(models.Incident{Severity: 5, Criticality: 4})
		shouldEsc := escalation.ShouldEscalate(priority, 1, 5)
		if !shouldEsc {
			t.Fatalf("priority %d should escalate", priority)
		}
		if escalation.AutoResolveEligible(5, 200, 1) {
			t.Error("severity 5 escalated incident with active responders must not auto-resolve")
		}
	})
	t.Run("LowSeverityCanAutoResolve", func(t *testing.T) {
		if !escalation.AutoResolveEligible(1, 200, 0) {
			t.Error("severity 1 open 200min with no responders: should auto-resolve")
		}
	})
}

func TestMultiStepRegionalBalanceToAdmission(t *testing.T) {
	// RegionalCapacitySummary returns sum not average.
	// Regions with more facilities appear to have more capacity per facility.

	t.Run("TwoFacilitiesAveraged", func(t *testing.T) {
		facilities := []capacity.Facility{
			{Name: "H1", BedsFree: 10, ICUFree: 5, DistanceK: 2.0, Region: "north"},
			{Name: "H2", BedsFree: 30, ICUFree: 8, DistanceK: 4.0, Region: "north"},
		}
		summary := capacity.RegionalCapacitySummary(facilities)
		s1, s2 := capacity.RankScore(facilities[0]), capacity.RankScore(facilities[1])
		expectedAvg := (s1 + s2) / 2.0
		if math.Abs(summary["north"]-expectedAvg) > 0.01 {
			t.Errorf("expected average %.2f, got %.2f (sum=%.2f)", expectedAvg, summary["north"], s1+s2)
		}
	})
}
