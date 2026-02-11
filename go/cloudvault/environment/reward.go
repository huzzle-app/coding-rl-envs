package environment

import "strings"

// Sparse reward function for RL training
// Rewards are non-linear and sparse to encourage exploration

// PassThresholds defines the pass rate thresholds (5-tier for senior)
var PassThresholds = []float64{0.50, 0.75, 0.90, 1.0}

// ThresholdRewards defines rewards at each threshold (5-tier for senior)
var ThresholdRewards = []float64{0.15, 0.35, 0.65, 1.0}

// CalculateReward calculates the reward based on pass rate
func CalculateReward(passRate float64) float64 {
	// Find the appropriate threshold bucket
	for i := len(PassThresholds) - 1; i >= 0; i-- {
		if passRate >= PassThresholds[i] {
			return ThresholdRewards[i]
		}
	}
	return 0.0
}

// TestWeights assigns weights to different test categories
var TestWeights = map[string]float64{
	"unit":        1.0,
	"integration": 1.5,
	"security":    2.0,
	"race":        2.5,
}

// CATEGORY_WEIGHTS mirrors TestWeights for the reward calculator
var CategoryWeights = map[string]float64{
	"unit":        1.0,
	"integration": 1.5,
	"security":    2.0,
	"race":        2.5,
}

// CalculateWeightedReward calculates reward with test category weights
func CalculateWeightedReward(results map[string]bool, categories map[string]string) float64 {
	if len(results) == 0 {
		return 0.0
	}

	totalWeight := 0.0
	passedWeight := 0.0

	for testName, passed := range results {
		category := "unit" // default
		if cat, ok := categories[testName]; ok {
			category = cat
		} else {
			category = categorizeTestName(testName)
		}

		weight := TestWeights[category]
		if weight == 0 {
			weight = 1.0
		}
		totalWeight += weight
		if passed {
			passedWeight += weight
		}
	}

	if totalWeight == 0 {
		return 0.0
	}

	passRate := passedWeight / totalWeight
	return CalculateReward(passRate)
}

// categorizeTestName determines the category from the test path
func categorizeTestName(testName string) string {
	if strings.Contains(testName, "security") {
		return "security"
	}
	if strings.Contains(testName, "integration") {
		return "integration"
	}
	if strings.Contains(testName, "Race") || strings.Contains(testName, "race") {
		return "race"
	}
	return "unit"
}

// containsCategory checks if a test name belongs to a category
func containsCategory(testName, category string) bool {
	return strings.Contains(strings.ToLower(testName), strings.ToLower(category))
}

// Bonuses for specific achievements
const (
	RegressionPenalty   = -0.15
	RaceConditionBonus  = 0.05
	SecurityFixBonus    = 0.08
	AllConcurrencyBonus = 0.10
	CompleteFixBonus    = 0.15
)

// CalculateBonuses calculates additional bonuses
func CalculateBonuses(fixedBugs []string, previouslyFixed []string) float64 {
	bonus := 0.0

	// Check for regressions
	for _, prev := range previouslyFixed {
		stillFixed := false
		for _, curr := range fixedBugs {
			if curr == prev {
				stillFixed = true
				break
			}
		}
		if !stillFixed {
			bonus += RegressionPenalty
		}
	}

	// Bonus for fixing race conditions (hard to debug)
	for _, bug := range fixedBugs {
		if bug == "A2-RaceCondition" {
			bonus += RaceConditionBonus
		}
	}

	// Bonus for security fixes
	securityBugs := []string{"E1-WeakCrypto", "E2-PathTraversal", "E3-SQLInjection", "E4-IDOR"}
	for _, bug := range fixedBugs {
		for _, sec := range securityBugs {
			if bug == sec {
				bonus += SecurityFixBonus
				break
			}
		}
	}

	// Bonus for fixing all concurrency bugs
	concurrencyBugs := []string{"A1-GoroutineLeak", "A2-RaceCondition", "A3-ChannelDeadlock", "A4-WaitGroupMisuse", "A5-MutexCopy"}
	allConcurrency := true
	for _, cb := range concurrencyBugs {
		found := false
		for _, fb := range fixedBugs {
			if fb == cb {
				found = true
				break
			}
		}
		if !found {
			allConcurrency = false
			break
		}
	}
	if allConcurrency {
		bonus += AllConcurrencyBonus
	}

	// Bonus for complete fix (all bugs)
	if len(fixedBugs) >= TotalBugs() {
		bonus += CompleteFixBonus
	}

	return bonus
}

// CalculateRegressionPenalty returns a penalty for tests that were passing but now fail
func CalculateRegressionPenalty(current map[string]bool, previous map[string]bool) float64 {
	if len(previous) == 0 {
		return 0.0
	}

	regressions := 0
	for name, wasPassing := range previous {
		if wasPassing {
			if nowPassing, ok := current[name]; !ok || !nowPassing {
				regressions++
			}
		}
	}

	penalty := float64(regressions) / float64(len(previous))
	if penalty > 1.0 {
		penalty = 1.0
	}
	return penalty
}

// Legacy stubs - kept for backward compatibility
func CalculateBugBonus(_ map[string]bool) float64 { return 0.0 }

var BugTestMapping = map[string][]string{}
var BugDependencies = map[string][]string{}
