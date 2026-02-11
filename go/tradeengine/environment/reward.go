package environment

import (
	"math"
)

// RewardCalculator calculates rewards based on test results
type RewardCalculator struct {
	// Category weights
	weights map[string]float64

	// Pass thresholds for sparse rewards
	passThresholds   []float64
	thresholdRewards []float64

	// Previous results for regression detection
	previousPassRate float64

	// Bonus/penalty values
	regressionPenalty  float64
	raceConditionBonus float64
	chaosTestBonus     float64
	securityBonus      float64
}

// NewRewardCalculator creates a new reward calculator
func NewRewardCalculator() *RewardCalculator {
	return &RewardCalculator{
		weights: map[string]float64{
			"unit":        1.0,
			"integration": 1.5,
			"security":    2.5,
			"chaos":       3.0,
			"performance": 2.0,
			"race":        2.0,
			"system":      3.0,
		},
		passThresholds:   []float64{0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0},
		thresholdRewards: []float64{0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0},

		regressionPenalty:  -0.15,
		raceConditionBonus: 0.05,
		chaosTestBonus:     0.10,
		securityBonus:      0.08,
	}
}

// Calculate calculates the reward based on test results
func (r *RewardCalculator) Calculate(results *TestResults, previousResults map[string]bool) float64 {
	if results.TotalTests == 0 {
		return 0.0
	}

	// Calculate weighted pass rate
	weightedPassed := 0.0
	weightedTotal := 0.0

	for category, cat := range results.Categories {
		weight := r.weights[category]
		if weight == 0 {
			weight = 1.0
		}
		weightedPassed += float64(cat.Passed) * weight
		weightedTotal += float64(cat.Total) * weight
	}

	if weightedTotal == 0 {
		return 0.0
	}

	passRate := weightedPassed / weightedTotal

	// Calculate sparse reward
	reward := r.getSparseReward(passRate)

	// Apply regression penalty
	if passRate < r.previousPassRate {
		reward += r.regressionPenalty * (r.previousPassRate - passRate)
	}

	// Apply bonuses for difficult test categories
	if results.Categories["race"].Passed > 0 {
		racePassRate := float64(results.Categories["race"].Passed) / float64(results.Categories["race"].Total)
		reward += r.raceConditionBonus * racePassRate
	}

	if results.Categories["chaos"].Passed > 0 {
		chaosPassRate := float64(results.Categories["chaos"].Passed) / float64(results.Categories["chaos"].Total)
		reward += r.chaosTestBonus * chaosPassRate
	}

	if results.Categories["security"].Passed > 0 {
		securityPassRate := float64(results.Categories["security"].Passed) / float64(results.Categories["security"].Total)
		reward += r.securityBonus * securityPassRate
	}

	// Update previous pass rate
	r.previousPassRate = passRate

	// Clamp reward to [0, 1]
	return math.Max(0, math.Min(1, reward))
}

// getSparseReward calculates sparse reward based on pass rate thresholds
func (r *RewardCalculator) getSparseReward(passRate float64) float64 {
	// Find the highest threshold that passRate exceeds
	for i := len(r.passThresholds) - 1; i >= 0; i-- {
		if passRate >= r.passThresholds[i] {
			return r.thresholdRewards[i]
		}
	}
	return 0.0
}

// CalculateDetailedReward provides detailed reward breakdown
func (r *RewardCalculator) CalculateDetailedReward(results *TestResults) RewardBreakdown {
	breakdown := RewardBreakdown{
		CategoryRewards: make(map[string]float64),
	}

	// Calculate per-category rewards
	for category, cat := range results.Categories {
		if cat.Total == 0 {
			continue
		}

		weight := r.weights[category]
		if weight == 0 {
			weight = 1.0
		}

		passRate := float64(cat.Passed) / float64(cat.Total)
		breakdown.CategoryRewards[category] = passRate * weight / 3.0 // Normalize
	}

	// Calculate base reward
	for _, catReward := range breakdown.CategoryRewards {
		breakdown.BaseReward += catReward
	}
	breakdown.BaseReward /= float64(len(breakdown.CategoryRewards))

	// Calculate bonuses
	if results.Categories["race"].Total > 0 {
		racePassRate := float64(results.Categories["race"].Passed) / float64(results.Categories["race"].Total)
		breakdown.BonusReward += r.raceConditionBonus * racePassRate
	}

	if results.Categories["chaos"].Total > 0 {
		chaosPassRate := float64(results.Categories["chaos"].Passed) / float64(results.Categories["chaos"].Total)
		breakdown.BonusReward += r.chaosTestBonus * chaosPassRate
	}

	if results.Categories["security"].Total > 0 {
		securityPassRate := float64(results.Categories["security"].Passed) / float64(results.Categories["security"].Total)
		breakdown.BonusReward += r.securityBonus * securityPassRate
	}

	breakdown.TotalReward = breakdown.BaseReward + breakdown.BonusReward

	return breakdown
}

// RewardBreakdown provides detailed reward information
type RewardBreakdown struct {
	BaseReward      float64
	BonusReward     float64
	PenaltyReward   float64
	TotalReward     float64
	CategoryRewards map[string]float64
}

// Legacy stubs - kept for backward compatibility
func TotalBugs() int  { return 0 }
func TotalTests() int { return 0 }
func AreDependenciesMet(_ string, _ map[string]bool) bool { return true }
func BugCategories() map[string]int { return map[string]int{} }

// GetBugProgress is a legacy stub method
func (r *RewardCalculator) GetBugProgress(_ *TestResults) map[string]float64 {
	return map[string]float64{}
}

var BugTestMapping = map[string][]string{}
var BugDependencies = map[string][]string{}

func GetDependencyChains() [][]string { return [][]string{} }
