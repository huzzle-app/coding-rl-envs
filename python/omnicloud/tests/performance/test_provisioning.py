"""
OmniCloud Performance Provisioning Tests
Terminal Bench v2 - Performance tests for resource provisioning, scheduling, and throughput.

~40 tests
"""
import pytest
import time
import uuid
from decimal import Decimal
from collections import defaultdict

from services.compute.main import ComputeNode, Scheduler, PlacementGroup
from services.tenants.models import Tenant, TenantResourceStore
from shared.utils.distributed import DistributedLock, LockManager, QuorumChecker
from shared.clients.base import CircuitBreaker, CircuitState


class TestProvisioningThroughput:
    """Tests for resource provisioning performance."""

    def test_scheduler_handles_many_nodes(self):
        """Scheduler should handle large number of nodes efficiently."""
        scheduler = Scheduler()
        for i in range(100):
            scheduler.nodes[f"n{i}"] = ComputeNode(
                node_id=f"n{i}", total_cpu=64.0, total_memory_gb=256.0
            )
        result = scheduler.schedule("t1", cpu=1.0, memory_gb=1.0)
        assert result is not None

    def test_scheduling_latency_acceptable(self):
        """Schedule operation should complete within acceptable time."""
        scheduler = Scheduler()
        for i in range(50):
            scheduler.nodes[f"n{i}"] = ComputeNode(
                node_id=f"n{i}", total_cpu=32.0, total_memory_gb=128.0
            )

        start = time.time()
        for _ in range(100):
            scheduler.schedule("t1", cpu=0.1, memory_gb=0.1)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"100 scheduling operations took {elapsed:.2f}s, should be < 5s"

    def test_concurrent_tenant_operations(self):
        """Multiple tenants should be able to provision simultaneously."""
        store = TenantResourceStore()
        tenants = [Tenant(tenant_id=f"t{i}", max_compute_instances=100) for i in range(10)]

        for tenant in tenants:
            for j in range(10):
                rid = str(uuid.uuid4())
                store.resources[rid] = {
                    "tenant_id": tenant.tenant_id,
                    "type": "compute",
                    "name": f"vm-{j}",
                }

        assert len(store.resources) == 100

    def test_resource_lookup_performance(self):
        """Resource lookup should be efficient with many resources."""
        store = TenantResourceStore()
        for i in range(1000):
            rid = f"r{i}"
            store.resources[rid] = {
                "tenant_id": f"t{i % 10}",
                "type": "compute",
            }

        start = time.time()
        results = store.get_resources("t0")
        elapsed = time.time() - start

        assert len(results) == 100
        assert elapsed < 1.0

    def test_quota_check_performance(self):
        """Quota checks should be fast."""
        store = TenantResourceStore()
        tenant = Tenant(max_compute_instances=10000)

        start = time.time()
        for _ in range(10000):
            store.check_quota(tenant, "compute_instance", 1)
        elapsed = time.time() - start

        assert elapsed < 2.0, f"10000 quota checks took {elapsed:.2f}s"


class TestLockPerformance:
    """Tests for distributed lock performance."""

    def test_lock_acquisition_speed(self):
        """Lock acquisition should be fast."""
        lock = DistributedLock(name="perf-test")
        start = time.time()
        for _ in range(100):
            lock.acquire(blocking=False)
            lock.release()
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_lock_manager_multi_lock_speed(self):
        """Multi-lock acquisition should be efficient."""
        lm = LockManager()
        start = time.time()
        for i in range(50):
            locks = [f"lock_{j}" for j in range(5)]
            lm.acquire_locks(locks)
            lm.release_all()
        elapsed = time.time() - start
        assert elapsed < 2.0


