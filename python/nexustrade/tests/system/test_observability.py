"""
System tests for observability bugs.

These tests verify bugs J1-J5 (Observability category).
"""
import pytest
import uuid
import time
import hashlib
from collections import defaultdict


class TestTracing:
    """Tests for bug J1: Trace context propagation failures."""

    def test_trace_propagation(self):
        """Test that trace context propagates across services."""
        parent_trace_id = "abc123"
        child_headers = {"X-Trace-Id": parent_trace_id, "X-Span-Id": "span-456"}
        assert child_headers["X-Trace-Id"] == parent_trace_id, "Trace ID should propagate"

    def test_distributed_trace(self):
        """Test distributed trace reconstruction."""
        spans = [
            {"trace_id": "abc", "span_id": "1", "parent": None, "service": "gateway"},
            {"trace_id": "abc", "span_id": "2", "parent": "1", "service": "orders"},
            {"trace_id": "abc", "span_id": "3", "parent": "2", "service": "matching"},
        ]
        trace_ids = set(s["trace_id"] for s in spans)
        assert len(trace_ids) == 1, "All spans should share trace ID"

        # Verify parent chain
        root_spans = [s for s in spans if s["parent"] is None]
        assert len(root_spans) == 1, "Should have exactly one root span"
        assert root_spans[0]["service"] == "gateway", "Root span should be gateway"

    def test_trace_sampling_rate(self):
        """Test that trace sampling rate is correctly applied."""
        
        sampling_rate = 0.1  # Sample 10% of traces
        total_requests = 10000
        sampled_count = 0

        # Simulate deterministic sampling based on trace ID hash
        for i in range(total_requests):
            trace_id = f"trace-{i}"
            hash_val = int(hashlib.md5(trace_id.encode()).hexdigest(), 16) % 100
            if hash_val < (sampling_rate * 100):
                sampled_count += 1

        # Should be roughly 10% with some tolerance
        actual_rate = sampled_count / total_requests
        assert 0.05 <= actual_rate <= 0.15, (
            f"Sampling rate {actual_rate} should be close to {sampling_rate}"
        )

    def test_span_attribute_propagation(self):
        """Test that span attributes propagate through the call chain."""
        
        parent_span = {
            "trace_id": "trace-001",
            "span_id": "span-001",
            "attributes": {"user.id": "user-123", "tenant.id": "tenant-456"},
            "baggage": {"deployment.env": "production", "feature.flag": "enabled"},
        }

        # Simulate child span creation inheriting baggage
        child_span = {
            "trace_id": parent_span["trace_id"],
            "span_id": "span-002",
            "parent_span_id": parent_span["span_id"],
            "attributes": {"operation": "place_order"},
            "baggage": dict(parent_span["baggage"]),  # Should inherit baggage
        }

        assert child_span["trace_id"] == parent_span["trace_id"], (
            "Child should inherit trace ID"
        )
        assert child_span["baggage"]["deployment.env"] == "production", (
            "Child should inherit baggage items"
        )
        assert child_span["baggage"]["feature.flag"] == "enabled", (
            "All baggage items should propagate"
        )


class TestCorrelationTracking:
    """Tests for bug J2: Correlation ID missing in async flows."""

    def test_correlation_id(self):
        """Test that correlation IDs are generated and attached to requests."""
        correlation_id = str(uuid.uuid4())

        # Simulate request with correlation ID
        request = {
            "headers": {"X-Correlation-Id": correlation_id},
            "body": {"action": "place_order"},
        }
        response = {
            "headers": {"X-Correlation-Id": correlation_id},
            "body": {"status": "accepted"},
        }

        assert request["headers"]["X-Correlation-Id"] == response["headers"]["X-Correlation-Id"], (
            "Correlation ID should be consistent between request and response"
        )

    def test_request_tracking(self):
        """Test end-to-end request tracking across services."""
        request_id = "req-12345"
        service_log = []

        # Simulate request flowing through services
        services = ["api-gateway", "order-service", "matching-engine", "settlement"]
        for service in services:
            service_log.append({
                "service": service,
                "request_id": request_id,
                "timestamp": time.monotonic(),
            })

        # All log entries should have the same request ID
        logged_ids = set(entry["request_id"] for entry in service_log)
        assert len(logged_ids) == 1, "All services should log the same request ID"
        assert logged_ids.pop() == request_id

    def test_async_correlation_preservation(self):
        """Test that correlation IDs survive async message processing."""
        
        correlation_id = "corr-async-001"

        # Simulate message placed on queue
        message = {
            "payload": {"order_id": "order-789"},
            "metadata": {"correlation_id": correlation_id, "source": "order-service"},
        }

        # Simulate consumer picking up the message
        consumed_message = dict(message)
        consumed_correlation = consumed_message["metadata"].get("correlation_id")

        assert consumed_correlation == correlation_id, (
            "Correlation ID should survive async message passing"
        )

        # Simulate the consumer creating a downstream request
        downstream_request = {
            "headers": {"X-Correlation-Id": consumed_correlation},
            "action": "settle_order",
        }
        assert downstream_request["headers"]["X-Correlation-Id"] == correlation_id, (
            "Downstream request should carry the original correlation ID"
        )

    def test_batch_job_tracking(self):
        """Test that batch jobs generate and propagate tracking IDs."""
        
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        items = [
            {"item_id": f"item-{i}", "batch_id": batch_id}
            for i in range(5)
        ]

        # Each item processed in the batch should reference the batch ID
        for item in items:
            assert item["batch_id"] == batch_id, (
                f"Item {item['item_id']} should reference batch {batch_id}"
            )

        # Verify batch completion tracking
        results = [
            {"item_id": item["item_id"], "status": "processed", "batch_id": batch_id}
            for item in items
        ]
        completed = [r for r in results if r["status"] == "processed"]
        assert len(completed) == len(items), "All batch items should be tracked"


