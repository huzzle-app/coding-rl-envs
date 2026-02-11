package stress

import (
	"math"
	"testing"

	"incidentmesh/internal/compliance"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
	"incidentmesh/shared/contracts"
)

// Domain logic bugs: require understanding of emergency response domain to detect.

func TestDomainPriorityTieBreaking(t *testing.T) {
	// ComparePriority has correct main comparison but INVERTED tie-break.
	// When composite scores are equal, lower severity gets ranked higher (wrong).
	// Domain rule: higher severity wins ties because severity indicates life-threat level.

	t.Run("EqualScoreDifferentDistributions", func(t *testing.T) {
		// sev=4,crit=2: score=4*3+2*2=16. sev=2,crit=5: score=2*3+5*2=16. Tied.
		// Tie-break: severity 4 should beat severity 2 (higher severity = more urgent)
		a := models.Incident{ID: "high-sev", Severity: 4, Criticality: 2}
		b := models.Incident{ID: "high-crit", Severity: 2, Criticality: 5}
		result := models.ComparePriority(a, b)
		if result != -1 {
			t.Errorf("severity 4 should win tie-break vs severity 2 (both score 16), got %d", result)
		}
	})
	t.Run("TieBreakIsAntisymmetric", func(t *testing.T) {
		a := models.Incident{ID: "a", Severity: 4, Criticality: 2}
		b := models.Incident{ID: "b", Severity: 2, Criticality: 5}
		ab := models.ComparePriority(a, b)
		ba := models.ComparePriority(b, a)
		if ab != -ba {
			t.Errorf("comparison should be antisymmetric: compare(a,b)=%d, compare(b,a)=%d", ab, ba)
		}
	})
	t.Run("EqualIncidentsAreEqual", func(t *testing.T) {
		a := models.Incident{ID: "a", Severity: 3, Criticality: 3}
		b := models.Incident{ID: "b", Severity: 3, Criticality: 3}
		if models.ComparePriority(a, b) != 0 {
			t.Error("identical severity and criticality should compare as equal")
		}
	})
	t.Run("ClearPriorityDifference", func(t *testing.T) {
		// No tie-break involved — this should PASS
		a := models.Incident{Severity: 5, Criticality: 5}
		b := models.Incident{Severity: 1, Criticality: 1}
		if models.ComparePriority(a, b) != -1 {
			t.Error("sev=5,crit=5 (score 25) should beat sev=1,crit=1 (score 5)")
		}
	})
}

func TestDomainDispatchCoverageSemantics(t *testing.T) {
	// DispatchCoverage counts unique UNIT IDs instead of unique INCIDENT IDs.
	// Coverage should measure: what fraction of incidents have dispatch plans?

	t.Run("CoverageIsIncidentBased", func(t *testing.T) {
		plans := []models.DispatchPlan{
			{IncidentID: "inc-1", UnitIDs: []string{"u1", "u2"}},
			{IncidentID: "inc-2", UnitIDs: []string{"u3"}},
		}
		coverage := models.DispatchCoverage(plans, 4)
		// 2 incidents covered / 4 total = 0.5
		if math.Abs(coverage-0.5) > 0.001 {
			t.Errorf("2 incidents covered of 4: expected 0.5, got %.3f", coverage)
		}
	})
	t.Run("SharedUnitsDoNotInflate", func(t *testing.T) {
		// Same units assigned to different incidents — coverage should still count incidents
		plans := []models.DispatchPlan{
			{IncidentID: "inc-1", UnitIDs: []string{"u1", "u2"}},
			{IncidentID: "inc-2", UnitIDs: []string{"u1", "u2"}},
			{IncidentID: "inc-3", UnitIDs: []string{"u1"}},
		}
		coverage := models.DispatchCoverage(plans, 3)
		// 3 incidents / 3 total = 1.0 (all covered)
		if math.Abs(coverage-1.0) > 0.001 {
			t.Errorf("3 of 3 incidents covered: expected 1.0, got %.3f", coverage)
		}
	})
}

func TestDomainTriageSortDirection(t *testing.T) {
	// MultiIncidentSort sorts ascending (lowest priority first).
	// In triage, highest priority incidents must be first — lives depend on it.

	t.Run("CriticalIncidentFirst", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "minor", Severity: 1, Criticality: 1},
			{ID: "critical", Severity: 5, Criticality: 5},
			{ID: "moderate", Severity: 3, Criticality: 3},
		}
		sorted := triage.MultiIncidentSort(incidents)
		if sorted[0].ID != "critical" {
			t.Errorf("triage sort: critical incident (sev=5*crit=5=25) should be first, got %s (score=%d)",
				sorted[0].ID, sorted[0].Severity*sorted[0].Criticality)
		}
	})
	t.Run("DescendingOrder", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "a", Severity: 2, Criticality: 3},
			{ID: "b", Severity: 4, Criticality: 4},
			{ID: "c", Severity: 1, Criticality: 1},
		}
		sorted := triage.MultiIncidentSort(incidents)
		for i := 1; i < len(sorted); i++ {
			prev := sorted[i-1].Severity * sorted[i-1].Criticality
			curr := sorted[i].Severity * sorted[i].Criticality
			if prev < curr {
				t.Errorf("not descending at [%d]: score %d followed by %d", i, prev, curr)
			}
		}
	})
}

