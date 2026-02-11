package environment

var passThresholds = []float64{0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0}
var thresholdRewards = []float64{0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0}

func SparseReward(passRate float64) float64 {
	for i := len(passThresholds) - 1; i >= 0; i-- {
		if passRate >= passThresholds[i] {
			return thresholdRewards[i]
		}
	}
	return 0.0
}

// TotalBugs is a legacy stub for backward compatibility
func TotalBugs() int { return 0 }

// TotalTests is a legacy stub for backward compatibility
func TotalTests() int { return 0 }
