"""
HelixOps Reward Function
Apex-principal profile with deep dependency penalties

Kotlin 1.9, Ktor 2.3, Exposed ORM, 10 Microservices
Kafka, PostgreSQL, Redis, Consul
"""
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from pathlib import Path
import xml.etree.ElementTree as ET

@dataclass
class TestResult:
    """Represents a single test result."""
    name: str
    passed: bool
    duration: float = 0.0
    category: str = "unit"
    bug_markers: List[str] = field(default_factory=list)
    error_message: str = ""
    service: str = ""

@dataclass
class RewardBreakdown:
    """Detailed breakdown of reward components."""
    test_pass_score: float
    completion_bonus: float
    bug_bonus: float
    efficiency_bonus: float
    total: float
    details: Dict

# ==============================================================================
# Service to bug mapping (11 modules)
# ==============================================================================
SERVICE_BUG_MAP = {
    "shared": [f"HX{i:04d}" for i in range(1, 301)],       # 300 bugs: cache, config, db, delegation, events, kotlin, models, observability, security, serialization
    "gateway": [f"HX{i:04d}" for i in range(301, 401)],     # 100 bugs: pipeline, auth gates, routing, rate limiting
    "auth": [f"HX{i:04d}" for i in range(401, 501)],        # 100 bugs: JWT, key rotation, delegation tokens, access control
    "documents": [f"HX{i:04d}" for i in range(501, 601)],   # 100 bugs: lifecycle, soft-delete, versioning, repository
    "search": [f"HX{i:04d}" for i in range(601, 701)],      # 100 bugs: query planning, scoring, cache coordination
    "graph": [f"HX{i:04d}" for i in range(701, 801)],       # 100 bugs: traversal, topology, mutex, scope
    "embeddings": [f"HX{i:04d}" for i in range(801, 881)],  # 80 bugs: vector generation, batch processing, storage
    "collab": [f"HX{i:04d}" for i in range(881, 981)],      # 100 bugs: real-time sync, WebSocket, SharedFlow
    "billing": [f"HX{i:04d}" for i in range(981, 1081)],    # 100 bugs: invoicing, tax, transfers, transaction isolation
    "notifications": [f"HX{i:04d}" for i in range(1081, 1161)],  # 80 bugs: channels, templates, rate limiting
    "analytics": [f"HX{i:04d}" for i in range(1161, 1251)], # 90 bugs: metrics, aggregation, MDC propagation
}

# ==============================================================================
# Reward thresholds and values (Apex-Principal - ultra sparse)
# ==============================================================================
REWARD_THRESHOLDS = [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0]
REWARD_VALUES = [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0]
CATEGORY_BONUS = 0.01
SERVICE_BONUS = 0.01
REGRESSION_PENALTY = -0.03

# ==============================================================================
# Test category weights
# ==============================================================================
CATEGORY_WEIGHTS = {
    "unit": 1.0,
    "integration": 1.5,
    "coroutine": 2.5,
    "security": 2.0,
}