func TestDomainMultiCasualtyBoostField(t *testing.T) {
	// CompositeTriageScore multi-casualty boost uses criticality instead of severity.
	// Domain rule: severity indicates number of casualties, so multi-casualty boost
	// should scale with severity (more casualties → bigger boost).

	t.Run("HighSevGetsLargerBoost", func(t *testing.T) {
		highSevBoost := triage.CompositeTriageScore(5, 1, true) - triage.CompositeTriageScore(5, 1, false)
		lowSevBoost := triage.CompositeTriageScore(1, 5, true) - triage.CompositeTriageScore(1, 5, false)
		if highSevBoost <= lowSevBoost {
			t.Errorf("multi-casualty boost should be larger for higher severity: sev5=%.3f, sev1=%.3f",
				highSevBoost, lowSevBoost)
		}
	})
	t.Run("BoostProportionalToSeverity", func(t *testing.T) {
		boost5 := triage.CompositeTriageScore(5, 1, true) - triage.CompositeTriageScore(5, 1, false)
		expected := float64(5) / float64(5+1) // severity / (severity+criticality)
		if math.Abs(boost5-expected) > 0.01 {
			t.Errorf("severity=5 boost should be %.3f (severity-based), got %.3f", expected, boost5)
		}
	})
}

func TestDomainHaversineGeometricBug(t *testing.T) {
	// HaversineApprox uses cos(lat1)*cos(lat1) instead of cos(lat1)*cos(lat2).
	// Correct for lat1≈lat2 (nearby), progressively wrong for distant latitudes.
	// Also breaks symmetry: distance(A,B) ≠ distance(B,A) when lats differ.

	t.Run("SamePointZeroDistance", func(t *testing.T) {
		dist := routing.HaversineApprox(40.0, -74.0, 40.0, -74.0)
		if dist > 0.01 {
			t.Errorf("same point should be 0 distance, got %.2f km", dist)
		}
	})
	t.Run("SymmetryViolation", func(t *testing.T) {
		// With cos(lat1)^2 bug: distance(equator→60°) ≠ distance(60°→equator)
		d1 := routing.HaversineApprox(0.0, 0.0, 60.0, 10.0)
		d2 := routing.HaversineApprox(60.0, 10.0, 0.0, 0.0)
		if math.Abs(d1-d2) > 1.0 {
			t.Errorf("distance must be symmetric: A→B=%.1f km, B→A=%.1f km (diff=%.1f)",
				d1, d2, math.Abs(d1-d2))
		}
	})
	t.Run("LargeLatDifferenceAccuracy", func(t *testing.T) {
		// Equator to 60°N at same longitude: ~6670 km
		dist := routing.HaversineApprox(0.0, 0.0, 60.0, 0.0)
		expected := 6671.0
		if math.Abs(dist-expected) > 100.0 {
			t.Errorf("equator to 60°N: expected ~%.0f km, got %.0f km (geometric error)", expected, dist)
		}
	})
}

func TestDomainRegulatoryMissingTier(t *testing.T) {
	// RegulatoryClassification skips severity=3 tier "standard-reportable".
	// Severity 3 falls through to "minor-internal", under-classifying moderate incidents.

	t.Run("Severity3Standard", func(t *testing.T) {
		if compliance.RegulatoryClassification(3) != "standard-reportable" {
			t.Errorf("severity 3: expected 'standard-reportable', got '%s'", compliance.RegulatoryClassification(3))
		}
	})
	t.Run("Severity4Major", func(t *testing.T) {
		if compliance.RegulatoryClassification(4) != "major-reportable" {
			t.Errorf("severity 4: expected 'major-reportable', got '%s'", compliance.RegulatoryClassification(4))
		}
	})
	t.Run("Severity5Critical", func(t *testing.T) {
		if compliance.RegulatoryClassification(5) != "critical-reportable" {
			t.Errorf("severity 5: expected 'critical-reportable', got '%s'", compliance.RegulatoryClassification(5))
		}
	})
	t.Run("Severity1Informational", func(t *testing.T) {
		if compliance.RegulatoryClassification(1) != "informational" {
			t.Errorf("severity 1: expected 'informational', got '%s'", compliance.RegulatoryClassification(1))
		}
	})
}

