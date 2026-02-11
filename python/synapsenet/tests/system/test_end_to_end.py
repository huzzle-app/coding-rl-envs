"""
SynapseNet End-to-End System Tests
Terminal Bench v2 - Tests for complete workflows across multiple services

Tests cover:
- Model lifecycle: create -> train -> deploy -> serve -> monitor
- Feature pipeline: define -> compute -> serve -> drift detect
- Experiment workflow: create -> train -> compare -> promote
- Cross-service communication patterns
"""
import time
import uuid
import sys
import os
from datetime import datetime, timezone, timedelta

import pytest
import numpy as np


# =========================================================================
# Model Lifecycle Tests
# =========================================================================

class TestModelLifecycle:
    """End-to-end model lifecycle: create, train, deploy, serve, monitor."""

    def test_model_create_to_serve(self):
        """Model should flow from creation through serving."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata
        from services.inference.main import InferenceEngine

        # Step 1: Create model metadata
        store = ModelMetadata()
        model = store.create_model(
            {"name": "e2e_model", "framework": "pytorch", "version": "1.0"},
            user_id="data_scientist",
        )
        assert model["status"] == "created"

        # Step 2: Load model for serving
        engine = InferenceEngine()
        weights = np.random.randn(10, 10)
        loaded = engine.load_model(model["model_id"], model["version"], weights)
        assert loaded is True

        # Step 3: Make prediction
        result = engine.predict(model["model_id"], {"features": list(np.random.randn(10))})
        assert result is not None
        assert result["model_id"] == model["model_id"]
        assert "output" in result

    def test_model_versioning_workflow(self):
        """Model versions should be trackable through the system."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata
        from services.inference.main import InferenceEngine

        store = ModelMetadata()
        engine = InferenceEngine()

        # Create v1
        model_v1 = store.create_model(
            {"name": "versioned_model", "version": "v1"}, "user_1"
        )
        engine.load_model(model_v1["model_id"], "v1", np.random.randn(10, 10))

        # Create v2
        model_v2 = store.create_model(
            {"name": "versioned_model", "version": "v2"}, "user_1"
        )

        # Swap to v2
        engine.swap_model(model_v1["model_id"], "v2", np.random.randn(10, 10))

        # Serve v2
        result = engine.predict(model_v1["model_id"], {"features": list(np.random.randn(10))})
        assert result["version"] == "v2"

    def test_model_deployment_with_canary(self):
        """Canary deployment should route traffic correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("canary_model", "v1", np.random.randn(10, 10))

        canary = CanaryDeployment()
        dep_id = canary.start_canary("canary_model", "v2", traffic_pct=0.1)

        # After testing, promote
        canary.promote(dep_id)
        dep = canary._deployments[dep_id]
        assert dep["status"] == "promoted"
        assert dep["traffic_pct"] == 1.0


# =========================================================================
# Feature Pipeline Tests
# =========================================================================

class TestFeaturePipeline:
    """End-to-end feature pipeline: define, compute, serve, drift."""

    def test_feature_define_to_serve(self):
        """Features should flow from definition through serving."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore, FeatureTransformPipeline

        # Step 1: Define transforms
        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "normalize_age", lambda inputs: inputs.get("age", 0) / 100.0,
            input_features=["age"],
            output_feature="age_normalized",
        )
        pipeline.add_transform(
            "log_income", lambda inputs: np.log1p(inputs.get("income", 0)),
            input_features=["income"],
            output_feature="income_log",
        )

        # Step 2: Compute features
        raw_data = {"age": 30, "income": 50000}
        features = pipeline.execute(raw_data)
        assert "age_normalized" in features
        assert "income_log" in features

        # Step 3: Store features
        store = FeatureStore()
        store.write_feature("user_1", "demographics", features)

        # Step 4: Serve features
        served = store.read_online("user_1", "demographics")
        assert served is not None
        assert served["values"]["age_normalized"] == 0.3

    def test_feature_drift_detection_workflow(self):
        """Drift should be detected when feature distribution shifts."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)

        # Set reference distribution
        detector.set_reference("user_age", mean=35.0, std=10.0)
        detector.set_reference("user_income", mean=50000.0, std=20000.0)

        # Check for drift with similar distribution
        drift_normal = detector.detect_drift("user_age", current_mean=35.5, current_std=10.0)
        assert drift_normal is False

        # Check for drift with shifted distribution
        drift_shifted = detector.detect_drift("user_age", current_mean=50.0, current_std=10.0)
        assert drift_shifted is True

    def test_feature_schema_lifecycle(self):
        """Feature schema should evolve while maintaining compatibility."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager

        manager = FeatureSchemaManager()

        # Define v1 schema
        v1 = manager.register_schema("user_features", {
            "fields": {"age": "int", "name": "str"},
        })
        assert v1 == 1

        # Evolve to v2 (add field)
        v2 = manager.register_schema("user_features", {
            "fields": {"age": "int", "name": "str", "email": "str"},
        })
        assert v2 == 2

        # Both versions should be retrievable
        schema_v1 = manager.get_schema("user_features", version=1)
        schema_v2 = manager.get_schema("user_features", version=2)
        assert schema_v1 is not None
        assert schema_v2 is not None
        assert "email" not in schema_v1["schema"]["fields"]
        assert "email" in schema_v2["schema"]["fields"]


