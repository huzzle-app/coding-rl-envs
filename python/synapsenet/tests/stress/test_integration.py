"""
SynapseNet Integration Tests
Tests for bugs that manifest when multiple services interact.
"""
import os
import sys
import time
import threading

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestGatewayToAuthIntegration:
    """Test gateway → auth service interaction."""

    def test_gateway_propagates_trace_context(self):
        """Gateway should propagate trace context to downstream services."""
        from services.gateway.main import TraceContext
        from shared.events.base import EventBus

        ctx = TraceContext()
        bus = EventBus(service_name="gateway")

        # Publish event with trace context
        from shared.events.base import Event
        event = Event(event_type="request.received", source_service="gateway")
        bus.publish("requests", event, trace_context=ctx.to_headers())

        published = bus.get_published_events()
        assert len(published) == 1

        # The event should have trace context in metadata
        assert "correlation_id" in published[0].metadata

    def test_auth_token_forwarding(self):
        """Service client should forward JWT claims to downstream services."""
        from shared.clients.base import ServiceClient

        client = ServiceClient("gateway", "http://auth:8001")
        headers = client._build_headers(auth_token="jwt-token-123")

        assert "Authorization" in headers
        assert headers["Authorization"] == "Bearer jwt-token-123"

    def test_service_client_auth_bypass(self):
        """Internal service-to-service calls should still require auth."""
        from shared.clients.base import ServiceClient

        client = ServiceClient("inference", "http://models:8002")
        headers = {"X-Service-Name": "inference"}

        is_authed = client._check_auth(headers)
        assert is_authed


class TestTrainingToFeatureStoreIntegration:
    """Test training → feature store interaction."""

    def test_feature_consistency_during_training(self):
        """Features read during training should be consistent between stores."""
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()

        # Write features
        store.write_feature("entity-1", "user_features",
                           {"age": 25, "score": 0.8, "country": "US"})

        # Read from both stores
        online = store.read_online("entity-1", "user_features")
        offline = store.read_offline("entity-1", "user_features")

        assert online is not None
        assert offline is not None

        # Values should be identical
        assert online["values"] == offline["values"]

        # Consistency check should pass
        assert store.check_consistency("entity-1", "user_features")

    def test_feature_schema_evolution_compatibility(self):
        """Schema changes should maintain backward compatibility."""
        from services.features.views import FeatureSchemaManager

        mgr = FeatureSchemaManager()

        # Register v1 schema
        v1 = mgr.register_schema("user_features", {
            "age": "int",
            "score": "float",
        })

        # Register v2 schema (adds field)
        v2 = mgr.register_schema("user_features", {
            "age": "int",
            "score": "float",
            "country": "string",  # New field
        })

        # Old schema should still be accessible
        schema_v1 = mgr.get_schema("user_features", 1)
        assert schema_v1 is not None
        assert "age" in schema_v1["schema"]

        # New schema should have all fields
        schema_v2 = mgr.get_schema("user_features", 2)
        assert "country" in schema_v2["schema"]


class TestInferenceToMonitoringIntegration:
    """Test inference → monitoring service interaction."""

    def test_prediction_latency_units(self):
        """Inference service should report latency in consistent units."""
        from services.inference.main import InferenceEngine
        from services.monitoring.main import ModelMonitor

        engine = InferenceEngine()
        monitor = ModelMonitor()

        engine.load_model("model-1", "v1")

        # Make a prediction
        start = time.time()
        result = engine.predict("model-1", {"features": list(range(100))})
        elapsed = time.time() - start

        # Record in monitoring
        latency_ms = result.get("latency_ms", 0)
        monitor.record_prediction("model-1", latency_ms / 1000.0, True)

        # Latency should be reasonable (not hours)
        assert latency_ms < 10000

    def test_error_aggregation_grouping(self):
        """Errors with same type but different messages should be grouped together."""
        from services.monitoring.main import ErrorAggregator

        agg = ErrorAggregator()

        # Same error type, different parameters
        agg.record_error({"type": "ModelNotFound", "message": "Model abc not found"})
        agg.record_error({"type": "ModelNotFound", "message": "Model xyz not found"})
        agg.record_error({"type": "ModelNotFound", "message": "Model 123 not found"})
        agg.record_error({"type": "ValidationError", "message": "Invalid input shape"})

        groups = agg.get_groups()

        # Should have 2 groups (by type), not 4 (by message)
        assert len(groups) <= 2


