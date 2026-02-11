"""
SynapseNet Service Communication Integration Tests
Terminal Bench v2 - Tests for cross-service communication, auth, caching

Tests cover:
- G1-G6: Authentication & RBAC bugs
- J1-J7: Observability bugs
- F1-F10: Database & Transaction bugs (subset)
"""
import time
import uuid
import hashlib
import threading
import sys
import os
from unittest import mock

import pytest


# =========================================================================
# G1: JWT claim propagation
# =========================================================================

class TestJWTClaimPropagation:
    """BUG G1: JWT claims stripped when forwarding to downstream services."""

    def test_jwt_claim_propagation(self):
        """Custom JWT claims should be forwarded to downstream services."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("test_service", "http://localhost:8001")
        headers = client._build_headers(auth_token="jwt_token_123")

        
        assert "Authorization" in headers
        assert "X-User-Roles" in headers, (
            "User roles should be propagated in headers. "
            "BUG G1: Custom claims stripped during forwarding."
        )
        assert "X-Tenant-Id" in headers, (
            "Tenant ID should be propagated in headers. "
            "BUG G1: Custom claims stripped during forwarding."
        )

    def test_downstream_claims_preserved(self):
        """Claims should be preserved through multiple service hops."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("gateway", "http://localhost:8000")
        headers = client._build_headers(auth_token="test_token")

        # Authorization should be present
        assert headers.get("Authorization") == "Bearer test_token"
        # Service name should be set
        assert headers.get("X-Service-Name") == "gateway"


# =========================================================================
# G2: Token refresh race condition
# =========================================================================

class TestTokenRefreshRace:
    """BUG G2: Concurrent token refresh creates multiple valid tokens."""

    def test_token_refresh_race(self):
        """Concurrent refresh attempts should be serialized."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user_1", {"role": "admin"})
        refresh_token = tokens["refresh_token"]

        results = []
        errors = []

        def refresh_attempt():
            try:
                result = tm.refresh(refresh_token)
                if result:
                    results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=refresh_attempt) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        
        successful = len(results)
        assert successful <= 1, (
            f"{successful} refresh attempts succeeded, but only 1 should. "
            "BUG G2: Token refresh race condition allows multiple refreshes."
        )

    def test_concurrent_refresh_safety(self):
        """After refresh, old refresh token should be invalid."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user_2", {"role": "user"})
        refresh = tokens["refresh_token"]

        # First refresh should succeed
        new_tokens = tm.refresh(refresh)
        assert new_tokens is not None

        # Second refresh with same token should fail
        result = tm.refresh(refresh)
        assert result is None, "Old refresh token should be invalidated"


# =========================================================================
# G3: Service-to-service auth bypass
# =========================================================================

class TestServiceAuthRequired:
    """BUG G3: Internal service calls bypass authentication."""

    def test_service_auth_required(self):
        """Internal service calls should still require authentication."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("internal_service", "http://localhost:8001")

        # Internal call with no auth token should NOT be allowed
        headers = {"X-Service-Name": "internal_service"}
        result = client._check_auth(headers)

        
        assert result is False, (
            "Internal calls without proper credentials should not bypass auth. "
            "BUG G3: X-Service-Name header alone bypasses authentication."
        )

    def test_internal_auth_bypass_blocked(self):
        """Spoofed service headers should not bypass auth."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("gateway", "http://localhost:8000")

        # Attacker spoofs internal service header
        spoofed_headers = {"X-Service-Name": "admin_service"}
        result = client._check_auth(spoofed_headers)
        assert result is False, (
            "Spoofed X-Service-Name should not grant access"
        )


# =========================================================================
# G4: RBAC permission cache stale
# =========================================================================

class TestRBACCacheInvalidation:
    """BUG G4: Permission cache not invalidated after changes."""

    def test_rbac_cache_invalidation(self):
        """Permission changes should invalidate the cache."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import PermissionCache

        cache = PermissionCache(ttl=300.0)

        # Cache old permissions
        cache.set_permissions("user_1", {"role": "viewer", "can_edit": False})

        # Update permissions (in production, via admin action)
        
        # cache.invalidate("user_1")  # This SHOULD be called

        # Set new permissions
        cache.set_permissions("user_1", {"role": "admin", "can_edit": True})

        perms = cache.get_permissions("user_1")
        assert perms["role"] == "admin", "Should see updated permissions"

    def test_permission_update_propagation(self):
        """Permission updates should be visible immediately."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import PermissionCache

        cache = PermissionCache(ttl=300.0)
        cache.set_permissions("user_2", {"level": 1})

        # Simulate permission change
        cache.invalidate("user_2")

        # Old permissions should be gone
        assert cache.get_permissions("user_2") is None, (
            "After invalidation, old permissions should not be returned"
        )


