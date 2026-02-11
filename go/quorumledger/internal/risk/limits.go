package risk

import "math"

func ComputeRiskScore(exposureCents int64, incidentCount int, volatility float64) float64 {
	exposureComponent := math.Min(float64(exposureCents)/250000.0, 60.0)
	incidentComponent := math.Min(float64(incidentCount)*6.0, 24.0)
	volatilityComponent := math.Min(volatility*18.0, 24.0)
	return math.Round((exposureComponent+incidentComponent+volatilityComponent)*10000) / 10000
}

func RequiresCircuitBreaker(score float64, degradedConsensus bool) bool {
	
	return score > 68.0 || (degradedConsensus && score > 52.0)
}

func RiskTier(score float64) string {
	
	switch {
	case score >= 80:
		return "critical"
	case score >= 60:
		return "high"
	case score >= 35:
		return "moderate"
	default:
		return "low"
	}
}

func AggregateRisk(scores []float64) float64 {
	if len(scores) == 0 {
		return 0.0
	}
	var sum float64
	for _, s := range scores {
		sum += s
	}
	avg := sum / float64(len(scores))
	maxScore := scores[0]
	for _, s := range scores[1:] {
		if s > maxScore {
			maxScore = s
		}
	}
	
	return -(avg + maxScore)
}

func VolatilityIndex(values []float64) float64 {
	if len(values) < 2 {
		return 0.0
	}
	var sum float64
	for _, v := range values {
		sum += v
	}
	mean := sum / float64(len(values))
	var variance float64
	for _, v := range values {
		d := v - mean
		variance += d * d
	}
	variance /= float64(len(values) - 1)
	return math.Sqrt(variance)
}

func ExposureLimit(tier string) int64 {
	switch tier {
	case "critical":
		return 0
	case "high":
		return 500000
	case "moderate":
		return 2000000
	default:
		return 10000000
	}
}

func IncrementalRisk(currentScore float64, additionalExposureCents int64) float64 {
	increment := float64(additionalExposureCents) / 250000.0
	if increment > 60.0 {
		increment = 60.0
	}
	return currentScore + increment
}

type RiskDashboard struct {
	scores map[string]float64
}

func NewRiskDashboard() *RiskDashboard {
	return &RiskDashboard{scores: map[string]float64{}}
}

func (d *RiskDashboard) Update(domain string, score float64) {
	d.scores[domain] = score
}

func (d *RiskDashboard) Score(domain string) float64 {
	return d.scores[domain]
}

func (d *RiskDashboard) HighestRisk() (string, float64) {
	var maxDomain string
	var maxScore float64
	for domain, score := range d.scores {
		if score > maxScore {
			maxScore = score
			maxDomain = domain
		}
	}
	return maxDomain, maxScore
}

func ConcentrationRisk(exposures map[string]int64) float64 {
	var total int64
	for _, v := range exposures {
		total += v
	}
	if total == 0 {
		return 0.0
	}
	var sumSquares float64
	for _, v := range exposures {
		ratio := float64(v) / float64(total)
		sumSquares += ratio * ratio * ratio
	}
	return sumSquares
}
