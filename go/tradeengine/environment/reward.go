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
		passThresholds:   []float64{0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0},
		thresholdRewards: []float64{0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0},

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

// TotalBugs returns the number of intentional bugs in the environment
func TotalBugs() int { return 87 }

// TotalTests returns the expected total number of test assertions (sub-tests)
// Actual measured: 202 sub-tests produce PASS/FAIL lines when all packages compile
func TotalTests() int { return 359 }

// BugCategories returns the bug count per category
func BugCategories() map[string]int {
	return map[string]int{
		"L": 8,  // Setup/Infrastructure
		"A": 12, // Concurrency
		"B": 8,  // Data Structures
		"C": 8,  // Event Sourcing
		"D": 10, // Distributed State
		"E": 8,  // Database
		"F": 10, // Financial Calculation
		"G": 6,  // Risk Logic
		"H": 5,  // Caching
		"I": 6,  // Security
		"J": 4,  // Observability
	}
}

// AreDependenciesMet checks if all prerequisite bugs are fixed
func AreDependenciesMet(bugID string, fixedBugs map[string]bool) bool {
	deps, ok := BugDependencies[bugID]
	if !ok {
		return true
	}
	for _, dep := range deps {
		if !fixedBugs[dep] {
			return false
		}
	}
	return true
}

// GetBugProgress computes per-bug fix progress from test results
func (r *RewardCalculator) GetBugProgress(results *TestResults) map[string]float64 {
	progress := make(map[string]float64)
	if results == nil {
		return progress
	}

	// Collect all passing test names across categories
	passingTests := make(map[string]bool)
	for _, cat := range results.Categories {
		// FailedTests tracks failures; anything not in FailedTests that
		// ran is assumed passing. For per-bug tracking we check if all
		// mapped tests are absent from FailedTests.
		for _, ft := range cat.FailedTests {
			passingTests[ft] = false
		}
	}

	for bugID, tests := range BugTestMapping {
		if len(tests) == 0 {
			continue
		}
		passing := 0
		for _, t := range tests {
			if failed, tracked := passingTests[t]; tracked && failed {
				continue
			}
			// If the test was not explicitly tracked as failed and the
			// total count is > 0, assume it passed
			passing++
		}
		progress[bugID] = float64(passing) / float64(len(tests))
	}
	return progress
}

// BugTestMapping maps each bug ID to its associated test function names
var BugTestMapping = map[string][]string{
	// L: Setup/Infrastructure
	"L1": {"TestClientCreation", "TestClientReconnection"},
	"L2": {"TestServiceDiscovery"},
	"L3": {"TestHealthChecks"},
	"L4": {"TestRiskCalculatorCreation", "TestTrackerCreation"},
	"L5": {"TestClientCreation"},
	"L6": {"TestDatabaseConnections"},
	"L7": {"TestMatchingEngineCreation"},
	"L8": {"TestConnectionPooling"},

	// A: Concurrency
	"A1":  {"TestMatchingEngineLockOrdering"},
	"A2":  {"TestMatchingEngineConcurrentAccess"},
	"A3":  {"TestMatchingEngineGoroutineLeak"},
	"A4":  {"TestHighLoad"},
	"A5":  {"TestConcurrentPositionUpdates"},
	"A6":  {"TestConcurrentRiskChecks"},
	"A7":  {"TestCircuitBreakerConcurrency"},
	"A8":  {"TestContextCancellation"},
	"A9":  {"TestCircuitBreakerHalfOpen"},
	"A10": {"TestNATSFailure"},
	"A11": {"TestPositionLimitsConcurrent"},
	"A12": {"TestSnapshotting"},

	// B: Data Structures
	"B1": {"TestOrderBookCancelOrder"},
	"B2": {"TestOrderBookDepth"},
	"B3": {"TestOrderBookMatching"},
	"B4": {"TestEventOrdering"},
	"B5": {"TestBreakerGroupGet"},
	"B6": {"TestOrderBookAddOrder"},
	"B7": {"TestGetAllPositions"},
	"B8": {"TestMessageOrdering"},

	// C: Event Sourcing
	"C1": {"TestEventOrdering"},
	"C2": {"TestTradeExecutionFlow"},
	"C3": {"TestCircuitBreakerStateChange"},
	"C4": {"TestSnapshotting"},
	"C5": {"TestEventSourcingFlow"},
	"C6": {"TestNATSMessaging"},
	"C7": {"TestNATSFailure"},
	"C8": {"TestMessageOrdering"},

	// D: Distributed State
	"D1":  {"TestConcurrentRiskChecks"},
	"D2":  {"TestDistributedLocking"},
	"D3":  {"TestOrderCancellationFlow"},
	"D4":  {"TestMatchingEngineConcurrentAccess"},
	"D5":  {"TestServiceDiscovery"},
	"D6":  {"TestCircuitBreakerOpen"},
	"D7":  {"TestRedisFailure"},
	"D8":  {"TestDatabaseFailure"},
	"D9":  {"TestDatabaseConnections"},
	"D10": {"TestOrderSubmissionFlow"},

	// E: Database
	"E1": {"TestDatabaseConnections"},
	"E2": {"TestDatabaseFailure"},
	"E3": {"TestSQLInjection"},
	"E4": {"TestTradeExecutionFlow"},
	"E5": {"TestDatabaseConnections"},
	"E6": {"TestDatabaseFailure"},
	"E7": {"TestConcurrentOrderFlow"},
	"E8": {"TestDatabaseConnections"},

	// F: Financial Calculation
	"F1":  {"TestMoneyOperations", "TestPriceCreation"},
	"F2":  {"TestCalculatePnL", "TestPnLFloatPrecision"},
	"F3":  {"TestParseMoney", "TestParseMoneyLargePrecision"},
	"F4":  {"TestPriceRounding", "TestRoundingModeConsistency", "TestRoundMoney"},
	"F5":  {"TestCalculateMargin", "TestMarginOverflow"},
	"F6":  {"TestFillCompletionFloatComparison"},
	"F7":  {"TestDivisionByZero"},
	"F8":  {"TestMaxDrawdownCalculation"},
	"F9":  {"TestAllocationDivisionByZero"},
	"F10": {"TestFloatComparisonEpsilon"},

	// G: Risk Logic
	"G1": {"TestMarginCalculation", "TestMarginWithDecimal"},
	"G2": {"TestPositionLimits", "TestPositionLimitsConcurrent"},
	"G3": {"TestDailyLossLimit", "TestDailyLossLimitReset"},
	"G4": {"TestLeverageCalculation", "TestLeverageOverflow"},
	"G5": {"TestVaRCalculation"},
	"G6": {"TestExposureAggregation"},

	// H: Caching
	"H1": {"TestRedisFailure"},
	"H2": {"TestHighLoad"},
	"H3": {"TestRedisFailure"},
	"H4": {"TestRedisFailure"},
	"H5": {"TestConcurrentOrderFlow"},

	// I: Security
	"I1": {"TestJWTSecurity", "TestJWTWeakSecret"},
	"I2": {"TestEmailValidation", "TestEmailFormatValidation", "TestInputValidation"},
	"I3": {"TestTimingAttack", "TestConstantTimeComparison"},
	"I4": {"TestAPIKeySecurity", "TestAPIKeyGeneration", "TestAPIKeyEntropy"},
	"I5": {"TestPasswordSecurity", "TestPasswordHashing", "TestBcryptUsage"},
	"I6": {"TestPermissionParsing", "TestPermissionEscalation", "TestPermissionInjection"},

	// J: Observability
	"J1": {"TestContextCancellation"},
	"J2": {"TestServicePartition"},
	"J3": {"TestHighLoad"},
	"J4": {"TestHealthChecks"},
}

