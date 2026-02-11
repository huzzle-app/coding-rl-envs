package integration

import (
	"testing"

	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/internal/security"
	"gridweaver/pkg/models"
)

func TestWorkflow(t *testing.T) {
	state := models.RegionState{Region: "west", BaseLoadMW: 700, TemperatureC: 28, WindPct: 2, ReservePct: 0.12}
	demand := estimator.EstimateLoad(state)
	plan := dispatch.BuildPlan("west", demand, 0.12)
	plan = dispatch.ApplyConstraint(plan, demand*1.2)
	if !security.Authorize("grid_admin", "control.substation") {
		t.Fatalf("expected admin authorization")
	}
	if plan.GenerationMW <= 0 {
		t.Fatalf("invalid generation")
	}
}

func TestWorkflowExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"MultiRegionWorkflow", func(t *testing.T) {
			regions := []string{"west", "east", "central"}
			for _, r := range regions {
				state := models.RegionState{Region: r, BaseLoadMW: 600, TemperatureC: 25, WindPct: 5, ReservePct: 0.12}
				demand := estimator.EstimateLoad(state)
				plan := dispatch.BuildPlan(r, demand, 0.12)
				if plan.GenerationMW <= 0 {
					t.Fatalf("invalid generation for region %s", r)
				}
			}
		}},
		{"WorkflowWithConstraint", func(t *testing.T) {
			state := models.RegionState{Region: "west", BaseLoadMW: 1000, TemperatureC: 35, WindPct: 2, ReservePct: 0.15}
			demand := estimator.EstimateLoad(state)
			plan := dispatch.BuildPlan("west", demand, 0.15)
			plan = dispatch.ApplyConstraint(plan, 800)
			if plan.CurtailmentMW <= 0 {
				t.Fatalf("expected curtailment")
			}
		}},
		{"SecurityCheckInWorkflow", func(t *testing.T) {
			if security.Authorize("observer", "control.substation") {
				t.Fatalf("observer should not control substation")
			}
			if !security.Authorize("field_operator", "dispatch.plan") {
				t.Fatalf("field operator should dispatch")
			}
		}},
		{"StabilityCheckInWorkflow", func(t *testing.T) {
			state := models.RegionState{ReservePct: 0.20, ActiveOutages: 1}
			margin := estimator.StabilityMargin(state)
			if margin <= 0 {
				t.Fatalf("expected positive stability margin")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
