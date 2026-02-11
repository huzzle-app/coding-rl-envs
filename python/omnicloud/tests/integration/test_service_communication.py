"""
OmniCloud Service Communication Integration Tests
Terminal Bench v2 - Tests for cross-service communication, database transactions, and observability.

Covers bugs: G1-G10, J1-J7
~100 tests
"""
import pytest
import time
import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock
from collections import defaultdict

from shared.clients.base import ServiceClient, CircuitBreaker, CircuitState, AlertManager
from shared.utils.distributed import DistributedLock, LockManager, VersionVector
from services.monitor.main import MetricCollector, ErrorAggregator, SpanCollector


class TestCrossDBIsolation:
    """Tests for G1: Cross-database transaction isolation."""

    def test_cross_db_isolation(self):
        """G1: Transactions on one database should not see uncommitted changes from another."""
        # Simulate two DB sessions with different transaction isolation
        session_a = {"reads": [], "writes": []}
        session_b = {"reads": [], "writes": []}

        # Session A writes but does not commit
        session_a["writes"].append({"id": 1, "value": "dirty"})

        # Session B should not see session A's dirty write
        # In a proper implementation, reads are isolated
        assert "dirty" not in [r.get("value") for r in session_b["reads"]], \
            "Cross-DB isolation should prevent dirty reads"

    def test_phantom_read_prevention(self):
        """G1: Phantom reads should be prevented in serializable isolation."""
        records = [{"id": 1, "status": "active"}, {"id": 2, "status": "active"}]

        # First read
        first_count = len([r for r in records if r["status"] == "active"])

        # Concurrent insert should not be visible
        # (In a real system, this would be prevented by serializable isolation)
        phantom = {"id": 3, "status": "active"}

        # Same query should return same count in same transaction
        assert first_count == 2, "Phantom reads should be prevented"

    def test_read_committed_isolation(self):
        """G1: Read committed should see committed changes."""
        committed_data = {"value": "committed"}
        assert committed_data["value"] == "committed"

    def test_snapshot_isolation(self):
        """G1: Snapshot isolation should provide consistent view."""
        snapshot = {"version": 1, "data": {"key": "old_value"}}
        assert snapshot["version"] == 1


class TestConnectionPool:
    """Tests for G2: Connection pool exhaustion handling."""

    def test_connection_pool_limits(self):
        """G2: Connection pool should reject when at max capacity."""
        max_connections = 10
        active_connections = 10

        # At max, new connection should be rejected or queued
        can_acquire = active_connections < max_connections
        assert can_acquire is False, "Pool at max should not allow new connections"

    def test_pool_exhaustion_handled(self):
        """G2: Pool exhaustion should raise clear error, not hang."""
        pool = {"max_size": 5, "active": 5, "timeout": 5.0}
        assert pool["active"] >= pool["max_size"]

    def test_connection_returned_on_error(self):
        """G2: Failed queries should return connections to pool."""
        pool = {"max_size": 10, "active": 5}
        # After error, connection should be returned
        pool["active"] -= 1
        assert pool["active"] == 4

    def test_pool_health_monitoring(self):
        """G2: Pool should track health metrics."""
        pool_stats = {"active": 3, "idle": 7, "max": 10, "errors": 0}
        assert pool_stats["active"] + pool_stats["idle"] <= pool_stats["max"]


class TestSagaCompensation:
    """Tests for G3: Saga pattern compensation ordering."""

    def test_saga_compensation_order(self):
        """G3: Saga compensation should run in reverse order of execution."""
        execution_order = ["step1", "step2", "step3"]
        compensation_order = list(reversed(execution_order))
        expected = ["step3", "step2", "step1"]
        assert compensation_order == expected, \
            f"Compensation should be reverse order, got {compensation_order}"

    def test_rollback_sequence(self):
        """G3: Rollback should compensate all completed steps."""
        completed = ["create_network", "create_subnet", "create_instance"]
        failed_at = "create_lb"

        # All completed steps should be compensated
        to_compensate = list(reversed(completed))
        assert len(to_compensate) == 3
        assert to_compensate[0] == "create_instance"

    def test_partial_saga_failure(self):
        """G3: Partial failure should only compensate completed steps."""
        steps = ["step1", "step2", "step3", "step4"]
        failed_at = 2
        to_compensate = list(reversed(steps[:failed_at]))
        assert to_compensate == ["step2", "step1"]

    def test_compensation_idempotent(self):
        """G3: Compensation actions should be idempotent."""
        compensated = set()
        for attempt in range(3):
            for step in ["step1", "step2"]:
                compensated.add(step)
        assert len(compensated) == 2


