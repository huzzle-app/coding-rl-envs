"""
FleetPulse Reward Function
Principal difficulty: ~66 bugs, 510+ tests
Very sparse reward with regression penalties
"""
from typing import Any, Dict, List

# ==============================================================================
# Service to bug mapping (11 modules)
# ==============================================================================
SERVICE_BUG_MAP = {
    "shared": [
        "L4", "L5", "L6", "L7",  # Setup/Config bugs
        "L8",                      # Kafka config
        "C1", "C3", "C5",         # Concurrency (VirtualThreadExecutor)
        "C6",                      # Observability (MetricsCollector)
        "E2",                      # EventBus
        "E5", "E6", "E7",         # EventStore
        "I7", "I8",               # Security (JwtTokenProvider)
        "J2", "J3", "J4",         # Observability (MdcPropagator, MetricsCollector)
        "M1", "M2", "M3",         # CollectionUtils
        "M4",                      # EventRecord
    ],
    "gateway": [
        "I1", "I2", "I3",         # Security (GatewayController)
        "L2", "L3",               # RequestService
    ],
    "auth": [
        "C2",                      # Concurrency (AuthenticationService)
        "I4", "I5", "I6",         # Security (TokenValidator)
    ],
    "vehicles": [
        "B1",                      # Data Structures (Vehicle model)
        "D1",                      # Database (VehicleService)
    ],
    "routes": [
        "G2",                      # Arithmetic (RouteService)
        "GEOFENCE",                # Logic (GeofenceService)
        "INFINITE_LOOP",           # Logic (RouteService)
        "SUBLIST",                 # Collections (RouteService)
    ],
    "dispatch": [
        "A3", "A4", "A5",         # Concurrency (DispatchService)
        "L1",                      # Distributed Systems (DispatchService)
        "RECORD_ARRAY",            # Records (JobAssignment)
    ],
    "tracking": [
        "A6", "A7",               # Concurrency (TrackingService)
        "B3",                      # Collections (TrackingService)
        "F4", "F5",               # Arithmetic (TrackingService)
        "G3",                      # Arithmetic (TrackingService)
        "K2",                      # Type Safety (TrackingEventBase)
    ],
    "billing": [
        "D5",                      # Transactions (PaymentService)
        "E3", "E4",               # Resource Management (PaymentService)
        "F6", "F7", "F8",         # Arithmetic (InvoiceService)
    ],
    "analytics": [
        "B4", "B5",               # Memory/Performance (AnalyticsService)
        "G4",                      # Logic (AnalyticsService)
        "J1",                      # Observability (AnalyticsService)
        "K3",                      # Type Safety (AnalyticsService)
    ],
    "notifications": [
        "A8", "A9",               # Concurrency (NotificationService)
        "C4",                      # Caching (NotificationService)
        "H1", "H2",               # Caching (NotificationService)
    ],
    "compliance": [
        "F9", "F10",              # Arithmetic (ComplianceService)
        "G5", "G6",               # Race condition, timezone (ComplianceService)
        "K4",                      # Virtual thread pinning (ComplianceService)
    ],
}

# Bug dependency graph: bug_id -> list of prerequisite bug_ids
BUG_DEPENDENCIES = {
    # Setup bugs must be fixed first
    "C1": ["L4"],     # VirtualThreadExecutor needs AppConfig
    "E2": ["L4"],     # EventBus needs AppConfig
    "E5": ["L4"],     # EventStore needs AppConfig
    "D1": ["L4"],     # VehicleService needs AppConfig
    "C2": ["L4"],     # AuthService needs AppConfig

    # Kafka bugs depend on Kafka config
    "L8": ["L6"],     # Kafka topics need correct version

    # Concurrency chain
    "A5": ["A4"],     # ForkJoinPool deadlock depends on ConcurrentModification fix
    "A6": ["C1"],     # Parallel stream deadlock needs virtual thread fix
    "K4": ["C1"],     # Virtual thread pinning is same pattern as C1

    # Arithmetic chain
    "F7": ["F6"],     # Accumulator precision depends on division fix
    "F8": ["F7"],     # Geo truncation depends on accumulator fix
    "F10": ["F9"],    # Rate calculation depends on duration fix

    # Security chain
    "I4": ["I7"],     # JWT bypass needs XXE fix context
}

