"""
VertexGrid Reward Function
Apex-principal profile with deep dependency penalties
"""
from typing import Any, Dict, List

# ==============================================================================
# Service to bug mapping (11 modules)
# ==============================================================================
SERVICE_BUG_MAP = {
    "gateway": [],
    "auth": [],
    "vehicles": [],
    "routes": [],
    "dispatch": [],
    "tracking": [],
    "billing": [],
    "analytics": [],
    "notifications": [],
    "compliance": [],
    "shared": [],
}

# Apex-principal reward thresholds (ultra sparse)
REWARD_THRESHOLDS = [0.10, 0.22, 0.36, 0.52, 0.67, 0.80, 0.90, 0.96, 0.99, 1.0]
REWARD_VALUES = [0.0, 0.015, 0.05, 0.11, 0.19, 0.31, 0.47, 0.66, 0.85, 1.0]
CATEGORY_BONUS = 0.01
SERVICE_BONUS = 0.01
REGRESSION_PENALTY = -0.03

def calculate_reward(current_results, initial_results):
    if not current_results:
        return {"reward": 0.0, "tests_passed": 0, "tests_total": 0, "pass_rate": 0.0,
                "bugs_fixed": 0, "bugs_total": 0, "categories_complete": 0,
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

    regressions = sum(1 for t in initial_passed if t not in current_passed)
    reward += regressions * REGRESSION_PENALTY
    reward = max(0.0, min(1.0, reward))

    return {
        "reward": round(reward, 4), "tests_passed": len(current_passed),
        "tests_total": len(current_results), "pass_rate": round(pass_rate, 4),
        "bugs_fixed": 0, "bugs_total": 0,
        "categories_complete": categories_complete,
        "services_complete": 0, "regressions": regressions,
    }

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