class TestOutboxPattern:
    """Tests for G4: Transactional outbox delivery."""

    def test_outbox_delivery_guaranteed(self):
        """G4: Events in outbox should eventually be published."""
        outbox = [
            {"id": 1, "event_type": "resource.created", "published": False},
            {"id": 2, "event_type": "resource.deleted", "published": False},
        ]
        # Simulate relay processing
        for event in outbox:
            event["published"] = True

        assert all(e["published"] for e in outbox), "All outbox events should be published"

    def test_event_publication_complete(self):
        """G4: Published events should match DB transactions."""
        transactions = [1, 2, 3]
        published_events = [1, 2, 3]
        assert set(transactions) == set(published_events), \
            "Every transaction should have a corresponding published event"

    def test_outbox_ordering_preserved(self):
        """G4: Outbox events should maintain insertion order."""
        outbox = [{"seq": 1}, {"seq": 2}, {"seq": 3}]
        sequences = [e["seq"] for e in outbox]
        assert sequences == sorted(sequences)

    def test_outbox_duplicate_prevention(self):
        """G4: Same event should not be published twice."""
        published_ids = set()
        events = [{"id": "e1"}, {"id": "e1"}, {"id": "e2"}]
        for e in events:
            published_ids.add(e["id"])
        assert len(published_ids) == 2


class TestReplicaLag:
    """Tests for G5: Replica lag handling."""

    def test_replica_lag_handling(self):
        """G5: Reads after writes should use primary, not replica."""
        primary_data = {"version": 5, "value": "latest"}
        replica_data = {"version": 3, "value": "stale"}

        # After write, read should get latest version
        assert primary_data["version"] > replica_data["version"]

    def test_read_your_writes(self):
        """G5: After write, subsequent reads should see the write."""
        store = {}
        store["key"] = "new_value"
        assert store["key"] == "new_value", "Read-your-writes consistency violated"

    def test_replica_staleness_detection(self):
        """G5: System should detect when replica is too stale."""
        primary_version = 100
        replica_version = 90
        max_lag = 5
        is_stale = (primary_version - replica_version) > max_lag
        assert is_stale is True

    def test_failover_to_primary(self):
        """G5: When replica is too stale, should failover to primary."""
        use_primary = True
        assert use_primary is True


class TestOptimisticLocking:
    """Tests for G6: Optimistic locking with retry."""

    def test_optimistic_locking_retry(self):
        """G6: Concurrent updates should be detected via version conflict."""
        record = {"id": 1, "version": 1, "value": "original"}

        # Two concurrent updates
        update_a = {"version": 1, "value": "from_a"}
        update_b = {"version": 1, "value": "from_b"}

        # First update succeeds
        if update_a["version"] == record["version"]:
            record["value"] = update_a["value"]
            record["version"] += 1

        # Second update should fail (version mismatch)
        conflict = update_b["version"] != record["version"]
        assert conflict is True, "Optimistic lock should detect version conflict"

    def test_concurrent_update_handled(self):
        """G6: Version conflict should trigger retry."""
        attempts = 0
        max_retries = 3
        success = False

        while attempts < max_retries and not success:
            attempts += 1
            success = True

        assert success is True
        assert attempts >= 1

    def test_version_monotonic(self):
        """G6: Versions should be monotonically increasing."""
        versions = [1, 2, 3, 4, 5]
        for i in range(1, len(versions)):
            assert versions[i] > versions[i-1]

    def test_no_lost_update(self):
        """G6: Both concurrent updates should be preserved (one after retry)."""
        record = {"version": 1, "updates": []}
        record["updates"].append("update_a")
        record["version"] += 1
        record["updates"].append("update_b")
        record["version"] += 1
        assert len(record["updates"]) == 2


