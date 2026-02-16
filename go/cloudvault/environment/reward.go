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

var BugTestMapping = map[string][]string{
	"A1-GoroutineLeak":         {"TestStorageServiceGoroutineLeak/should_not_leak_goroutines_on_upload"},
	"A2-RaceCondition":         {"TestSyncServiceRaceCondition/should_handle_concurrent_sync_starts_safely", "TestRateLimiterRaceCondition/should_handle_concurrent_requests_safely", "TestRateLimiterBucketAccess/should_not_race_on_bucket_token_modification"},
	"A3-ChannelDeadlock":       {"TestNotificationServiceDeadlock/should_not_deadlock_when_no_subscribers", "TestNotificationServiceDeadlock/should_not_deadlock_on_slow_subscriber", "TestNotificationServiceSubscribe/should_receive_notifications_on_channel", "TestNotificationServiceWaitForNotification/should_wait_for_notification"},
	"A4-WaitGroupMisuse":       {"TestStorageServiceConcurrency/should_handle_concurrent_chunk_uploads"},
	"A5-MutexCopy":             {"TestBucketMutexCopy/should_not_copy_bucket_by_value", "TestRateLimiterMutexCopy/should_not_copy_rate_limiter_by_value"},
	"B1-SliceBounds":           {"TestChunkerSplit/should_calculate_chunk_count_correctly"},
	"B2-NilMapWrite":           {"TestConflictResolver/should_not_panic_on_RegisterStrategy", "TestSlidingWindowLimiter/should_handle_Allow_without_panic"},
	"B3-SliceAliasing":         {"TestChunkerMerge/should_merge_chunks_in_correct_order"},
	"B4-MemoryLeak":            {},
	"C1-TransactionRollback":   {"TestVersioningCreateVersion/should_fail_without_database"},
	"C2-ConnectionLeak":        {"TestRepositoryConnectionLeak/should_not_leak_connections_on_error_in_GetByUserID"},
	"C3-PreparedStatementLeak": {"TestRepositoryPreparedStatementLeak/should_not_leak_prepared_statements_in_BulkCreate"},
	"C4-NPlus1Query":           {},
	"D1-IgnoredError":          {"TestSyncServiceApplyChange/should_handle_delete_change_with_invalid_file"},
	"D2-ErrorShadowing":        {"TestSyncServiceApplyChange/should_handle_delete_change_with_invalid_file"},
	"D3-NilInterfaceCheck":     {"TestGetUserID/should_panic_on_wrong_type"},
	"E1-WeakCrypto":            {"TestStreamEncryption/should_use_random_IV_for_stream", "TestHashPassword/should_produce_different_hashes_for_same_password_with_salt", "TestHashPassword/should_be_resistant_to_rainbow_tables", "TestCryptoSecurityIssues/should_use_proper_password_hashing", "TestCryptoSecurityIssues/should_use_unique_IVs_for_stream_encryption", "TestAuthenticationIssues/should_use_strong_password_hashing"},
	"E2-PathTraversal":         {"TestValidatePath/should_detect_URL-encoded_traversal", "TestValidatePath/should_detect_null_byte_injection", "TestPathTraversalPrevention/encoded_traversal", "TestPathTraversalPrevention/null_byte", "TestSanitizePath/should_fully_prevent_traversal", "TestJoinPath/should_prevent_escaping_base", "TestIsWithinBase/should_not_be_fooled_by_similar_prefixes", "TestIsAllowedExtension/should_not_be_bypassed_by_double_extension", "TestNormalizePath/should_handle_backslashes", "TestBuildPath/should_validate_components"},
	"E3-SQLInjection":          {"TestRepositorySQLInjection/should_be_vulnerable_to_SQL_injection_in_Search", "TestSQLInjection/should_prevent:_drop_table", "TestSQLInjection/should_prevent:_boolean_bypass", "TestSQLInjection/should_prevent:_stacked_query", "TestSQLInjection/should_prevent:_union_injection"},
	"E4-IDOR":                  {"TestIDORPrevention/should_check_file_ownership_on_download"},
	"F1-ImportCycle":            {},
	"F2-EnvParsing":            {"TestConfigEnvParsing/should_parse_MAX_FILE_SIZE_correctly", "TestConfigEnvParsing/should_parse_RATE_LIMIT_RPS_correctly", "TestConfigEnvParsing/should_parse_DEBUG_as_boolean", "TestConfigEnvParsing/should_accept_DEBUG=1_as_true"},
	"F3-ChunkSizeParsing":      {"TestConfigEnvParsing/should_parse_CHUNK_SIZE_with_Atoi"},
	"F4-MissingValidation":     {"TestConfigValidation/should_validate_required_fields", "TestConfigValidation/should_parse_ALLOWED_ORIGINS_correctly"},
	"L1-InitOrder":             {},
	"L2-EnvTypeParsing":        {"TestConfigEnvParsing/should_parse_DEBUG_as_boolean", "TestConfigEnvParsing/should_accept_DEBUG=1_as_true"},
}

var BugDependencies = map[string][]string{
	"F1-ImportCycle":  {},
	"L1-InitOrder":   {},
	"A2-RaceCondition": {"F1-ImportCycle"},
	"D1-IgnoredError":  {"F1-ImportCycle"},
	"D2-ErrorShadowing": {"F1-ImportCycle"},
	"B2-NilMapWrite":   {"F1-ImportCycle"},
	"C2-ConnectionLeak": {"L1-InitOrder"},
	"C3-PreparedStatementLeak": {"L1-InitOrder"},
	"E3-SQLInjection": {"L1-InitOrder"},
}
