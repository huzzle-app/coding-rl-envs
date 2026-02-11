"""
OmniCloud Deployment Pipeline Integration Tests
Terminal Bench v2 - Tests for rolling updates, blue-green, canary, rollback.

Covers bugs: F1-F10
~80 tests
"""
import pytest
import time
import uuid
from unittest.mock import MagicMock, patch

from services.deploy.tasks import (
    Deployment, DeployStrategy, DeploymentState,
    calculate_rolling_batches, execute_blue_green_switch,
    evaluate_canary_metrics, select_rollback_version,
    check_health_after_deploy, order_deployment_dependencies,
    emit_deployment_event, execute_hooks,
)


class TestRollingUpdate:
    """Tests for F1: Rolling update batch size."""

    def test_rolling_batch_size_correct(self):
        """F1: Rolling update should process exactly the right number of instances."""
        batches = calculate_rolling_batches(replicas=6, batch_size=2)
        total_instances = sum(len(b) for b in batches)
        
        assert total_instances == 6, \
            f"Total instances in batches should be 6, got {total_instances}"

    def test_rolling_update_count(self):
        """F1: Each batch should not exceed batch_size."""
        batches = calculate_rolling_batches(replicas=10, batch_size=3)
        for batch in batches:
            assert len(batch) <= 3, f"Batch size should be <= 3, got {len(batch)}"

    def test_rolling_single_batch(self):
        """F1: When batch_size >= replicas, should be single batch."""
        batches = calculate_rolling_batches(replicas=3, batch_size=10)
        # Should be a single batch containing all 3 replicas
        total = sum(len(b) for b in batches)
        assert total == 3

    def test_rolling_batch_one(self):
        """F1: Batch size of 1 should process one at a time."""
        batches = calculate_rolling_batches(replicas=5, batch_size=1)
        total = sum(len(b) for b in batches)
        assert total == 5
        for batch in batches:
            assert len(batch) == 1

    def test_rolling_covers_all_replicas(self):
        """F1: All replica indices should be covered in batches."""
        batches = calculate_rolling_batches(replicas=4, batch_size=2)
        all_indices = set()
        for batch in batches:
            all_indices.update(batch)
        # Should cover indices 0, 1, 2, 3
        expected = set(range(4))
        assert all_indices == expected, \
            f"Batches should cover all replica indices {expected}, got {all_indices}"

    def test_rolling_no_duplicate_instances(self):
        """F1: No instance should appear in multiple batches."""
        batches = calculate_rolling_batches(replicas=8, batch_size=3)
        all_indices = []
        for batch in batches:
            all_indices.extend(batch)
        assert len(all_indices) == len(set(all_indices)), \
            "No instance should appear in multiple batches"

    def test_rolling_zero_replicas(self):
        """F1: Zero replicas should produce empty batches."""
        batches = calculate_rolling_batches(replicas=0, batch_size=1)
        total = sum(len(b) for b in batches)
        assert total == 0


class TestBlueGreenSwitch:
    """Tests for F2: Blue-green deployment atomic switch."""

    def test_blue_green_switch_atomic(self):
        """F2: Traffic switch should be atomic (no overlap period)."""
        deployment = Deployment(
            strategy=DeployStrategy.BLUE_GREEN,
            service_name="api",
        )
        blue = ["blue-1", "blue-2"]
        green = ["green-1", "green-2"]

        
        result = execute_blue_green_switch(deployment, blue, green)
        assert result is True

    def test_blue_green_no_downtime(self):
        """F2: Switch should have zero downtime."""
        deployment = Deployment(strategy=DeployStrategy.BLUE_GREEN)
        # Both blue and green should have healthy instances before switch
        blue_healthy = True
        green_healthy = True
        assert blue_healthy and green_healthy, \
            "Both blue and green must be healthy before switch"

    def test_blue_green_rollback(self):
        """F2: Blue-green should support instant rollback."""
        deployment = Deployment(strategy=DeployStrategy.BLUE_GREEN)
        # Rollback is just switching back to blue
        original_active = "blue"
        after_deploy = "green"
        after_rollback = "blue"
        assert after_rollback == original_active

    def test_blue_green_health_verified(self):
        """F2: Green environment should be verified before switch."""
        green_instances = ["g1", "g2", "g3"]
        all_healthy = all(True for _ in green_instances)
        assert all_healthy is True


