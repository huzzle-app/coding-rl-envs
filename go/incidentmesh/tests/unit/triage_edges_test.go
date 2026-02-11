package unit

import (
	"testing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestPriorityScoreCriticalBoost(t *testing.T) {
	i := models.Incident{Severity: 5, Criticality: 5}
	if triage.PriorityScore(i) < 150 { t.Fatalf("priority should be high") }
}

func TestRequiredUnitsMinimum(t *testing.T) {
	i := models.Incident{Severity: -1, Criticality: -1}
	if triage.RequiredUnits(i) != 1 { t.Fatalf("required units floor should be 1") }
}

func TestRequiredUnitsScale(t *testing.T) {
	i := models.Incident{Severity: 6, Criticality: 6}
	if triage.RequiredUnits(i) < 4 { t.Fatalf("expected more units") }
}

func TestTriageExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"ClassifyLow", func(t *testing.T) {
			i := models.Incident{Severity: 1}
			c := triage.ClassifyIncident(i)
			if c == "" { t.Fatalf("expected non-empty") }
		}},
		{"ClassifyHigh", func(t *testing.T) {
			i := models.Incident{Severity: 5}
			c := triage.ClassifyIncident(i)
			
			if c != "critical" { t.Fatalf("expected critical for sev=5, got %s", c) }
		}},
		{"SeverityWeight", func(t *testing.T) {
			w := triage.SeverityWeight(3)
			if w <= 0 { t.Fatalf("expected positive weight") }
		}},
		{"CriticalityBoost", func(t *testing.T) {
			b := triage.CriticalityBoost(2)
			
			if b != 16 { t.Fatalf("expected 16, got %d", b) }
		}},
		{"BatchPriority", func(t *testing.T) {
			scores := triage.BatchPriority([]models.Incident{{Severity:3,Criticality:2},{Severity:5,Criticality:4}})
			if len(scores) != 2 { t.Fatalf("expected 2 scores") }
		}},
		{"TriagePolicy", func(t *testing.T) {
			r := triage.TriagePolicyApply(models.Incident{Severity:3,Criticality:2}, "strict")
			if r.Priority <= 0 { t.Fatalf("expected positive priority") }
		}},
		{"MinSeverity", func(t *testing.T) {
			min := triage.MinimumSeverity([]models.Incident{{Severity:3},{Severity:1},{Severity:5}})
			
			if min != 1 { t.Fatalf("expected min=1, got %d", min) }
		}},
		{"MaxCriticality", func(t *testing.T) {
			max := triage.MaxCriticality([]models.Incident{{Criticality:3},{Criticality:1},{Criticality:5}})
			
			if max != 5 { t.Fatalf("expected max=5, got %d", max) }
		}},
		{"FilterBySeverity", func(t *testing.T) {
			filtered := triage.FilterBySeverity([]models.Incident{{Severity:1},{Severity:3},{Severity:5}}, 3)
			
			if len(filtered) != 2 { t.Fatalf("expected 2 (sev>=3), got %d", len(filtered)) }
		}},
		{"NormalizePriority", func(t *testing.T) {
			n := triage.NormalizePriority(50, 100)
			
			if n != 0.5 { t.Fatalf("expected 0.5 (50/100), got %.2f", n) }
		}},
		{"CategorySev1", func(t *testing.T) {
			c := triage.CategoryFromSeverity(1)
			if c != "low" { t.Fatalf("expected low") }
		}},
		{"CategorySev3", func(t *testing.T) {
			c := triage.CategoryFromSeverity(3)
			if c == "" { t.Fatalf("expected non-empty") }
		}},
		{"CategorySev5", func(t *testing.T) {
			c := triage.CategoryFromSeverity(5)
			if c == "" { t.Fatalf("expected non-empty") }
		}},
		{"TotalUrgency", func(t *testing.T) {
			total := triage.TotalUrgency([]models.Incident{{Severity:2,Criticality:3},{Severity:4,Criticality:1}})
			if total <= 0 { t.Fatalf("expected positive") }
		}},
		{"EmptyBatch", func(t *testing.T) {
			scores := triage.BatchPriority(nil)
			if len(scores) != 0 { t.Fatalf("expected empty") }
		}},
		{"EmptyMinSev", func(t *testing.T) {
			min := triage.MinimumSeverity(nil)
			if min != 0 { t.Fatalf("expected 0") }
		}},
		{"EmptyMaxCrit", func(t *testing.T) {
			max := triage.MaxCriticality(nil)
			if max != 0 { t.Fatalf("expected 0") }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