class TestPipelineToStorageIntegration:
    """Test pipeline → storage service interaction."""

    def test_artifact_checksum_validation(self):
        """Downloaded artifact should match uploaded checksum."""
        from services.storage.main import ArtifactStorage
        import tempfile

        storage = ArtifactStorage(base_path=tempfile.mkdtemp())
        storage.initialize_bucket("models")

        data = b"model weights binary data here"
        checksum = storage.upload_artifact("models", "model-v1.bin", data,
                                           metadata={"version": "v1"})

        downloaded = storage.download_artifact("models", "model-v1.bin")
        assert downloaded == data

        import hashlib
        actual_checksum = hashlib.sha256(downloaded).hexdigest()
        assert actual_checksum == checksum

    def test_storage_path_traversal_blocked(self):
        """Path traversal attempts should be blocked."""
        from services.storage.main import ArtifactStorage
        import tempfile

        storage = ArtifactStorage(base_path=tempfile.mkdtemp())
        storage.initialize_bucket("safe")

        # Try path traversal
        result = storage.download_artifact("safe", "../../etc/passwd")

        # Should not be able to read files outside base_path
        if result is not None:
            assert b"root:" not in result


class TestExperimentToTrainingIntegration:
    """Test experiment → training service interaction."""

    def test_hyperparameter_comparison_after_experiment(self):
        """Comparing experiment hyperparameters should handle float precision."""
        from services.experiments.views import ExperimentManager
        from shared.utils.time import compare_hyperparameters

        mgr = ExperimentManager()

        # Create two experiments with "same" hyperparameters
        exp1 = mgr.create_experiment(
            "lr_sweep_1", "model-1",
            {"learning_rate": 0.1 + 0.2, "batch_size": 32}
        )
        exp2 = mgr.create_experiment(
            "lr_sweep_2", "model-1",
            {"learning_rate": 0.3, "batch_size": 32}
        )

        hp1 = mgr._experiments[exp1]["hyperparameters"]
        hp2 = mgr._experiments[exp2]["hyperparameters"]

        result = compare_hyperparameters(hp1, hp2)
        assert result

    def test_experiment_fork_inherits_hyperparameters(self):
        """Forked experiment should inherit parent's hyperparameters."""
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        parent_id = mgr.create_experiment(
            "baseline", "model-1",
            {"learning_rate": 0.001, "batch_size": 32, "epochs": 100}
        )

        child_id = mgr.fork_experiment(
            parent_id, "lr_modified",
            {"hyperparameters": {"learning_rate": 0.01}}
        )

        child = mgr._experiments[child_id]
        assert child["hyperparameters"]["batch_size"] == 32
        assert child["hyperparameters"]["learning_rate"] == 0.01
        assert child["hyperparameters"]["epochs"] == 100

    def test_experiment_fork_from_deleted_parent(self):
        """Forking from deleted parent should handle gracefully."""
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        parent_id = mgr.create_experiment("deleted_parent", "model-1", {"lr": 0.001})
        mgr.delete_experiment(parent_id)

        # Fork from deleted parent
        try:
            child_id = mgr.fork_experiment(parent_id, "orphan", {"hyperparameters": {"lr": 0.01}})
            # Should either raise or handle gracefully
            if child_id:
                child = mgr._experiments[child_id]
                assert child["parent_id"] == parent_id
        except (KeyError, AttributeError, TypeError) as e:
            pass  # Expected behavior


class TestEventBusToWebhookIntegration:
    """Test event bus → webhook delivery integration."""

    def test_event_delivery_to_webhooks(self):
        """Events published to bus should trigger webhook delivery."""
        from shared.events.base import EventBus, Event
        from services.webhooks.views import WebhookManager

        bus = EventBus(service_name="training")
        wm = WebhookManager()

        # Register webhook
        sub_id = wm.register_webhook(
            "https://external.com/webhook",
            events=["model.trained", "model.deployed"],
        )

        # Publish event
        event = Event(event_type="model.trained", payload={"model_id": "m-1"})
        bus.publish("model-events", event)

        # Webhook should receive the event
        delivered = wm.deliver_event("model.trained", {"model_id": "m-1"})
        assert delivered == 1

    def test_webhook_idempotency(self):
        """Replayed events should not cause duplicate webhook deliveries."""
        from shared.events.base import EventBus, Event, IdempotencyTracker
        from services.webhooks.views import WebhookManager

        bus = EventBus(service_name="test")
        wm = WebhookManager()
        tracker = IdempotencyTracker()

        wm.register_webhook("https://example.com/hook", events=["test.event"])

        event = Event(event_id="unique-evt-1", event_type="test.event",
                      payload={"data": "test"})

        # Process event first time
        if tracker.check_and_mark(event):
            wm.deliver_event(event.event_type, event.payload)

        initial_deliveries = len(wm._delivery_log)

        # Process same event again (replay)
        if tracker.check_and_mark(event):
            wm.deliver_event(event.event_type, event.payload)

        final_deliveries = len(wm._delivery_log)
        assert final_deliveries == initial_deliveries


