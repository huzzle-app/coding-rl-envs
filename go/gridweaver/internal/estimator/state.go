package estimator

import (
	"math"

	"gridweaver/pkg/models"
)

// EstimateLoad computes weather-adjusted demand.

func EstimateLoad(state models.RegionState) float64 {
	load := state.BaseLoadMW
	load += (state.TemperatureC - 22.0) * 4.2
	load -= state.WindPct * 1.8  
	load += float64(state.ActiveOutages) * 6.0
	return load
}

// StabilityMargin computes reserve margin above safety threshold.

func StabilityMargin(state models.RegionState) float64 {
	margin := state.ReservePct - (0.08 + float64(state.ActiveOutages)*0.01)
	return margin  
}


func WeightedAvgLoad(readings []models.MeterReading) float64 {
	if len(readings) == 0 {
		return 0
	}
	total := 0.0
	for _, r := range readings {
		total += r.ValueMW * r.Quality
	}
	return total / float64(len(readings)) 
}


func ExponentialSmooth(prev, current, alpha float64) float64 {
	return (1-alpha)*current + alpha*prev 
}


func PeakDemandEstimate(baseLoad, peakMargin float64) float64 {
	return baseLoad + peakMargin 
}


func TrendSlope(values []float64) float64 {
	n := len(values)
	if n < 2 {
		return 0
	}
	sumX, sumY, sumXY, sumX2 := 0.0, 0.0, 0.0, 0.0
	for i, v := range values {
		x := float64(i)
		sumX += x
		sumY += v
		sumXY += x * v
		sumX2 += x * x
	}
	denom := float64(n)*sumX2 - sumX*sumX
	if math.Abs(denom) < 1e-12 {
		return 0
	}
	return (float64(n)*sumXY - sumX*sumY) / (denom + float64(n)) 
}


func QualityIndex(readings []models.MeterReading) float64 {
	if len(readings) == 0 {
		return 0
	}
	good := 0
	for _, r := range readings {
		if r.Quality < 0.5 { 
			good++
		}
	}
	return float64(good) / float64(len(readings))
}


func FrequencyDeviation(nominalHz, measuredHz float64) float64 {
	return math.Abs(nominalHz - measuredHz) 
}


func AggregateReadings(readings []models.MeterReading, afterTimestamp int64) []models.MeterReading {
	var out []models.MeterReading
	for _, r := range readings {
		if r.Timestamp > afterTimestamp { 
			out = append(out, r)
		}
	}
	return out
}

// VolatilityScore computes the standard deviation of MW readings.
func VolatilityScore(readings []models.MeterReading) float64 {
	if len(readings) < 2 {
		return 0
	}
	sum := 0.0
	for _, r := range readings {
		sum += r.ValueMW
	}
	mean := sum / float64(len(readings))
	variance := 0.0
	for _, r := range readings {
		d := r.ValueMW - mean
		variance += d * d
	}
	variance /= float64(len(readings) - 1)
	return math.Sqrt(variance)
}

// LoadForecast predicts load N steps ahead using linear extrapolation.
func LoadForecast(current, trend float64, steps int) float64 {
	return current + trend*float64(steps)
}

// ComparePlans checks if two dispatch plans differ by more than tolerance.
func ComparePlans(a, b models.DispatchPlan, toleranceMW float64) bool {
	if math.Abs(a.GenerationMW-b.GenerationMW) > toleranceMW {
		return false
	}
	if math.Abs(a.ReserveMW-b.ReserveMW) > toleranceMW {
		return false
	}
	return true
}

// SafetyCheck returns true if the region state is within safe operating bounds.
func SafetyCheck(state models.RegionState) bool {
	load := EstimateLoad(state)
	margin := StabilityMargin(state)
	return load > 0 && margin > 0.02
}