func TestDomainCorrelationIDMissingUniqueness(t *testing.T) {
	// CorrelationIDFromCommand omits CommandID, so different commands with
	// same region+action get identical correlation IDs.

	t.Run("DifferentCommandsCollide", func(t *testing.T) {
		cmd1 := contracts.IncidentCommand{CommandID: "cmd-1", Region: "north", Action: "dispatch"}
		cmd2 := contracts.IncidentCommand{CommandID: "cmd-2", Region: "north", Action: "dispatch"}
		if contracts.CorrelationIDFromCommand(cmd1) == contracts.CorrelationIDFromCommand(cmd2) {
			t.Error("different commands should have different correlation IDs")
		}
	})
	t.Run("ContainsCommandID", func(t *testing.T) {
		cmd := contracts.IncidentCommand{CommandID: "cmd-abc-123", Region: "south", Action: "triage"}
		cid := contracts.CorrelationIDFromCommand(cmd)
		found := false
		for i := 0; i <= len(cid)-7; i++ {
			if cid[i:i+7] == "cmd-abc" {
				found = true
				break
			}
		}
		if !found {
			t.Errorf("correlation ID should contain CommandID, got '%s'", cid)
		}
	})
}

func TestDomainRouteWithFallbackInconsistency(t *testing.T) {
	// RouteWithFallback returns FIRST available unit in primary (ignores ETA),
	// but correctly selects BEST ETA in fallback. Inconsistent selection logic.

	t.Run("PrimaryShouldSelectBestETA", func(t *testing.T) {
		units := []models.Unit{
			{ID: "u-slow", Region: "north", ETAmins: 30, Status: "available"},
			{ID: "u-fast", Region: "north", ETAmins: 5, Status: "available"},
			{ID: "u-med", Region: "north", ETAmins: 15, Status: "available"},
		}
		best := routing.RouteWithFallback(units, "north", "south")
		if best == nil {
			t.Fatal("should find unit in primary region")
		}
		if best.ETAmins != 5 {
			t.Errorf("should select lowest ETA unit (5min), got %s (%dmin)", best.ID, best.ETAmins)
		}
	})
	t.Run("ConsistencyBetweenPrimaryAndFallback", func(t *testing.T) {
		units := []models.Unit{
			{ID: "n-slow", Region: "north", ETAmins: 30, Status: "available"},
			{ID: "n-fast", Region: "north", ETAmins: 10, Status: "available"},
			{ID: "s-slow", Region: "south", ETAmins: 25, Status: "available"},
			{ID: "s-fast", Region: "south", ETAmins: 8, Status: "available"},
		}
		primary := routing.RouteWithFallback(units, "north", "south")
		fallback := routing.RouteWithFallback(units, "west", "south")
		if primary.ETAmins != 10 {
			t.Errorf("primary should select best ETA in north (10min), got %d", primary.ETAmins)
		}
		if fallback.ETAmins != 8 {
			t.Errorf("fallback correctly selects best ETA in south (8min), got %d", fallback.ETAmins)
		}
	})
}

func TestDomainLoadBalanceHighSeverityBottleneck(t *testing.T) {
	// LoadBalancedAssign routes ALL high-severity incidents to unit[0].
	// During mass casualty events, this creates a single point of failure.

	t.Run("HighSeverityDistributed", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "i1", Severity: 5}, {ID: "i2", Severity: 5}, {ID: "i3", Severity: 5},
			{ID: "i4", Severity: 5}, {ID: "i5", Severity: 5}, {ID: "i6", Severity: 5},
		}
		units := []models.Unit{{ID: "u1"}, {ID: "u2"}, {ID: "u3"}}
		assignments := routing.LoadBalancedAssign(incidents, units)
		unitCounts := map[string]int{}
		for _, uid := range assignments {
			unitCounts[uid]++
		}
		for _, u := range units {
			if unitCounts[u.ID] == 0 {
				t.Errorf("unit %s got 0 high-severity incidents — bottleneck at another unit", u.ID)
			}
		}
	})
	t.Run("EvenDistributionRegardlessOfSeverity", func(t *testing.T) {
		incidents := []models.Incident{
			{ID: "i1", Severity: 4}, {ID: "i2", Severity: 5}, {ID: "i3", Severity: 4},
			{ID: "i4", Severity: 5}, {ID: "i5", Severity: 4}, {ID: "i6", Severity: 5},
		}
		units := []models.Unit{{ID: "u1"}, {ID: "u2"}, {ID: "u3"}}
		assignments := routing.LoadBalancedAssign(incidents, units)
		unitCounts := map[string]int{}
		for _, uid := range assignments {
			unitCounts[uid]++
		}
		maxLoad := 0
		minLoad := len(incidents)
		for _, c := range unitCounts {
			if c > maxLoad {
				maxLoad = c
			}
			if c < minLoad {
				minLoad = c
			}
		}
		if maxLoad-minLoad > 1 {
			t.Errorf("load imbalance: max=%d, min=%d (diff=%d) — high severity creates bottleneck",
				maxLoad, minLoad, maxLoad-minLoad)
		}
	})
}
