package unit

import (
	"testing"
	"incidentmesh/pkg/models"
)

func TestTriageAndCompliance(t *testing.T) {
	i := models.Incident{Severity: 4, Criticality: 3}
	if i.UrgencyScore() <= 0 { t.Fatalf("expected positive urgency") }
}

func TestModelExtended(t *testing.T) {
	cases := []struct{ name string; fn func(t *testing.T) }{
		{"UrgencyHigh", func(t *testing.T) {
			i := models.Incident{Severity:5,Criticality:5}
			if i.UrgencyScore() < 100 { t.Fatalf("expected high urgency") }
		}},
		{"UrgencyZero", func(t *testing.T) {
			i := models.Incident{}
			if i.UrgencyScore() != 0 { t.Fatalf("expected 0") }
		}},
		{"IsAvailable", func(t *testing.T) {
			u := models.Unit{Status:"available"}
			if !u.IsAvailable() { t.Fatalf("expected available") }
		}},
		{"NotAvailable", func(t *testing.T) {
			u := models.Unit{Status:"busy"}
			if u.IsAvailable() { t.Fatalf("expected not available") }
		}},
		{"TotalPriority", func(t *testing.T) {
			plans := []models.DispatchPlan{{Priority:10},{Priority:20}}
			if models.TotalPriority(plans) != 30 { t.Fatalf("expected 30") }
		}},
		{"TotalPriorityEmpty", func(t *testing.T) {
			if models.TotalPriority(nil) != 0 { t.Fatalf("expected 0") }
		}},
		{"FilterByRegion", func(t *testing.T) {
			plans := []models.DispatchPlan{{Region:"north",Priority:10},{Region:"south",Priority:20}}
			f := models.FilterPlansByRegion(plans, "north")
			if len(f) != 1 { t.Fatalf("expected 1") }
		}},
		{"FilterEmpty", func(t *testing.T) {
			f := models.FilterPlansByRegion(nil, "north")
			if len(f) != 0 { t.Fatalf("expected empty") }
		}},
		{"IncidentFields", func(t *testing.T) {
			i := models.Incident{ID:"i1",Type:"fire",ReportedBy:"user1"}
			if i.ID != "i1" || i.Type != "fire" { t.Fatalf("fields mismatch") }
		}},
		{"SnapshotFields", func(t *testing.T) {
			s := models.IncidentSnapshot{IncidentID:"i1",Priority:5,ActiveUnits:3,Version:1}
			if s.IncidentID != "i1" { t.Fatalf("field mismatch") }
		}},
	}
	for _, tc := range cases { t.Run(tc.name, tc.fn) }
}