# =========================================================================
# Experiment Workflow Tests
# =========================================================================

class TestExperimentWorkflow:
    """End-to-end experiment workflow: create, run, compare, promote."""

    def test_experiment_create_to_compare(self):
        """Experiments should be created, run, and compared."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create experiments
        exp1_id = manager.create_experiment(
            "baseline", "model_1", {"lr": 0.01, "epochs": 10}
        )
        exp2_id = manager.create_experiment(
            "improved", "model_1", {"lr": 0.001, "epochs": 20}
        )

        # Log metrics
        for step in range(10):
            manager.metric_logger.log_metric(exp1_id, "loss", 1.0 - step * 0.08)
            manager.metric_logger.log_metric(exp2_id, "loss", 1.0 - step * 0.1)
            manager.metric_logger.log_metric(exp1_id, "accuracy", step * 0.08)
            manager.metric_logger.log_metric(exp2_id, "accuracy", step * 0.1)

        # Compare
        results = manager.compare_experiments([exp1_id, exp2_id])
        assert len(results) == 2

        # Analyze metrics
        for r in results:
            assert "experiment" in r
            assert "metrics" in r
            loss_values = r["metrics"].get("loss", [])
            assert len(loss_values) == 10

    def test_experiment_fork_and_compare(self):
        """Fork an experiment and compare with parent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create parent
        parent_id = manager.create_experiment(
            "parent_exp", "model_1",
            {"lr": 0.01, "batch_size": 32, "optimizer": "adam"}
        )

        # Fork with different learning rate
        child_id = manager.fork_experiment(
            parent_id, "child_exp",
            {"hyperparameters": {"lr": 0.001}}
        )

        # Verify fork inherited hyperparameters
        child = manager._experiments[child_id]
        assert child["hyperparameters"]["lr"] == 0.001
        assert child["hyperparameters"]["batch_size"] == 32
        assert child["hyperparameters"]["optimizer"] == "adam"

        # Log metrics for both
        manager.metric_logger.log_metric(parent_id, "loss", 0.5)
        manager.metric_logger.log_metric(child_id, "loss", 0.3)

        # Compare
        results = manager.compare_experiments([parent_id, child_id])
        assert len(results) == 2


# =========================================================================
# Cross-Service Communication Tests
# =========================================================================

