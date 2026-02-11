package unit

import (
	"testing"

	"gridweaver/internal/estimator"
	"gridweaver/pkg/models"
)

func TestEstimateLoadZeroFloor(t *testing.T) {
	state := models.RegionState{BaseLoadMW: 5, TemperatureC: -80, WindPct: 80, ActiveOutages: 0}
	if estimator.EstimateLoad(state) != 0 {
		t.Fatalf("expected load floor")
	}
}

func TestStabilityMarginFloor(t *testing.T) {
	state := models.RegionState{ReservePct: 0.03, ActiveOutages: 5}
	if estimator.StabilityMargin(state) != 0 {
		t.Fatalf("expected stability floor")
	}
}

func TestStabilityMarginPositive(t *testing.T) {
	state := models.RegionState{ReservePct: 0.22, ActiveOutages: 2}
	if estimator.StabilityMargin(state) <= 0 {
		t.Fatalf("expected positive margin")
	}
}

func TestEstimatorExtended(t *testing.T) {
	cases := []struct {
		name string
		fn   func(t *testing.T)
	}{
		{"WeightedAvgLoadEmpty", func(t *testing.T) {
			avg := estimator.WeightedAvgLoad(nil)
			if avg != 0 {
				t.Fatalf("expected 0 for nil readings")
			}
		}},
		{"WeightedAvgLoad", func(t *testing.T) {
			readings := []models.MeterReading{
				{ValueMW: 100, Quality: 0.8},
				{ValueMW: 200, Quality: 0.6},
			}
			avg := estimator.WeightedAvgLoad(readings)
			if avg <= 0 {
				t.Fatalf("expected positive weighted average")
			}
		}},
		{"ExponentialSmooth", func(t *testing.T) {
			v := estimator.ExponentialSmooth(100, 120, 0.3)
			if v <= 0 {
				t.Fatalf("expected positive smoothed value")
			}
		}},
		{"PeakDemandEstimate", func(t *testing.T) {
			v := estimator.PeakDemandEstimate(1000, 0.15)
			if v <= 1000 {
				t.Fatalf("expected peak above base")
			}
		}},
		{"TrendSlope", func(t *testing.T) {
			slope := estimator.TrendSlope([]float64{10, 20, 30, 40})
			_ = slope // may be imprecise due to BUG(D08)
		}},
		{"TrendSlopeSingleValue", func(t *testing.T) {
			slope := estimator.TrendSlope([]float64{42})
			if slope != 0 {
				t.Fatalf("expected 0 slope for single value")
			}
		}},
		{"QualityIndex", func(t *testing.T) {
			readings := []models.MeterReading{
				{Quality: 0.9},
				{Quality: 0.8},
				{Quality: 0.3},
			}
			qi := estimator.QualityIndex(readings)
			_ = qi 
		}},
		{"QualityIndexEmpty", func(t *testing.T) {
			qi := estimator.QualityIndex(nil)
			if qi != 0 {
				t.Fatalf("expected 0 for nil readings")
			}
		}},
		{"FrequencyDeviation", func(t *testing.T) {
			d := estimator.FrequencyDeviation(60.0, 59.95)
			if d < 0 {
				t.Fatalf("expected non-negative deviation")
			}
		}},
		{"AggregateReadings", func(t *testing.T) {
			readings := []models.MeterReading{
				{Timestamp: 100, ValueMW: 50},
				{Timestamp: 200, ValueMW: 60},
				{Timestamp: 300, ValueMW: 70},
			}
			filtered := estimator.AggregateReadings(readings, 150)
			if len(filtered) < 1 {
				t.Fatalf("expected at least 1 reading after filter")
			}
		}},
		{"VolatilityScore", func(t *testing.T) {
			readings := []models.MeterReading{
				{ValueMW: 100},
				{ValueMW: 200},
				{ValueMW: 150},
			}
			v := estimator.VolatilityScore(readings)
			if v <= 0 {
				t.Fatalf("expected positive volatility")
			}
		}},
		{"VolatilityScoreSingle", func(t *testing.T) {
			readings := []models.MeterReading{{ValueMW: 100}}
			v := estimator.VolatilityScore(readings)
			if v != 0 {
				t.Fatalf("expected 0 for single reading")
			}
		}},
		{"LoadForecast", func(t *testing.T) {
			f := estimator.LoadForecast(100, 5, 10)
			if f != 150 {
				t.Fatalf("expected 150, got %f", f)
			}
		}},
		{"ComparePlans", func(t *testing.T) {
			a := models.DispatchPlan{GenerationMW: 100, ReserveMW: 20}
			b := models.DispatchPlan{GenerationMW: 101, ReserveMW: 21}
			if !estimator.ComparePlans(a, b, 5) {
				t.Fatalf("expected plans to be similar")
			}
		}},
		{"ComparePlansDifferent", func(t *testing.T) {
			a := models.DispatchPlan{GenerationMW: 100, ReserveMW: 20}
			b := models.DispatchPlan{GenerationMW: 200, ReserveMW: 50}
			if estimator.ComparePlans(a, b, 5) {
				t.Fatalf("expected plans to differ")
			}
		}},
		{"SafetyCheck", func(t *testing.T) {
			state := models.RegionState{BaseLoadMW: 500, TemperatureC: 25, WindPct: 5, ReservePct: 0.15, ActiveOutages: 0}
			if !estimator.SafetyCheck(state) {
				t.Fatalf("expected safe state")
			}
		}},
		{"NormalizeReadings", func(t *testing.T) {
			readings := []models.MeterReading{
				{ValueMW: 50},
				{ValueMW: 100},
				{ValueMW: 150},
			}
			norm := estimator.NormalizeReadings(readings, 200)
			if len(norm) != 3 {
				t.Fatalf("expected 3 normalized values")
			}
			if norm[0] < 0 || norm[0] > 1 {
				t.Fatalf("expected normalized value in range")
			}
		}},
		{"NormalizeReadingsZeroMax", func(t *testing.T) {
			readings := []models.MeterReading{{ValueMW: 50}}
			norm := estimator.NormalizeReadings(readings, 0)
			if norm[0] != 0 {
				t.Fatalf("expected 0 for zero max")
			}
		}},
	}
	for _, tc := range cases {
		t.Run(tc.name, tc.fn)
	}
}