class TestCircuitBreakerPerformance:
    """Tests for circuit breaker performance under load."""

    def test_circuit_breaker_state_transitions_fast(self):
        """Circuit breaker state machine should be fast."""
        cb = CircuitBreaker(failure_threshold=100)

        start = time.time()
        for _ in range(10000):
            cb.can_execute()
            cb.record_success()
        elapsed = time.time() - start

        assert elapsed < 1.0

    def test_circuit_breaker_many_failures(self):
        """Circuit breaker should handle many failures gracefully."""
        cb = CircuitBreaker(failure_threshold=5)
        for _ in range(1000):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestPlacementGroupPerformance:
    """Tests for placement group capacity checks under load."""

    def test_placement_capacity_check_speed(self):
        """Placement capacity check should be fast."""
        pg = PlacementGroup(max_instances=10000)
        pg.current_instances = [f"i{j}" for j in range(5000)]

        start = time.time()
        for _ in range(10000):
            pg.has_capacity()
        elapsed = time.time() - start

        assert elapsed < 1.0

    def test_node_capacity_calculation(self):
        """Node available capacity should be computed correctly."""
        node = ComputeNode(
            node_id="perf-node",
            total_cpu=64.0,
            used_cpu=32.0,
            total_memory_gb=256.0,
            used_memory_gb=128.0,
        )
        assert node.available_cpu == 32.0
        assert node.available_memory_gb == 128.0


class TestBulkOperations:
    """Tests for bulk resource operations."""

    def test_bulk_resource_creation(self):
        """Bulk resource creation should be efficient."""
        store = TenantResourceStore()

        start = time.time()
        for i in range(500):
            store.resources[f"r{i}"] = {
                "tenant_id": "t1",
                "type": "compute",
                "name": f"vm-{i}",
            }
        elapsed = time.time() - start

        assert len(store.resources) == 500
        assert elapsed < 1.0

    def test_bulk_tenant_deletion(self):
        """Bulk deletion should handle many resources."""
        store = TenantResourceStore()
        for i in range(500):
            store.resources[f"r{i}"] = {"tenant_id": "t1", "type": "compute"}

        start = time.time()
        deleted = store.delete_tenant_resources("t1")
        elapsed = time.time() - start

        assert deleted == 500
        assert elapsed < 1.0

    def test_bulk_scheduling(self):
        """Scheduler should handle burst of scheduling requests."""
        scheduler = Scheduler()
        for i in range(10):
            scheduler.nodes[f"n{i}"] = ComputeNode(
                node_id=f"n{i}", total_cpu=64.0, total_memory_gb=256.0
            )

        scheduled = 0
        start = time.time()
        for _ in range(200):
            result = scheduler.schedule("t1", cpu=0.5, memory_gb=1.0)
            if result:
                scheduled += 1
        elapsed = time.time() - start

        assert scheduled > 0
        assert elapsed < 3.0


class TestQuorumPerformance:
    """Tests for quorum check performance."""

    def test_quorum_check_speed(self):
        """Quorum checks should be O(1)."""
        checker = QuorumChecker(total_nodes=1000)
        start = time.time()
        for i in range(100000):
            checker.has_quorum(501)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_minimum_quorum_calculation(self):
        """Minimum quorum calculation should be fast."""
        checker = QuorumChecker(total_nodes=9999)
        start = time.time()
        for _ in range(100000):
            checker.minimum_for_quorum()
        elapsed = time.time() - start
        assert elapsed < 1.0


class TestCachePerformance:
    """Tests for cache operation performance."""

    def test_cache_read_write_speed(self):
        """Cache operations should be fast."""
        store = TenantResourceStore()

        start = time.time()
        for i in range(10000):
            store.set_cached(f"key_{i}", f"value_{i}")
        for i in range(10000):
            store.get_cached(f"key_{i}")
        elapsed = time.time() - start

        assert elapsed < 2.0

    def test_cache_miss_performance(self):
        """Cache misses should not be significantly slower."""
        store = TenantResourceStore()

        start = time.time()
        for i in range(10000):
            store.get_cached(f"missing_key_{i}")
        elapsed = time.time() - start

        assert elapsed < 1.0


class TestDeploymentPerformance:
    """Tests for deployment pipeline performance."""

    def test_rolling_batch_calculation_speed(self):
        """Rolling batch calculation should be fast for many replicas."""
        from services.deploy.tasks import calculate_rolling_batches
        start = time.time()
        for _ in range(1000):
            calculate_rolling_batches(replicas=100, batch_size=5)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_event_emission_speed(self):
        """Event emission should be fast."""
        from services.deploy.tasks import Deployment, emit_deployment_event
        d = Deployment()
        start = time.time()
        for i in range(1000):
            emit_deployment_event(d, f"event_{i}", {"index": i})
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_hook_execution_speed(self):
        """Hook execution should be fast for many hooks."""
        from services.deploy.tasks import execute_hooks
        hooks = {
            "pre_deploy": [lambda: None for _ in range(50)],
            "post_deploy": [lambda: None for _ in range(50)],
        }
        start = time.time()
        execute_hooks(hooks, "deploy")
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_dependency_ordering_speed(self):
        """Dependency ordering should handle many deployments."""
        from services.deploy.tasks import Deployment, order_deployment_dependencies
        deploys = [
            Deployment(service_name=f"svc-{i}", dependencies=[f"svc-{i-1}"] if i > 0 else [])
            for i in range(50)
        ]
        start = time.time()
        order_deployment_dependencies(deploys)
        elapsed = time.time() - start
        assert elapsed < 1.0


