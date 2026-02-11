package unit

import (
	"testing"

	"gridweaver/internal/dispatch"
	"gridweaver/pkg/models"
)

func TestConstraintNoCapHit(t *testing.T) {
	plan := dispatch.BuildPlan("west", 100, 0.1)
	capped := dispatch.ApplyConstraint(plan, 200)
	if capped.CurtailmentMW != 0 {
		t.Fatalf("did not expect curtailment")
	}
}

func TestConstraintCapHit(t *testing.T) {
	plan := dispatch.BuildPlan("west", 100, 0.4)
	capped := dispatch.ApplyConstraint(plan, 110)
	if capped.CurtailmentMW <= 0 {
		t.Fatalf("expected curtailment")
	}
}

func TestReserveLimitAfterCap(t *testing.T) {
	plan := dispatch.BuildPlan("west", 200, 0.5)
	capped := dispatch.ApplyConstraint(plan, 100)
	if capped.ReserveMW > 25 {
		t.Fatalf("reserve should be bounded")
	}
}

func TestDispatchExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"BuildPlanBasic", func(t *testing.T) {
			plan := dispatch.BuildPlan("east", 500, 0.2)
			if plan.Region != "east" {
				t.Fatalf("wrong region")
			}
			if plan.GenerationMW <= 500 {
				t.Fatalf("generation should exceed demand")
			}
		}},
		{"PlanDispatch", func(t *testing.T) {
			orders := []dispatch.Order{
				{ID: "o1", Urgency: 5, ETA: "10:00"},
				{ID: "o2", Urgency: 9, ETA: "09:00"},
				{ID: "o3", Urgency: 7, ETA: "11:00"},
			}
			result := dispatch.PlanDispatch(orders, 2)
			if len(result) != 2 {
				t.Fatalf("expected 2 orders, got %d", len(result))
			}
		}},
		{"RoundGeneration", func(t *testing.T) {
			v := dispatch.RoundGeneration(123.456, 2)
			if v <= 0 {
				t.Fatalf("expected positive rounded value")
			}
		}},
		{"AggregateGeneration", func(t *testing.T) {
			total := dispatch.AggregateGeneration([]float64{10, 20, 30})
			if total != 60 {
				t.Fatalf("expected 60, got %f", total)
			}
		}},
		{"NormalizeReserve", func(t *testing.T) {
			v := dispatch.NormalizeReserve(0.12)
			_ = v 
		}},
		{"CalculateRampRate", func(t *testing.T) {
			rate := dispatch.CalculateRampRate(100, 200, 10)
			_ = rate 
		}},
		{"CalculateRampRateZeroMin", func(t *testing.T) {
			rate := dispatch.CalculateRampRate(100, 200, 0)
			if rate != 0 {
				t.Fatalf("expected 0 for zero minutes")
			}
		}},
		{"MeritOrder", func(t *testing.T) {
			units := []struct {
				ID        string
				CostPerMW float64
			}{
				{"gen1", 50},
				{"gen2", 30},
				{"gen3", 70},
			}
			ids := dispatch.MeritOrder(units)
			if len(ids) != 3 {
				t.Fatalf("expected 3 IDs")
			}
		}},
		{"ValidateRampConstraint", func(t *testing.T) {
			result := dispatch.ValidateRampConstraint(100, 150, 100)
			_ = result
		}},
		{"SplitDispatch", func(t *testing.T) {
			result := dispatch.SplitDispatch(100, 4)
			if len(result) != 4 {
				t.Fatalf("expected 4 splits")
			}
		}},
		{"SplitDispatchZeroUnits", func(t *testing.T) {
			result := dispatch.SplitDispatch(100, 0)
			if result != nil {
				t.Fatalf("expected nil for zero units")
			}
		}},
		{"CurtailmentNeeded", func(t *testing.T) {
			c := dispatch.CurtailmentNeeded(100, 80, 10)
			if c <= 0 {
				t.Fatalf("expected curtailment needed")
			}
		}},
		{"CurtailmentNotNeeded", func(t *testing.T) {
			c := dispatch.CurtailmentNeeded(100, 200, 10)
			if c != 0 {
				t.Fatalf("expected no curtailment: %f", c)
			}
		}},
		{"ScheduleDispatch", func(t *testing.T) {
			orders := []dispatch.Order{{ID: "o1"}, {ID: "o2"}}
			schedule := dispatch.ScheduleDispatch(orders, 15)
			if schedule["o1"] != 0 || schedule["o2"] != 15 {
				t.Fatalf("unexpected schedule")
			}
		}},
		{"CapacityMargin", func(t *testing.T) {
			margin := dispatch.CapacityMargin(120, 100)
			if margin <= 0 {
				t.Fatalf("expected positive margin")
			}
		}},
		{"CapacityMarginZeroDemand", func(t *testing.T) {
			margin := dispatch.CapacityMargin(120, 0)
			if margin != 1.0 {
				t.Fatalf("expected 1.0 for zero demand")
			}
		}},
		{"PriorityDispatch", func(t *testing.T) {
			orders := []dispatch.Order{
				{ID: "o1", Urgency: 3},
				{ID: "o2", Urgency: 7},
				{ID: "o3", Urgency: 5},
			}
			result := dispatch.PriorityDispatch(orders, 5)
			if len(result) != 2 {
				t.Fatalf("expected 2 priority orders")
			}
		}},
		{"MultiRegionPlan", func(t *testing.T) {
			plans := dispatch.MultiRegionPlan(
				[]string{"west", "east"},
				map[string]float64{"west": 500, "east": 300},
				0.1,
			)
			if len(plans) != 2 {
				t.Fatalf("expected 2 plans")
			}
		}},
		{"UrgencyScore", func(t *testing.T) {
			o := models.DispatchOrder{ID: "d1", Severity: 5, SLAMinutes: 60}
			score := o.UrgencyScore()
			if score <= 0 {
				t.Fatalf("expected positive urgency score")
			}
		}},
		{"TotalGeneration", func(t *testing.T) {
			plans := []models.DispatchPlan{
				{GenerationMW: 100.5},
				{GenerationMW: 200.7},
			}
			total := dispatch.TotalGeneration(plans)
			if total <= 0 {
				t.Fatalf("expected positive total generation")
			}
		}},
		{"WeightedDispatch", func(t *testing.T) {
			demands := []float64{100, 200, 300}
			weights := []float64{1, 2, 3}
			alloc := dispatch.WeightedDispatch(demands, weights)
			if len(alloc) != 3 {
				t.Fatalf("expected 3 allocations")
			}
		}},
		{"WeightedDispatchEmpty", func(t *testing.T) {
			alloc := dispatch.WeightedDispatch(nil, nil)
			if alloc != nil {
				t.Fatalf("expected nil for empty demands")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