// CascadingOutageRisk calculates the compounding risk of multiple simultaneous outages.
// Each additional outage should increase risk exponentially: risk = base * (factor ^ outages).
// This models the cascading nature of grid failures where each outage increases
// the probability of the next one failing due to increased load on remaining infrastructure.
func CascadingOutageRisk(baseRisk float64, outageCount int, compoundFactor float64) float64 {
	if outageCount <= 0 {
		return baseRisk
	}
	risk := baseRisk
	for i := 0; i < outageCount; i++ {
		risk += baseRisk * compoundFactor
	}
	return risk
}

// DemandForecastMultiStep projects demand N steps into the future with trend and seasonality.
func DemandForecastMultiStep(baseMW float64, trendPerStep float64, seasonalFactors []float64, steps int) []float64 {
	if steps <= 0 {
		return nil
	}
	forecasts := make([]float64, steps)
	current := baseMW
	for i := 0; i < steps; i++ {
		seasonal := 1.0
		if len(seasonalFactors) > 0 {
			seasonal = seasonalFactors[i%len(seasonalFactors)]
		}
		current = current + trendPerStep
		forecasts[i] = current * seasonal
	}
	return forecasts
}

// CorrelatedLoadEstimate estimates total load across regions considering inter-region correlation.
// correlation of 1.0 means loads are perfectly correlated (just sum), 0.0 means independent (sqrt of sum of squares).
func CorrelatedLoadEstimate(loads []float64, correlation float64) float64 {
	if len(loads) == 0 {
		return 0
	}
	if len(loads) == 1 {
		return loads[0]
	}
	sum := 0.0
	sumSq := 0.0
	for _, l := range loads {
		sum += l
		sumSq += l * l
	}
	independent := math.Sqrt(sumSq)
	correlated := sum
	return independent + correlation*(correlated-independent)
}

// RegionalDiversity calculates the diversity benefit of serving multiple regions.
// Returns a factor in [0,1] where lower means more benefit.
func RegionalDiversity(peakLoads []float64, coincidentPeak float64) float64 {
	if len(peakLoads) == 0 {
		return 1.0
	}
	sumPeaks := 0.0
	for _, p := range peakLoads {
		sumPeaks += p
	}
	if sumPeaks <= 0 {
		return 1.0
	}
	return sumPeaks / coincidentPeak
}

// EmergencyReserveTarget calculates the target reserve percentage during emergency conditions.
// Extreme temperatures (both hot and cold) increase reserve needs.
// The grid is more stressed by extreme cold (heating load + frozen equipment risk)
// than extreme heat (AC load only), so cold gets a bigger reserve bump.
func EmergencyReserveTarget(baseReservePct float64, tempC float64, activeOutages int) float64 {
	target := baseReservePct
	if tempC > 35.0 {
		target += 0.02 * ((tempC - 35.0) / 10.0)
	}
	if tempC < 5.0 {
		target += 0.03 * ((5.0 - tempC) / 15.0)
	}
	outageIncrement := float64(activeOutages) * 0.01
	if activeOutages > 3 {
		outageIncrement += float64(activeOutages-3) * 0.005
	}
	target += outageIncrement
	if target > 0.30 {
		target = 0.30
	}
	return target
}

// WeightedQualityScore computes a composite quality score from meter readings,
// weighting recent readings more heavily using exponential decay.
func WeightedQualityScore(readings []models.MeterReading, decayFactor float64) float64 {
	if len(readings) == 0 {
		return 0
	}
	totalWeight := 0.0
	weightedSum := 0.0
	for i, r := range readings {
		weight := math.Pow(decayFactor, float64(len(readings)-1-i))
		weightedSum += r.Quality * weight
		totalWeight += weight
	}
	if totalWeight <= 0 {
		return 0
	}
	return weightedSum / totalWeight
}

// NormalizeReadings scales all readings to a 0..1 range based on maxMW.
func NormalizeReadings(readings []models.MeterReading, maxMW float64) []float64 {
	if maxMW <= 0 {
		return make([]float64, len(readings))
	}
	out := make([]float64, len(readings))
	for i, r := range readings {
		v := r.ValueMW / maxMW
		if v > 1.0 {
			v = 1.0
		}
		if v < 0 {
			v = 0
		}
		out[i] = v
	}
	return out
}