class TestNetworkPerformance:
    """Tests for network operations performance."""

    def test_cidr_allocation_speed(self):
        """CIDR allocation should be fast with many existing networks."""
        from services.network.views import allocate_cidr
        existing = [f"10.0.{i}.0/24" for i in range(200)]
        start = time.time()
        allocate_cidr(24, existing, "10.0.0.0/8")
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_firewall_rule_ordering_speed(self):
        """Firewall rule ordering should handle many rules."""
        from services.network.views import order_firewall_rules
        rules = [{"priority": i, "action": "allow", "port": 80 + i} for i in range(1000)]
        start = time.time()
        order_firewall_rules(rules)
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_dns_resolution_speed(self):
        """DNS resolution should handle long chains quickly."""
        from services.network.views import resolve_dns_cname
        records = {f"level{i}.example.com": f"level{i+1}.example.com" for i in range(50)}
        start = time.time()
        resolve_dns_cname("level0.example.com", records, max_depth=100)
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_nat_port_allocation_speed(self):
        """NAT port allocation should be fast."""
        from services.network.views import allocate_nat_port
        allocated = set()
        start = time.time()
        for _ in range(500):
            port = allocate_nat_port(allocated)
            if port:
                pass
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_security_group_dedup_speed(self):
        """Security group dedup should handle many rules."""
        from services.network.views import deduplicate_security_group_rules
        rules = [
            {"protocol": "tcp", "port": i % 100, "source": f"10.0.{i % 256}.0/24"}
            for i in range(500)
        ]
        start = time.time()
        deduplicate_security_group_rules(rules)
        elapsed = time.time() - start
        assert elapsed < 1.0


class TestBillingPerformance:
    """Tests for billing operation performance."""

    def test_proration_calculation_speed(self):
        """Proration should be fast for many calculations."""
        from services.billing.views import calculate_proration
        start = time.time()
        for i in range(10000):
            calculate_proration(Decimal("100.00"), days_used=i % 30, total_days=30)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_discount_application_speed(self):
        """Discount application should be fast."""
        from services.billing.views import apply_discounts
        discounts = [{"type": "percentage", "value": 5} for _ in range(10)]
        start = time.time()
        for _ in range(5000):
            apply_discounts(Decimal("100.00"), discounts)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_cost_allocation_speed(self):
        """Cost allocation should handle many tenants."""
        from services.billing.views import allocate_costs
        usages = {f"t{i}": Decimal(str(i + 1)) for i in range(100)}
        start = time.time()
        for _ in range(1000):
            allocate_costs(usages, Decimal("10000.00"))
        elapsed = time.time() - start
        assert elapsed < 3.0


class TestConfigPerformance:
    """Tests for configuration operation performance."""

    def test_interpolation_speed(self):
        """Variable interpolation should be fast."""
        from services.config.views import interpolate_variables
        variables = {f"var_{i}": f"value_{i}" for i in range(100)}
        template = " ".join(f"${{{k}}}" for k in list(variables.keys())[:10])
        start = time.time()
        for _ in range(1000):
            interpolate_variables(template, variables, max_depth=5)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_topological_sort_speed(self):
        """Topological sort should handle large graphs."""
        from services.config.views import topological_sort
        graph = {f"n{i}": {f"n{i+1}"} if i < 99 else set() for i in range(100)}
        start = time.time()
        for _ in range(100):
            topological_sort(graph)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_merge_defaults_speed(self):
        """Resource default merge should be fast."""
        from services.config.views import merge_resource_defaults
        defaults = {f"key_{i}": f"default_{i}" for i in range(100)}
        overrides = {f"key_{i}": f"override_{i}" for i in range(0, 100, 2)}
        start = time.time()
        for _ in range(10000):
            merge_resource_defaults(defaults, overrides)
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_dynamic_block_expansion_speed(self):
        """Dynamic block expansion should be fast."""
        from services.config.views import expand_dynamic_blocks
        blocks = [
            {"name": f"block_{i}", "for_each": [f"item_{j}" for j in range(10)]}
            for i in range(50)
        ]
        start = time.time()
        expand_dynamic_blocks(blocks)
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_env_precedence_speed(self):
        """Environment variable precedence resolution should be fast."""
        from services.config.views import resolve_env_precedence
        cli = {f"key_{i}": f"cli_{i}" for i in range(50)}
        env = {f"key_{i}": f"env_{i}" for i in range(50, 100)}
        config = {f"key_{i}": f"config_{i}" for i in range(100, 150)}
        defaults = {f"key_{i}": f"default_{i}" for i in range(150, 200)}
        start = time.time()
        for _ in range(5000):
            resolve_env_precedence(cli, env, config, defaults)
        elapsed = time.time() - start
        assert elapsed < 3.0


