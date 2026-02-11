package unit

import (
	"testing"

	"gridweaver/internal/demandresponse"
)

func TestDemandResponseDispatch(t *testing.T) {
	p := demandresponse.Program{CommittedMW: 20, MaxMW: 50}
	p2 := demandresponse.ApplyDispatch(p, 10)
	if p2.CommittedMW != 30 {
		t.Fatalf("expected committed 30, got %v", p2.CommittedMW)
	}
}

func TestDemandResponseExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"EfficiencyRatio", func(t *testing.T) {
			r := demandresponse.EfficiencyRatio(80, 100)
			if r <= 0 {
				t.Fatalf("expected positive efficiency ratio")
			}
		}},
		{"EfficiencyRatioZero", func(t *testing.T) {
			r := demandresponse.EfficiencyRatio(0, 100)
			if r != 0 {
				t.Fatalf("expected 0 for zero delivered")
			}
		}},
		{"CostPerMW", func(t *testing.T) {
			c := demandresponse.CostPerMW(10000, 50)
			if c <= 0 {
				t.Fatalf("expected positive cost per MW")
			}
		}},
		{"CostPerMWZero", func(t *testing.T) {
			c := demandresponse.CostPerMW(10000, 0)
			if c != 0 {
				t.Fatalf("expected 0 for zero MW")
			}
		}},
		{"InterpolateLoad", func(t *testing.T) {
			v := demandresponse.InterpolateLoad(100, 200, 0.5)
			if v <= 0 {
				t.Fatalf("expected positive interpolated value")
			}
		}},
		{"MaxAvailable", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 30, MaxMW: 100}
			avail := demandresponse.MaxAvailable(p)
			if avail <= 0 {
				t.Fatalf("expected positive available capacity")
			}
		}},
		{"BatchDispatch", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 0, MaxMW: 100}
			p2, count := demandresponse.BatchDispatch(p, []float64{10, 20, 30})
			if count < 1 {
				t.Fatalf("expected at least 1 dispatched")
			}
			_ = p2
		}},
		{"ProgramUtilization", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 30, MaxMW: 100}
			u := demandresponse.ProgramUtilization(p)
			if u < 0 || u > 1 {
				t.Fatalf("utilization out of range: %f", u)
			}
		}},
		{"ProgramUtilizationZeroMax", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 0, MaxMW: 0}
			u := demandresponse.ProgramUtilization(p)
			if u != 0 {
				t.Fatalf("expected 0 for zero max")
			}
		}},
		{"RemainingCapacity", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 30, MaxMW: 100}
			r := demandresponse.RemainingCapacity(p)
			if r != 70 {
				t.Fatalf("expected 70, got %f", r)
			}
		}},
		{"IsFullyCommitted", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 100, MaxMW: 100}
			if !demandresponse.IsFullyCommitted(p) {
				t.Fatalf("expected fully committed")
			}
		}},
		{"ScaleProgram", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 10, MaxMW: 50}
			scaled := demandresponse.ScaleProgram(p, 2.0)
			if scaled.MaxMW != 100 {
				t.Fatalf("expected scaled max 100")
			}
		}},
		{"AggregatePrograms", func(t *testing.T) {
			programs := []demandresponse.Program{
				{CommittedMW: 10, MaxMW: 50},
				{CommittedMW: 20, MaxMW: 80},
			}
			agg := demandresponse.AggregatePrograms(programs)
			if agg.CommittedMW != 30 || agg.MaxMW != 130 {
				t.Fatalf("unexpected aggregate: %+v", agg)
			}
		}},
		{"OptimalDispatch", func(t *testing.T) {
			programs := []demandresponse.Program{
				{CommittedMW: 0, MaxMW: 100},
				{CommittedMW: 50, MaxMW: 100},
			}
			allocs := demandresponse.OptimalDispatch(programs, 60)
			if len(allocs) != 2 {
				t.Fatalf("expected 2 allocations")
			}
		}},
		{"CanDispatchNegative", func(t *testing.T) {
			p := demandresponse.Program{CommittedMW: 0, MaxMW: 100}
			if demandresponse.CanDispatch(p, -1) {
				t.Fatalf("should not dispatch negative")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