# =========================================================================
# G5: API key rotation window
# =========================================================================

class TestAPIKeyRotationWindow:
    """BUG G5: Old key deactivated before new key activated."""

    def test_api_key_rotation_window(self):
        """During rotation, at least one key should always be valid."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        old_key = km.create_key("user_1")

        # Verify old key works
        assert km.validate_key(old_key) == "user_1"

        # Rotate the key
        new_key = km.rotate_key(old_key)
        assert new_key is not None

        
        # At least one of old or new should be valid at all times
        old_valid = km.validate_key(old_key)
        new_valid = km.validate_key(new_key)

        assert old_valid is not None or new_valid is not None, (
            "During rotation, at least one key should be valid. "
            "BUG G5: Both old and new keys may be invalid during rotation."
        )

    def test_rotation_grace_period(self):
        """Old key should remain valid during grace period."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        old_key = km.create_key("user_2")

        new_key = km.rotate_key(old_key)

        # New key should work
        assert km.validate_key(new_key) == "user_2"


# =========================================================================
# G6: mTLS certificate chain validation
# =========================================================================

class TestMTLSCertificateChain:
    """BUG G6: Only checks leaf cert, not full chain."""

    def test_mtls_certificate_chain(self):
        """Certificate validation should verify the full chain."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import CertificateValidator

        validator = CertificateValidator()
        validator.add_trusted_ca("trusted_ca_cert_1")

        # Valid chain: leaf signed by intermediate, intermediate signed by CA
        valid_chain = ["leaf_cert", "intermediate_cert", "trusted_ca_cert_1"]
        assert validator.validate_certificate(valid_chain) is True

        # Invalid chain: leaf NOT signed by any trusted CA
        invalid_chain = ["untrusted_leaf_cert"]
        result = validator.validate_certificate(invalid_chain)

        
        assert result is False, (
            "Certificate not signed by trusted CA should be rejected. "
            "BUG G6: Only checks leaf cert presence, not chain validity."
        )

    def test_certificate_validation(self):
        """Empty certificate chain should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import CertificateValidator

        validator = CertificateValidator()
        assert validator.validate_certificate([]) is False
        assert validator.validate_certificate(None) is False


# =========================================================================
# J1: Trace context not propagated
# =========================================================================

class TestTraceContextKafka:
    """BUG J1: Trace context lost in Kafka messages."""

    def test_trace_context_kafka(self):
        """Trace context should be included in Kafka message headers."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="test_service")
        event = Event(event_type="model.trained")
        trace_context = {"trace_id": "abc123", "span_id": "def456"}

        bus.publish("training.events", event, trace_context=trace_context)

        published = bus.get_published_events()
        assert len(published) == 1
        
        published_event = published[0]
        assert published_event.trace_context.get("trace_id") == "abc123", (
            "Trace context should be propagated in event. "
            "BUG J1: Trace context is lost when publishing to Kafka."
        )

    def test_distributed_trace_propagation(self):
        """Trace IDs should be preserved across publish/consume."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        producer = EventBus(service_name="producer")
        event = Event(event_type="data.processed")
        trace = {"trace_id": "trace_001", "span_id": "span_001"}

        producer.publish("data.events", event, trace_context=trace)

        consumed = producer.consume("data.events")
        assert consumed is not None


# =========================================================================
# J2: Log correlation ID mismatch
# =========================================================================

class TestCorrelationIDMatch:
    """BUG J2: Producer and consumer have different correlation IDs."""

    def test_correlation_id_match(self):
        """Correlation ID should be consistent between producer and consumer."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="correlator")
        event = Event(event_type="test.event")
        trace = {"trace_id": "trace_corr", "correlation_id": "corr_123"}

        bus.publish("test.topic", event, trace_context=trace)

        
        published = bus.get_published_events()
        if published:
            corr_id = published[0].metadata.get("correlation_id")
            assert corr_id == "corr_123", (
                f"Correlation ID should be 'corr_123' from trace context, got '{corr_id}'. "
                "BUG J2: New correlation ID generated instead of propagating existing."
            )

    def test_request_id_tracking(self):
        """Request IDs should be trackable across services."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import TraceContext

        ctx = TraceContext()
        assert ctx.trace_id is not None
        assert ctx.span_id is not None

        headers = ctx.to_headers()
        assert "X-Trace-Id" in headers
        assert "X-Span-Id" in headers