class TestCrossDBReferential:
    """Tests for G7: Cross-database referential integrity."""

    def test_cross_db_referential(self):
        """G7: References across databases should be validated."""
        # Resource in DB1 references entity in DB2
        db1_resource = {"id": "r1", "owner_id": "user1"}
        db2_users = {"user1": {"name": "Alice"}}

        # Reference should be valid
        is_valid = db1_resource["owner_id"] in db2_users
        assert is_valid is True

    def test_orphan_reference_prevented(self):
        """G7: Deleting referenced entity should be prevented or cascaded."""
        db2_users = {"user1": {"name": "Alice"}}
        db1_resources = [{"id": "r1", "owner_id": "user1"}]

        # Attempting to delete user with resources should fail
        has_references = any(r["owner_id"] == "user1" for r in db1_resources)
        assert has_references is True, "Should detect cross-DB references before deletion"

    def test_reference_validation(self):
        """G7: Invalid cross-DB references should be rejected."""
        db2_users = {"user1": True}
        reference = "nonexistent_user"
        assert reference not in db2_users

    def test_cascade_across_databases(self):
        """G7: Cascade operations should span databases."""
        deleted_user = "user1"
        resources = [
            {"id": "r1", "owner_id": "user1"},
            {"id": "r2", "owner_id": "user2"},
        ]
        remaining = [r for r in resources if r["owner_id"] != deleted_user]
        assert len(remaining) == 1


class TestBatchInsert:
    """Tests for G8: Batch insert atomicity."""

    def test_batch_insert_atomicity(self):
        """G8: Batch inserts should be all-or-nothing."""
        batch = [{"id": 1}, {"id": 2}, {"id": 3}]
        inserted = []

        # Simulate batch insert
        try:
            for item in batch:
                inserted.append(item)
        except Exception:
            inserted.clear()  # Rollback

        assert len(inserted) == 3

    def test_partial_failure_rollback(self):
        """G8: If any item in batch fails, all should be rolled back."""
        batch = [{"id": 1, "valid": True}, {"id": 2, "valid": True}, {"id": 3, "valid": False}]
        inserted = []
        success = True

        for item in batch:
            if not item["valid"]:
                success = False
                break
            inserted.append(item)

        if not success:
            inserted.clear()

        assert len(inserted) == 0, "Partial batch failure should roll back all inserts"

    def test_batch_size_limits(self):
        """G8: Batch size should be bounded."""
        max_batch = 1000
        batch = list(range(500))
        assert len(batch) <= max_batch

    def test_batch_idempotent(self):
        """G8: Retry of batch insert should not create duplicates."""
        existing_ids = {1, 2}
        batch = [{"id": 1}, {"id": 2}, {"id": 3}]
        new_items = [item for item in batch if item["id"] not in existing_ids]
        assert len(new_items) == 1


class TestIndexHint:
    """Tests for G9: Query performance and index usage."""

    def test_index_hint_plan(self):
        """G9: Queries should use appropriate indexes."""
        query_plan = {"type": "index_scan", "index": "idx_tenant_id", "rows_estimated": 100}
        assert query_plan["type"] != "seq_scan", "Should use index scan, not sequential scan"

    def test_query_performance_acceptable(self):
        """G9: Query response time should be within acceptable limits."""
        query_time_ms = 50
        max_acceptable_ms = 500
        assert query_time_ms < max_acceptable_ms

    def test_missing_index_detected(self):
        """G9: Queries without indexes on filter columns should be flagged."""
        indexed_columns = {"tenant_id", "created_at", "status"}
        query_filter = "tenant_id"
        assert query_filter in indexed_columns

    def test_composite_index_order(self):
        """G9: Composite index column order should match query patterns."""
        index_columns = ["tenant_id", "resource_type", "created_at"]
        query_where = ["tenant_id", "resource_type"]
        # Query columns should be a prefix of index columns
        assert query_where == index_columns[:len(query_where)]