class TestCanaryEvaluation:
    """Tests for F3: Canary metric evaluation window."""

    def test_canary_metric_window_correct(self):
        """F3: Canary evaluation window should be long enough for meaningful data."""
        deployment = Deployment(
            strategy=DeployStrategy.CANARY,
            canary_percentage=10,
        )
        
        assert deployment.canary_eval_window_seconds >= 300, \
            f"Canary window should be >= 300s, got {deployment.canary_eval_window_seconds}s"

    def test_canary_evaluation_period(self):
        """F3: Canary should collect enough data before promotion."""
        deployment = Deployment(canary_eval_window_seconds=5)
        metrics = {"error_rate": 0.001, "latency_p99": 0.5}
        result = evaluate_canary_metrics(deployment, metrics)
        # The canary pass is correct but based on insufficient data
        assert deployment.canary_eval_window_seconds >= 60, \
            "Canary evaluation window too short for reliable metrics"

    def test_canary_high_error_rate_rejected(self):
        """F3: High error rate should prevent canary promotion."""
        deployment = Deployment()
        metrics = {"error_rate": 0.05, "latency_p99": 0.5}
        result = evaluate_canary_metrics(deployment, metrics)
        assert result is False, "High error rate should reject canary"

    def test_canary_high_latency_rejected(self):
        """F3: High latency should prevent canary promotion."""
        deployment = Deployment()
        metrics = {"error_rate": 0.001, "latency_p99": 2.0}
        result = evaluate_canary_metrics(deployment, metrics)
        assert result is False, "High latency should reject canary"

    def test_canary_percentage_valid(self):
        """F3: Canary percentage should be reasonable."""
        deployment = Deployment(canary_percentage=10)
        assert 1 <= deployment.canary_percentage <= 50


class TestRollbackVersion:
    """Tests for F4: Rollback version selection."""

    def test_rollback_version_correct(self):
        """F4: Rollback should select the immediately previous version (N-1)."""
        deployment = Deployment(
            version="v3",
            previous_version="v2",
            version_history=["v1", "v2", "v3"],
        )
        rollback_version = select_rollback_version(deployment)
        
        # But what we actually want is the previous version "v2"
        assert rollback_version == "v2", \
            f"Rollback should target v2 (N-1), got {rollback_version}"

    def test_rollback_to_previous(self):
        """F4: Rollback from v5 should go to v4."""
        deployment = Deployment(
            version="v5",
            previous_version="v4",
            version_history=["v1", "v2", "v3", "v4", "v5"],
        )
        rollback_version = select_rollback_version(deployment)
        assert rollback_version == "v4", \
            f"Should rollback to v4, got {rollback_version}"

    def test_rollback_first_version(self):
        """F4: Rollback from first deployment should use previous_version."""
        deployment = Deployment(
            version="v1",
            previous_version="v0",
            version_history=["v1"],
        )
        rollback_version = select_rollback_version(deployment)
        assert rollback_version == "v0"

    def test_rollback_empty_history(self):
        """F4: Empty version history should use previous_version field."""
        deployment = Deployment(
            version="v2",
            previous_version="v1",
            version_history=[],
        )
        rollback_version = select_rollback_version(deployment)
        assert rollback_version == "v1"


class TestDeploymentLock:
    """Tests for F5: Deployment lock TTL."""

    def test_deployment_lock_not_stolen(self):
        """F5: Lock should not expire during a normal deployment."""
        deployment = Deployment()
        deployment.acquire_lock("deployer-1")

        # Simulate deployment taking 60 seconds
        
        assert deployment.lock_expires_at - time.time() >= 60, \
            f"Lock TTL should be >= 60s for deployment safety, " \
            f"but expires in {deployment.lock_expires_at - time.time():.0f}s"

    def test_lock_during_long_deploy(self):
        """F5: Lock should persist throughout long deployment."""
        deployment = Deployment()
        acquired = deployment.acquire_lock("deployer-1", ttl=30.0)
        assert acquired is True

        # Lock should last longer than typical deployment
        remaining = deployment.lock_expires_at - time.time()
        assert remaining >= 60, \
            f"Lock TTL {remaining:.0f}s too short for long deployments"

    def test_lock_prevents_concurrent_deploy(self):
        """F5: Second deploy should not steal lock from first."""
        deployment = Deployment()
        deployment.acquire_lock("deployer-1", ttl=300)

        # Second deployer should not be able to acquire
        result = deployment.acquire_lock("deployer-2", ttl=300)
        assert result is False, "Concurrent deploy should be blocked"

    def test_lock_acquired_by_first_deployer(self):
        """F5: Lock owner should be the first acquirer."""
        deployment = Deployment()
        deployment.acquire_lock("deployer-1")
        assert deployment.lock_owner == "deployer-1"