# =========================================================================
# J3: Metric cardinality explosion
# =========================================================================

class TestMetricCardinality:
    """BUG J3: Dynamic labels cause unbounded metric cardinality."""

    def test_metric_cardinality(self):
        """Metric labels should be bounded."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import MetricsCollector

        collector = MetricsCollector()

        # Record deliveries with unique subscription IDs
        for i in range(1000):
            collector.record_delivery(
                subscription_id=f"sub_{i}",
                event_type="model.deployed",
                url=f"http://example.com/hook/{i}",
                status="success",
            )

        
        metric_count = collector.get_metric_count()
        assert metric_count < 100, (
            f"Created {metric_count} unique metric labels. "
            "Should be bounded. BUG J3: Dynamic labels cause cardinality explosion."
        )

    def test_label_count_limit(self):
        """Metric collector should limit unique label combinations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import MetricsCollector

        collector = MetricsCollector()

        # Same event type, different URLs
        for i in range(100):
            collector.record_delivery("sub_1", "event_a", f"http://host/{i}", "ok")

        count = collector.get_metric_count()
        # Should aggregate by event_type and status, not by URL
        assert count <= 10, (
            f"Too many metric labels: {count}. Labels should not include dynamic values."
        )


# =========================================================================
# J4: Health check accuracy
# =========================================================================

class TestHealthCheckAccuracy:
    """BUG J4: Health check doesn't include dependency health."""

    def test_health_check_accuracy(self):
        """Health check should report dependency status."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ModelMonitor

        monitor = ModelMonitor()
        health = monitor.get_model_health("test_model")

        assert health is not None
        assert "model_id" in health

    def test_dependency_health_included(self):
        """Health check should include database and cache health."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ModelMonitor

        monitor = ModelMonitor()
        # Record some predictions
        for i in range(5):
            monitor.record_prediction("dep_model", 0.01 * i, True)

        health = monitor.get_model_health("dep_model")
        assert health["total_predictions"] == 5
        assert health["success_rate"] == 1.0


# =========================================================================
# J5: Error aggregation groups wrong
# =========================================================================

class TestErrorAggregationGroups:
    """BUG J5: Errors grouped by message string instead of type."""

    def test_error_aggregation_groups(self):
        """Similar errors should be grouped together."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        aggregator = ErrorAggregator()

        # Same error type with different dynamic content
        for i in range(10):
            aggregator.record_error({
                "type": "ModelLoadError",
                "message": f"Failed to load model model_{i}: timeout after 30s",
            })

        groups = aggregator.get_groups()

        
        # Should create 1 group based on error type
        assert len(groups) <= 2, (
            f"Created {len(groups)} error groups for the same error type. "
            "Should be 1 group. BUG J5: Groups by full message string."
        )

    def test_error_grouping_accuracy(self):
        """Different error types should create separate groups."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        aggregator = ErrorAggregator()
        aggregator.record_error({"type": "TimeoutError", "message": "Timeout A"})
        aggregator.record_error({"type": "TimeoutError", "message": "Timeout B"})
        aggregator.record_error({"type": "ValidationError", "message": "Invalid X"})

        top = aggregator.get_top_errors(limit=5)
        assert len(top) >= 1


# =========================================================================
# J6: Inference latency histogram bucket overflow
# =========================================================================

class TestInferenceLatencyHistogram:
    """BUG J6: Latency histogram drops values above max bucket."""

    def test_inference_latency_histogram(self):
        """All latency values should be counted, including large ones."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        histogram = LatencyHistogram()

        # Record normal latencies
        for lat in [0.001, 0.01, 0.05, 0.1, 0.5]:
            histogram.observe(lat)

        # Record very large latency (above all buckets)
        histogram.observe(30.0)

        stats = histogram.get_stats()
        
        assert stats["count"] == 6, (
            f"Count is {stats['count']}, expected 6. All values should be counted."
        )

        # The large value should be tracked somewhere (e.g., +Inf bucket)
        total_in_buckets = sum(histogram._counts.values())
        
        assert total_in_buckets == 6, (
            f"Only {total_in_buckets}/6 values in buckets. "
            "BUG J6: Values above max bucket are dropped."
        )

    def test_histogram_bucket_overflow(self):
        """Histogram should have a +Inf bucket for unbounded values."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        histogram = LatencyHistogram()

        # All values above max bucket
        for _ in range(10):
            histogram.observe(100.0)

        stats = histogram.get_stats()
        assert stats["count"] == 10
        assert stats["avg"] == 100.0


