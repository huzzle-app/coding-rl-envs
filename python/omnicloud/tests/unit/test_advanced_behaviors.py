"""
OmniCloud Advanced Behavior Tests
Terminal Bench v2 - Tests for complex infrastructure behaviors.

Tests cover: state management edge cases, distributed systems correctness,
network calculations, billing accuracy, deployment lifecycle, scheduling
invariants, tenant isolation, load balancing, monitoring accuracy,
configuration management, event processing, and connection management.
"""
import pytest
import time
import uuid
import threading
import copy
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List


# =============================================================================
# State Management - Batch Operations & Cloning
# =============================================================================


class TestBatchStateTransitions:
    """Batch state transitions should be atomic."""

    def test_batch_transition_all_succeed(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        r1 = Resource(resource_id="r1", resource_type="compute")
        r2 = Resource(resource_id="r2", resource_type="compute")
        sm.add_resource(r1)
        sm.add_resource(r2)
        sm.transition_state("r1", ResourceState.CREATING)
        sm.transition_state("r1", ResourceState.ACTIVE)
        sm.transition_state("r2", ResourceState.CREATING)
        sm.transition_state("r2", ResourceState.ACTIVE)

        results = sm.batch_transition([
            ("r1", ResourceState.UPDATING),
            ("r2", ResourceState.UPDATING),
        ])
        assert results["r1"] is True
        assert results["r2"] is True

    def test_batch_transition_partial_failure_rolls_back(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        r1 = Resource(resource_id="r1", resource_type="compute")
        r2 = Resource(resource_id="r2", resource_type="compute")
        sm.add_resource(r1)
        sm.add_resource(r2)
        sm.transition_state("r1", ResourceState.CREATING)
        sm.transition_state("r1", ResourceState.ACTIVE)
        # r2 stays PENDING - can't transition to UPDATING

        results = sm.batch_transition([
            ("r1", ResourceState.UPDATING),
            ("r2", ResourceState.UPDATING),  # Invalid from PENDING
        ])
        # r2 should fail
        assert results["r2"] is False
        # r1 should be rolled back to ACTIVE since batch is atomic
        assert sm.resources["r1"].state == ResourceState.ACTIVE, \
            "Failed batch should roll back all transitions"

    def test_batch_transition_empty_list(self):
        from shared.infra.state import StateManager
        sm = StateManager()
        results = sm.batch_transition([])
        assert results == {}


class TestStateMerge:
    """Merging state managers should produce independent copies."""

    def test_merge_states_copies_resources(self):
        from shared.infra.state import StateManager, Resource
        sm1 = StateManager()
        sm2 = StateManager()
        r = Resource(resource_id="r1", resource_type="compute", desired_config={"cpu": 4})
        sm2.add_resource(r)

        merged = sm1.merge_states(sm2)
        assert merged == 1
        assert "r1" in sm1.resources

    def test_merge_states_independent_mutation(self):
        from shared.infra.state import StateManager, Resource
        sm1 = StateManager()
        sm2 = StateManager()
        r = Resource(resource_id="r1", resource_type="compute", desired_config={"cpu": 4})
        sm2.add_resource(r)

        sm1.merge_states(sm2)
        # Modify resource in sm1
        sm1.resources["r1"].desired_config["cpu"] = 8

        # sm2's resource should be unchanged (deep copy)
        assert sm2.resources["r1"].desired_config["cpu"] == 4, \
            "Merged resources should be independent copies"

    def test_merge_higher_version_wins(self):
        from shared.infra.state import StateManager, Resource
        sm1 = StateManager()
        sm2 = StateManager()
        r1 = Resource(resource_id="r1", resource_type="compute", version=5, desired_config={"cpu": 2})
        r2 = Resource(resource_id="r1", resource_type="compute", version=10, desired_config={"cpu": 8})
        sm1.add_resource(r1)
        sm2.add_resource(r2)

        sm1.merge_states(sm2)
        assert sm1.resources["r1"].desired_config["cpu"] == 8


class TestResourcesByState:
    """Filtering resources by state should respect tenant isolation."""

    def test_get_resources_by_state_with_tenant_filter(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        r1 = Resource(resource_id="r1", resource_type="compute", tenant_id="t1")
        r2 = Resource(resource_id="r2", resource_type="compute", tenant_id="t2")
        sm.add_resource(r1)
        sm.add_resource(r2)

        results = sm.get_resources_by_state(ResourceState.PENDING, tenant_id="t1")
        tenant_ids = {r.tenant_id for r in results}
        assert "t2" not in tenant_ids, \
            "Tenant filter should exclude other tenants' resources"

    def test_get_resources_by_state_no_filter(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        sm.add_resource(Resource(resource_id="r1", resource_type="compute", tenant_id="t1"))
        sm.add_resource(Resource(resource_id="r2", resource_type="compute", tenant_id="t2"))

        results = sm.get_resources_by_state(ResourceState.PENDING)
        assert len(results) == 2


class TestTransitionWithPrecondition:
    """Preconditions should be checked before state transition takes effect."""

    def test_precondition_checked_before_transition(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        r = Resource(resource_id="r1", resource_type="compute",
                     desired_config={"cpu": 2})
        sm.add_resource(r)
        sm.transition_state("r1", ResourceState.CREATING)
        sm.transition_state("r1", ResourceState.ACTIVE)

        # Precondition requires cpu=4, but actual is cpu=2
        result = sm.transition_with_precondition(
            "r1", ResourceState.UPDATING, precondition={"cpu": 4}
        )
        assert result is False, "Precondition failure should prevent transition"
        # State should NOT have changed
        assert sm.resources["r1"].state == ResourceState.ACTIVE, \
            "Failed precondition should leave state unchanged"

    def test_precondition_passes(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        r = Resource(resource_id="r1", resource_type="compute",
                     desired_config={"cpu": 4})
        sm.add_resource(r)
        sm.transition_state("r1", ResourceState.CREATING)
        sm.transition_state("r1", ResourceState.ACTIVE)

        result = sm.transition_with_precondition(
            "r1", ResourceState.UPDATING, precondition={"cpu": 4}
        )
        assert result is True


class TestResourceCloning:
    """Cloned resources should be fully independent."""

    def test_clone_independence(self):
        from shared.infra.state import StateManager, Resource, ResourceState
        sm = StateManager()
        original = Resource(
            resource_id="r1", resource_type="compute",
            desired_config={"cpu": 4, "tags": ["web"]},
            actual_config={"cpu": 4, "tags": ["web"]},
            dependencies=["dep1"],
        )
        sm.add_resource(original)

        clone_id = sm.clone_resource("r1")
        assert clone_id is not None

        # Modify clone's config
        sm.resources[clone_id].desired_config["cpu"] = 8
        sm.resources[clone_id].desired_config["tags"].append("api")

        # Original should be unchanged
        assert sm.resources["r1"].desired_config["cpu"] == 4, \
            "Cloned resource config changes should not affect original"
        assert sm.resources["r1"].desired_config["tags"] == ["web"], \
            "Cloned resource nested config should be independent"

    def test_clone_dependencies_independent(self):
        from shared.infra.state import StateManager, Resource
        sm = StateManager()
        original = Resource(resource_id="r1", resource_type="compute",
                           dependencies=["dep1"])
        sm.add_resource(original)

        clone_id = sm.clone_resource("r1")
        sm.resources[clone_id].dependencies.append("dep2")

        assert "dep2" not in sm.resources["r1"].dependencies, \
            "Cloned resource dependency changes should not affect original"


# =============================================================================
# Distributed Systems - Rate Limiting, Hashing, Counters
# =============================================================================


class TestTokenBucketRateLimiter:
    """Token bucket should refill at a constant rate, not instantly."""

    def test_rate_limiter_gradual_refill(self):
        from shared.utils.distributed import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(max_tokens=10, refill_rate=1.0)
        # Drain all tokens
        for _ in range(10):
            limiter.try_acquire()
        assert limiter.current_tokens == 0

        # Wait briefly and try again
        time.sleep(0.1)
        result = limiter.try_acquire()
        # With rate=1.0 token/sec and 0.1s elapsed, should have ~0.1 tokens
        # Should NOT have all 10 tokens back
        assert limiter.current_tokens < 5, \
            f"Rate limiter should refill gradually, not to max. Got {limiter.current_tokens}"

    def test_rate_limiter_allows_burst(self):
        from shared.utils.distributed import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(max_tokens=10, refill_rate=1.0)
        # Should allow initial burst up to max
        for i in range(10):
            assert limiter.try_acquire() is True
        assert limiter.try_acquire() is False

    def test_rate_limiter_respects_max(self):
        from shared.utils.distributed import TokenBucketRateLimiter
        limiter = TokenBucketRateLimiter(max_tokens=5, refill_rate=100.0)
        time.sleep(0.1)
        limiter._refill()
        assert limiter.current_tokens <= 5, "Tokens should never exceed max"


class TestConsistentHashRing:
    """Consistent hash ring should handle node removal correctly."""

    def test_hash_ring_node_removal(self):
        from shared.utils.distributed import ConsistentHashRing
        ring = ConsistentHashRing(nodes=["node-a", "node-b", "node-c"])

        # Record assignments before removal
        assignments_before = {}
        keys = [f"key-{i}" for i in range(100)]
        for key in keys:
            assignments_before[key] = ring.get_node(key)

        # Remove a node
        ring.remove_node("node-b")

        # After removal, keys should only route to remaining nodes
        for key in keys:
            assigned = ring.get_node(key)
            assert assigned in ["node-a", "node-c"], \
                f"Key {key} routed to removed node {assigned}"

    def test_hash_ring_distribution(self):
        from shared.utils.distributed import ConsistentHashRing
        ring = ConsistentHashRing(nodes=["a", "b", "c"])
        counts = {"a": 0, "b": 0, "c": 0}
        for i in range(1000):
            node = ring.get_node(f"key-{i}")
            counts[node] += 1
        # Each node should get at least 10% of keys
        for node, count in counts.items():
            assert count >= 100, f"Node {node} only got {count}/1000 keys"

    def test_hash_ring_empty(self):
        from shared.utils.distributed import ConsistentHashRing
        ring = ConsistentHashRing(nodes=[])
        assert ring.get_node("any-key") is None


class TestDistributedCounter:
    """Distributed counter total should be the sum across all nodes."""

    def test_counter_total_is_sum(self):
        from shared.utils.distributed import DistributedCounter
        counter = DistributedCounter()
        counter.increment("node-a", 10)
        counter.increment("node-b", 20)
        counter.increment("node-c", 30)
        assert counter.total() == 60, \
            f"Total should be sum of all nodes (60), got {counter.total()}"

    def test_counter_merge(self):
        from shared.utils.distributed import DistributedCounter
        c1 = DistributedCounter()
        c2 = DistributedCounter()
        c1.increment("node-a", 5)
        c1.increment("node-b", 10)
        c2.increment("node-a", 8)
        c2.increment("node-c", 3)

        merged = c1.merge(c2)
        assert merged.node_counts["node-a"] == 8  # max(5, 8)
        assert merged.node_counts["node-b"] == 10  # from c1
        assert merged.node_counts["node-c"] == 3   # from c2
        assert merged.total() == 21  # 8 + 10 + 3

    def test_counter_single_node(self):
        from shared.utils.distributed import DistributedCounter
        counter = DistributedCounter()
        counter.increment("node-a", 42)
        assert counter.total() == 42


class TestVersionVectorDominance:
    """Version vector dominance should be strict (not equal)."""

    def test_dominates_strict(self):
        from shared.utils.distributed import VersionVector
        vv1 = VersionVector(versions={"a": 2, "b": 3})
        vv2 = VersionVector(versions={"a": 1, "b": 2})
        assert vv1.dominates(vv2) is True

    def test_equal_does_not_dominate(self):
        from shared.utils.distributed import VersionVector
        vv1 = VersionVector(versions={"a": 2, "b": 3})
        vv2 = VersionVector(versions={"a": 2, "b": 3})
        assert vv1.dominates(vv2) is False, \
            "Equal version vectors should not dominate each other"

    def test_concurrent_does_not_dominate(self):
        from shared.utils.distributed import VersionVector
        vv1 = VersionVector(versions={"a": 2, "b": 1})
        vv2 = VersionVector(versions={"a": 1, "b": 2})
        assert vv1.dominates(vv2) is False
        assert vv2.dominates(vv1) is False


class TestReadWriteLock:
    """Read-write lock upgrade should be safe from data races."""

    def test_rwlock_multiple_readers(self):
        from shared.utils.distributed import ReadWriteLock
        rwl = ReadWriteLock()
        assert rwl.acquire_read(timeout=1.0) is True
        assert rwl.acquire_read(timeout=1.0) is True
        rwl.release_read()
        rwl.release_read()

    def test_rwlock_writer_excludes_readers(self):
        from shared.utils.distributed import ReadWriteLock
        rwl = ReadWriteLock()
        assert rwl.acquire_write(timeout=1.0) is True
        # Reader should not be able to acquire while writer holds
        result = rwl.acquire_read(timeout=0.1)
        assert result is False, "Reader should not acquire while writer holds lock"
        rwl.release_write()

    def test_rwlock_upgrade_atomicity(self):
        from shared.utils.distributed import ReadWriteLock
        rwl = ReadWriteLock()
        # Acquire read lock
        rwl.acquire_read(timeout=1.0)

        # Track if another writer sneaks in during upgrade
        intruder_acquired = [False]

        def intruder():
            time.sleep(0.01)  # Small delay to let upgrade start
            if rwl.acquire_write(timeout=0.2):
                intruder_acquired[0] = True
                rwl.release_write()

        t = threading.Thread(target=intruder)
        t.start()
        # Try to upgrade
        upgraded = rwl.try_upgrade_to_write(timeout=0.5)
        if upgraded:
            # If we got the write lock, intruder should NOT have gotten it
            time.sleep(0.05)
            rwl.release_write()
        else:
            rwl.release_read()
        t.join()

        if upgraded:
            assert intruder_acquired[0] is False, \
                "Upgrade should be atomic - no other writer should acquire during upgrade"


# =============================================================================
# Network - IP Calculations & Firewall Merging
# =============================================================================


class TestUsableIPCalculation:
    """Usable IP count should account for all reserved addresses."""

    def test_usable_ips_24(self):
        from services.network.views import calculate_usable_ips
        # /24 = 256 total. Cloud VPCs reserve 5 addresses.
        usable = calculate_usable_ips("10.0.0.0/24")
        assert usable == 251, \
            f"/24 should have 251 usable IPs (256 - 5 reserved), got {usable}"

    def test_usable_ips_28(self):
        from services.network.views import calculate_usable_ips
        # /28 = 16 total - 5 reserved = 11 usable
        usable = calculate_usable_ips("10.0.0.0/28")
        assert usable == 11, \
            f"/28 should have 11 usable IPs, got {usable}"

    def test_usable_ips_31(self):
        from services.network.views import calculate_usable_ips
        # /31 = 2 total, point-to-point link, 0 usable in VPC context
        usable = calculate_usable_ips("10.0.0.0/31")
        assert usable == 0, f"/31 should have 0 usable IPs, got {usable}"


class TestCIDRContainment:
    """CIDR containment check should verify the entire range, not just first IP."""

    def test_contained_cidr(self):
        from services.network.views import validate_cidr_containment
        assert validate_cidr_containment("10.0.0.0/8", "10.0.1.0/24") is True

    def test_not_contained_cidr(self):
        from services.network.views import validate_cidr_containment
        # 10.0.0.0/24 (10.0.0.0-10.0.0.255) does NOT contain 10.0.1.0/24
        assert validate_cidr_containment("10.0.0.0/24", "10.0.1.0/24") is False, \
            "10.0.1.0/24 is not within 10.0.0.0/24"

    def test_partial_overlap_not_contained(self):
        from services.network.views import validate_cidr_containment
        # 10.0.0.0/25 (10.0.0.0-10.0.0.127) should NOT contain 10.0.0.64/25
        # because 10.0.0.64/25 = 10.0.0.64-10.0.0.191 which extends past .127
        result = validate_cidr_containment("10.0.0.0/25", "10.0.0.64/25")
        # The child starts at 10.0.0.64 which IS in parent range,
        # but the child extends to 10.0.0.191 which is NOT in parent
        assert result is False, \
            "Partial overlap should not count as containment"


class TestFirewallRulesetMerge:
    """When merging firewall rulesets, deny rules should override allow rules."""

    def test_merge_deny_overrides_allow(self):
        from services.network.views import merge_firewall_rulesets
        ruleset_a = [
            {"protocol": "tcp", "port": 80, "action": "allow"},
        ]
        ruleset_b = [
            {"protocol": "tcp", "port": 80, "action": "deny"},
        ]
        merged = merge_firewall_rulesets(ruleset_a, ruleset_b)
        port_80_rules = [r for r in merged if r.get("port") == 80]
        assert len(port_80_rules) == 1
        assert port_80_rules[0]["action"] == "deny", \
            "Deny rules should take precedence when merging rulesets"

    def test_merge_non_conflicting(self):
        from services.network.views import merge_firewall_rulesets
        a = [{"protocol": "tcp", "port": 80, "action": "allow"}]
        b = [{"protocol": "tcp", "port": 443, "action": "allow"}]
        merged = merge_firewall_rulesets(a, b)
        assert len(merged) == 2

    def test_merge_empty(self):
        from services.network.views import merge_firewall_rulesets
        assert merge_firewall_rulesets([], []) == []


class TestSubnetUtilization:
    """Subnet utilization should account for reserved addresses."""

    def test_utilization_with_reserved(self):
        from services.network.views import calculate_subnet_utilization
        # 50 allocated, 256 total, 5 reserved = 50/(256-5) = 19.9%
        util = calculate_subnet_utilization(50, 256, reserved=5)
        expected = (50 / (256 - 5)) * 100.0
        assert abs(util - expected) < 0.1, \
            f"Utilization should account for reserved IPs. Expected ~{expected:.1f}%, got {util:.1f}%"


# =============================================================================
# Billing - Late Penalties, Usage Aggregation, Tiered Pricing
# =============================================================================


class TestLatePenalty:
    """Late payment penalty should be simple interest, not compound."""

    def test_late_penalty_simple_interest(self):
        from services.billing.views import calculate_late_penalty
        # $100 outstanding, 10 days late, 1% daily
        # Simple interest: 100 * 0.01 * 10 = $10.00
        penalty = calculate_late_penalty(
            Decimal("100.00"), days_late=10, daily_rate=Decimal("0.01")
        )
        assert penalty == Decimal("10.00"), \
            f"Late penalty should be simple interest ($10.00), got ${penalty}"

    def test_late_penalty_zero_days(self):
        from services.billing.views import calculate_late_penalty
        penalty = calculate_late_penalty(Decimal("100.00"), days_late=0)
        assert penalty == Decimal("0.00")

    def test_late_penalty_one_day(self):
        from services.billing.views import calculate_late_penalty
        penalty = calculate_late_penalty(
            Decimal("1000.00"), days_late=1, daily_rate=Decimal("0.01")
        )
        assert penalty == Decimal("10.00")


class TestUsageAggregation:
    """Usage aggregation should respect tenant timezone for billing."""

    def test_hourly_aggregation_with_timezone(self):
        from services.billing.views import aggregate_hourly_usage
        # Create records at 23:30 UTC. For UTC+1 tenant, this is 00:30 next day.
        base_ts = datetime(2024, 1, 15, 23, 30, tzinfo=timezone.utc).timestamp()
        records = [
            {"timestamp": base_ts, "amount": 10.0},
            {"timestamp": base_ts + 1800, "amount": 5.0},  # 00:00 UTC = 01:00 UTC+1
        ]

        buckets = aggregate_hourly_usage(records, timezone_offset_hours=1)
        # With UTC+1, the first record at 23:30 UTC is 00:30 local (Jan 16)
        # The second record at 00:00 UTC is 01:00 local (Jan 16)
        # They should be in DIFFERENT hourly buckets in local time
        assert len(buckets) >= 2 or sum(buckets.values()) == Decimal("15.0")


class TestUsageReconciliation:
    """Usage reconciliation should deduplicate events by event_id."""

    def test_reconcile_deduplicates_events(self):
        from services.billing.views import reconcile_usage_events
        events = [
            {"event_id": "e1", "resource_id": "r1", "amount": 10.0},
            {"event_id": "e1", "resource_id": "r1", "amount": 10.0},  # Duplicate
            {"event_id": "e2", "resource_id": "r1", "amount": 5.0},
        ]
        totals = reconcile_usage_events(events)
        assert totals["r1"] == Decimal("15.0"), \
            f"Duplicate events should be ignored. Expected 15.0, got {totals['r1']}"

    def test_reconcile_multiple_resources(self):
        from services.billing.views import reconcile_usage_events
        events = [
            {"event_id": "e1", "resource_id": "r1", "amount": 10.0},
            {"event_id": "e2", "resource_id": "r2", "amount": 20.0},
        ]
        totals = reconcile_usage_events(events)
        assert totals["r1"] == Decimal("10.0")
        assert totals["r2"] == Decimal("20.0")


class TestTieredPricing:
    """Tiered pricing should charge at the correct rate for each tier."""

    def test_tiered_pricing_basic(self):
        from services.billing.views import calculate_tiered_pricing
        tiers = [
            {"up_to": 100, "price_per_unit": 0.10},
            {"up_to": 100, "price_per_unit": 0.08},
            {"up_to": 100, "price_per_unit": 0.05},
        ]
        # 250 units: first 100 @ $0.10 = $10, next 100 @ $0.08 = $8, last 50 @ $0.05 = $2.50
        cost = calculate_tiered_pricing(Decimal("250"), tiers)
        expected = Decimal("10.00") + Decimal("8.00") + Decimal("2.50")
        assert cost == expected, f"Expected ${expected}, got ${cost}"

    def test_tiered_pricing_first_tier_only(self):
        from services.billing.views import calculate_tiered_pricing
        tiers = [
            {"up_to": 100, "price_per_unit": 0.10},
            {"up_to": 100, "price_per_unit": 0.08},
        ]
        cost = calculate_tiered_pricing(Decimal("50"), tiers)
        assert cost == Decimal("5.00")

    def test_tiered_pricing_zero_usage(self):
        from services.billing.views import calculate_tiered_pricing
        tiers = [{"up_to": 100, "price_per_unit": 0.10}]
        cost = calculate_tiered_pricing(Decimal("0"), tiers)
        assert cost == Decimal("0")


# =============================================================================
# Deployment - State Machine, Canary, Config Merge
# =============================================================================


class TestDeploymentStateMachine:
    """Deployment state machine should prevent illegal transitions."""

    def test_completed_cannot_go_to_in_progress(self):
        from services.deploy.tasks import (
            Deployment, DeploymentState, deployment_transition,
        )
        d = Deployment(state=DeploymentState.COMPLETED)
        result = deployment_transition(d, DeploymentState.IN_PROGRESS)
        assert result is False, \
            "Completed deployments should not transition back to IN_PROGRESS"

    def test_queued_cannot_skip_to_completed(self):
        from services.deploy.tasks import (
            Deployment, DeploymentState, deployment_transition,
        )
        d = Deployment(state=DeploymentState.QUEUED)
        result = deployment_transition(d, DeploymentState.COMPLETED)
        assert result is False, \
            "Deployments should not skip from QUEUED to COMPLETED"

    def test_normal_lifecycle(self):
        from services.deploy.tasks import (
            Deployment, DeploymentState, deployment_transition,
        )
        d = Deployment(state=DeploymentState.QUEUED)
        assert deployment_transition(d, DeploymentState.IN_PROGRESS) is True
        assert deployment_transition(d, DeploymentState.COMPLETED) is True


class TestCanaryInstances:
    """Canary deployment must always have at least 1 instance."""

    def test_canary_minimum_one_instance(self):
        from services.deploy.tasks import calculate_canary_instances
        # 3 replicas, 10% = 0.3 -> should round up to 1
        instances = calculate_canary_instances(3, 10)
        assert instances >= 1, \
            f"Canary must have at least 1 instance, got {instances}"

    def test_canary_percentage_zero(self):
        from services.deploy.tasks import calculate_canary_instances
        instances = calculate_canary_instances(10, 0)
        assert instances == 0

    def test_canary_large_fleet(self):
        from services.deploy.tasks import calculate_canary_instances
        instances = calculate_canary_instances(100, 10)
        assert instances == 10


class TestDeploymentConfigMerge:
    """Deployment config merge should deep-merge nested dictionaries."""

    def test_deep_merge_nested_dicts(self):
        from services.deploy.tasks import merge_deployment_configs
        base = {
            "resources": {"cpu": 2, "memory": "4Gi"},
            "replicas": 3,
        }
        override = {
            "resources": {"cpu": 4},  # Should only override cpu, keep memory
        }
        merged = merge_deployment_configs(base, override)
        assert merged["resources"]["cpu"] == 4
        assert merged["resources"].get("memory") == "4Gi", \
            "Deep merge should preserve unoverridden nested values"

    def test_merge_top_level(self):
        from services.deploy.tasks import merge_deployment_configs
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        merged = merge_deployment_configs(base, override)
        assert merged == {"a": 1, "b": 3, "c": 4}


class TestDeploymentWindow:
    """Deployment window validation including midnight wraparound."""

    def test_within_window(self):
        from services.deploy.tasks import validate_deployment_window
        dt = datetime(2024, 1, 15, 3, 0, tzinfo=timezone.utc)
        windows = [{"start_hour": 2, "end_hour": 6}]
        assert validate_deployment_window(dt, windows) is True

    def test_outside_window(self):
        from services.deploy.tasks import validate_deployment_window
        dt = datetime(2024, 1, 15, 12, 0, tzinfo=timezone.utc)
        windows = [{"start_hour": 2, "end_hour": 6}]
        assert validate_deployment_window(dt, windows) is False

    def test_midnight_wrap_window(self):
        from services.deploy.tasks import validate_deployment_window
        # Window from 22:00 to 06:00
        dt = datetime(2024, 1, 15, 2, 0, tzinfo=timezone.utc)
        windows = [{"start_hour": 22, "end_hour": 6}]
        assert validate_deployment_window(dt, windows) is True

    def test_at_window_boundary(self):
        from services.deploy.tasks import validate_deployment_window
        dt = datetime(2024, 1, 15, 6, 0, tzinfo=timezone.utc)
        windows = [{"start_hour": 2, "end_hour": 6}]
        assert validate_deployment_window(dt, windows) is True


# =============================================================================
# Compute - Rebalancing, Batch Scheduling, Fragmentation
# =============================================================================


class TestNodeRebalancing:
    """Rebalancing should update both source and target node resources."""

    def test_rebalance_updates_both_nodes(self):
        from services.compute.main import ComputeNode, Scheduler, rebalance_nodes
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", total_cpu=8.0, used_cpu=6.0,
            total_memory_gb=32.0, used_memory_gb=24.0,
        )
        scheduler.nodes["n2"] = ComputeNode(
            node_id="n2", total_cpu=8.0, used_cpu=2.0,
            total_memory_gb=32.0, used_memory_gb=8.0,
        )

        result = rebalance_nodes(scheduler, "n1", "n2", cpu_to_move=2.0, memory_to_move=8.0)
        assert result is True
        # Source should have reduced usage
        assert scheduler.nodes["n1"].used_cpu == 4.0, \
            f"Source CPU should decrease. Expected 4.0, got {scheduler.nodes['n1'].used_cpu}"
        # Target should have increased usage
        assert scheduler.nodes["n2"].used_cpu == 4.0


class TestBatchScheduling:
    """Batch scheduling should be all-or-nothing."""

    def test_batch_schedule_all_or_nothing(self):
        from services.compute.main import ComputeNode, Scheduler, try_schedule_batch
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", total_cpu=4.0, total_memory_gb=16.0,
        )

        workloads = [
            {"tenant_id": "t1", "cpu": 2.0, "memory_gb": 4.0},
            {"tenant_id": "t1", "cpu": 2.0, "memory_gb": 4.0},
            {"tenant_id": "t1", "cpu": 2.0, "memory_gb": 4.0},  # Exceeds capacity
        ]
        results = try_schedule_batch(scheduler, workloads)
        assert all(r is None for r in results), \
            "Failed batch scheduling should roll back all allocations"
        assert scheduler.nodes["n1"].used_cpu == 0.0, \
            "Node resources should be fully restored after batch failure"

    def test_batch_schedule_success(self):
        from services.compute.main import ComputeNode, Scheduler, try_schedule_batch
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", total_cpu=8.0, total_memory_gb=32.0,
        )
        workloads = [
            {"tenant_id": "t1", "cpu": 2.0, "memory_gb": 4.0},
            {"tenant_id": "t1", "cpu": 2.0, "memory_gb": 4.0},
        ]
        results = try_schedule_batch(scheduler, workloads)
        assert all(r is not None for r in results)


class TestClusterFragmentation:
    """Fragmentation score should reflect inability to schedule despite free resources."""

    def test_fragmentation_zero_when_consolidated(self):
        from services.compute.main import ComputeNode, Scheduler, calculate_cluster_fragmentation
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=8.0, used_cpu=0.0)
        frag = calculate_cluster_fragmentation(scheduler)
        assert frag == 0.0

    def test_fragmentation_high_when_scattered(self):
        from services.compute.main import ComputeNode, Scheduler, calculate_cluster_fragmentation
        scheduler = Scheduler()
        # 4 nodes each with 2 free CPU = 8 total free, but no single node has more than 2
        for i in range(4):
            scheduler.nodes[f"n{i}"] = ComputeNode(
                node_id=f"n{i}", total_cpu=8.0, used_cpu=6.0,
            )
        frag = calculate_cluster_fragmentation(scheduler)
        # Fragmentation should be > 0 since free resources are scattered
        assert frag > 0.0


# =============================================================================
# Tenant - Atomic Operations, Resource Transfer, Cloning
# =============================================================================


class TestTenantAtomicAllocation:
    """Atomic check-and-allocate should prevent race conditions."""

    def test_concurrent_allocations_respect_quota(self):
        from services.tenants.models import Tenant, TenantResourceStore
        store = TenantResourceStore()
        tenant = Tenant(max_compute_instances=5, current_compute_instances=4)

        # Two concurrent allocations - only one should succeed
        results = []

        def allocate():
            r = store.atomic_check_and_allocate(tenant, "compute_instance", 1)
            results.append(r)

        t1 = threading.Thread(target=allocate)
        t2 = threading.Thread(target=allocate)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        success_count = sum(1 for r in results if r is True)
        assert tenant.current_compute_instances <= tenant.max_compute_instances, \
            f"Quota should never be exceeded. Current: {tenant.current_compute_instances}, Max: {tenant.max_compute_instances}"


class TestResourceTransfer:
    """Resource transfer should update both source and target tenant quotas."""

    def test_transfer_decrements_source_usage(self):
        from services.tenants.models import Tenant, TenantResourceStore
        store = TenantResourceStore()
        source = Tenant(tenant_id="src", current_compute_instances=3)
        target = Tenant(tenant_id="tgt", current_compute_instances=1)

        store.resources["r1"] = {"tenant_id": "src", "type": "compute_instance"}
        store.resources["r2"] = {"tenant_id": "src", "type": "compute_instance"}

        transferred = store.transfer_resources(source, target, ["r1"])
        assert transferred == 1
        assert source.current_compute_instances == 2, \
            "Source tenant usage should decrease after transfer"
        assert target.current_compute_instances == 2


class TestTenantCloning:
    """Cloned tenants should have fully independent resource copies."""

    def test_clone_tenant_independence(self):
        from services.tenants.models import Tenant, TenantResourceStore
        store = TenantResourceStore()
        original = Tenant(tenant_id="orig", name="Original")
        store.resources["r1"] = {
            "tenant_id": "orig",
            "type": "compute_instance",
            "config": {"cpu": 4, "tags": ["web"]},
        }

        clone = store.deep_clone_tenant(original)
        # Modify clone's resources
        clone_resources = [
            (rid, r) for rid, r in store.resources.items()
            if r.get("tenant_id") == clone.tenant_id
        ]
        for rid, r in clone_resources:
            r["config"]["cpu"] = 8
            r["config"]["tags"].append("api")

        # Original should be unchanged
        assert store.resources["r1"]["config"]["cpu"] == 4, \
            "Original resource should not be affected by clone modification"
        assert store.resources["r1"]["config"]["tags"] == ["web"], \
            "Original resource nested data should be independent"


class TestTenantUtilization:
    """Utilization calculation should handle edge cases."""

    def test_utilization_percentages(self):
        from services.tenants.models import Tenant, TenantResourceStore
        store = TenantResourceStore()
        tenant = Tenant(
            max_compute_instances=100,
            current_compute_instances=50,
            max_storage_gb=1000,
            current_storage_gb=250,
        )
        util = store.calculate_resource_utilization(tenant)
        assert util["compute"] == 0.5
        assert util["storage"] == 0.25


# =============================================================================
# Load Balancer - Weight Distribution, Connection Draining
# =============================================================================


class TestTrafficWeightDistribution:
    """Traffic weights should sum to exactly the total weight."""

    def test_weights_sum_to_total(self):
        from services.loadbalancer.main import distribute_traffic_weights
        targets = [
            {"id": "t1", "capacity": 3},
            {"id": "t2", "capacity": 3},
            {"id": "t3", "capacity": 4},
        ]
        result = distribute_traffic_weights(targets, total_weight=100)
        total = sum(t["weight"] for t in result)
        assert total == 100, \
            f"Weights should sum to 100, got {total}"

    def test_weights_proportional(self):
        from services.loadbalancer.main import distribute_traffic_weights
        targets = [
            {"id": "t1", "capacity": 1},
            {"id": "t2", "capacity": 3},
        ]
        result = distribute_traffic_weights(targets, total_weight=100)
        w1 = next(t["weight"] for t in result if t["id"] == "t1")
        w2 = next(t["weight"] for t in result if t["id"] == "t2")
        assert w1 == 25
        assert w2 == 75


class TestConnectionDraining:
    """Connection drain timeout should account for active connections."""

    def test_drain_timeout_zero_connections(self):
        from services.loadbalancer.main import calculate_connection_drain_timeout
        timeout = calculate_connection_drain_timeout(0, 100.0)
        assert timeout == 0.0

    def test_drain_timeout_proportional(self):
        from services.loadbalancer.main import calculate_connection_drain_timeout
        timeout = calculate_connection_drain_timeout(
            active_connections=100, avg_request_duration_ms=50.0, safety_factor=2.0
        )
        # Should consider active connections in the calculation
        assert timeout > 0.0


# =============================================================================
# Monitor - Rate Calculation, Error Aggregation
# =============================================================================


class TestMetricRateCalculation:
    """Rate calculation should handle out-of-order timestamps."""

    def test_rate_calculation_ordered(self):
        from services.monitor.main import calculate_rate
        points = [
            {"timestamp": 100.0, "value": 0.0},
            {"timestamp": 110.0, "value": 100.0},
        ]
        rate = calculate_rate(points)
        assert rate == 10.0  # 100 values / 10 seconds

    def test_rate_out_of_order_timestamps(self):
        from services.monitor.main import calculate_rate
        # If timestamps are out of order, naive first/last calculation is wrong
        points = [
            {"timestamp": 100.0, "value": 0.0},
            {"timestamp": 95.0, "value": 50.0},   # Out of order
            {"timestamp": 110.0, "value": 100.0},
        ]
        rate = calculate_rate(points)
        # Should sort by timestamp first; rate = 100/10 = 10.0
        assert rate == 10.0, \
            f"Rate should be calculated on sorted data. Expected 10.0, got {rate}"


class TestErrorAggregation:
    """Error aggregation should group by the specified field."""

    def test_aggregate_by_error_type(self):
        from services.monitor.main import aggregate_error_counts
        errors = [
            {"error_type": "timeout", "status_code": 504, "message": "Gateway timeout"},
            {"error_type": "timeout", "status_code": 504, "message": "Gateway timeout"},
            {"error_type": "auth_failure", "status_code": 401, "message": "Unauthorized"},
        ]
        counts = aggregate_error_counts(errors, group_by="error_type")
        assert "timeout" in counts and counts["timeout"] == 2, \
            f"Should group by error_type. Got: {counts}"
        assert "auth_failure" in counts and counts["auth_failure"] == 1, \
            f"Should group by error_type. Got: {counts}"


# =============================================================================
# Config - Schema Validation, Variable Chains
# =============================================================================


class TestConfigSchemaValidation:
    """Schema validation should correctly recurse into nested structures."""

    def test_nested_schema_validation(self):
        from services.config.views import validate_config_schema
        schema = {
            "database": {
                "type": "dict",
                "required": True,
                "children": {
                    "host": {"type": "str", "required": True},
                    "port": {"type": "int", "required": True},
                },
            },
        }
        config = {
            "database": {
                "host": "localhost",
                # Missing required "port"
            },
        }
        errors = validate_config_schema(config, schema)
        port_errors = [e for e in errors if "port" in e]
        assert len(port_errors) > 0, \
            f"Should detect missing required nested field 'port'. Errors: {errors}"

    def test_valid_config_no_errors(self):
        from services.config.views import validate_config_schema
        schema = {
            "name": {"type": "str", "required": True},
            "count": {"type": "int", "required": False},
        }
        config = {"name": "test", "count": 5}
        errors = validate_config_schema(config, schema)
        assert errors == []


class TestVariableChainResolution:
    """Variable chain resolution should detect cycles and resolve correctly."""

    def test_simple_chain(self):
        from services.config.views import resolve_variable_chain
        variables = {"a": "b", "b": "c", "c": "final_value"}
        result = resolve_variable_chain(variables, "a")
        assert result == "final_value"

    def test_circular_chain(self):
        from services.config.views import resolve_variable_chain
        variables = {"a": "b", "b": "c", "c": "a"}
        result = resolve_variable_chain(variables, "a")
        assert result is None, "Circular chain should return None"


# =============================================================================
# Events - Replay Buffer, Ordered Processing
# =============================================================================


class TestEventReplayBuffer:
    """Replay buffer overflow should not lose recent events."""

    def test_replay_buffer_overflow_preserves_recent(self):
        from shared.events.base import EventReplayBuffer
        buf = EventReplayBuffer(max_size=10)
        # Add 15 events
        for i in range(15):
            buf.append({"data": f"event-{i}"})

        # Most recent events should still be accessible
        assert buf.size > 0
        events = buf.replay_from(1)
        seq_numbers = [e["_seq"] for e in events]
        assert 15 in seq_numbers, "Most recent event should be in buffer"

    def test_replay_buffer_sequence_ordering(self):
        from shared.events.base import EventReplayBuffer
        buf = EventReplayBuffer(max_size=100)
        for i in range(10):
            buf.append({"data": i})

        events = buf.replay_from(5)
        seqs = [e["_seq"] for e in events]
        assert seqs == sorted(seqs), "Replayed events should be in order"


class TestOrderedEventProcessor:
    """Ordered processor should buffer out-of-order events."""

    def test_in_order_processing(self):
        from shared.events.base import OrderedEventProcessor
        proc = OrderedEventProcessor()
        results = []
        for i in range(1, 6):
            results.extend(proc.process({"_seq": i, "data": i}))
        assert len(results) == 5

    def test_out_of_order_buffering(self):
        from shared.events.base import OrderedEventProcessor
        proc = OrderedEventProcessor()
        # Send event 3 first, then 1, 2
        r3 = proc.process({"_seq": 3, "data": "c"})
        assert len(r3) == 0  # Should be buffered

        r1 = proc.process({"_seq": 1, "data": "a"})
        assert len(r1) == 1  # Seq 1 processed

        r2 = proc.process({"_seq": 2, "data": "b"})
        # Seq 2 processed, and then buffered seq 3 should also process
        assert len(r2) == 2, \
            f"Processing seq 2 should also release buffered seq 3. Got {len(r2)} events"


# =============================================================================
# Connection Pool - Error Handling
# =============================================================================


class TestConnectionPoolErrorHandling:
    """Connection pool should return connections even when errors occur."""

    def test_connection_returned_on_error(self):
        from shared.clients.base import ConnectionPoolManager
        pool = ConnectionPoolManager(max_connections=2)

        def failing_func():
            raise ValueError("operation failed")

        with pytest.raises(ValueError):
            pool.execute_with_connection(failing_func)

        # Connection should have been returned to pool
        assert pool.available == 2, \
            f"Connection should be returned on error. Available: {pool.available}, expected: 2"

    def test_pool_exhaustion(self):
        from shared.clients.base import ConnectionPoolManager
        pool = ConnectionPoolManager(max_connections=2)
        assert pool.acquire() is True
        assert pool.acquire() is True
        assert pool.acquire() is False


class TestRetryPolicyIdempotency:
    """Retry policy should only retry idempotent operations."""

    def test_post_not_idempotent(self):
        from shared.clients.base import RetryPolicy
        policy = RetryPolicy()
        assert policy.is_idempotent("POST") is False, \
            "POST is not idempotent and should not be retried"
        assert policy.is_idempotent("PATCH") is False, \
            "PATCH is not idempotent and should not be retried"

    def test_get_is_idempotent(self):
        from shared.clients.base import RetryPolicy
        policy = RetryPolicy()
        assert policy.is_idempotent("GET") is True
        assert policy.is_idempotent("PUT") is True
        assert policy.is_idempotent("DELETE") is True

    def test_non_idempotent_not_retried(self):
        from shared.clients.base import RetryPolicy
        policy = RetryPolicy()
        # POST that fails with 500 should not be retried if using idempotency check
        should = policy.should_retry("POST", attempt=0, status_code=500)
        is_safe = policy.is_idempotent("POST")
        # The retry policy retries POST (which is wrong for non-idempotent ops)
        assert not (should and not is_safe), \
            "Non-idempotent operations (POST) should not be retried on server errors"