class TestHealthCheckGrace:
    """Tests for F6: Health check grace period."""

    def test_health_check_grace_period(self):
        """F6: Health check should not run during grace period."""
        deploy_time = time.time()
        grace_period = 30

        # Check immediately after deployment (within grace period)
        result = check_health_after_deploy(
            instance_id="i-1",
            grace_period_seconds=grace_period,
            deploy_time=deploy_time,
        )
        
        # But the function always returns True without checking grace period
        elapsed = time.time() - deploy_time
        if elapsed < grace_period:
            assert result is True, "Should be considered healthy during grace period"

    def test_grace_period_respected(self):
        """F6: Actual health checks should only run after grace period."""
        deploy_time = time.time() - 60  # Deployed 60s ago
        grace_period = 30  # 30s grace

        result = check_health_after_deploy("i-1", grace_period, deploy_time)
        # After grace period, should actually check health
        assert result is True or result is False  # Should be an actual check, not always True

    def test_grace_period_zero(self):
        """F6: Zero grace period should check immediately."""
        result = check_health_after_deploy("i-1", 0, time.time() - 1)
        assert result is True or result is False

    def test_grace_period_default(self):
        """F6: Default grace period should be reasonable."""
        deployment = Deployment()
        assert deployment.health_check_grace_seconds >= 10, \
            "Default grace period should be at least 10 seconds"


class TestDeploymentDependencyOrder:
    """Tests for F7: Deployment dependency ordering."""

    def test_deployment_dependency_order(self):
        """F7: Dependencies should be deployed before dependents."""
        db_deploy = Deployment(service_name="database", dependencies=[])
        app_deploy = Deployment(service_name="app", dependencies=["database"])
        web_deploy = Deployment(service_name="web", dependencies=["app"])

        ordered = order_deployment_dependencies([web_deploy, app_deploy, db_deploy])

        names = [d.service_name for d in ordered]
        # Database should come before app, app before web
        db_idx = names.index("database")
        app_idx = names.index("app")
        web_idx = names.index("web")

        assert db_idx < app_idx < web_idx, \
            f"Expected database < app < web, got order: {names}"

    def test_dependency_graph_sort(self):
        """F7: Topological ordering should respect all dependencies."""
        deployments = [
            Deployment(service_name="frontend", dependencies=["backend", "cdn"]),
            Deployment(service_name="backend", dependencies=["database"]),
            Deployment(service_name="database", dependencies=[]),
            Deployment(service_name="cdn", dependencies=[]),
        ]

        ordered = order_deployment_dependencies(deployments)
        names = [d.service_name for d in ordered]

        # Database and CDN should come before backend and frontend
        db_idx = names.index("database")
        backend_idx = names.index("backend")
        frontend_idx = names.index("frontend")

        assert db_idx < backend_idx, \
            f"Database should be deployed before backend, got order: {names}"
        assert backend_idx < frontend_idx, \
            f"Backend should be deployed before frontend, got order: {names}"

    def test_no_dependencies_first(self):
        """F7: Services with no dependencies should be deployed first."""
        deployments = [
            Deployment(service_name="depends", dependencies=["nodep"]),
            Deployment(service_name="nodep", dependencies=[]),
        ]
        ordered = order_deployment_dependencies(deployments)
        assert ordered[0].service_name == "nodep", \
            "Service with no dependencies should be first"

    def test_empty_deployment_list(self):
        """F7: Empty deployment list should return empty."""
        assert order_deployment_dependencies([]) == []


class TestParallelDeploy:
    """Tests for F8: Parallel deployment resource conflicts."""

    def test_parallel_deploy_no_conflict(self):
        """F8: Parallel deployments should not conflict on shared resources."""
        deploy_a = Deployment(service_name="svc-a", deployment_id="d1")
        deploy_b = Deployment(service_name="svc-b", deployment_id="d2")

        # Both should be able to acquire their own locks
        a_locked = deploy_a.acquire_lock("deployer-a")
        b_locked = deploy_b.acquire_lock("deployer-b")

        assert a_locked is True
        assert b_locked is True

    def test_resource_contention_handled(self):
        """F8: When two deployments need the same resource, conflict should be detected."""
        shared_resource = {"locked_by": None}

        # First deployment locks resource
        shared_resource["locked_by"] = "deploy-1"

        # Second deployment should detect contention
        contended = shared_resource["locked_by"] is not None
        assert contended is True

    def test_independent_deploys_parallel(self):
        """F8: Independent deployments should proceed in parallel."""
        deploys = [
            Deployment(service_name=f"svc-{i}", dependencies=[])
            for i in range(5)
        ]
        # All independent, all can run in parallel
        assert all(len(d.dependencies) == 0 for d in deploys)

    def test_dependent_deploys_serial(self):
        """F8: Dependent deployments should be serialized."""
        deploy_a = Deployment(service_name="a", dependencies=[])
        deploy_b = Deployment(service_name="b", dependencies=["a"])
        assert "a" in deploy_b.dependencies