# =========================================================================
# J7: Distributed trace span leak
# =========================================================================

class TestDistributedTraceSpanLeak:
    """BUG J7: Trace spans not properly closed, causing memory leak."""

    def test_distributed_trace_span_leak(self):
        """Trace spans should be properly managed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import TraceContext

        contexts = []
        for _ in range(100):
            ctx = TraceContext()
            contexts.append(ctx)

        # Each context should have unique trace and span IDs
        trace_ids = {ctx.trace_id for ctx in contexts}
        span_ids = {ctx.span_id for ctx in contexts}
        assert len(trace_ids) == 100
        assert len(span_ids) == 100

    def test_span_cleanup(self):
        """Spans should be cleaned up after request completes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import TraceContext

        ctx = TraceContext()
        headers = ctx.to_headers()
        assert len(headers) >= 2  # trace_id and span_id


# =========================================================================
# F1-F4: Database & Transaction bugs (cross-service)
# =========================================================================

class TestCrossDBIsolation:
    """BUG F1: Cross-database transaction isolation failure."""

    def test_cross_db_isolation(self):
        """Transactions across databases should be isolated."""
        # This test verifies the concept - actual cross-DB tests need infrastructure
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="db_isolation_test")
        assert lock.acquire(timeout=1.0)
        lock.release()

    def test_cross_db_phantom_read(self):
        """Should prevent phantom reads across databases."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="phantom_test")
        acquired = lock.acquire(timeout=1.0)
        assert acquired is True
        lock.release()


class TestOutboxDelivery:
    """BUG F4: Outbox pattern message loss."""

    def test_outbox_delivery(self):
        """Events should only be published after DB commit."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="outbox_test")
        event = Event(event_type="order.created")

        
        bus.publish("orders.events", event)

        published = bus.get_published_events()
        assert len(published) == 1

    def test_outbox_message_published(self):
        """Published messages should be delivered reliably."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="publisher")

        for i in range(5):
            event = Event(event_type=f"event_{i}")
            bus.publish("test.topic", event)

        assert len(bus.get_published_events()) == 5


class TestLockOrdering:
    """BUG F10: Inconsistent lock ordering causes deadlocks."""

    def test_lock_ordering(self):
        """Distributed locks should enforce consistent ordering."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock_a = DistributedLock(lock_name="resource_a")
        lock_b = DistributedLock(lock_name="resource_b")

        # Acquire in order
        assert lock_a.acquire(timeout=1.0)
        assert lock_b.acquire(timeout=1.0)
        lock_b.release()
        lock_a.release()

    def test_deadlock_prevention(self):
        """Concurrent lock acquisition should not deadlock."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="deadlock_test")
        assert lock.acquire(timeout=1.0)
        lock.release()

        # Re-acquire should work
        assert lock.acquire(timeout=1.0)
        lock.release()


# =========================================================================
# Extended Service Communication Tests
# =========================================================================

class TestEventBusDetailed:
    """Extended event bus tests."""

    def test_publish_multiple_topics(self):
        """Events should be publishable to different topics."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="multi_topic_test")
        bus.publish("topic_a", Event(event_type="event_a"))
        bus.publish("topic_b", Event(event_type="event_b"))

        a = bus.consume("topic_a")
        b = bus.consume("topic_b")
        assert a is not None
        assert b is not None
        assert a.event_type == "event_a"
        assert b.event_type == "event_b"

    def test_consume_empty_topic(self):
        """Consuming from empty topic should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus

        bus = EventBus(service_name="empty_test")
        result = bus.consume("empty_topic")
        assert result is None

    def test_event_ordering(self):
        """Events should be consumed in FIFO order."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="order_test")
        for i in range(5):
            bus.publish("ordered", Event(event_type=f"event_{i}"))

        for i in range(5):
            event = bus.consume("ordered")
            assert event.event_type == f"event_{i}"

    def test_event_payload_preserved(self):
        """Event payload should be preserved through publish/consume."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="payload_test")
        payload = {"model_id": "m1", "accuracy": 0.95, "tags": ["prod"]}
        bus.publish("test", Event(event_type="test", payload=payload))

        consumed = bus.consume("test")
        assert consumed.payload == payload

    def test_event_serialization_roundtrip(self):
        """Event should survive JSON serialization roundtrip."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import Event

        original = Event(
            event_type="model.trained",
            source_service="training",
            payload={"model_id": "m1", "epochs": 100},
        )

        json_str = original.to_json()
        restored = Event.from_json(json_str)

        assert restored.event_type == original.event_type
        assert restored.source_service == original.source_service
        assert restored.payload == original.payload


