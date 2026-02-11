package integration

import (
	"testing"

	"incidentmesh/internal/escalation"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestEscalationPriorityPath(t *testing.T) {
	i := models.Incident{Severity: 5, Criticality: 5}
	priority := triage.PriorityScore(i)
	if !escalation.ShouldEscalate(priority, 1, 5) {
		t.Fatalf("expected escalation")
	}
}

func TestEscalationResourceGap(t *testing.T) {
	i := models.Incident{Severity: 2, Criticality: 1}
	required := triage.RequiredUnits(i)
	if !escalation.ShouldEscalate(10, 0, required) {
		t.Fatalf("expected gap escalation")
	}
}

func TestEscalationFlowExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"LevelMapping", func(t *testing.T) {
			i := models.Incident{Severity: 5, Criticality: 5}
			p := triage.PriorityScore(i)
			lv := escalation.EscalationLevel(p)
			// High severity/criticality should give high escalation level
			if lv < 2 { t.Fatalf("expected high escalation level, got %d", lv) }
		}},
		{"BatchFromIncidents", func(t *testing.T) {
			incs := []models.Incident{{Severity: 1}, {Severity: 3}, {Severity: 5}}
			priorities := make([]int, len(incs))
			for j, inc := range incs {
				priorities[j] = triage.PriorityScore(inc)
			}
			results := escalation.BatchEscalation(priorities, 80)
			if len(results) != 3 {
				t.Fatalf("expected 3")
			}
		}},
		{"TimeAndSeverity", func(t *testing.T) {
			r := escalation.TimeBasedEscalation(120, 5)
			// High severity with long time should escalate
			if !r { t.Fatalf("expected escalation for high severity with long time") }
		}},
		{"ChainFromPriority", func(t *testing.T) {
			i := models.Incident{Severity: 4, Criticality: 4}
			p := triage.PriorityScore(i)
			idx := escalation.EscalationChain(p, []int{50, 100, 150, 200})
			// Priority should map to a valid chain index
			if idx < 0 || idx > 3 { t.Fatalf("expected valid chain index 0-3, got %d", idx) }
		}},
		{"LowPriorityNoEsc", func(t *testing.T) {
			if escalation.ShouldEscalate(30, 5, 2) {
				t.Fatalf("no escalation expected")
			}
		}},
		{"HighPriorityEsc", func(t *testing.T) {
			if !escalation.ShouldEscalate(150, 10, 5) {
				t.Fatalf("expected escalation at 150")
			}
		}},
		{"ResourceSufficient", func(t *testing.T) {
			if escalation.ShouldEscalate(50, 5, 3) {
				t.Fatalf("no escalation expected")
			}
		}},
		{"ResourceInsufficient", func(t *testing.T) {
			if !escalation.ShouldEscalate(50, 1, 5) {
				t.Fatalf("expected escalation")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