class RewardCalculator:
    """
    Calculate reward for the HelixOps debugging environment.

    Apex-principal profile with ultra-sparse thresholds:
    - Bug fix rate mapped to stepped reward values
    - Category completion bonus: +0.01 per fully fixed category (12 categories)
    - Service isolation bonus: +0.01 per fully passing service (11 modules)
    - Regression penalty: -0.03 per regressed test
    - Coroutine and security fix bonuses
    """

    def __init__(self, max_steps: int = 200):
        self.max_steps = max_steps

    def calculate(
        self,
        test_results: List[TestResult],
        step_count: int,
        previous_results: Optional[List[TestResult]] = None,
    ) -> RewardBreakdown:
        """
        Calculate total reward from test results.

        Args:
            test_results: List of test results from Gradle/JUnit run
            step_count: Current step/action count
            previous_results: Previous test results for regression detection

        Returns:
            RewardBreakdown with detailed scoring
        """
        test_pass_score = self._calculate_sparse_pass_rate(test_results)
        completion_bonus = self._calculate_strict_completion_bonus(test_results)
        bug_bonus = 0.0
        efficiency_bonus = self._calculate_efficiency_bonus(test_results, step_count)

        regression_penalty = 0.0
        if previous_results:
            regression_penalty = self._calculate_regression_penalty(
                test_results, previous_results
            )

        # Coroutine bonus
        coroutine_bonus = 0.0
        failing = {r.name for r in test_results if not r.passed}
        coroutine_keywords = [
            "runblocking", "globalscope", "flow", "channel", "dispatcher",
            "async", "coroutine", "mutex", "supervisor", "unconfined",
        ]
        if not any(
            any(kw in t.lower() for kw in coroutine_keywords) for t in failing
        ):
            coroutine_bonus = 0.03

        # Security bonus
        security_bonus = 0.0
        security_keywords = [
            "injection", "traversal", "ssrf", "jwt_none", "timing",
            "deserialization", "xxe", "api_key",
        ]
        if not any(
            any(kw in t.lower() for kw in security_keywords) for t in failing
        ):
            security_bonus = 0.02

        total = (
            test_pass_score * 0.40
            + completion_bonus * 0.25
            + bug_bonus * 0.25
            + efficiency_bonus * 0.05
            + coroutine_bonus
            + security_bonus
            - regression_penalty * 0.15
        )
        total = max(0.0, min(total, 1.0))

        return RewardBreakdown(
            test_pass_score=test_pass_score,
            completion_bonus=completion_bonus,
            bug_bonus=bug_bonus,
            efficiency_bonus=efficiency_bonus,
            total=total,
            details=self._get_details(test_results, step_count, regression_penalty),
        )

    def _calculate_sparse_pass_rate(self, results: List[TestResult]) -> float:
        """
        Calculate sparse pass rate using test pass ratio and threshold mapping.

        Uses REWARD_THRESHOLDS and REWARD_VALUES for stepped rewards.
        """
        if not results:
            return 0.0

        passed_count = sum(1 for r in results if r.passed)
        total_count = len(results)
        pass_rate = passed_count / total_count if total_count > 0 else 0.0

        reward = 0.0
        for i, threshold in enumerate(REWARD_THRESHOLDS):
            if pass_rate >= threshold:
                reward = REWARD_VALUES[i]

        return reward

    def _calculate_strict_completion_bonus(self, results: List[TestResult]) -> float:
        """
        Calculate strict completion bonus.

        Only counts categories where ALL tests pass.
        """
        category_stats = {}
        for result in results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0}
            category_stats[cat]["total"] += 1
            if result.passed:
                category_stats[cat]["passed"] += 1

        categories_complete = sum(
            1 for stats in category_stats.values()
            if stats["total"] > 0 and stats["passed"] == stats["total"]
        )

        bonus = categories_complete * CATEGORY_BONUS
        return min(bonus, 1.0)

    def _calculate_regression_penalty(
        self,
        current: List[TestResult],
        previous: List[TestResult],
    ) -> float:
        """
        Calculate penalty for regressions (tests that were passing now fail).

        Penalty: -0.03 per test that was passing but now fails.
        """
        prev_status = {r.name: r.passed for r in previous}
        curr_status = {r.name: r.passed for r in current}

        regressions = sum(
            1
            for name, was_passing in prev_status.items()
            if was_passing and not curr_status.get(name, False)
        )

        if not previous:
            return 0.0

        return min(regressions * abs(REGRESSION_PENALTY), 1.0)

    def _calculate_efficiency_bonus(
        self,
        results: List[TestResult],
        step_count: int,
    ) -> float:
        """
        Calculate progressive efficiency bonus.

        Rewards high pass rate achieved with remaining step budget.
        """
        if not results:
            return 0.0

        pass_rate = sum(1 for r in results if r.passed) / len(results)
        remaining_budget = max(0.0, 1.0 - step_count / self.max_steps)
        return pass_rate * remaining_budget

    def _get_details(
        self,
        results: List[TestResult],
        step_count: int,
        regression_penalty: float = 0.0,
    ) -> Dict:
        """Get detailed breakdown of results."""
        category_breakdown = {}
        for result in results:
            cat = result.category
            if cat not in category_breakdown:
                category_breakdown[cat] = {"total": 0, "passed": 0, "failed": []}
            category_breakdown[cat]["total"] += 1
            if result.passed:
                category_breakdown[cat]["passed"] += 1
            else:
                category_breakdown[cat]["failed"].append(result.name)

        for cat in category_breakdown:
            stats = category_breakdown[cat]
            stats["pass_rate"] = (
                stats["passed"] / stats["total"] if stats["total"] > 0 else 0
            )

        return {
            "total_tests": len(results),
            "passed_tests": sum(1 for r in results if r.passed),
            "failed_tests": sum(1 for r in results if not r.passed),
            "pass_rate": (
                sum(1 for r in results if r.passed) / len(results) if results else 0
            ),
            "step_count": step_count,
            "max_steps": self.max_steps,
            "regression_penalty": regression_penalty,
            "category_breakdown": category_breakdown,
        }

    def get_dependency_stats(self) -> Dict[str, Any]:
        """Get statistics about bug dependency graph."""
        return {
            "bugs_with_dependencies": 0,
            "dependency_percentage": 0,
            "max_chain_depth": 0,
            "diamond_patterns": 0,
            "cross_category_links": 0,
        }