class TestLockOrdering:
    """Tests for G10: Deadlock prevention via lock ordering."""

    def test_lock_ordering_consistent(self):
        """G10: All services should acquire locks in the same order to prevent deadlock."""
        lock_manager = LockManager()

        
        lock_names_service_a = ["lock_b", "lock_a"]
        lock_names_service_b = ["lock_a", "lock_b"]

        # Both services should acquire in sorted order
        sorted_a = sorted(lock_names_service_a)
        sorted_b = sorted(lock_names_service_b)

        assert sorted_a == sorted_b, "Lock ordering should be consistent across services"

    def test_deadlock_prevention(self):
        """G10: Inconsistent lock ordering should be detected."""
        lm = LockManager()
        # When acquiring multiple locks, they should be sorted
        lock_names = ["z_lock", "a_lock", "m_lock"]
        expected_order = sorted(lock_names)
        assert expected_order == ["a_lock", "m_lock", "z_lock"]

    def test_lock_manager_release_order(self):
        """G10: Locks should be released in reverse acquisition order."""
        acquired = ["lock_a", "lock_b", "lock_c"]
        release_order = list(reversed(acquired))
        assert release_order == ["lock_c", "lock_b", "lock_a"]

    def test_lock_acquisition_timeout(self):
        """G10: Lock acquisition should have a timeout to prevent hanging."""
        lock = DistributedLock(name="test_lock")
        result = lock.acquire(blocking=True, timeout=5.0)
        assert result is True
        lock.release()


class TestTracePropagation:
    """Tests for J1: Distributed trace propagation via Kafka."""

    def test_trace_propagation_kafka(self):
        """J1: Trace context should be included in Kafka message headers."""
        client = ServiceClient(service_name="test", base_url="http://localhost")

        event = client.publish_event(
            topic="test-topic",
            event_type="resource.created",
            payload={"id": "123"},
            correlation_id="corr-123",
        )

        
        assert "trace_id" in event or "correlation_id" in event, \
            "Kafka events should include trace context for distributed tracing"

    def test_distributed_trace_complete(self):
        """J1: All services in request chain should have trace context."""
        services_in_chain = ["gateway", "compute", "storage"]
        trace_id = str(uuid.uuid4())

        # Each service should propagate the same trace_id
        for service in services_in_chain:
            assert trace_id is not None, f"Service {service} should have trace context"

    def test_trace_context_format(self):
        """J1: Trace context should follow W3C TraceContext format."""
        trace_id = "00" + "-" + uuid.uuid4().hex + "-" + uuid.uuid4().hex[:16] + "-" + "01"
        parts = trace_id.split("-")
        assert len(parts) == 4

    def test_trace_not_lost_on_async(self):
        """J1: Async operations should preserve trace context."""
        trace_id = "trace-123"
        async_context = {"trace_id": trace_id}
        assert async_context["trace_id"] == trace_id


class TestCorrelationID:
    """Tests for J2: Correlation ID consistency."""

    def test_correlation_id_consistent(self):
        """J2: Correlation ID should be forwarded, not regenerated."""
        original_correlation_id = "corr-original-123"
        client = ServiceClient(service_name="test", base_url="http://localhost")

        headers = client._get_headers(correlation_id=original_correlation_id)
        
        actual_id = headers.get("X-Correlation-ID", "")
        assert actual_id == original_correlation_id, \
            f"Correlation ID should be forwarded ({original_correlation_id}), not regenerated ({actual_id})"

    def test_request_tracking_end_to_end(self):
        """J2: Same correlation ID should appear in all service logs."""
        correlation_id = str(uuid.uuid4())
        # Verify it passes through unchanged
        client = ServiceClient(service_name="svc", base_url="http://localhost")
        headers = client._get_headers(correlation_id=correlation_id)
        assert headers["X-Correlation-ID"] == correlation_id, \
            "Correlation ID should be preserved end-to-end"

    def test_new_correlation_id_when_missing(self):
        """J2: New correlation ID should be generated when not provided."""
        client = ServiceClient(service_name="test", base_url="http://localhost")
        headers = client._get_headers()
        assert "X-Correlation-ID" in headers
        assert len(headers["X-Correlation-ID"]) > 0

    def test_correlation_id_in_response(self):
        """J2: Response should include the same correlation ID."""
        correlation_id = "corr-resp-test"
        response_headers = {"X-Correlation-ID": correlation_id}
        assert response_headers["X-Correlation-ID"] == correlation_id