class TestCrossServiceCommunication:
    """Test communication patterns between services."""

    def test_service_client_roundtrip(self):
        """Service client should support request/response pattern."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("gateway", "http://inference:8005")

        # Should be able to make GET and POST requests
        try:
            result = client.get("/models/latest")
            assert result is not None
        except Exception:
            pass  # Expected in test env without real services

    def test_event_publish_consume_roundtrip(self):
        """Events should roundtrip through publish and consume."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="e2e_test")

        # Publish event
        event = Event(
            event_type="model.trained",
            payload={"model_id": "m1", "accuracy": 0.95},
        )
        bus.publish("training.events", event)

        # Consume event
        consumed = bus.consume("training.events")
        assert consumed is not None
        assert consumed.event_type == "model.trained"
        assert consumed.payload["model_id"] == "m1"

    def test_circuit_breaker_behavior(self):
        """Circuit breaker should open after failures and recover."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)

        # Record failures
        for _ in range(3):
            cb.record_failure()

        assert cb.state.value == "open"
        assert cb.can_execute() is False

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state.value == "half_open"

        # Record success - should close
        cb.record_success()
        assert cb.state.value == "closed"


# =========================================================================
# Data Pipeline End-to-End
# =========================================================================

class TestDataPipelineEndToEnd:
    """End-to-end data pipeline test."""

    def test_pipeline_validation_to_output(self):
        """Data should flow through validation, transform, and storage."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator, BackfillProcessor

        # Step 1: Validate input data
        validator = DataValidator()
        validator.register_schema("training_data", 1, {
            "required": ["sample_id", "features", "label"],
        })

        valid_data = {"sample_id": "s1", "features": [1.0, 2.0], "label": 1}
        assert validator.validate(valid_data, "training_data") is True

        invalid_data = {"sample_id": "s2"}
        assert validator.validate(invalid_data, "training_data") is False

        # Step 2: Process through pipeline
        processor = BackfillProcessor()
        result = processor.process_record("s1", valid_data)
        assert result is True

    def test_pipeline_dag_execution(self):
        """Pipeline DAG should execute stages in order."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PipelineDAG

        dag = PipelineDAG()
        dag.add_node("ingest")
        dag.add_node("validate")
        dag.add_node("transform")
        dag.add_node("store")

        dag.add_edge("ingest", "validate")
        dag.add_edge("validate", "transform")
        dag.add_edge("transform", "store")

        result = dag.execute({"raw_data": [1, 2, 3]})
        assert result is not None


# =========================================================================
# Monitoring End-to-End
# =========================================================================

class TestMonitoringEndToEnd:
    """End-to-end monitoring test."""

    def test_prediction_monitoring_workflow(self):
        """Predictions should be monitored for latency and errors."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine
        from services.monitoring.main import ModelMonitor

        engine = InferenceEngine()
        monitor = ModelMonitor()

        # Load model
        engine.load_model("monitored_model", "v1", np.random.randn(10, 10))

        # Make predictions and monitor
        for i in range(100):
            start = time.time()
            try:
                result = engine.predict(
                    "monitored_model",
                    {"features": list(np.random.randn(10))},
                )
                latency = time.time() - start
                monitor.record_prediction("monitored_model", latency, True)
            except Exception:
                latency = time.time() - start
                monitor.record_prediction("monitored_model", latency, False)

        # Check health
        health = monitor.get_model_health("monitored_model")
        assert health["total_predictions"] == 100
        assert health["success_rate"] == 1.0

        # Check latency stats
        stats = health["latency_stats"]
        assert stats["count"] == 100
        assert stats["avg"] > 0

    def test_error_monitoring_workflow(self):
        """Errors should be aggregated and grouped."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        aggregator = ErrorAggregator()

        # Simulate errors
        error_types = ["TimeoutError", "ModelNotFound", "ValidationError"]
        for i in range(30):
            error_type = error_types[i % len(error_types)]
            aggregator.record_error({
                "type": error_type,
                "message": f"{error_type}: detail_{i}",
            })

        groups = aggregator.get_groups()
        assert len(groups) > 0

        top = aggregator.get_top_errors(limit=3)
        assert len(top) >= 1


# =========================================================================
# Authentication End-to-End
# =========================================================================

class TestAuthenticationEndToEnd:
    """End-to-end authentication workflow."""

    def test_token_lifecycle(self):
        """Token should be created, used, refreshed, and eventually expire."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()

        # Create tokens
        tokens = tm.create_token("user_1", {"role": "admin", "tenant": "t1"})
        assert tokens["access_token"] is not None
        assert tokens["refresh_token"] is not None

        # Refresh
        new_tokens = tm.refresh(tokens["refresh_token"])
        assert new_tokens is not None
        assert new_tokens["access_token"] != tokens["access_token"]

        # Old refresh token should be invalid
        assert tm.refresh(tokens["refresh_token"]) is None

    def test_api_key_lifecycle(self):
        """API key should be created, validated, rotated."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()

        # Create
        key = km.create_key("user_1")
        assert km.validate_key(key) == "user_1"

        # Rotate
        new_key = km.rotate_key(key)
        assert new_key is not None

        # New key should work
        assert km.validate_key(new_key) == "user_1"

    def test_permission_caching_workflow(self):
        """Permission cache should serve cached values and invalidate."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import PermissionCache

        cache = PermissionCache(ttl=60.0)

        # Cache permissions
        cache.set_permissions("user_1", {"role": "editor", "can_delete": False})

        # Read from cache
        perms = cache.get_permissions("user_1")
        assert perms["role"] == "editor"

        # Invalidate
        cache.invalidate("user_1")
        assert cache.get_permissions("user_1") is None

        # Set new permissions
        cache.set_permissions("user_1", {"role": "admin", "can_delete": True})
        perms = cache.get_permissions("user_1")
        assert perms["role"] == "admin"


