package integration

import (
	"testing"

	"gridweaver/internal/demandresponse"
	"gridweaver/internal/workflow"
	"gridweaver/pkg/models"
)

func TestControlOrchestrationUsesDRUnderCurtailment(t *testing.T) {
	state := models.RegionState{Region: "west", BaseLoadMW: 1000, TemperatureC: 36, WindPct: 1, ReservePct: 0.18, ActiveOutages: 2}
	dr := demandresponse.Program{CommittedMW: 10, MaxMW: 500}
	decision := workflow.BuildControlDecision(state, dr, "grid_admin", 900)
	if !decision.UsedDemandResponse {
		t.Fatalf("expected demand response usage under curtailment")
	}
	if !decision.Authorized {
		t.Fatalf("expected admin authorization")
	}
}

func TestControlOrchestrationKeepsCurtailmentWithoutDRCapacity(t *testing.T) {
	state := models.RegionState{Region: "west", BaseLoadMW: 1000, TemperatureC: 36, WindPct: 1, ReservePct: 0.18, ActiveOutages: 1}
	dr := demandresponse.Program{CommittedMW: 45, MaxMW: 50}
	decision := workflow.BuildControlDecision(state, dr, "field_operator", 920)
	if decision.UsedDemandResponse {
		t.Fatalf("did not expect demand response usage")
	}
	if decision.Plan.CurtailmentMW <= 0 {
		t.Fatalf("expected curtailment to remain")
	}
	if decision.Authorized {
		t.Fatalf("field operator should not control substation")
	}
}

func TestControlOrchestrationOutagePriorityRises(t *testing.T) {
	base := models.RegionState{Region: "west", BaseLoadMW: 700, TemperatureC: 24, WindPct: 5, ReservePct: 0.12, ActiveOutages: 0}
	heavy := models.RegionState{Region: "west", BaseLoadMW: 700, TemperatureC: 24, WindPct: 5, ReservePct: 0.12, ActiveOutages: 4}
	dr := demandresponse.Program{CommittedMW: 0, MaxMW: 100}
	b := workflow.BuildControlDecision(base, dr, "grid_admin", 2000)
	h := workflow.BuildControlDecision(heavy, dr, "grid_admin", 2000)
	if h.OutagePriority <= b.OutagePriority {
		t.Fatalf("expected higher outage priority with more outages")
	}
}

func TestControlOrchestrationExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"NoCurtailment", func(t *testing.T) {
			state := models.RegionState{Region: "east", BaseLoadMW: 500, TemperatureC: 22, WindPct: 10, ReservePct: 0.12}
			dr := demandresponse.Program{CommittedMW: 0, MaxMW: 100}
			decision := workflow.BuildControlDecision(state, dr, "grid_admin", 5000)
			if decision.UsedDemandResponse {
				t.Fatalf("should not use DR when no curtailment")
			}
		}},
		{"ObserverDenied", func(t *testing.T) {
			state := models.RegionState{Region: "west", BaseLoadMW: 500, TemperatureC: 25, WindPct: 5, ReservePct: 0.12}
			dr := demandresponse.Program{CommittedMW: 0, MaxMW: 100}
			decision := workflow.BuildControlDecision(state, dr, "observer", 5000)
			if decision.Authorized {
				t.Fatalf("observer should not be authorized")
			}
		}},
		{"WorkflowMetrics", func(t *testing.T) {
			steps := []workflow.WorkflowStep{
				{Name: "estimate"},
				{Name: "dispatch"},
				{Name: "control"},
			}
			metrics := workflow.WorkflowMetrics(steps)
			if metrics["total_steps"] != 3 {
				t.Fatalf("expected 3 total steps")
			}
		}},
		{"AuditTrail", func(t *testing.T) {
			steps := []workflow.WorkflowStep{
				{Name: "step1"},
				{Name: "step2"},
			}
			trail := workflow.AuditTrail(steps)
			if len(trail) != 2 {
				t.Fatalf("expected 2 trail entries")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
