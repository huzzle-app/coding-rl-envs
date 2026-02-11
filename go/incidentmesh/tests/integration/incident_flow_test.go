package integration

import (
	"testing"

	"incidentmesh/internal/escalation"
	"incidentmesh/internal/routing"
	"incidentmesh/internal/triage"
	"incidentmesh/pkg/models"
)

func TestIncidentFlow(t *testing.T) {
	i := models.Incident{ID: "flow-1", Severity: 4, Region: "north", Criticality: 3}
	priority := triage.PriorityScore(i)
	required := triage.RequiredUnits(i)
	units := []models.Unit{{ID: "u1", Region: "north", ETAmins: 5}, {ID: "u2", Region: "north", ETAmins: 2}}
	best := routing.BestUnit(units, i.Region)
	esc := escalation.ShouldEscalate(priority, len(units), required)
	if best == nil {
		t.Fatalf("expected unit")
	}
	_ = esc
}

func TestFlowExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"HighSeverityFlow", func(t *testing.T) {
			i := models.Incident{Severity: 5, Region: "east", Criticality: 5}
			p := triage.PriorityScore(i)
			if p < 100 {
				t.Fatalf("expected high priority")
			}
		}},
		{"LowSeverityFlow", func(t *testing.T) {
			i := models.Incident{Severity: 1, Region: "west", Criticality: 1}
			p := triage.PriorityScore(i)
			if p <= 0 {
				t.Fatalf("expected positive")
			}
		}},
		{"RoutingFallback", func(t *testing.T) {
			units := []models.Unit{{ID: "u1", Region: "south", ETAmins: 3}}
			best := routing.BestUnit(units, "north")
			if best != nil {
				t.Fatalf("expected nil")
			}
		}},
		{"EscalationTrigger", func(t *testing.T) {
			if !escalation.ShouldEscalate(200, 1, 5) {
				t.Fatalf("expected escalation")
			}
		}},
		{"NoEscalation", func(t *testing.T) {
			if escalation.ShouldEscalate(50, 10, 3) {
				t.Fatalf("no escalation expected")
			}
		}},
		{"UrgencyCheck", func(t *testing.T) {
			i := models.Incident{Severity: 4, Criticality: 3}
			if i.UrgencyScore() <= 0 {
				t.Fatalf("expected positive urgency")
			}
		}},
		{"RequiredUnitsCheck", func(t *testing.T) {
			i := models.Incident{Severity: 5, Criticality: 5}
			if triage.RequiredUnits(i) < 3 {
				t.Fatalf("expected several units")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
