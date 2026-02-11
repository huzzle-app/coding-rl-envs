package integration

import (
	"sync"
	"testing"

	"incidentmesh/internal/capacity"
	"incidentmesh/internal/workflow"
	"incidentmesh/pkg/models"
)

func TestDispatchOrchestrationSelectsBestRegionalUnit(t *testing.T) {
	i := models.Incident{ID: "i-1", Severity: 4, Region: "north", Criticality: 4}
	units := []models.Unit{{ID: "u1", Region: "north", ETAmins: 9}, {ID: "u2", Region: "north", ETAmins: 3}, {ID: "u3", Region: "south", ETAmins: 1}}
	fac := capacity.Facility{Name: "F1", BedsFree: 12, ICUFree: 4, DistanceK: 8}
	d := workflow.BuildDispatchDecision(i, units, fac)
	if d.ChosenUnitID != "u2" {
		t.Fatalf("expected fastest regional unit")
	}
}

func TestDispatchOrchestrationEscalatesOnResourceGap(t *testing.T) {
	i := models.Incident{ID: "i-2", Severity: 3, Region: "north", Criticality: 3}
	units := []models.Unit{{ID: "u1", Region: "north", ETAmins: 8}}
	fac := capacity.Facility{Name: "F2", BedsFree: 6, ICUFree: 2, DistanceK: 12}
	d := workflow.BuildDispatchDecision(i, units, fac)
	if !d.Escalate {
		t.Fatalf("expected escalation when resources are insufficient")
	}
}

func TestDispatchOrchestrationFacilityScorePositive(t *testing.T) {
	i := models.Incident{ID: "i-3", Severity: 2, Region: "north", Criticality: 1}
	units := []models.Unit{{ID: "u1", Region: "north", ETAmins: 5}}
	fac := capacity.Facility{Name: "F3", BedsFree: 30, ICUFree: 12, DistanceK: 3}
	d := workflow.BuildDispatchDecision(i, units, fac)
	if d.FacilityScore <= 0 {
		t.Fatalf("expected positive facility score")
	}
}

func TestDispatchExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"NoUnits", func(t *testing.T) {
			i := models.Incident{ID: "i-4", Severity: 5, Region: "north", Criticality: 5}
			fac := capacity.Facility{Name: "F4", BedsFree: 10, ICUFree: 5, DistanceK: 2}
			d := workflow.BuildDispatchDecision(i, nil, fac)
			if d.ChosenUnitID != "" {
				t.Fatalf("expected empty")
			}
		}},
		{"HighPriority", func(t *testing.T) {
			i := models.Incident{ID: "i-5", Severity: 5, Region: "east", Criticality: 5}
			units := []models.Unit{{ID: "u1", Region: "east", ETAmins: 2}}
			fac := capacity.Facility{Name: "F5", BedsFree: 20, ICUFree: 8, DistanceK: 1}
			d := workflow.BuildDispatchDecision(i, units, fac)
			if d.Priority <= 0 {
				t.Fatalf("expected positive priority")
			}
		}},
		{"WrongRegion", func(t *testing.T) {
			i := models.Incident{ID: "i-6", Severity: 3, Region: "north"}
			units := []models.Unit{{ID: "u1", Region: "south", ETAmins: 5}}
			fac := capacity.Facility{Name: "F6", BedsFree: 15, ICUFree: 3, DistanceK: 5}
			d := workflow.BuildDispatchDecision(i, units, fac)
			if d.ChosenUnitID != "" {
				t.Fatalf("expected empty")
			}
		}},
		{"MultipleUnits", func(t *testing.T) {
			i := models.Incident{ID: "i-7", Severity: 2, Region: "west", Criticality: 2}
			units := []models.Unit{{ID: "u1", Region: "west", ETAmins: 15}, {ID: "u2", Region: "west", ETAmins: 5}, {ID: "u3", Region: "west", ETAmins: 10}}
			fac := capacity.Facility{Name: "F7", BedsFree: 8, ICUFree: 2, DistanceK: 4}
			d := workflow.BuildDispatchDecision(i, units, fac)
			if d.ChosenUnitID != "u2" {
				t.Fatalf("expected u2")
			}
		}},
		{"WorkflowMetrics", func(t *testing.T) {
			steps := []workflow.WorkflowStep{{Name: "s1"}, {Name: "s2"}, {Name: "s3"}}
			m := workflow.WorkflowMetrics(steps)
			if m["total_steps"] != 3 {
				t.Fatalf("expected 3")
			}
		}},
		{"ParallelCollect", func(t *testing.T) {
			tasks := []func() string{func() string { return "a" }, func() string { return "b" }}
			r := workflow.ParallelCollect(tasks)
			if len(r) != 2 {
				t.Fatalf("expected 2")
			}
		}},
		{"SafeMapOps", func(t *testing.T) {
			var m sync.Map
			workflow.SafeMapSet(&m, "key1", "val1")
			v, ok := workflow.SafeMapGet(&m, "key1")
			if !ok || v != "val1" {
				t.Fatalf("expected val1")
			}
		}},
		{"SafeMapMissing", func(t *testing.T) {
			var m sync.Map
			_, ok := workflow.SafeMapGet(&m, "nonexistent")
			if ok {
				t.Fatalf("expected not found")
			}
		}},
		{"AggregateCounters", func(t *testing.T) {
			total := workflow.AggregateCounters([]int64{10, 20, 30})
			if total != 60 { t.Fatalf("expected total 60, got %d", total) }
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