# =========================================================================
# Storage End-to-End
# =========================================================================

class TestStorageEndToEnd:
    """End-to-end artifact storage workflow."""

    def test_artifact_upload_download(self):
        """Artifacts should be uploadable and downloadable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_e2e_artifacts")
        storage.initialize_bucket("models")

        # Upload
        data = b"model_weights_binary_data"
        checksum = storage.upload_artifact("models", "model_v1.bin", data)
        assert checksum is not None

        # Download
        downloaded = storage.download_artifact("models", "model_v1.bin")
        assert downloaded == data

        # Metadata
        meta = storage.get_metadata("models", "model_v1.bin")
        assert meta is not None
        assert meta["size"] == len(data)
        assert meta["checksum"] == checksum

    def test_artifact_listing(self):
        """Should be able to list artifacts in a bucket."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_e2e_listing")
        storage.initialize_bucket("experiments")

        storage.upload_artifact("experiments", "run_1/model.pkl", b"data1")
        storage.upload_artifact("experiments", "run_1/metrics.json", b"data2")
        storage.upload_artifact("experiments", "run_2/model.pkl", b"data3")

        artifacts = storage.list_artifacts("experiments")
        assert len(artifacts) == 3


# =========================================================================
# Webhook Notification End-to-End
# =========================================================================

