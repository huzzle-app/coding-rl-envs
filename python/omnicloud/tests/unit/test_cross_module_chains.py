"""
OmniCloud Cross-Module Chain Tests
Terminal Bench v2 - Tests requiring fixes across 2-3 modules to pass.

These tests exercise bug combinations that span multiple subsystems,
ensuring agents must fix interrelated bugs rather than isolated ones.

6 tests covering 12 unique bugs across 6 modules.
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock


class TestBillingTenantIsolation:
    """Cross-module: C1 (tenant isolation) + H4 (cost allocation precision)."""

    def test_billing_tenant_isolation(self):
        """C1+H4: Resource access must enforce tenant AND cost allocation must use Decimal."""
        from services.tenants.models import TenantResourceStore
        from services.billing.views import allocate_costs

        store = TenantResourceStore()
        store.resources["r1"] = {"id": "r1", "tenant_id": "t1", "type": "compute"}
        store.resources["r2"] = {"id": "r2", "tenant_id": "t2", "type": "compute"}

        # C1: get_resource_by_id should enforce tenant isolation
        # BUG: currently returns any resource regardless of who asks
        r1 = store.get_resource_by_id("r1")
        # The function signature should accept tenant_id to enforce isolation
        import inspect
        sig = inspect.signature(store.get_resource_by_id)
        assert 'tenant_id' in sig.parameters, \
            "C1: get_resource_by_id must accept tenant_id parameter to enforce isolation"

        # H4: Cost allocation must use Decimal precision
        total_cost = Decimal("300.00")
        usages = {"t1": Decimal("100"), "t2": Decimal("200")}
        costs = allocate_costs(total_cost, usages)
        t1_cost = costs.get("t1", 0)
        assert isinstance(t1_cost, Decimal), \
            f"H4: Cost allocation should return Decimal, got {type(t1_cost)}"


class TestDeploymentLockTTL:
    """Cross-module: F5 (deployment lock) + B3 (distributed lock TTL)."""

    def test_deployment_lock_ttl(self):
        """F5+B3: Deployment lock TTL must exceed deploy operation duration."""
        from shared.utils.distributed import DistributedLock

        # B3: Default TTL should be long enough for deployments (>=30s)
        lock = DistributedLock(name="deploy-lock")
        assert lock.ttl_seconds >= 30.0, \
            f"B3: Lock TTL should be >= 30s for deployment operations, got {lock.ttl_seconds}s"

        # F5: Deployment lock should be held through a long operation
        # Simulate a deployment that takes time by acquiring and checking
        acquired = lock.acquire(timeout=5.0)
        assert acquired is True, "F5: Should be able to acquire deployment lock"

        # Lock should still be valid after simulated operation start
        assert lock.is_held(), \
            "F5: Deployment lock should remain held during operation"
        lock.release()


class TestStateTransitionWithLocking:
    """Cross-module: A1 (state transitions) + G10 (lock ordering)."""

    def test_state_transition_with_locking(self):
        """A1+G10: State transition must acquire locks in consistent order."""
        from shared.infra.state import StateManager, Resource, ResourceState
        from shared.utils.distributed import LockManager

        sm = StateManager()
        r = Resource(resource_id="r1", resource_type="compute")
        sm.add_resource(r)

        # A1: State transition should work correctly
        sm.transition_state("r1", ResourceState.CREATING)
        assert sm.resources["r1"].state == ResourceState.CREATING

        # G10: Lock ordering must be consistent (sorted)
        lm = LockManager()
        lm.acquire_locks(["state-r1", "deploy-r1", "config-r1"])
        assert lm._acquisition_order == ["config-r1", "deploy-r1", "state-r1"], \
            f"G10: Locks must be acquired in sorted order, got {lm._acquisition_order}"
        lm.release_all()


class TestReconcileWithRollback:
    """Cross-module: A3 (reconciliation loop) + A7 (partial rollback)."""

    def test_reconcile_with_rollback(self):
        """A3+A7: Reconciliation must be bounded AND partial failures rolled back."""
        from shared.infra.reconciler import Reconciler
        from shared.infra.state import StateManager, Resource

        sm = StateManager()
        r1 = Resource(resource_id="r1", resource_type="compute", desired_config={"cpu": 2})
        r2 = Resource(resource_id="r2", resource_type="network", desired_config={"cidr": "10.0.0.0/24"})
        sm.add_resource(r1)
        sm.add_resource(r2)

        reconciler = Reconciler(state_manager=sm)

        # A3: Default max_iterations must be bounded (> 0)
        assert reconciler.max_iterations > 0, \
            f"A3: Reconciler must have bounded iterations, got max_iterations={reconciler.max_iterations}"

        # A7: Partial failure should trigger rollback of applied changes
        original_config = dict(r1.desired_config)
        result = reconciler.apply_changes(
            ["r1", "nonexistent"],
            {"r1": {"cpu": 8}, "nonexistent": {"bad": True}},
        )
        if result.failed > 0:
            assert sm.resources["r1"].desired_config == original_config, \
                "A7: After partial failure, successfully applied changes must be rolled back"


class TestQuotaWithPrecision:
    """Cross-module: C2 (atomic quota) + E1 (Decimal bin packing)."""

    def test_quota_with_precision(self):
        """C2+E1: Quota check must be atomic AND scheduling must use Decimal."""
        from services.tenants.models import TenantResourceStore, Tenant
        from services.compute.main import Scheduler, ComputeNode

        # C2: Quota check and increment must be atomic
        store = TenantResourceStore()
        tenant = Tenant(tenant_id="t1", max_compute_instances=5, current_compute_instances=4)

        # check_quota and increment should be atomic (one operation)
        can_use = store.check_quota(tenant, "compute_instance", count=1)
        assert can_use is True, "Should be able to use 1 more of 5 quota"
        # BUG C2: After check passes, another thread could also pass before increment
        # check_quota should atomically check AND increment
        # Verify by checking the usage was incremented
        assert tenant.current_compute_instances == 5, \
            f"C2: check_quota should atomically increment usage, got {tenant.current_compute_instances}"

        # E1: Bin packing should use precise arithmetic
        scheduler = Scheduler()
        node = ComputeNode(node_id="n1", total_cpu=4.0, total_memory_gb=16.0)
        scheduler.nodes["n1"] = node

        scheduler.schedule("task-1", cpu=0.1, memory_gb=1.0)
        scheduler.schedule("task-2", cpu=0.2, memory_gb=1.0)
        remaining_cpu = node.total_cpu - node.allocated_cpu
        assert remaining_cpu > 3.6, \
            f"E1: Remaining CPU should be ~3.7 after allocating 0.3, got {remaining_cpu}"


class TestDnsWithSubnetExhaustion:
    """Cross-module: D4 (DNS CNAME resolution) + D5 (subnet exhaustion)."""

    def test_dns_with_subnet_exhaustion(self):
        """D4+D5: DNS CNAME resolution must be bounded AND subnet exhaustion detected."""
        from services.network.views import resolve_dns_cname, check_subnet_exhaustion

        # D4: CNAME resolution must not follow infinite loops
        # resolve_dns_cname expects records as {name: target_name} flat mapping
        dns_records = {
            "a.example.com": "b.example.com",
            "b.example.com": "c.example.com",
            "c.example.com": "a.example.com",  # cycle!
        }
        result = resolve_dns_cname("a.example.com", dns_records, max_depth=10)
        # Should detect the cycle and not loop forever
        assert result is None or result == "a.example.com", \
            f"D4: Circular CNAME should return None or original, got {result}"

        # D5: Subnet exhaustion should be detected
        subnet_size = 4  # /30 = 4 addresses (2 usable)
        used_ips = 4  # All addresses used
        is_exhausted = check_subnet_exhaustion(used_ips, subnet_size)
        assert is_exhausted is True, \
            f"D5: Subnet with {used_ips}/{subnet_size} IPs should be detected as exhausted"
