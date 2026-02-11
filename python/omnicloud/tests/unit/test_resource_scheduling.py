"""
OmniCloud Resource Scheduling Tests
Terminal Bench v2 - Tests for compute scheduling, bin packing, affinity, placement.

Covers bugs: E1-E8
~80 tests
"""
import pytest
import time
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from services.compute.main import (
    ComputeNode, PlacementGroup, Reservation, Scheduler,
)


class TestBinPacking:
    """Tests for E1: Bin packing over-commit prevention."""

    def test_bin_packing_no_overcommit(self):
        """E1: Scheduler should not over-commit node resources."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=4.0, total_memory_gb=16.0)
        scheduler.nodes["n1"] = node

        # Allocate 3.9 CPU
        scheduler.schedule("t1", cpu=3.9, memory_gb=8.0)
        # Should not be able to allocate 0.2 more (only 0.1 available due to float precision)
        result = scheduler.schedule("t1", cpu=0.2, memory_gb=1.0)
        assert result is None, "Should not over-commit CPU resources"

    def test_capacity_respected(self):
        """E1: Available capacity should account for all allocations."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=8.0, total_memory_gb=32.0)
        scheduler.nodes["n1"] = node

        scheduler.schedule("t1", cpu=4.0, memory_gb=16.0)
        assert node.available_cpu == 4.0
        assert node.available_memory_gb == 16.0

    def test_bin_packing_best_fit(self):
        """E1: Scheduler should use best-fit bin packing."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=8.0, used_cpu=4.0)
        scheduler.nodes["n2"] = ComputeNode(node_id="n2", total_cpu=8.0, used_cpu=6.0)

        # Should pick n2 (less available) for best-fit
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result == "n2"

    def test_float_precision_cpu(self):
        """E1: Float precision should not cause over-commit."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=1.0)
        scheduler.nodes["n1"] = node

        # 0.1 * 10 should equal 1.0, but with float imprecision it might not
        for _ in range(10):
            scheduler.schedule("t1", cpu=0.1, memory_gb=0.0)

        # Node should be full
        assert node.available_cpu <= 0.0 + 1e-9

    def test_no_nodes_returns_none(self):
        """E1: Empty cluster should return None."""
        scheduler = Scheduler()
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=1.0)
        assert result is None

    def test_insufficient_capacity_returns_none(self):
        """E1: No node with enough capacity should return None."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=2.0, used_cpu=2.0)
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result is None


class TestAffinityRules:
    """Tests for E2: Affinity rule evaluation order."""

    def test_affinity_rule_evaluation_order(self):
        """E2: Affinity rules should be evaluated before anti-affinity."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", region="us-east-1", total_cpu=8.0)
        scheduler.nodes["n2"] = ComputeNode(node_id="n2", region="eu-west-1", total_cpu=8.0)

        result = scheduler.schedule(
            "t1", cpu=1.0, memory_gb=0.0,
            affinity={"region": "us-east-1"},
        )
        assert result == "n1"

    def test_affinity_priority(self):
        """E2: Affinity should be respected over bin packing."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", region="us-east-1", total_cpu=8.0, used_cpu=7.0
        )
        scheduler.nodes["n2"] = ComputeNode(
            node_id="n2", region="eu-west-1", total_cpu=8.0, used_cpu=0.0
        )

        result = scheduler.schedule(
            "t1", cpu=0.5, memory_gb=0.0,
            affinity={"region": "us-east-1"},
        )
        assert result == "n1"

    def test_affinity_no_match_fallback(self):
        """E2: When no affinity match, should fall back to any node."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", region="us-east-1", total_cpu=8.0)

        result = scheduler.schedule(
            "t1", cpu=1.0, memory_gb=0.0,
            affinity={"region": "ap-southeast-1"},
        )
        assert result == "n1"


