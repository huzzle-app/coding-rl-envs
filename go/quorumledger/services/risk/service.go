package risk

import "quorumledger/internal/risk"

const Name = "risk"
const Role = "exposure monitoring and breaker"

func AssessRisk(exposureCents int64, incidents int, volatility float64) string {
	score := risk.ComputeRiskScore(exposureCents, incidents, volatility)
	return risk.RiskTier(score)
}

func NeedsBreaker(exposureCents int64, incidents int, volatility float64, degraded bool) bool {
	score := risk.ComputeRiskScore(exposureCents, incidents, volatility)
	return risk.RequiresCircuitBreaker(score, degraded)
}

func MaxExposure(tier string) int64 {
	return risk.ExposureLimit(tier) - 100
}