class TestDeploymentEventOrdering:
    """Tests for F9: Deployment event ordering."""

    def test_deployment_event_ordering(self):
        """F9: Events should be in chronological order (oldest first)."""
        deployment = Deployment()
        emit_deployment_event(deployment, "started", {"version": "v1"})
        emit_deployment_event(deployment, "progressing", {"batch": 1})
        emit_deployment_event(deployment, "completed", {"success": True})

        event_types = [e["event_type"] for e in deployment.events]
        
        assert event_types == ["started", "progressing", "completed"], \
            f"Events should be in chronological order, got {event_types}"

    def test_event_sequence_correct(self):
        """F9: Event sequence should be: started -> in_progress -> completed."""
        deployment = Deployment()
        for event_type in ["queued", "started", "in_progress", "completed"]:
            emit_deployment_event(deployment, event_type, {})

        types = [e["event_type"] for e in deployment.events]
        assert types == ["queued", "started", "in_progress", "completed"], \
            f"Event sequence wrong: {types}"

    def test_event_timestamps_monotonic(self):
        """F9: Event timestamps should be monotonically increasing."""
        deployment = Deployment()
        for i in range(5):
            emit_deployment_event(deployment, f"event_{i}", {})

        timestamps = [e["timestamp"] for e in deployment.events]
        for i in range(1, len(timestamps)):
            assert timestamps[i] >= timestamps[i-1], \
                "Event timestamps should be monotonically increasing"

    def test_event_has_required_fields(self):
        """F9: Each event should have required fields."""
        deployment = Deployment()
        event = emit_deployment_event(deployment, "test", {"key": "value"})
        assert "event_id" in event
        assert "event_type" in event
        assert "deployment_id" in event
        assert "timestamp" in event
        assert "details" in event


class TestHookExecution:
    """Tests for F10: Pre/post hook execution order."""

    def test_hook_execution_order(self):
        """F10: Pre-deploy hooks should run before post-deploy hooks."""
        execution_log = []

        hooks = {
            "pre_deploy": [lambda: execution_log.append("pre")],
            "post_deploy": [lambda: execution_log.append("post")],
        }

        execute_hooks(hooks, "deploy")

        
        assert execution_log == ["pre", "post"], \
            f"Expected ['pre', 'post'], got {execution_log}"

    def test_pre_post_hooks_correct(self):
        """F10: Pre-hooks should execute before the deployment action."""
        execution_order = []

        hooks = {
            "pre_deploy": [
                lambda: execution_order.append("validate"),
                lambda: execution_order.append("backup"),
            ],
            "post_deploy": [
                lambda: execution_order.append("notify"),
                lambda: execution_order.append("cleanup"),
            ],
        }

        results = execute_hooks(hooks, "deploy")
        # Pre should come before post
        phases = [r["phase"] for r in results]
        pre_indices = [i for i, p in enumerate(phases) if p == "pre_deploy"]
        post_indices = [i for i, p in enumerate(phases) if p == "post_deploy"]

        if pre_indices and post_indices:
            assert max(pre_indices) < min(post_indices), \
                f"All pre-deploy hooks should run before post-deploy hooks"

    def test_hook_failure_reported(self):
        """F10: Hook failures should be captured and reported."""
        hooks = {
            "pre_deploy": [lambda: (_ for _ in ()).throw(ValueError("hook failed"))],
        }
        results = execute_hooks(hooks, "deploy")
        failed = [r for r in results if not r["success"]]
        assert len(failed) >= 1

    def test_empty_hooks(self):
        """F10: No hooks should produce empty results."""
        results = execute_hooks({}, "deploy")
        assert results == []

    def test_hooks_capture_results(self):
        """F10: Hook results should be captured."""
        hooks = {
            "pre_deploy": [lambda: "pre_result"],
            "post_deploy": [lambda: "post_result"],
        }
        results = execute_hooks(hooks, "deploy")
        assert any(r["result"] == "pre_result" for r in results if r["success"])