// BugDependencies maps each bug to bugs that must be fixed first
var BugDependencies = map[string][]string{
	// Setup bugs must be fixed before most other bugs
	"A1":  {"L1", "L4"},
	"A2":  {"L1"},
	"A3":  {"L1"},
	"A4":  {"L1"},
	"A5":  {"L4"},
	"A6":  {"L4"},
	"A8":  {"L1"},
	"A12": {"L4"},

	"B1": {"L4"},
	"B2": {"L4"},
	"B4": {"L4", "L1"},

	"C1": {"L1", "L4"},
	"C2": {"L1", "E1"},
	"C3": {"L1"},
	"C4": {"L4", "A5"},
	"C5": {"L1", "C1"},
	"C6": {"L1"},
	"C7": {"L1"},
	"C8": {"L1", "C1"},

	"D1":  {"L4", "A6"},
	"D2":  {"L1", "L2"},
	"D3":  {"L1", "A1"},
	"D4":  {"L4", "A1"},
	"D5":  {"L2"},
	"D7":  {"L1"},
	"D8":  {"L1", "E1"},
	"D9":  {"E1", "E2"},
	"D10": {"L1", "L4"},

	"E2": {"E1"},
	"E3": {"E1"},
	"E4": {"E1", "C2"},
	"E5": {"E1"},
	"E6": {"E1"},
	"E7": {"E1"},

	"F2":  {"F1"},
	"F5":  {"F1"},
	"F8":  {"F1"},
	"F9":  {"F1"},
	"F10": {"F6"},

	"G1": {"F1"},
	"G2": {"G1", "A6"},
	"G3": {"G1"},
	"G4": {"G1", "F5"},
	"G5": {"G1"},
	"G6": {"G1", "G5"},

	"H2": {"H1"},
	"H3": {"H1"},
	"H4": {"H1"},
	"H5": {"H1", "E7"},

	"I3": {"I1"},
	"I6": {"I1"},

	"J2": {"J1"},
	"J3": {"J1"},
}

// GetDependencyChains returns the critical dependency chains
func GetDependencyChains() [][]string {
	return [][]string{
		{"L1", "A1", "D3", "D4"},
		{"L1", "C1", "C5", "C8"},
		{"L4", "A5", "C4"},
		{"L1", "L2", "D2", "D5"},
		{"E1", "E2", "D9"},
		{"F1", "G1", "G2", "G6"},
		{"F1", "F2", "F5"},
		{"H1", "H2", "H3", "H5"},
		{"I1", "I3", "I6"},
	}
}