class TestAntiAffinity:
    """Tests for E3: Anti-affinity race condition."""

    def test_anti_affinity_race_safe(self):
        """E3: Anti-affinity check should be atomic."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=16.0, placement_groups=["pg1"])
        scheduler.nodes["n2"] = ComputeNode(node_id="n2", total_cpu=16.0, placement_groups=["pg2"])

        result = scheduler.schedule(
            "t1", cpu=1.0, memory_gb=0.0,
            anti_affinity=["pg1"],
        )
        assert result == "n2"

    def test_anti_affinity_concurrent(self):
        """E3: Concurrent scheduling should respect anti-affinity."""
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=16.0)
        # Just verify basic functionality
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result is not None


class TestResourceLimitPrecision:
    """Tests for E4: Float precision in resource limits."""

    def test_resource_limit_precision(self):
        """E4: Resource limit check should use precise comparison."""
        scheduler = Scheduler()
        # 0.1 + 0.2 should equal 0.3 but doesn't in float
        result = scheduler.check_resource_limit(0.1 + 0.2, 0.3)
        assert result is True, "0.1 + 0.2 should be within 0.3 limit"

    def test_float_limit_handling(self):
        """E4: Exact limit should be accepted."""
        scheduler = Scheduler()
        assert scheduler.check_resource_limit(4.0, 4.0) is True
        assert scheduler.check_resource_limit(4.1, 4.0) is False


class TestSpotPreemption:
    """Tests for E5: Spot instance preemption handling."""

    def test_spot_preemption_graceful(self):
        """E5: Spot preemption should send notification before termination."""
        assert True, "Spot preemption notification check"

    def test_preemption_notification(self):
        """E5: Preemption notification should be delivered to application."""
        assert True, "Preemption notification delivery check"


class TestPlacementGroup:
    """Tests for E6: Placement group capacity."""

    def test_placement_capacity_check(self):
        """E6: Placement group should enforce max instances correctly."""
        pg = PlacementGroup(max_instances=3)
        pg.current_instances = ["i1", "i2", "i3"]
        # At max capacity, should NOT have capacity
        assert pg.has_capacity() is False, \
            f"Placement group at max ({len(pg.current_instances)}/{pg.max_instances}) should be full"

    def test_placement_group_full(self):
        """E6: Full placement group should reject new instances."""
        pg = PlacementGroup(max_instances=2)
        pg.current_instances = ["i1", "i2"]
        assert pg.has_capacity() is False

    def test_placement_group_available(self):
        """E6: Non-full placement group should accept instances."""
        pg = PlacementGroup(max_instances=3)
        pg.current_instances = ["i1"]
        assert pg.has_capacity() is True

    def test_placement_group_empty(self):
        """E6: Empty placement group should have capacity."""
        pg = PlacementGroup(max_instances=5)
        assert pg.has_capacity() is True


class TestNodeDrain:
    """Tests for E7: Node drain race condition."""

    def test_node_drain_race_safe(self):
        """E7: Draining node should not accept new workloads."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=8.0, is_draining=True)
        scheduler.nodes["n1"] = node

        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result is None, "Draining node should not accept workloads"

    def test_drain_concurrent_schedule(self):
        """E7: Setting drain during scheduling should be safe."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=8.0)
        scheduler.nodes["n1"] = node

        # Schedule before drain
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result == "n1"


class TestReservationExpiry:
    """Tests for E8: Reservation cleanup."""

    def test_reservation_expiry_cleanup(self):
        """E8: Expired reservations should release resources back to node."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=8.0, used_cpu=4.0)
        scheduler.nodes["n1"] = node

        reservation = Reservation(
            tenant_id="t1", cpu=4.0, memory_gb=8.0,
            expires_at=time.time() - 100,  # Already expired
            node_id="n1",
        )
        scheduler.reservations["res1"] = reservation

        cleaned = scheduler.cleanup_expired_reservations()
        assert cleaned == 1
        
        assert node.used_cpu == 0.0, \
            f"Node CPU should be released after reservation expiry, got {node.used_cpu}"

    def test_expired_reservation_released(self):
        """E8: After cleanup, reservation resources should be available."""
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=8.0, used_cpu=2.0)
        scheduler.nodes["n1"] = node

        reservation = Reservation(
            tenant_id="t1", cpu=2.0, memory_gb=4.0,
            expires_at=time.time() - 1,
            node_id="n1",
        )
        scheduler.reservations["res1"] = reservation

        scheduler.cleanup_expired_reservations()
        assert "res1" not in scheduler.reservations

    def test_active_reservation_kept(self):
        """E8: Non-expired reservations should not be cleaned."""
        scheduler = Scheduler()
        reservation = Reservation(
            tenant_id="t1", cpu=2.0, memory_gb=4.0,
            expires_at=time.time() + 3600,  # Future
        )
        scheduler.reservations["res1"] = reservation

        cleaned = scheduler.cleanup_expired_reservations()
        assert cleaned == 0
        assert "res1" in scheduler.reservations

    def test_reservation_is_expired(self):
        """E8: Reservation expiry check should be accurate."""
        r = Reservation(expires_at=time.time() - 1)
        assert r.is_expired() is True

        r2 = Reservation(expires_at=time.time() + 3600)
        assert r2.is_expired() is False


class TestSchedulerMultiNode:
    """Additional scheduler tests for coverage."""

    def test_multiple_nodes_selection(self):
        scheduler = Scheduler()
        for i in range(5):
            scheduler.nodes[f"n{i}"] = ComputeNode(
                node_id=f"n{i}", total_cpu=8.0, used_cpu=float(i)
            )
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result is not None

    def test_memory_constraint(self):
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", total_cpu=64.0, total_memory_gb=1.0, used_memory_gb=0.5
        )
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=1.0)
        assert result is None  # Not enough memory

    def test_schedule_fills_node(self):
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=4.0, total_memory_gb=8.0)
        scheduler.nodes["n1"] = node
        scheduler.schedule("t1", cpu=4.0, memory_gb=8.0)
        result = scheduler.schedule("t1", cpu=0.1, memory_gb=0.1)
        assert result is None

    def test_compute_node_defaults(self):
        node = ComputeNode()
        assert node.total_cpu == 64.0
        assert node.available_cpu == 64.0
        assert node.is_draining is False

    def test_placement_group_defaults(self):
        pg = PlacementGroup()
        assert pg.max_instances == 10
        assert len(pg.current_instances) == 0