class TestStatePerformance:
    """Tests for state management performance."""

    def test_state_transition_speed(self):
        """State transitions should be fast."""
        from shared.infra.state import StateManager, Resource, ResourceState
        manager = StateManager()
        for i in range(100):
            r = Resource(resource_id=f"r{i}", resource_type="compute")
            manager.resources[f"r{i}"] = r

        start = time.time()
        for i in range(100):
            manager.transition_state(f"r{i}", ResourceState.CREATING)
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_snapshot_speed(self):
        """State snapshot should be fast."""
        from shared.infra.state import StateManager, Resource
        manager = StateManager()
        for i in range(200):
            r = Resource(
                resource_id=f"r{i}",
                resource_type="compute",
                desired_config={"cpu": 4, "memory": 8},
            )
            manager.resources[f"r{i}"] = r

        start = time.time()
        manager.take_snapshot("perf-snap")
        elapsed = time.time() - start
        assert elapsed < 1.0

    def test_restore_speed(self):
        """State restore should be fast."""
        from shared.infra.state import StateManager, Resource
        manager = StateManager()
        for i in range(200):
            r = Resource(resource_id=f"r{i}", resource_type="compute")
            manager.resources[f"r{i}"] = r

        manager.take_snapshot("restore-snap")
        manager.resources.clear()

        start = time.time()
        manager.restore_snapshot("restore-snap")
        elapsed = time.time() - start
        assert elapsed < 1.0
        assert len(manager.resources) == 200

    def test_drift_detection_speed(self):
        """Drift detection across many resources should be fast."""
        from shared.infra.state import StateManager, Resource
        manager = StateManager()
        for i in range(500):
            r = Resource(
                resource_id=f"r{i}",
                desired_config={"cpu": 4},
                actual_config={"cpu": 4 if i % 2 == 0 else 2},
            )
            manager.resources[f"r{i}"] = r

        start = time.time()
        drifted = sum(1 for rid in manager.resources if manager.detect_drift(rid))
        elapsed = time.time() - start
        assert elapsed < 1.0
        assert drifted == 250


class TestVersionVectorPerformance:
    """Tests for version vector operations performance."""

    def test_merge_many_nodes(self):
        """Version vector merge with many nodes should be fast."""
        from shared.utils.distributed import VersionVector
        vv1 = VersionVector(versions={f"n{i}": i for i in range(100)})
        vv2 = VersionVector(versions={f"n{i}": 100 - i for i in range(100)})

        start = time.time()
        for _ in range(10000):
            vv1.merge(vv2)
        elapsed = time.time() - start
        assert elapsed < 3.0

    def test_increment_speed(self):
        """Version vector increment should be fast."""
        from shared.utils.distributed import VersionVector
        vv = VersionVector()
        start = time.time()
        for i in range(100000):
            vv.increment(f"node_{i % 10}")
        elapsed = time.time() - start
        assert elapsed < 2.0

    def test_concurrency_check_speed(self):
        """Concurrency check should be fast."""
        from shared.utils.distributed import VersionVector
        vv1 = VersionVector(versions={f"n{i}": i for i in range(50)})
        vv2 = VersionVector(versions={f"n{i}": 50 - i for i in range(50)})

        start = time.time()
        for _ in range(10000):
            vv1.is_concurrent_with(vv2)
        elapsed = time.time() - start
        assert elapsed < 2.0
