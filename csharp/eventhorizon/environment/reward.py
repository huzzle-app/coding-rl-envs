"""
EventHorizon Reward Function
Principal difficulty: sparse reward based on pass rate
"""
from typing import Any, Dict, List

REWARD_THRESHOLDS = [0.10, 0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARD_VALUES = [0.0, 0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]

def calculate_reward(current_results, initial_results):
    if not current_results:
        return {"reward": 0.0, "tests_passed": 0, "tests_total": 0, "pass_rate": 0.0}

    current_passed = {r.name for r in current_results if r.passed}
    tests_total = len(current_results)
    tests_passed = len(current_passed)

    pass_rate = tests_passed / tests_total if tests_total > 0 else 0.0

    reward = 0.0
    for i, threshold in enumerate(REWARD_THRESHOLDS):
        if pass_rate >= threshold:
            reward = REWARD_VALUES[i]

    reward = max(0.0, min(1.0, reward))

    return {
        "reward": round(reward, 4),
        "tests_passed": tests_passed,
        "tests_total": tests_total,
        "pass_rate": round(pass_rate, 4),
    }

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}