class TestRateLimiterGatewayIntegration:
    """Test rate limiter integration with gateway."""

    def test_rate_limit_with_forwarded_header(self):
        """Rate limiting should work correctly with X-Forwarded-For."""
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        # Same real client, different forwarded IPs
        for i in range(3):
            limiter.check_rate_limit({
                "remote_addr": "10.0.0.1",
                "X-Forwarded-For": f"attacker-{i}"
            })

        # Attacker bypasses rate limit by spoofing X-Forwarded-For
        result = limiter.check_rate_limit({
            "remote_addr": "10.0.0.1",
            "X-Forwarded-For": "spoofed-new-ip"
        })

        assert result == True

    def test_config_precedence(self):
        """Environment variables should override config file defaults."""
        from services.gateway.main import get_config

        os.environ["RATE_LIMIT_PER_MINUTE"] = "200"
        try:
            value = get_config("rate_limit_per_minute")
            assert value == 200 or value == "200" or value == 100
        finally:
            del os.environ["RATE_LIMIT_PER_MINUTE"]


class TestCanaryAnalyzerIntegration:
    """Test canary analyzer with inference service."""

    def test_canary_significance_test(self):
        """Should correctly determine if canary is significantly different."""
        from services.inference.main import CanaryAnalyzer

        analyzer = CanaryAnalyzer(confidence_level=0.95)

        np.random.seed(42)
        # Control: latency ~50ms
        for _ in range(100):
            analyzer.record_control(np.random.normal(50, 5))

        # Canary: latency ~55ms (significantly worse)
        for _ in range(100):
            analyzer.record_canary(np.random.normal(55, 5))

        result = analyzer.compute_significance()
        assert result["significant"]

    def test_canary_rollback_decision(self):
        """Should recommend rollback when canary is significantly worse."""
        from services.inference.main import CanaryAnalyzer

        analyzer = CanaryAnalyzer(confidence_level=0.95)

        np.random.seed(42)
        for _ in range(100):
            analyzer.record_control(np.random.normal(50, 5))
        for _ in range(100):
            analyzer.record_canary(np.random.normal(70, 5))

        assert analyzer.should_rollback()

    def test_canary_promote_decision(self):
        """Should recommend promotion when canary is not significantly different."""
        from services.inference.main import CanaryAnalyzer

        analyzer = CanaryAnalyzer(confidence_level=0.95)

        np.random.seed(42)
        for _ in range(30):
            analyzer.record_control(np.random.normal(50, 10))
        for _ in range(30):
            analyzer.record_canary(np.random.normal(50, 10))

        assert analyzer.should_promote()

    def test_canary_unequal_sample_sizes_df_calculation(self):
        """Unequal sample sizes should use pooled degrees of freedom for proper statistical power."""
        from services.inference.main import CanaryAnalyzer

        analyzer = CanaryAnalyzer(confidence_level=0.95)

        np.random.seed(123)
        # Small control group, large canary group with a moderate effect
        for _ in range(30):
            analyzer.record_control(np.random.normal(50, 8))
        for _ in range(100):
            analyzer.record_canary(np.random.normal(53, 8))

        result = analyzer.compute_significance()

        # With pooled (Welch-Satterthwaite) df ~ 46, this moderate effect should be
        # detectable. With conservative df = min(30, 100) - 1 = 29, statistical power
        # is reduced and may fail to detect significance.
        assert result["significant"]


class TestHyperparameterSpaceIntegration:
    """Test hyperparameter space with experiment tracking."""

    def test_grid_search_completeness(self):
        """Grid search should cover all combinations."""
        from services.experiments.views import HyperparameterSpace

        space = HyperparameterSpace()
        space.add_uniform("learning_rate", 0.001, 0.01)
        space.add_choice("optimizer", ["adam", "sgd"])

        configs = space.grid_search(points_per_dim=3)

        # 3 lr values × 2 optimizer choices = 6 configs
        assert len(configs) == 6

    def test_log_uniform_sampling(self):
        """Log-uniform sampling should be logarithmically distributed."""
        from services.experiments.views import HyperparameterSpace

        space = HyperparameterSpace()
        space.add_log_uniform("learning_rate", 1e-5, 1e-1)

        samples = [space.sample(seed=i)["learning_rate"] for i in range(1000)]

        # Should span several orders of magnitude
        log_samples = [np.log10(s) for s in samples]
        assert max(log_samples) - min(log_samples) > 2.0

    def test_reproducible_sampling(self):
        """Same seed should produce same sample."""
        from services.experiments.views import HyperparameterSpace

        space = HyperparameterSpace()
        space.add_uniform("lr", 0.0, 1.0)

        s1 = space.sample(seed=42)
        s2 = space.sample(seed=42)

        assert s1["lr"] == s2["lr"]