# Bug to test name mapping
BUG_TEST_MAPPING = {
    # Shared module
    "L7": ["test_kafka_auto_create", "test_kafka_topics_available"],
    "L8": ["test_kafka_auto_create", "test_kafka_topics_available"],
    "C1": ["test_virtual_thread_no_pinning"],
    "C3": ["test_atomic_sequence"],
    "C5": ["test_parallel_with_single_task"],
    "C6": ["test_log_level_case_insensitive", "test_info_equals_INFO"],
    "E7": ["test_event_version_ordering"],
    "I7": ["test_xxe_prevented"],
    "I8": ["test_api_key_constant_time"],
    "J2": ["test_mdc_in_thread", "test_context_preserved"],
    "J3": ["test_kafka_trace_header", "test_trace_in_message"],
    "M1": ["test_enum_set_used"],

    # Gateway
    "I1": ["test_sql_injection_blocked"],
    "I2": ["test_path_traversal_blocked"],
    "I3": ["test_ssrf_blocked"],
    "L2": ["test_threadlocal_cleanup"],
    "L3": ["test_transactional_proxy"],

    # Auth
    "C2": ["test_double_checked_locking_thread_safety"],
    "I4": ["test_jwt_none_algorithm_rejected"],
    "I5": ["test_password_constant_time_comparison"],
    "I6": ["test_safe_deserialization"],

    # Compliance
    "F9": ["test_remaining_hours_single_log", "test_remaining_hours_exact_integer"],
    "F10": ["test_rate_calculation_boundary", "test_rate_two_thirds", "test_rate_quarter",
            "test_rate_five_sixths", "test_rate_half", "test_rate_high_compliance",
            "test_rate_low_compliance"],
    "G5": ["test_book_driver_returns_false_when_unavailable"],
    "G6": ["test_eta_short_duration", "test_eta_end_of_year"],
    "K4": ["test_compliance_concurrent_access"],
}

# Principal reward thresholds (very sparse)
REWARD_THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARD_VALUES = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]
CATEGORY_BONUS = 0.01
SERVICE_BONUS = 0.01
REGRESSION_PENALTY = -0.03


def calculate_reward(current_results, initial_results):
    if not current_results:
        return {"reward": 0.0, "tests_passed": 0, "tests_total": 0, "pass_rate": 0.0,
                "bugs_fixed": 0, "bugs_total": len(_all_bugs()), "categories_complete": 0,
                "services_complete": 0, "regressions": 0}

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
        cat = getattr(r, 'category', 'unit')
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

    # Count service completions
    service_stats = {}
    for r in current_results:
        svc = getattr(r, 'service', 'shared')
        if svc not in service_stats:
            service_stats[svc] = {"total": 0, "passed": 0}
        service_stats[svc]["total"] += 1
        if r.passed:
            service_stats[svc]["passed"] += 1

    services_complete = sum(
        1 for stats in service_stats.values()
        if stats["total"] > 0 and stats["passed"] == stats["total"]
    )
    reward += services_complete * SERVICE_BONUS

    # Count bugs fixed
    bugs_fixed = 0
    for bug_id, test_names in BUG_TEST_MAPPING.items():
        if all(t in current_passed for t in test_names):
            bugs_fixed += 1

    regressions = sum(1 for t in initial_passed if t not in current_passed)
    reward += regressions * REGRESSION_PENALTY
    reward = max(0.0, min(1.0, reward))

    return {
        "reward": round(reward, 4), "tests_passed": len(current_passed),
        "tests_total": len(current_results), "pass_rate": round(pass_rate, 4),
        "bugs_fixed": bugs_fixed, "bugs_total": len(_all_bugs()),
        "categories_complete": categories_complete,
        "services_complete": services_complete, "regressions": regressions,
    }


def _all_bugs():
    """Return flat list of all bug IDs across all services."""
    bugs = []
    for service_bugs in SERVICE_BUG_MAP.values():
        bugs.extend(service_bugs)
    return bugs