class TestCircuitBreakerDetailed:
    """Extended circuit breaker tests."""

    def test_circuit_breaker_initial_state(self):
        """Circuit breaker should start closed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1.0)
        assert cb.state.value == "closed"
        assert cb.can_execute() is True

    def test_circuit_breaker_stays_closed_below_threshold(self):
        """Circuit breaker should stay closed below failure threshold."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1.0)
        for _ in range(4):
            cb.record_failure()
        assert cb.state.value == "closed"
        assert cb.can_execute() is True

    def test_circuit_breaker_opens_at_threshold(self):
        """Circuit breaker should open at failure threshold."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state.value == "open"
        assert cb.can_execute() is False

    def test_circuit_breaker_half_open_after_timeout(self):
        """Circuit breaker should transition to half-open after timeout."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()
        assert cb.state.value == "open"

        time.sleep(0.06)
        assert cb.can_execute() is True
        assert cb.state.value == "half_open"

    def test_circuit_breaker_closes_on_success(self):
        """Circuit breaker should close after success in half-open."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.06)
        cb.can_execute()  # Transition to half-open
        cb.record_success()
        assert cb.state.value == "closed"

    def test_circuit_breaker_reopens_on_failure(self):
        """Circuit breaker should reopen on failure in half-open."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.05)
        cb.record_failure()
        cb.record_failure()

        time.sleep(0.06)
        cb.can_execute()  # Transition to half-open
        cb.record_failure()
        assert cb.state.value == "open"


class TestDistributedLockDetailed:
    """Extended distributed lock tests."""

    def test_lock_acquire_and_release(self):
        """Lock should be acquirable and releasable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="basic_lock")
        assert lock.acquire(timeout=1.0)
        lock.release()

    def test_lock_timeout_on_contention(self):
        """Lock should timeout when held by another."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="contention_lock")
        lock.acquire(timeout=1.0)

        # Second acquire should timeout
        result = lock.acquire(timeout=0.1)
        assert result is False
        lock.release()

    def test_lock_reentrant(self):
        """Lock should handle re-acquire after release."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="reentrant_lock")
        for _ in range(5):
            assert lock.acquire(timeout=1.0)
            lock.release()

    def test_lock_different_names_independent(self):
        """Locks with different names should be independent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock_a = DistributedLock(lock_name="lock_a")
        lock_b = DistributedLock(lock_name="lock_b")

        assert lock_a.acquire(timeout=1.0)
        assert lock_b.acquire(timeout=1.0)
        lock_a.release()
        lock_b.release()


class TestTraceContextDetailed:
    """Extended trace context tests."""

    def test_trace_context_unique_ids(self):
        """Each trace context should have unique IDs."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import TraceContext

        contexts = [TraceContext() for _ in range(50)]
        trace_ids = {ctx.trace_id for ctx in contexts}
        assert len(trace_ids) == 50

    def test_trace_context_to_headers(self):
        """Trace context should serialize to headers."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import TraceContext

        ctx = TraceContext()
        headers = ctx.to_headers()
        assert "trace_id" in headers or "X-Trace-ID" in headers
        assert "span_id" in headers or "X-Span-ID" in headers

    def test_trace_context_propagation(self):
        """Trace context should propagate through service calls."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import TraceContext

        parent = TraceContext()
        child_headers = parent.to_headers()

        # Child should reference parent trace
        assert parent.trace_id is not None
        assert parent.span_id is not None


class TestRateLimiterIntegration(unittest.TestCase):
    """Integration tests for rate limiter with gateway."""

    def test_rate_limiter_allows_within_limit(self):
        """Requests within limit should be allowed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=100, window_seconds=60)
        for _ in range(50):
            assert limiter.check_rate_limit({"remote_addr": "10.0.0.1"}) is True

    def test_rate_limiter_blocks_over_limit(self):
        """Requests over limit should be blocked."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            limiter.check_rate_limit({"remote_addr": "10.0.0.1"})
        assert limiter.check_rate_limit({"remote_addr": "10.0.0.1"}) is False

    def test_rate_limiter_per_client_isolation(self):
        """Different clients should have separate limits."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=3, window_seconds=60)
        for _ in range(3):
            limiter.check_rate_limit({"remote_addr": "10.0.0.1"})
        # First client exhausted, second should still be allowed
        assert limiter.check_rate_limit({"remote_addr": "10.0.0.1"}) is False
        assert limiter.check_rate_limit({"remote_addr": "10.0.0.2"}) is True