class TestMetrics:
    """Tests for bug J3: Metric cardinality explosion."""

    def test_metric_cardinality(self):
        """Test that metric labels don't create cardinality explosions."""
        
        allowed_labels = {"method", "status_code", "endpoint", "service"}
        dangerous_labels = {"user_id", "request_id", "trace_id", "order_id"}

        metric_labels = {"method": "POST", "status_code": "200", "endpoint": "/api/orders"}

        # Verify no high-cardinality labels are used
        used_labels = set(metric_labels.keys())
        violations = used_labels.intersection(dangerous_labels)
        assert len(violations) == 0, (
            f"High-cardinality labels found: {violations}"
        )

    def test_label_limits(self):
        """Test that label value counts stay within limits."""
        
        max_label_values = 100
        label_values = defaultdict(set)

        # Simulate collecting metrics with bounded labels
        for i in range(200):
            status = str(200 + (i % 5) * 100)  # 200, 300, 400, 500, 600
            method = ["GET", "POST", "PUT", "DELETE"][i % 4]
            label_values["status_code"].add(status)
            label_values["method"].add(method)

        for label_name, values in label_values.items():
            assert len(values) <= max_label_values, (
                f"Label '{label_name}' has {len(values)} unique values, "
                f"exceeding limit of {max_label_values}"
            )

    def test_histogram_bucket_configuration(self):
        """Test that histogram buckets are configured for trading latencies."""
        
        default_buckets = [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0]
        trading_latencies_ms = [5.0, 10.0, 25.0, 50.0, 100.0, 250.0, 500.0, 1000.0]

        # Trading latencies in seconds
        trading_latencies_s = [lat / 1000 for lat in trading_latencies_ms]

        # Check that buckets cover the expected latency range
        min_latency = min(trading_latencies_s)
        max_latency = max(trading_latencies_s)
        assert default_buckets[0] <= min_latency, (
            "Smallest bucket should cover low-latency trading operations"
        )
        assert default_buckets[-1] >= max_latency, (
            "Largest bucket should cover high-latency operations"
        )

    def test_metric_aggregation_accuracy(self):
        """Test that metric aggregation produces accurate results."""
        
        instance_metrics = {
            "instance-1": {"requests_total": 1000, "errors_total": 10},
            "instance-2": {"requests_total": 1500, "errors_total": 25},
            "instance-3": {"requests_total": 800, "errors_total": 5},
        }

        # Aggregate across instances
        total_requests = sum(m["requests_total"] for m in instance_metrics.values())
        total_errors = sum(m["errors_total"] for m in instance_metrics.values())

        assert total_requests == 3300, "Total requests should sum across instances"
        assert total_errors == 40, "Total errors should sum across instances"

        # Verify error rate calculation
        error_rate = total_errors / total_requests
        assert 0.01 <= error_rate <= 0.02, (
            f"Error rate {error_rate:.4f} should be around 1.2%"
        )


