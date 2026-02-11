package unit

import (
	"testing"

	"gridweaver/internal/dispatch"
	"gridweaver/internal/estimator"
	"gridweaver/pkg/models"
)

func TestEstimateAndDispatch(t *testing.T) {
	state := models.RegionState{Region: "west", BaseLoadMW: 900, TemperatureC: 30, WindPct: 4, ReservePct: 0.14, ActiveOutages: 1}
	demand := estimator.EstimateLoad(state)
	if demand <= 900 {
		t.Fatalf("expected weather-adjusted demand")
	}
	plan := dispatch.BuildPlan("west", demand, 0.14)
	if plan.GenerationMW <= demand || plan.ReserveMW <= 0 {
		t.Fatalf("invalid plan: %+v", plan)
	}
}

func TestGridLogicExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"HighTempIncreasesLoad", func(t *testing.T) {
			base := models.RegionState{BaseLoadMW: 500, TemperatureC: 22, WindPct: 5}
			hot := models.RegionState{BaseLoadMW: 500, TemperatureC: 40, WindPct: 5}
			if estimator.EstimateLoad(hot) <= estimator.EstimateLoad(base) {
				t.Fatalf("high temp should increase load")
			}
		}},
		{"HighWindReducesLoad", func(t *testing.T) {
			base := models.RegionState{BaseLoadMW: 500, TemperatureC: 25, WindPct: 5}
			windy := models.RegionState{BaseLoadMW: 500, TemperatureC: 25, WindPct: 50}
			if estimator.EstimateLoad(windy) >= estimator.EstimateLoad(base) {
				t.Fatalf("high wind should reduce load")
			}
		}},
		{"OutagesIncreaseLoad", func(t *testing.T) {
			noOutage := models.RegionState{BaseLoadMW: 500, TemperatureC: 25, WindPct: 5, ActiveOutages: 0}
			withOutage := models.RegionState{BaseLoadMW: 500, TemperatureC: 25, WindPct: 5, ActiveOutages: 3}
			if estimator.EstimateLoad(withOutage) <= estimator.EstimateLoad(noOutage) {
				t.Fatalf("outages should increase load")
			}
		}},
		{"PlanReservePositive", func(t *testing.T) {
			plan := dispatch.BuildPlan("west", 1000, 0.15)
			if plan.ReserveMW <= 0 {
				t.Fatalf("reserve should be positive")
			}
		}},
		{"EndToEndHighLoad", func(t *testing.T) {
			state := models.RegionState{Region: "east", BaseLoadMW: 2000, TemperatureC: 38, WindPct: 2, ReservePct: 0.1, ActiveOutages: 3}
			demand := estimator.EstimateLoad(state)
			plan := dispatch.BuildPlan("east", demand, 0.1)
			plan = dispatch.ApplyConstraint(plan, 2500)
			if plan.GenerationMW <= 0 {
				t.Fatalf("generation must be positive")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