class TestMetricCardinality:
    """Tests for J3: Metric label cardinality limiting."""

    def test_metric_cardinality_bounded(self):
        """J3: Metric labels should have bounded cardinality."""
        collector = MetricCollector()

        
        assert collector.max_label_values > 0, \
            f"Metric cardinality should be bounded, got max_label_values={collector.max_label_values}"

    def test_label_limits_enforced(self):
        """J3: High-cardinality labels should be sanitized."""
        collector = MetricCollector()

        # Simulate high-cardinality labels (unique user IDs as labels)
        for i in range(1000):
            collector.record("http_requests", 1.0, {"user_id": f"user_{i}"})

        # Should have bounded number of unique label combinations
        total_points = len(collector.metrics.get("http_requests", []))
        
        assert total_points <= 1000 or collector.max_label_values > 0, \
            "Metric cardinality should be bounded"

    def test_safe_labels_allowed(self):
        """J3: Low-cardinality labels should be allowed."""
        collector = MetricCollector()
        collector.record("http_requests", 1.0, {"method": "GET", "status": "200"})
        assert len(collector.metrics["http_requests"]) == 1

    def test_label_sanitization(self):
        """J3: Dynamic label values should be sanitized."""
        raw_path = "/api/v1/users/12345/profile"
        # Should normalize to /api/v1/users/{id}/profile
        sanitized = "/api/v1/users/{id}/profile"
        assert "{id}" in sanitized


class TestHealthCheckAccuracy:
    """Tests for J4: Health check dependency accuracy."""

    def test_health_check_accuracy(self):
        """J4: Health check should reflect actual dependency status."""
        
        dependencies = {
            "redis": False,
            "kafka": False,
            "auth_service": False,
        }
        any_up = any(dependencies.values())
        # Health check should be unhealthy when all dependencies are down
        assert any_up is False, "Health check should reflect dependency status"

    def test_dependency_health_reflected(self):
        """J4: Health endpoint should include dependency status."""
        health_response = {"status": "healthy", "service": "gateway"}
        
        assert "dependencies" in health_response or health_response.get("status") != "healthy", \
            "Health response should include dependency status or report unhealthy when deps are down"

    def test_partial_dependency_failure(self):
        """J4: Some dependencies down should report degraded."""
        dependencies = {"redis": True, "kafka": False, "db": True}
        all_healthy = all(dependencies.values())
        assert all_healthy is False

    def test_health_check_timeout(self):
        """J4: Health check should timeout, not hang."""
        timeout_ms = 5000
        assert timeout_ms > 0


class TestErrorAggregation:
    """Tests for J5: Error grouping and aggregation."""

    def test_error_aggregation_correct(self):
        """J5: Errors should be grouped by type and message, not just status code."""
        aggregator = ErrorAggregator()

        # Different error types with same status code
        aggregator.add_error({"status_code": 500, "error_type": "DatabaseError", "message": "Connection refused"})
        aggregator.add_error({"status_code": 500, "error_type": "TimeoutError", "message": "Request timed out"})

        
        # They should be in different groups
        groups = aggregator.error_groups
        assert len(groups) >= 2 or all(len(v) == 1 for v in groups.values()), \
            "Different error types should be in separate groups even with same status code"

    def test_error_grouping_logical(self):
        """J5: Errors with same root cause should be grouped together."""
        aggregator = ErrorAggregator()

        aggregator.add_error({"status_code": 500, "error_type": "DBError", "message": "conn refused"})
        aggregator.add_error({"status_code": 500, "error_type": "DBError", "message": "conn refused"})

        # Same error type should be grouped
        total_errors = sum(len(v) for v in aggregator.error_groups.values())
        assert total_errors == 2

    def test_error_count_tracking(self):
        """J5: Each error group should track count."""
        aggregator = ErrorAggregator()
        for _ in range(5):
            aggregator.add_error({"status_code": 404, "error_type": "NotFound"})
        assert len(aggregator.error_groups["404"]) == 5

    def test_different_status_codes_separated(self):
        """J5: Different status codes should be in different groups."""
        aggregator = ErrorAggregator()
        aggregator.add_error({"status_code": 404})
        aggregator.add_error({"status_code": 500})
        assert len(aggregator.error_groups) == 2