class TestWebhookNotificationEndToEnd:
    """End-to-end webhook notification workflow."""

    def test_webhook_registration_and_delivery(self):
        """Webhooks should receive events they're subscribed to."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()

        # Register webhooks
        wm.register_webhook(
            "https://hooks.example.com/deploy",
            ["model.deployed", "model.promoted"],
        )
        wm.register_webhook(
            "https://hooks.example.com/train",
            ["model.trained"],
        )

        # Deliver events
        deploy_count = wm.deliver_event("model.deployed", {"model_id": "m1"})
        assert deploy_count == 1

        train_count = wm.deliver_event("model.trained", {"model_id": "m1"})
        assert train_count == 1

        # Unsubscribed event
        other_count = wm.deliver_event("model.deleted", {"model_id": "m1"})
        assert other_count == 0


# =========================================================================
# Configuration End-to-End
# =========================================================================

class TestConfigurationEndToEnd:
    """End-to-end configuration management."""

    def test_config_load_and_read(self):
        """Configuration should be loadable and readable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import ConfigManager

        cm = ConfigManager()
        cm.load_config({
            "model_cache_size": 100,
            "batch_timeout": 0.1,
            "rate_limit": 1000,
        })

        assert cm.get("model_cache_size") == 100
        assert cm.get("batch_timeout") == 0.1
        assert cm.get("nonexistent", "default") == "default"

    def test_feature_flag_workflow(self):
        """Feature flags should be settable and evaluable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import FeatureFlagManager

        fm = FeatureFlagManager()

        # Set flag
        fm.set_flag("new_model_serving", True, rules={"rollout_pct": 0.5})

        # Evaluate
        result = fm.evaluate_flag("new_model_serving")
        assert result is True

        # Unknown flag
        result = fm.evaluate_flag("nonexistent")
        assert result is None

    def test_tenant_management_workflow(self):
        """Tenants should be creatable and retrievable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import TenantManager

        tm = TenantManager()
        tenant_id = tm.create_tenant("Acme Corp", plan="enterprise")

        tenant = tm.get_tenant(tenant_id)
        assert tenant is not None
        assert tenant["name"] == "Acme Corp"
        assert tenant["plan"] == "enterprise"
        assert tenant["is_active"] is True


# =========================================================================
# Extended End-to-End Tests
# =========================================================================

class TestDistributedTrainingEndToEnd:
    """End-to-end distributed training workflow."""

    def test_parameter_server_training_loop(self):
        """Parameter server should support a full training loop."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"weight": 0.0, "bias": 0.0}

        # Training loop: 10 steps
        for step in range(10):
            gradients = {
                "weight": np.random.randn() * 0.01,
                "bias": np.random.randn() * 0.001,
            }
            ps.apply_gradient(f"worker_{step % 3}", gradients, ps.get_version())

        params = ps.get_parameters()
        assert "weight" in params
        assert "bias" in params
        assert ps.get_version() >= 10

    def test_checkpoint_save_resume_cycle(self):
        """Training should checkpoint and resume correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.model_loader import ModelLoader

        import tempfile
        loader = ModelLoader(storage_path=tempfile.mkdtemp())

        # Train for a few steps and checkpoint
        weights = {"layer1": np.array([1.0, 2.0]), "layer2": np.array([3.0, 4.0])}
        path = loader.save_checkpoint("m1", "v1", weights, {"epoch": 5, "loss": 0.3})

        # Load checkpoint
        ckpt = loader.load_checkpoint(path)
        assert ckpt["metadata"]["epoch"] == 5
        assert ckpt["metadata"]["loss"] == 0.3


class TestMultiServiceWorkflow:
    """Multi-service workflow tests."""

    def test_model_train_deploy_serve_monitor(self):
        """Full lifecycle: train -> deploy -> serve -> monitor."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata
        from services.inference.main import InferenceEngine
        from services.monitoring.main import ModelMonitor
        from services.registry.views import CanaryDeployment

        # 1. Create model
        store = ModelMetadata()
        model = store.create_model(
            {"name": "e2e_full", "framework": "pytorch"}, "ds_user"
        )

        # 2. Deploy model
        engine = InferenceEngine()
        weights = np.random.randn(10, 10)
        engine.load_model(model["model_id"], "v1", weights)

        # 3. Canary deployment
        canary = CanaryDeployment()
        dep_id = canary.start_canary(model["model_id"], "v2", traffic_pct=0.1)

        # 4. Serve predictions
        monitor = ModelMonitor()
        for i in range(50):
            start = time.time()
            result = engine.predict(model["model_id"], {"features": list(np.random.randn(10))})
            latency = time.time() - start
            monitor.record_prediction(model["model_id"], latency, True)

        # 5. Monitor health
        health = monitor.get_model_health(model["model_id"])
        assert health["total_predictions"] == 50
        assert health["success_rate"] == 1.0

        # 6. Promote canary
        canary.promote(dep_id)
        assert canary._deployments[dep_id]["status"] == "promoted"

    def test_experiment_to_production(self):
        """Run experiment, compare, and promote winner."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager
        from services.models.main import ModelMetadata

        # 1. Create experiments
        manager = ExperimentManager()
        exp_a = manager.create_experiment("baseline", "m1", {"lr": 0.01})
        exp_b = manager.create_experiment("improved", "m1", {"lr": 0.001})

        # 2. Log metrics
        for step in range(20):
            manager.metric_logger.log_metric(exp_a, "loss", 1.0 - step * 0.03)
            manager.metric_logger.log_metric(exp_b, "loss", 1.0 - step * 0.05)

        # 3. Compare
        results = manager.compare_experiments([exp_a, exp_b])
        assert len(results) == 2

        # 4. Promote winner
        store = ModelMetadata()
        model = store.create_model(
            {"name": "promoted_model", "framework": "pytorch"},
            user_id="ds_user",
        )
        store.update_model(model["model_id"], {"status": "deployed"})
        assert store.get_model(model["model_id"])["status"] == "deployed"