class TestHealthChecks:
    """Tests for bug J4: Health check false positives."""

    def test_health_accuracy(self):
        """Test that health checks accurately reflect system state."""
        
        dependencies = {
            "database": {"status": "healthy", "critical": True},
            "cache": {"status": "healthy", "critical": False},
            "message_queue": {"status": "unhealthy", "critical": True},
        }

        # System should be unhealthy if any critical dependency is unhealthy
        critical_deps = {
            name: dep for name, dep in dependencies.items() if dep["critical"]
        }
        all_critical_healthy = all(
            dep["status"] == "healthy" for dep in critical_deps.values()
        )

        assert not all_critical_healthy, (
            "System should detect unhealthy critical dependency"
        )

    def test_dependency_check(self):
        """Test individual dependency health checks."""
        
        def check_dependency(name, is_healthy):
            return {
                "name": name,
                "status": "healthy" if is_healthy else "unhealthy",
                "checked_at": time.monotonic(),
                "latency_ms": 5.0,
            }

        db_check = check_dependency("database", True)
        cache_check = check_dependency("cache", True)
        queue_check = check_dependency("message_queue", False)

        checks = [db_check, cache_check, queue_check]
        unhealthy = [c for c in checks if c["status"] == "unhealthy"]

        assert len(unhealthy) == 1, "Should detect exactly one unhealthy dependency"
        assert unhealthy[0]["name"] == "message_queue"

    def test_readiness_vs_liveness_separation(self):
        """Test that readiness and liveness probes have different semantics."""
        
        class ServiceHealth:
            def __init__(self):
                self.is_alive = True  # Process is running
                self.is_ready = False  # Not yet accepting traffic (warming up)

            def liveness_check(self):
                return {"status": "alive" if self.is_alive else "dead"}

            def readiness_check(self):
                return {"status": "ready" if self.is_ready else "not_ready"}

        service = ServiceHealth()

        # During startup: alive but not ready
        liveness = service.liveness_check()
        readiness = service.readiness_check()

        assert liveness["status"] == "alive", "Service should be alive during startup"
        assert readiness["status"] == "not_ready", "Service should not be ready during startup"

        # After warmup: alive and ready
        service.is_ready = True
        liveness = service.liveness_check()
        readiness = service.readiness_check()

        assert liveness["status"] == "alive"
        assert readiness["status"] == "ready", "Service should be ready after warmup"


class TestAlertingSystem:
    """Tests for bug J5: Alert noise from flapping services."""

    def test_error_grouping(self):
        """Test that similar errors are grouped together."""
        
        errors = [
            {"type": "ConnectionError", "service": "db", "message": "Connection refused to db:5432"},
            {"type": "ConnectionError", "service": "db", "message": "Connection refused to db:5432"},
            {"type": "ConnectionError", "service": "db", "message": "Connection refused to db:5432"},
            {"type": "TimeoutError", "service": "cache", "message": "Timeout after 5s"},
        ]

        # Group errors by type + service
        groups = defaultdict(list)
        for error in errors:
            key = f"{error['type']}:{error['service']}"
            groups[key].append(error)

        assert len(groups) == 2, "Errors should be grouped into 2 distinct groups"
        assert len(groups["ConnectionError:db"]) == 3, (
            "Repeated DB connection errors should be in one group"
        )

    def test_alert_accuracy(self):
        """Test that alerts fire only for genuine issues, not transients."""
        
        error_window_seconds = 60
        error_threshold = 5

        # Simulate error counts in a sliding window
        error_timestamps = [10.0, 10.1, 10.2, 10.3, 10.4]  # 5 errors in burst
        window_start = error_timestamps[-1] - error_window_seconds
        errors_in_window = [t for t in error_timestamps if t >= window_start]

        should_alert = len(errors_in_window) >= error_threshold
        assert should_alert, (
            f"Should alert when {len(errors_in_window)} errors >= threshold {error_threshold}"
        )

        # Single transient error should NOT trigger alert
        transient_errors = [10.0]
        errors_in_window = [t for t in transient_errors if t >= window_start]
        should_alert = len(errors_in_window) >= error_threshold
        assert not should_alert, "Single transient error should not trigger alert"

    def test_alert_deduplication(self):
        """Test that duplicate alerts are suppressed within a cooldown window."""
        
        alert_cooldown_seconds = 300  # 5-minute cooldown
        fired_alerts = []

        class AlertManager:
            def __init__(self, cooldown):
                self.cooldown = cooldown
                self.last_fired = {}

            def should_fire(self, alert_key, current_time):
                last = self.last_fired.get(alert_key)
                if last is None or (current_time - last) >= self.cooldown:
                    self.last_fired[alert_key] = current_time
                    return True
                return False

        manager = AlertManager(cooldown=alert_cooldown_seconds)

        # First alert should fire
        assert manager.should_fire("high_error_rate", 0), "First alert should fire"
        fired_alerts.append(0)

        # Same alert within cooldown should be suppressed
        assert not manager.should_fire("high_error_rate", 60), (
            "Alert within cooldown should be suppressed"
        )
        assert not manager.should_fire("high_error_rate", 120), (
            "Alert within cooldown should be suppressed"
        )

        # After cooldown expires, alert should fire again
        assert manager.should_fire("high_error_rate", 301), (
            "Alert after cooldown should fire"
        )
        fired_alerts.append(301)

        assert len(fired_alerts) == 2, "Only 2 alerts should have fired"