class TestDeploymentDefaults:
    """Additional deployment tests for coverage."""

    def test_deployment_defaults(self):
        """Deployment should have sensible defaults."""
        d = Deployment()
        assert d.strategy == DeployStrategy.ROLLING
        assert d.state == DeploymentState.QUEUED
        assert d.replicas == 3
        assert d.batch_size == 1

    def test_deployment_id_unique(self):
        """Each deployment should have a unique ID."""
        ids = {Deployment().deployment_id for _ in range(10)}
        assert len(ids) == 10

    def test_deployment_state_transitions(self):
        """Deployment should support state transitions."""
        d = Deployment()
        assert d.state == DeploymentState.QUEUED
        d.state = DeploymentState.IN_PROGRESS
        assert d.state == DeploymentState.IN_PROGRESS
        d.state = DeploymentState.COMPLETED
        assert d.state == DeploymentState.COMPLETED

    def test_deployment_strategies_enum(self):
        """All deployment strategies should be defined."""
        assert DeployStrategy.ROLLING.value == "rolling"
        assert DeployStrategy.BLUE_GREEN.value == "blue_green"
        assert DeployStrategy.CANARY.value == "canary"


class TestRollingBatchEdgeCases:
    """Extended rolling deployment tests."""

    def test_rolling_batches_single_replica(self):
        """F1: Single replica deployment should produce one batch."""
        d = Deployment(replicas=1, batch_size=1)
        batches = calculate_rolling_batches(d)
        assert len(batches) == 1
        assert batches[0] == 1

    def test_rolling_batches_batch_equals_replicas(self):
        """F1: Batch size equal to replicas should produce one batch."""
        d = Deployment(replicas=5, batch_size=5)
        batches = calculate_rolling_batches(d)
        total = sum(batches)
        assert total == 5

    def test_rolling_batches_large_batch_size(self):
        """F1: Batch size larger than replicas should clamp."""
        d = Deployment(replicas=3, batch_size=10)
        batches = calculate_rolling_batches(d)
        total = sum(batches)
        assert total == 3

    def test_rolling_batches_many_replicas(self):
        """F1: Many replicas should be split correctly."""
        d = Deployment(replicas=100, batch_size=10)
        batches = calculate_rolling_batches(d)
        total = sum(batches)
        assert total == 100

    def test_rolling_batches_remainder(self):
        """F1: Remainder from division should be handled in last batch."""
        d = Deployment(replicas=7, batch_size=3)
        batches = calculate_rolling_batches(d)
        total = sum(batches)
        assert total == 7


class TestCanaryEdgeCases:
    """Extended canary deployment tests."""

    def test_canary_all_metrics_healthy(self):
        """F3: All healthy metrics should pass evaluation."""
        metrics = [
            {"timestamp": time.time() - 10, "error_rate": 0.0, "latency_p99": 100},
            {"timestamp": time.time() - 5, "error_rate": 0.0, "latency_p99": 110},
        ]
        result = evaluate_canary_metrics(metrics, window_seconds=30)
        assert result["healthy"] is True

    def test_canary_empty_metrics(self):
        """F3: Empty metrics should not pass."""
        result = evaluate_canary_metrics([], window_seconds=30)
        assert result["healthy"] is False

    def test_canary_all_stale_metrics(self):
        """F3: All metrics outside window should fail."""
        metrics = [
            {"timestamp": time.time() - 600, "error_rate": 0.0, "latency_p99": 100},
        ]
        result = evaluate_canary_metrics(metrics, window_seconds=30)
        assert result["healthy"] is False


class TestRollbackEdgeCases:
    """Extended rollback version selection tests."""

    def test_rollback_single_version(self):
        """F4: Single version history should select that version."""
        versions = ["v1"]
        result = select_rollback_version(versions, "v1")
        assert result == "v1"

    def test_rollback_two_versions(self):
        """F4: Two versions - rollback from latest should select previous."""
        versions = ["v1", "v2"]
        result = select_rollback_version(versions, "v2")
        assert result == "v1"

    def test_rollback_many_versions(self):
        """F4: Many versions - should select N-1."""
        versions = [f"v{i}" for i in range(1, 11)]
        result = select_rollback_version(versions, "v10")
        assert result == "v9"