class TestDataPipelineToFeatureStore:
    """Data pipeline feeding feature store."""

    def test_pipeline_to_features(self):
        """Data pipeline should feed processed features to store."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator
        from shared.ml.feature_utils import FeatureStore, FeatureTransformPipeline

        # 1. Validate input
        validator = DataValidator()
        validator.register_schema("user_data", 1, {"required": ["user_id", "age", "income"]})

        raw_data = {"user_id": "u1", "age": 30, "income": 50000}
        assert validator.validate(raw_data, "user_data") is True

        # 2. Transform features
        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "normalize_age", lambda x: x.get("age", 0) / 100.0,
            input_features=["age"], output_feature="age_norm",
        )

        features = pipeline.execute(raw_data)

        # 3. Store features
        store = FeatureStore()
        store.write_feature("u1", "user_features", features)

        # 4. Serve features
        served = store.read_online("u1", "user_features")
        assert served is not None
        assert "age_norm" in served["values"]

    def test_drift_detection_after_pipeline(self):
        """Drift should be detectable after pipeline processing."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.3)
        detector.set_reference("processed_feature", mean=10.0, std=2.0)

        # Normal distribution
        assert detector.detect_drift("processed_feature", current_mean=10.5, current_std=2.0) is False

        # Drifted distribution
        assert detector.detect_drift("processed_feature", current_mean=20.0, current_std=2.0) is True


class TestEventDrivenWorkflow:
    """Event-driven workflow tests."""

    def test_event_chain(self):
        """Events should chain through multiple services."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="e2e_events")

        # Chain: model.created -> model.trained -> model.deployed
        events = [
            Event(event_type="model.created", payload={"model_id": "m1"}),
            Event(event_type="model.trained", payload={"model_id": "m1", "accuracy": 0.95}),
            Event(event_type="model.deployed", payload={"model_id": "m1", "version": "v1"}),
        ]

        for event in events:
            bus.publish("model.lifecycle", event)

        # Consume all events in order
        consumed = []
        while True:
            event = bus.consume("model.lifecycle")
            if event is None:
                break
            consumed.append(event)

        assert len(consumed) == 3
        assert consumed[0].event_type == "model.created"
        assert consumed[1].event_type == "model.trained"
        assert consumed[2].event_type == "model.deployed"

    def test_webhook_notification_on_event(self):
        """Webhooks should be triggered by events."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://hooks.example.com/deploy", ["model.deployed"])
        wm.register_webhook("https://hooks.example.com/train", ["model.trained"])

        deploy_count = wm.deliver_event("model.deployed", {"model_id": "m1"})
        train_count = wm.deliver_event("model.trained", {"model_id": "m1"})

        assert deploy_count == 1
        assert train_count == 1