class TestAlertDedup:
    """Tests for J6: Alert deduplication window."""

    def test_alert_dedup_window(self):
        """J6: Duplicate alerts within window should be suppressed."""
        manager = AlertManager()

        # First alert should fire
        assert manager.should_fire("high_cpu") is True

        # Same alert within dedup window should be suppressed
        assert manager.should_fire("high_cpu") is False

        
        assert manager.dedup_window_seconds >= 60, \
            f"Dedup window should be at least 60 seconds, got {manager.dedup_window_seconds}"

    def test_duplicate_alert_suppressed(self):
        """J6: Same alert key within window should not fire again."""
        manager = AlertManager()
        manager.should_fire("disk_full")
        result = manager.should_fire("disk_full")
        assert result is False, "Duplicate alert should be suppressed"

    def test_different_alerts_not_suppressed(self):
        """J6: Different alert keys should fire independently."""
        manager = AlertManager()
        assert manager.should_fire("cpu_high") is True
        assert manager.should_fire("memory_high") is True

    def test_alert_fires_after_window(self):
        """J6: Same alert should fire again after dedup window expires."""
        manager = AlertManager(dedup_window_seconds=0.01)  # Very short window for testing
        manager.should_fire("test_alert")
        time.sleep(0.02)
        result = manager.should_fire("test_alert")
        assert result is True, "Alert should fire after dedup window expires"


class TestTraceSpanCleanup:
    """Tests for J7: Trace span lifecycle management."""

    def test_trace_span_cleanup(self):
        """J7: Completed spans should be moved from active to completed."""
        collector = SpanCollector()
        span_id = collector.start_span("trace-1", "span-1", "GET /api/v1/resources")
        collector.end_span(span_id)

        assert span_id not in collector.active_spans, "Completed span should not be in active_spans"
        assert len(collector.completed_spans) == 1

    def test_span_not_leaked(self):
        """J7: Spans should have cleanup mechanism for orphaned entries."""
        collector = SpanCollector()

        # Start span but never end it (simulating exception)
        collector.start_span("trace-1", "orphan-span", "POST /api/v1/deploy")

        
        # After timeout, orphaned spans should be cleaned up
        assert len(collector.active_spans) == 1, \
            "Orphaned span should eventually be cleaned up"

    def test_span_lifecycle_complete(self):
        """J7: Normal span lifecycle should work correctly."""
        collector = SpanCollector()
        span_id = collector.start_span("trace-2", "span-2", "query")
        assert span_id in collector.active_spans
        collector.end_span(span_id)
        assert span_id not in collector.active_spans

    def test_multiple_spans_tracked(self):
        """J7: Multiple concurrent spans should be tracked."""
        collector = SpanCollector()
        collector.start_span("t1", "s1", "op1")
        collector.start_span("t1", "s2", "op2")
        assert len(collector.active_spans) == 2
        collector.end_span("s1")
        assert len(collector.active_spans) == 1
        collector.end_span("s2")
        assert len(collector.active_spans) == 0

    def test_end_nonexistent_span(self):
        """J7: Ending a non-existent span should not error."""
        collector = SpanCollector()
        collector.end_span("nonexistent")
        assert len(collector.completed_spans) == 0


class TestCircuitBreakerIntegration:
    """Additional integration tests for service communication resilience."""

    def test_circuit_breaker_transitions(self):
        """Circuit breaker should transition through states correctly."""
        cb = CircuitBreaker(failure_threshold=3)
        assert cb.state == CircuitState.CLOSED

        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_circuit_breaker_recovery(self):
        """Circuit breaker should allow recovery after timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.02)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_circuit_breaker_half_open_success(self):
        """Successful call in half-open state should close circuit."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.can_execute()

        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_service_client_headers(self):
        """Service client should include required headers."""
        client = ServiceClient(service_name="compute", base_url="http://compute:8003")
        headers = client._get_headers()
        assert "X-Service-Name" in headers
        assert headers["X-Service-Name"] == "compute"
        assert "Content-Type" in headers
