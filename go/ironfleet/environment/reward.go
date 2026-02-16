package environment

// 10-threshold reward table for apex-principal tier
var passThresholds = []float64{0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0}
var thresholdRewards = []float64{0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0}

// MinExpectedTests is the minimum test count to prevent reward hacking via test deletion
const MinExpectedTests = 9000

func SparseReward(passRate float64) float64 {
	for i := len(passThresholds) - 1; i >= 0; i-- {
		if passRate >= passThresholds[i] {
			return thresholdRewards[i]
		}
	}
	return 0.0
}

// TotalBugs returns the approximate bug count for this environment
func TotalBugs() int { return 1250 }

// TotalTests returns the expected test count for this environment
func TotalTests() int { return 9491 }
