"""
HeliosOps Reward Function
Terminal Bench v2 - Hyper-Principal Environment

Emergency Dispatch Operations Center - 149 bugs across 15 categories.
8-tier sparse reward with regression penalties and service bonuses.
"""
from typing import Dict, Any, Optional, List, Set
from dataclasses import dataclass, field

# ============================================================================
# Service Isolation - bonus for fully passing services
# ============================================================================

SERVICE_TEST_GROUPS = {
    "gateway": ["test_gateway_*"],
    "auth": ["test_auth_*", "test_jwt_*", "test_oauth_*", "test_token_*"],
    "dispatch": ["test_dispatch_*", "test_priority_*"],
    "routing": ["test_route_*", "test_distance_*", "test_haversine_*"],
    "incidents": ["test_incident_*", "test_merge_*", "test_escalation_*"],
    "resources": ["test_resource_*", "test_shift_*", "test_capacity_*"],
    "notifications": ["test_notification_*", "test_channel_*"],
    "analytics": ["test_metric_*", "test_response_time_*"],
    "compliance": ["test_audit_*", "test_sla_*", "test_compliance_*"],
    "audit_events": ["test_event_store_*", "test_replay_*"],
}

# ============================================================================
# Constants
# ============================================================================

TOTAL_TESTS = 350  # Approximate based on 2 tests per bug

# 8-tier hyper-principal thresholds
THRESHOLDS = [0.25, 0.40, 0.55, 0.70, 0.85, 0.95, 1.0]
REWARDS = [0.05, 0.12, 0.22, 0.38, 0.55, 0.78, 1.0]

# ============================================================================
# Reward Functions
# ============================================================================

def sparse_reward(pass_rate: float) -> float:
    """Calculate sparse reward from pass rate using threshold table."""
    reward = 0.0
    for threshold, reward_value in zip(THRESHOLDS, REWARDS):
        if pass_rate >= threshold:
            reward = reward_value
        else:
            break
    return reward

def total_tests() -> int:
    return TOTAL_TESTS

# Legacy stubs - kept for backward compatibility with setup.py imports
BUG_TEST_MAPPING = {}
BUG_DEPENDENCIES = {}

def total_bugs() -> int:
    """Legacy stub - returns 0 as bug tracking is removed."""
    return 0