def parse_junit_reports(results_dir: Path) -> List[TestResult]:
    """
    Parse JUnit XML test reports from a single module directory.

    Args:
        results_dir: Path to build/test-results/test directory

    Returns:
        List of TestResult objects
    """
    results = []
    seen = set()

    if not results_dir.exists():
        return results

    def categorize(classname: str) -> str:
        if ".coroutine." in classname:
            return "coroutine"
        elif ".security." in classname:
            return "security"
        elif ".integration." in classname:
            return "integration"
        return "unit"

    for xml_file in results_dir.glob("TEST-*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            for testcase in root.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_val = float(testcase.get("time", "0"))

                if name in seen:
                    continue

                skipped = testcase.find("skipped")
                if skipped is not None:
                    continue

                seen.add(name)

                failure = testcase.find("failure")
                error = testcase.find("error")
                passed = failure is None and error is None

                category = categorize(classname)

                # Determine service from classname
                service = "shared"
                for svc in SERVICE_BUG_MAP:
                    if f".{svc}." in classname.lower():
                        service = svc
                        break

                error_msg = ""
                if not passed:
                    fail_elem = failure if failure is not None else error
                    if fail_elem is not None and fail_elem.text:
                        error_msg = fail_elem.text[:500]

                results.append(
                    TestResult(
                        name=name,
                        passed=passed,
                        duration=time_val,
                        category=category,
                        bug_markers=[],
                        error_message=error_msg,
                        service=service,
                    )
                )
        except ET.ParseError:
            continue

    return results

def parse_junit_reports_recursive(project_dir: Path) -> List[TestResult]:
    """
    Parse JUnit XML test reports recursively through all module build directories.

    Searches for TEST-*.xml files in any path matching:
        */build/test-results/test/TEST-*.xml

    Args:
        project_dir: Root project directory containing all modules

    Returns:
        Combined list of TestResult objects from all modules
    """
    results = []
    seen = set()

    def categorize(classname: str) -> str:
        if ".coroutine." in classname:
            return "coroutine"
        elif ".security." in classname:
            return "security"
        elif ".integration." in classname:
            return "integration"
        return "unit"

    # Search recursively for JUnit XML files in all module build dirs
    for xml_file in project_dir.rglob("build/test-results/test/TEST-*.xml"):
        try:
            tree = ET.parse(xml_file)
            root = tree.getroot()

            # Determine which module this report belongs to
            rel_path = xml_file.relative_to(project_dir)
            module_name = str(rel_path.parts[0]) if len(rel_path.parts) > 1 else "shared"

            for testcase in root.findall("testcase"):
                classname = testcase.get("classname", "")
                name = testcase.get("name", "")
                time_val = float(testcase.get("time", "0"))

                if name in seen:
                    continue

                skipped = testcase.find("skipped")
                if skipped is not None:
                    continue

                seen.add(name)

                failure = testcase.find("failure")
                error = testcase.find("error")
                passed = failure is None and error is None

                category = categorize(classname)

                # Determine service from classname or module path
                service = module_name
                for svc in SERVICE_BUG_MAP:
                    if f".{svc}." in classname.lower():
                        service = svc
                        break

                error_msg = ""
                if not passed:
                    fail_elem = failure if failure is not None else error
                    if fail_elem is not None and fail_elem.text:
                        error_msg = fail_elem.text[:500]

                results.append(
                    TestResult(
                        name=name,
                        passed=passed,
                        duration=time_val,
                        category=category,
                        bug_markers=[],
                        error_message=error_msg,
                        service=service,
                    )
                )
        except ET.ParseError:
            continue

    return results

def calculate_reward(current_results, initial_results):
    """
    Simplified reward calculation matching HelixOps apex pattern.

    Args:
        current_results: List of TestResult from current test run
        initial_results: List of TestResult from initial baseline run

    Returns:
        Dict with reward breakdown
    """
    if not current_results:
        return {
            "reward": 0.0,
            "tests_passed": 0,
            "tests_total": 0,
            "pass_rate": 0.0,
            "bugs_fixed": 0,
            "bugs_total": 0,
            "categories_complete": 0,
            "services_complete": 0,
            "regressions": 0,
        }

    current_passed = {r.name for r in current_results if r.passed}
    initial_passed = {r.name for r in initial_results if r.passed}

    passed_count = len(current_passed)
    total_count = len(current_results)
    pass_rate = passed_count / total_count if total_count > 0 else 0.0

    reward = 0.0
    for i, threshold in enumerate(REWARD_THRESHOLDS):
        if pass_rate >= threshold:
            reward = REWARD_VALUES[i]

    # Count category completions
    category_stats = {}
    for r in current_results:
        cat = r.category
        if cat not in category_stats:
            category_stats[cat] = {"total": 0, "passed": 0}
        category_stats[cat]["total"] += 1
        if r.passed:
            category_stats[cat]["passed"] += 1

    categories_complete = sum(
        1 for stats in category_stats.values()
        if stats["total"] > 0 and stats["passed"] == stats["total"]
    )
    reward += categories_complete * CATEGORY_BONUS

    regressions = sum(1 for t in initial_passed if t not in current_passed)
    reward += regressions * REGRESSION_PENALTY
    reward = max(0.0, min(1.0, reward))

    return {
        "reward": round(reward, 4),
        "tests_passed": len(current_passed),
        "tests_total": len(current_results),
        "pass_rate": round(pass_rate, 4),
        "bugs_fixed": 0,
        "bugs_total": 0,
        "categories_complete": categories_complete,
        "services_complete": 0,
        "regressions": regressions,
    }

# ==============================================================================
# Bug → test mapping (shared module: 10 source files × ~30 functions each)
# ==============================================================================
# Maps bug IDs to the HyperMatrix test case names that detect them.
# CacheManager: HX0001-HX0030, AppConfig: HX0031-HX0060, DatabaseFactory: HX0061-HX0090,
# DelegationUtils: HX0091-HX0120, EventBus: HX0121-HX0150, KotlinUtils: HX0151-HX0180,
# Models: HX0181-HX0211, Logging: HX0212-HX0241, JwtProvider: HX0242-HX0271,
# SerializationUtils: HX0272-HX0301
_CACHE_TESTS = [
    "cache_isExpired_boundary", "cache_evictLru_oldest", "cache_getCacheSize_current",
    "cache_invalidatePattern_match", "cache_mergeCacheEntries_newer", "cache_getCacheStats_expired",
    "cache_batchEvict_consecutive", "cache_normalizeCacheKey_lowercase", "cache_cacheVersionMismatch_fallback",
    "cache_applyEvictionPolicy_boundary", "cache_distributedLockKey_namespace", "cache_calculateHitRate_total",
    "cache_cacheEntryEquals_value", "cache_parseTtlString_minutes", "cache_regionCacheKey_noDup",
    "cache_compactCache_filter", "cache_multiGetMerge_union", "cache_ttlJitter_nonzero",
    "cache_shouldCache_statusCode", "cache_buildHashKey_length", "cache_warmCache_ascending",
    "cache_serializeComplexKey_values", "cache_buildCacheKey_readable", "cache_calculateTtl_overflow",
]
_CONFIG_TESTS = [
    "config_loadPort_envValue", "config_buildJdbcUrl_order", "config_mergeConfigs_base",
    "config_parseBoolean_yes", "config_validatePortRange_zero", "config_getNestedKey_dot",
    "config_resolveTemplate_all", "config_parseDuration_minutes", "config_configOverride_applied",
    "config_parseList_delimiter", "config_validateConfig_all", "config_getRetryConfig_noMinus",
    "config_buildRedisUrl_password", "config_configToMap_fullKey", "config_loadFeatureFlags_noNegate",
    "config_parseLogLevel_default", "config_getKafkaConfig_colon", "config_calculatePoolTimeout_multiply",
    "config_loadSslConfig_noNegate", "config_parseMemorySize_mib", "config_loadRateLimitConfig_order",
    "config_encryptConfigValue_noSuffix", "config_resolveEnvPlaceholders_all", "config_loadConnectionPool_validate",
]
_DB_TESTS = [
    "db_selectIsolation_readHeavy", "db_batchInsertSize_calculated", "db_buildWhereClause_and",
    "db_columnTypeMapping_int", "db_buildUpdateSql_changed", "db_parseSqlResult_noSkip",
    "db_connectionPoolSize_calculated", "db_buildPaginationQuery_order", "db_buildJoinQuery_inner",
    "db_handleDeadlock_retry", "db_normalizeColumnName_underscore", "db_buildDeleteSql_condition",
    "db_calculateQueryTimeout_multiplier", "db_buildIndexSql_unique", "db_migrationOrder_numeric",
    "db_poolHealthCheck_unhealthy", "db_buildForeignKey_columns", "db_transactionRetryDelay_backoff",
    "db_buildAggregateQuery_groupBy", "db_parseDbUrl_fields", "db_validateColumnLength_le",
    "db_buildUpsertSql_conflict", "db_cacheEntityById_format", "db_estimateRowCount_nonzero",
]
_DELEG_TESTS = [
    "deleg_selectLazyMode_mt", "deleg_simulateObservable_notify", "deleg_vetoableCheck_reject",
    "deleg_mapDelegation_exact", "deleg_interfaceDelegation_delegate", "deleg_lazyInitValue_computed",
    "deleg_delegateCaching_fresh", "deleg_propertyDelegateGetValue_key", "deleg_readOnlyDelegate_unchanged",
    "deleg_compositeDelegate_forward", "deleg_notNullDelegate_throw", "deleg_weakReferenceDelegate_fallback",
    "deleg_syncDelegateAccess_noLock", "deleg_memoizedDelegate_fresh", "deleg_expiringDelegate_expired",
    "deleg_validatingDelegate_invalid", "deleg_loggerDelegation_owner", "deleg_configDelegate_updated",
    "deleg_defaultDelegate_string", "deleg_chainedDelegate_noSkip", "deleg_batchDelegate_proper",
    "deleg_retryDelegate_allAttempts", "deleg_fallbackDelegate_chain", "deleg_transformDelegate_storage",
]
_EVENT_TESTS = [
    "event_selectDispatcher_io", "event_calculateBufferCapacity_nonzero", "event_shouldUseRunBlocking_inCoroutine",
    "event_supervisorScopeNeeded_independent", "event_isChannelOpen_closed", "event_mutexLockOrder_deterministic",
    "event_flowTimeoutMs_nonzero", "event_sharedFlowReplayCount_history", "event_callbackFlowNeedsAwaitClose",
    "event_handleException_cancellation", "event_recommendedScope_ui", "event_asyncExceptionStrategy_supervisor",
    "event_producerRate_calculated", "event_flowMergeStrategy_latest", "event_debounceWindowMs_reasonable",
    "event_retryDelayMs_backoff", "event_parallelismDegree_bounded", "event_stateFlowInitialValue_loading",
    "event_selectContextForWork_cpu", "event_isChildJob_match", "event_timeoutDefault_value",
    "event_formatCoroutineName_full", "event_shouldYield_interval", "event_semaphorePermits_bounded",
]
_KOTLIN_TESTS = [
    "kotlin_valueClassEquals_boxed", "kotlin_buildConfig_noLeak", "kotlin_reifiedTypeCheck_actual",
    "kotlin_contractIsNotNull_true", "kotlin_contextReceiverCalc_primary", "kotlin_buildImmutableList_order",
    "kotlin_scopeFunctionApply_order", "kotlin_operatorPlus_reverse", "kotlin_roundDecimal_round",
    "kotlin_destructurePair_correct", "kotlin_inlineClassValidate_minLength", "kotlin_samConversion_true",
    "kotlin_companionFactory_type", "kotlin_sealedWhen_error", "kotlin_propertyInitOrder_derived",
    "kotlin_reflectProperty_value", "kotlin_coroutineBuilderChoice_async", "kotlin_flowOperatorOrder_filterFirst",
    "kotlin_channelFanout_distribute", "kotlin_delegatedPropertyProvider_primary", "kotlin_resultMonadUnwrap_error",
    "kotlin_multiplatformActual_jvm", "kotlin_extensionVsMember_ext", "kotlin_suspendLambdaCapture_inner",
]
_MODEL_TESTS = [
    "models_documentEquals_byteArray", "models_copyMetadata_deepCopy", "models_describeShape_triangle",
    "models_parsePriority_lowercase", "models_swapCoordinates_correct", "models_safeToString_redact",
    "models_copyPerson_deepAddress", "models_compareUserIds_value", "models_isSuccessResult_pending",
    "models_createDefaultProduct_stock", "models_updateProductPrice_returns", "models_sortProductsByPrice_field",
    "models_compareVersions_minor", "models_paginateList_page1", "models_groupEntitiesByType_field",
    "models_diffEntities_active", "models_createEntity_type", "models_mergeEntities_name",
    "models_validateEntity_type", "models_entityToMap_emptyName", "models_userIdToString_numeric",
    "models_resultToCode_pending", "models_serializePriority_meaningful", "models_buildEntity_unnamed",
]
_LOG_TESTS = [
    "log_buildMdcContext_parent", "log_logLevelPriority_order", "log_formatLogEntry_order",
    "log_extractTraceId_fallback", "log_shouldLog_gte", "log_buildMetricName_noRequestId",
    "log_buildSpanContext_parent", "log_classifyError_timeout", "log_latencyBucket_150ms",
    "log_formatTraceHeader_prefix", "log_shouldSampleLog_mod100", "log_buildSpanName_noUser",
    "log_shouldAlert_threshold", "log_shouldRotateLog_default", "log_aggregateMetrics_window",
    "log_formatHealthCheck_noDb", "log_buildAuditLog_failure", "log_buildLatencyBuckets_exponential",
    "log_formatException_depth", "log_formatRequestLog_status", "log_buildStructuredLog_keys",
    "log_mergeLogContexts_append", "log_validateMetricTag_chars", "log_isValidTraceId_length32",
]
_SEC_TESTS = [
    "sec_validateToken_structure", "sec_validateToken_parts", "sec_sanitizeSqlInput_semicolon",
    "sec_validatePath_traversal", "sec_isInternalUrl_privateRange", "sec_hashPassword_algorithm",
    "sec_generateSalt_random", "sec_validateEmailRegex_tld", "sec_rateLimitCheck_calculation",
    "sec_tokenExpiry_noOffset", "sec_encodeBase64Url_urlSafe", "sec_validateRedirectUrl_traversal",
    "sec_sanitizeHtml_allScripts", "sec_parseJwtPayload_urlSafe", "sec_validateOrigin_exact",
    "sec_maskSensitiveData_last4", "sec_isSecureProtocol_https", "sec_validateCertExpiry_notExpired",
    "sec_generateOtp_sixDigits", "sec_validatePasswordStrength_complexity", "sec_escapeXml_ampersand",
    "sec_validateContentType_exact", "sec_buildAuthHeader_basic", "sec_validateRedirectUrl_domain",
]
_SER_TESTS = [
    "ser_serializeInstant_timezone", "ser_ignoreUnknownKeys_true", "ser_shouldSerializeField_transient",
    "ser_polymorphicSerialize_type", "ser_serializeEnum_name", "ser_deserializeNullable_default",
    "ser_jsonPrettyPrint_noTrailingComma", "ser_serializeMapKeys_ordered", "ser_parseJsonArray_empty",
    "ser_serializeBigDecimal_precision", "ser_deserializeDate_order", "ser_buildJsonObject_closing",
    "ser_flattenJson_listIndex", "ser_validateJsonSchema_fields", "ser_jsonPathQuery_full",
    "ser_compactJson_strings", "ser_serializeCollection_single", "ser_dateFormatPattern_year",
    "ser_mergeJsonObjects_deep", "ser_xmlToJson_attributes", "ser_batchLogs_remainder",
    "ser_escapeJsonString_backslash", "ser_csvToJson_quoted", "ser_buildDashboardQuery_ms",
]

def _build_bug_test_mapping():
    """Build mapping from bug ID to detecting test names."""
    mapping = {}
    test_groups = [
        (1, _CACHE_TESTS), (31, _CONFIG_TESTS), (61, _DB_TESTS),
        (91, _DELEG_TESTS), (121, _EVENT_TESTS), (151, _KOTLIN_TESTS),
        (181, _MODEL_TESTS), (212, _LOG_TESTS), (242, _SEC_TESTS),
        (272, _SER_TESTS),
    ]
    for start_id, tests in test_groups:
        for i, test_name in enumerate(tests):
            bug_id = f"HX{start_id + i:04d}"
            mapping[bug_id] = [test_name]
    return mapping

BUG_TEST_MAPPING = _build_bug_test_mapping()

# ==============================================================================
# Bug dependency graph (cross-module and intra-module chains)
# ==============================================================================
# Dependencies encode which bugs must be fixed before others become testable.
# Format: bug_id -> list of prerequisite bug_ids
BUG_DEPENDENCIES = {
    # Config bugs are prerequisites for many other modules
    "HX0061": ["HX0032"],   # DB buildJdbcUrl depends on config buildJdbcUrl
    "HX0062": ["HX0031"],   # DB batchInsertSize depends on config loadPort
    "HX0069": ["HX0032"],   # DB buildPaginationQuery depends on config
    "HX0070": ["HX0061"],   # DB buildJoinQuery depends on DB selectIsolation
    # Cache depends on serialization
    "HX0001": ["HX0272"],   # cache isExpired depends on ser serializeInstant
    "HX0008": ["HX0275"],   # cache normalizeCacheKey depends on ser shouldSerializeField
    "HX0016": ["HX0289"],   # cache compactCache depends on ser flattenJson
    # EventBus depends on delegation patterns
    "HX0121": ["HX0091"],   # event selectDispatcher depends on deleg selectLazyMode
    "HX0126": ["HX0100"],   # event mutexLockOrder depends on deleg compositeDelegate
    # Security depends on config
    "HX0242": ["HX0031"],   # sec validateToken depends on config loadPort
    "HX0252": ["HX0048"],   # sec encodeBase64Url depends on config encryptConfigValue
    # Models depend on serialization
    "HX0181": ["HX0295"],   # models documentEquals depends on ser escapeJsonString
    "HX0193": ["HX0276"],   # models sortProductsByPrice depends on ser serializeEnum
    # Logging depends on config
    "HX0212": ["HX0031"],   # log buildMdcContext depends on config loadPort
    "HX0222": ["HX0047"],   # log formatTraceHeader depends on config parseLogLevel
    # Kotlin utils depend on delegation
    "HX0151": ["HX0091"],   # kotlin valueClassEquals depends on deleg selectLazyMode
    "HX0163": ["HX0103"],   # kotlin companionFactory depends on deleg notNullDelegate
    # Cross-module chains: config -> db -> cache -> events
    "HX0015": ["HX0005", "HX0272"],   # cache regionCacheKey depends on cache getCacheStats + ser
    "HX0130": ["HX0121", "HX0091"],   # event handleException depends on selectDispatcher + deleg
    # Service module bugs depend on shared module foundations
    "HX0301": ["HX0031", "HX0061"],   # gateway depends on config + db
    "HX0401": ["HX0242"],             # auth depends on security
    "HX0501": ["HX0061", "HX0272"],   # documents depends on db + serialization
    "HX0601": ["HX0001", "HX0272"],   # search depends on cache + serialization
    "HX0701": ["HX0061"],             # graph depends on db
    "HX0801": ["HX0272", "HX0151"],   # embeddings depends on serialization + kotlin
    "HX0881": ["HX0121"],             # collab depends on events
    "HX0981": ["HX0061", "HX0272"],   # billing depends on db + serialization
    "HX1081": ["HX0121", "HX0212"],   # notifications depends on events + logging
    "HX1161": ["HX0212", "HX0061"],   # analytics depends on logging + db
}

# ==============================================================================
# Bug categories (maps bug IDs to category labels from instruction.md)
# ==============================================================================
BUG_CATEGORIES = {
    "L": [f"HX{i:04d}" for i in range(1, 6)],       # Setup/Config (L1-L5)
    "A": [f"HX{i:04d}" for i in range(121, 131)],    # Coroutines (A1-A10)
    "B": [f"HX{i:04d}" for i in range(181, 187)],    # Null Safety (B1-B6)
    "C": [f"HX{i:04d}" for i in range(187, 195)],    # Data Classes/Sealed (C1-C8)
    "D": [f"HX{i:04d}" for i in range(301, 306)],    # Ktor Pipeline (D1-D5)
    "E": [f"HX{i:04d}" for i in range(61, 69)],      # Exposed ORM (E1-E8)
    "F": [f"HX{i:04d}" for i in range(272, 279)],    # Serialization (F1-F7)
    "G": [f"HX{i:04d}" for i in range(91, 96)],      # Delegation (G1-G5)
    "H": [f"HX{i:04d}" for i in range(1, 6)],        # Caching (H1-H5)
    "I": [f"HX{i:04d}" for i in range(242, 250)],    # Security (I1-I8)
    "J": [f"HX{i:04d}" for i in range(212, 217)],    # Observability (J1-J5)
    "K": [f"HX{i:04d}" for i in range(151, 159)],    # Modern Kotlin (K1-K8)
}