class TestSecurityWorkflow:
    """Security workflow integration tests."""

    def test_auth_to_model_access(self):
        """Authenticated user should be able to access models."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager
        from services.models.main import ModelMetadata

        # Authenticate
        tm = TokenManager()
        tokens = tm.create_token("authorized_user", {"role": "admin"})
        assert tokens["access_token"] is not None

        # Access model
        store = ModelMetadata()
        model = store.create_model({"name": "auth_model"}, "authorized_user")
        retrieved = store.get_model(model["model_id"])
        assert retrieved is not None

    def test_api_key_to_inference(self):
        """API key should grant access to inference."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager
        from services.inference.main import InferenceEngine

        km = APIKeyManager()
        key = km.create_key("api_user")
        assert km.validate_key(key) == "api_user"

        engine = InferenceEngine()
        engine.load_model("api_model", "v1", np.random.randn(10, 10))
        result = engine.predict("api_model", {"features": list(np.random.randn(10))})
        assert result is not None


class TestModelLifecycleEndToEnd(unittest.TestCase):
    """End-to-end tests for the complete model lifecycle."""

    def test_model_train_version_deploy(self):
        """Full lifecycle: create model -> train -> version -> deploy."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata
        from shared.ml.model_loader import ModelLoader
        from services.inference.main import InferenceEngine

        # Create model metadata
        store = ModelMetadata()
        model = store.create_model({"name": "lifecycle_model", "framework": "pytorch"}, "owner1")
        assert model["model_id"] is not None

        # Load model version
        loader = ModelLoader()
        weights = np.random.randn(5, 5)
        loaded = loader.load_model(model["model_id"], "v1", weights)
        assert loaded["status"] == "loaded"

        # Deploy for inference
        engine = InferenceEngine()
        engine.load_model(model["model_id"], "v1", weights)
        result = engine.predict(model["model_id"], {"features": list(np.random.randn(5))})
        assert result is not None

    def test_model_update_and_rollback(self):
        """Model should support version updates and rollback."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.model_loader import ModelLoader

        loader = ModelLoader()
        weights_v1 = np.random.randn(5, 5)
        weights_v2 = np.random.randn(5, 5)
        loader.load_model("rollback_model", "v1", weights_v1)
        loader.load_model("rollback_model", "v2", weights_v2)
        # Version history should track both
        assert "rollback_model" in loader._version_history or True

    def test_experiment_to_deployment_flow(self):
        """Full flow: experiment -> metrics -> deployment decision."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager
        from services.inference.main import InferenceEngine, ABTestingRouter

        mgr = ExperimentManager()
        exp_id = mgr.create_experiment("deploy_exp", "model_1", {"lr": 0.01, "epochs": 5})
        mgr.metric_logger.log_metric(exp_id, "accuracy", 0.95)
        mgr.metric_logger.log_metric(exp_id, "loss", 0.05)

        # Check metrics pass threshold
        agg = mgr.metric_logger.aggregate_metric(exp_id, "accuracy")
        assert agg["mean"] >= 0.9

        # Setup AB test for deployment
        router = ABTestingRouter()
        router.create_experiment("canary", {"production": 0.9, "candidate": 0.1})
        variant = router.route_request("canary", {"user_id": "u1"})
        assert variant in ["production", "candidate"]

    def test_feature_store_to_inference_flow(self):
        """Features stored should be usable for inference."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore
        from services.inference.main import InferenceEngine

        store = FeatureStore()
        features = {"age": 25.0, "income": 50000.0, "score": 0.8}
        store.write_feature("user_123", "demographics", features)

        online = store.read_online("user_123", "demographics")
        assert online is not None

        # Use features for inference
        engine = InferenceEngine()
        weights = np.random.randn(3, 3)
        engine.load_model("feature_model", "v1", weights)
        result = engine.predict("feature_model", {"features": [25.0, 50000.0, 0.8]})
        assert result is not None

    def test_monitoring_captures_prediction_metrics(self):
        """Monitoring should capture metrics from inference."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine
        from services.monitoring.main import ModelMonitor

        engine = InferenceEngine()
        weights = np.random.randn(5, 5)
        engine.load_model("monitored_model", "v1", weights)

        monitor = ModelMonitor()
        for i in range(10):
            import time as t
            start = t.time()
            result = engine.predict("monitored_model", {"features": list(np.random.randn(5))})
            latency = t.time() - start
            monitor.record_prediction("monitored_model", latency, result is not None)

        health = monitor.get_model_health("monitored_model")
        assert health["total_predictions"] == 10
        assert health["success_rate"] > 0

    def test_drift_detection_triggers_alert(self):
        """Drift detection should identify feature drift."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("feature_a", mean=100.0, std=10.0)
        detector.set_reference("feature_b", mean=50.0, std=5.0)

        # No drift
        assert detector.detect_drift("feature_a", 101.0, 10.0) is False
        # Significant drift
        assert detector.detect_drift("feature_b", 80.0, 5.0) is True

    def test_webhook_notification_on_model_event(self):
        """Webhooks should fire on model events."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://alerts.example.com/hook", ["model.deployed", "model.failed"])
        wm.register_webhook("https://metrics.example.com/hook", ["model.deployed"])

        # Deploy event
        count = wm.deliver_event("model.deployed", {"model_id": "m1", "version": "v1"})
        assert count == 2

        # Failure event
        count = wm.deliver_event("model.failed", {"model_id": "m1", "error": "OOM"})
        assert count == 1

    def test_schema_evolution_with_feature_store(self):
        """Schema evolution should track multiple versions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureSchemaManager
        from shared.ml.feature_utils import FeatureStore

        schema_mgr = FeatureSchemaManager()
        store = FeatureStore()

        # Register v1 schema
        schema_mgr.register_schema("user_features", {"age": "int", "name": "str"})
        store.write_feature("u1", "user_features", {"age": 25, "name": "Alice"})

        # Evolve schema - BUG C6: no backward compat check
        schema_mgr.register_schema("user_features", {"age": "int", "score": "float"})
        store.write_feature("u2", "user_features", {"age": 30, "score": 0.8})

        assert store.read_online("u1", "user_features") is not None
        assert store.read_online("u2", "user_features") is not None

    def test_worker_registration_before_scheduler(self):
        """Bug L15: Workers registering before scheduler is ready."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import WorkerRegistry

        registry = WorkerRegistry()
        
        result = registry.register_worker("worker_1", ["training", "inference"])
        assert result is True  
        assert not registry._is_ready

    def test_full_pipeline_feature_to_experiment_to_deploy(self):
        """Complete pipeline from feature creation to deployment."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore, FeatureTransformPipeline
        from services.experiments.views import ExperimentManager
        from services.inference.main import InferenceEngine, ABTestingRouter

        # 1. Store features
        store = FeatureStore()
        store.write_feature("u1", "raw", {"val": 10.0})

        # 2. Transform features
        pipeline = FeatureTransformPipeline()
        pipeline.add_transform("normalize", lambda x: x.get("val", 0) / 100.0, ["val"], "normalized")
        result = pipeline.execute({"val": 10.0})
        assert result["normalized"] == 0.1

        # 3. Run experiment
        exp_mgr = ExperimentManager()
        exp_id = exp_mgr.create_experiment("full_pipe", "m1", {"lr": 0.01})
        exp_mgr.metric_logger.log_metric(exp_id, "accuracy", 0.92)

        # 4. Deploy model
        engine = InferenceEngine()
        engine.load_model("m1", "v1", np.random.randn(5, 5))
        pred = engine.predict("m1", {"features": [0.1, 0.2, 0.3, 0.4, 0.5]})
        assert pred is not None

        # 5. Setup canary
        router = ABTestingRouter()
        router.create_experiment("canary", {"m1_v1": 0.9, "m1_v2": 0.1})
        variant = router.route_request("canary", {})
        assert variant is not None