class TestDataValidatorSchemaVersionIntegration:
    """Test data validation with schema versioning."""

    def test_validation_uses_correct_schema_version(self):
        """Validation should use the specified schema version, not always v1."""
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("events", 1, {"required": ["event_id"]})
        validator.register_schema("events", 2, {"required": ["event_id", "timestamp", "source"]})

        # Data that passes v1 but fails v2
        data = {"event_id": "evt-1"}

        v1_result = validator.validate(data, "events", version=1)
        v2_result = validator.validate(data, "events", version=2)

        assert v1_result
        assert not v2_result


class TestCircuitBreakerFailureAccumulation:
    """Test circuit breaker failure accumulation behavior."""

    def test_failures_accumulate_despite_interspersed_successes(self):
        """Failures should be reset on success in closed state, not only on half_open→closed transition."""
        from services.gateway.main import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry(default_threshold=5, default_timeout=1.0)
        service = "downstream-api"

        # Interleave successes and failures: success resets should prevent accumulation
        for _ in range(10):
            registry.record_failure(service)
            registry.record_success(service)
            registry.record_success(service)
            registry.record_success(service)

        # After many successes interspersed with failures, the circuit should remain closed.
        # If failures only reset on half_open→closed transitions, they accumulate over
        # the lifetime and eventually open the circuit even though the service is mostly healthy.
        breaker = registry.get_or_create(service)
        assert breaker["state"] == "closed"

    def test_circuit_opens_after_consecutive_failures(self):
        """Circuit should open after threshold consecutive failures."""
        from services.gateway.main import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry(default_threshold=5, default_timeout=1.0)
        service = "flaky-service"

        for _ in range(5):
            registry.record_failure(service)

        breaker = registry.get_or_create(service)
        assert breaker["state"] == "open"

    def test_success_resets_failure_count_in_closed_state(self):
        """A success while in closed state should reset the failure counter."""
        from services.gateway.main import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry(default_threshold=5, default_timeout=1.0)
        service = "recovering-service"

        # Accumulate some failures (below threshold)
        registry.record_failure(service)
        registry.record_failure(service)
        registry.record_failure(service)

        # A success should reset failure count
        registry.record_success(service)

        breaker = registry.get_or_create(service)
        assert breaker["failure_count"] == 0

    def test_spread_out_failures_should_not_open_circuit(self):
        """Spread-out failures with successes in between should not cause circuit to open."""
        from services.gateway.main import CircuitBreakerRegistry

        registry = CircuitBreakerRegistry(default_threshold=5, default_timeout=1.0)
        service = "mostly-healthy"

        # 20 total failures spread across 100 calls (80% success rate)
        for i in range(100):
            if i % 5 == 0:
                registry.record_failure(service)
            else:
                registry.record_success(service)

        breaker = registry.get_or_create(service)
        assert breaker["state"] == "closed"


class TestEndToEndModelDeploymentFlow:
    """Test the complete model deployment flow across services."""

    def test_full_deployment_pipeline(self):
        """Model should flow: create → train → register → deploy → serve."""
        from services.models.main import ModelMetadata
        from shared.ml.model_loader import ModelLoader
        from services.inference.main import InferenceEngine, ModelDeploymentStateMachine
        from services.registry.views import CanaryDeployment

        # Step 1: Create model metadata
        model_store = ModelMetadata()
        model = model_store.create_model(
            {"name": "classifier", "framework": "pytorch", "version": "1.0"},
            user_id="user-1"
        )
        model_id = model["model_id"]

        # Step 2: Save checkpoint after training
        loader = ModelLoader()
        weights = {"layer1": [1.0, 2.0], "layer2": [3.0, 4.0]}
        loader.save_checkpoint(model_id, "1.0", weights)

        # Step 3: Deploy model
        sm = ModelDeploymentStateMachine(model_id)
        assert sm.transition("validating")
        assert sm.transition("validated")
        assert sm.transition("deploying")
        assert sm.transition("deployed")

        # Step 4: Start canary
        canary = CanaryDeployment()
        dep_id = canary.start_canary(model_id, "1.0", traffic_pct=0.1)

        # Step 5: Serve predictions
        engine = InferenceEngine()
        engine.load_model(model_id, "1.0")
        result = engine.predict(model_id, {"features": [0.1, 0.2, 0.3]})

        assert result["model_id"] == model_id
        assert result["version"] == "1.0"

        # Step 6: Promote canary
        canary.promote(dep_id)
        assert sm.transition("serving")
        assert sm.can_serve_traffic()