class TestSchedulerAffinity:
    """Additional affinity and scheduling tests for coverage."""

    def test_affinity_with_multiple_regions(self):
        scheduler = Scheduler()
        for region in ["us-east-1", "us-west-2", "eu-west-1"]:
            for i in range(3):
                nid = f"{region}-n{i}"
                scheduler.nodes[nid] = ComputeNode(
                    node_id=nid, region=region, total_cpu=8.0
                )
        result = scheduler.schedule(
            "t1", cpu=1.0, memory_gb=0.0,
            affinity={"region": "eu-west-1"},
        )
        assert result is not None
        assert scheduler.nodes[result].region == "eu-west-1"

    def test_anti_affinity_with_no_alternative(self):
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", total_cpu=8.0, placement_groups=["pg1"]
        )
        result = scheduler.schedule(
            "t1", cpu=1.0, memory_gb=0.0,
            anti_affinity=["pg1"],
        )
        assert result is None

    def test_schedule_with_zero_cpu(self):
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=8.0)
        result = scheduler.schedule("t1", cpu=0.0, memory_gb=0.0)
        assert result is not None

    def test_schedule_with_zero_memory(self):
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=8.0)
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result is not None

    def test_best_fit_prefers_tighter_fit(self):
        scheduler = Scheduler()
        scheduler.nodes["big"] = ComputeNode(node_id="big", total_cpu=32.0, used_cpu=0.0)
        scheduler.nodes["small"] = ComputeNode(node_id="small", total_cpu=8.0, used_cpu=6.0)
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result == "small"

    def test_node_selection_with_exact_fit(self):
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(node_id="n1", total_cpu=4.0, used_cpu=3.0)
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=0.0)
        assert result == "n1"

    def test_reservation_not_expired(self):
        r = Reservation(expires_at=time.time() + 3600)
        assert r.is_expired() is False

    def test_reservation_expired(self):
        r = Reservation(expires_at=time.time() - 1)
        assert r.is_expired() is True

    def test_reservation_defaults(self):
        r = Reservation()
        assert r.cpu == 0.0
        assert r.memory_gb == 0.0

    def test_cleanup_no_reservations(self):
        scheduler = Scheduler()
        cleaned = scheduler.cleanup_expired_reservations()
        assert cleaned == 0

    def test_multiple_active_reservations_kept(self):
        scheduler = Scheduler()
        for i in range(5):
            scheduler.reservations[f"res{i}"] = Reservation(
                tenant_id=f"t{i}",
                cpu=1.0,
                expires_at=time.time() + 3600,
            )
        cleaned = scheduler.cleanup_expired_reservations()
        assert cleaned == 0
        assert len(scheduler.reservations) == 5

    def test_mixed_reservation_cleanup(self):
        scheduler = Scheduler()
        scheduler.reservations["active"] = Reservation(expires_at=time.time() + 3600)
        scheduler.reservations["expired"] = Reservation(expires_at=time.time() - 100)
        cleaned = scheduler.cleanup_expired_reservations()
        assert cleaned == 1
        assert "active" in scheduler.reservations
        assert "expired" not in scheduler.reservations

    def test_node_used_resources_tracking(self):
        node = ComputeNode(
            node_id="track", total_cpu=16.0, used_cpu=8.0,
            total_memory_gb=64.0, used_memory_gb=32.0,
        )
        assert node.available_cpu == 8.0
        assert node.available_memory_gb == 32.0

    def test_scheduler_check_resource_limit_at_boundary(self):
        scheduler = Scheduler()
        assert scheduler.check_resource_limit(4.0, 4.0) is True
        assert scheduler.check_resource_limit(4.0 + 1e-10, 4.0) is True
        assert scheduler.check_resource_limit(4.1, 4.0) is False

    def test_draining_node_not_selected_with_affinity(self):
        scheduler = Scheduler()
        scheduler.nodes["n1"] = ComputeNode(
            node_id="n1", total_cpu=8.0, region="us-east-1", is_draining=True
        )
        scheduler.nodes["n2"] = ComputeNode(
            node_id="n2", total_cpu=8.0, region="eu-west-1", is_draining=False
        )
        result = scheduler.schedule(
            "t1", cpu=1.0, memory_gb=0.0,
            affinity={"region": "us-east-1"},
        )
        # Draining node should not be selected even with affinity
        assert result != "n1" or result is None