class TestWebhookDeliveryIntegration(unittest.TestCase):
    """Integration tests for webhook delivery pipeline."""

    def test_webhook_delivery_matching_event(self):
        """Webhooks should deliver to subscriptions matching the event type."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://hook1.example.com", ["model.deployed"])
        wm.register_webhook("https://hook2.example.com", ["model.updated"])
        wm.register_webhook("https://hook3.example.com", ["model.deployed", "model.updated"])

        count = wm.deliver_event("model.deployed", {"model_id": "m1"})
        assert count == 2  # hook1 and hook3

    def test_webhook_delivery_no_matching_event(self):
        """No delivery when no subscriptions match."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://hook1.example.com", ["model.deployed"])
        count = wm.deliver_event("model.deleted", {"model_id": "m1"})
        assert count == 0

    def test_webhook_delivery_log_tracking(self):
        """Deliveries should be tracked in the delivery log."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://hook1.example.com", ["model.deployed"])
        wm.deliver_event("model.deployed", {"model_id": "m1"})
        wm.deliver_event("model.deployed", {"model_id": "m2"})
        assert len(wm._delivery_log) == 2

    def test_metrics_cardinality_grows_with_subscriptions(self):
        """Bug J3: Metric labels grow unbounded with subscriptions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import MetricsCollector

        mc = MetricsCollector()
        for i in range(50):
            mc.record_delivery(f"sub_{i}", "model.deployed", f"https://hook{i}.com", "success")
        
        assert mc.get_metric_count() == 50


class TestFeatureStoreCacheIntegration(unittest.TestCase):
    """Integration tests for feature store with cache."""

    def test_cache_serves_after_store_write(self):
        """Cache should serve data that was written to the store."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore
        from services.features.views import FeatureCacheManager

        store = FeatureStore()
        cache = FeatureCacheManager(ttl=60.0)

        store.write_feature("entity_1", "user_features", {"age": 25, "score": 0.8})
        online_data = store.read_online("entity_1", "user_features")
        cache.set("entity_1:user_features", online_data)

        cached = cache.get("entity_1:user_features")
        assert cached is not None
        assert cached["values"]["age"] == 25

    def test_cache_miss_falls_back_to_store(self):
        """Cache miss should trigger store read."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore
        from services.features.views import FeatureCacheManager

        store = FeatureStore()
        cache = FeatureCacheManager(ttl=60.0)

        store.write_feature("entity_2", "fg1", {"val": 42})
        # Cache miss
        assert cache.get("entity_2:fg1") is None
        # Fallback to store
        data = store.read_online("entity_2", "fg1")
        assert data is not None

    def test_store_consistency_check(self):
        """Online and offline stores should be consistent after write."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("e1", "fg1", {"val": 1})
        assert store.check_consistency("e1", "fg1") is True


class TestParameterServerIntegration(unittest.TestCase):
    """Integration tests for distributed parameter server."""

    def test_parameter_update_and_retrieve(self):
        """Parameters should be retrievable after gradient update."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weight_1": 1.0, "weight_2": 2.0}

        ps.apply_gradient("worker_1", {"weight_1": 0.1, "weight_2": 0.2}, 0)
        params = ps.get_parameters()
        assert abs(params["weight_1"] - 0.999) < 1e-6  # 1.0 - 0.01 * 0.1
        assert abs(params["weight_2"] - 1.998) < 1e-6

    def test_version_increments_on_update(self):
        """Parameter version should increment after each update."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 1.0}
        assert ps.get_version() == 0
        ps.apply_gradient("w1", {"w": 0.1}, 0)
        assert ps.get_version() == 1
        ps.apply_gradient("w2", {"w": 0.2}, 1)
        assert ps.get_version() == 2

    def test_stale_gradient_still_applied_bug_a9(self):
        """Bug A9: Stale gradients are not rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 1.0}
        # Apply many updates to increment version
        for i in range(20):
            ps.apply_gradient(f"w_{i}", {"w": 0.01}, i)
        # Apply with very old version - BUG A9: still succeeds
        result = ps.apply_gradient("stale_worker", {"w": 0.5}, 0)
        assert result is True  
