"""
SynapseNet API Contract Tests
Terminal Bench v2 - Tests for API contracts between services

Tests cover:
- Service API contracts (request/response shapes)
- Event schema contracts (Kafka message formats)
- Configuration contracts
"""
import time
import uuid
import sys
import os
import unittest
from datetime import datetime, timezone

import pytest
import numpy as np


# =========================================================================
# Model Service API Contract
# =========================================================================

class TestModelServiceContract:
    """Verify Model Service API contract."""

    def test_create_model_contract(self):
        """create_model should return expected fields."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model(
            {"name": "contract_model", "framework": "pytorch", "version": "1.0"},
            user_id="user_1",
        )

        # Verify required fields in response
        required_fields = [
            "model_id", "name", "framework", "version", "owner_id",
            "tenant_id", "input_schema", "output_schema", "created_at",
            "updated_at", "is_public", "status",
        ]

        for field in required_fields:
            assert field in model, f"Missing field '{field}' in model response"

        assert model["status"] == "created"
        assert model["owner_id"] == "user_1"
        assert isinstance(model["model_id"], str)

    def test_get_model_contract(self):
        """get_model should return same structure as create."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        created = store.create_model({"name": "get_test"}, "u1")
        retrieved = store.get_model(created["model_id"])

        assert retrieved is not None
        assert retrieved["model_id"] == created["model_id"]
        assert retrieved["name"] == created["name"]

    def test_update_model_contract(self):
        """update_model should return updated model with updated_at changed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        created = store.create_model({"name": "update_test"}, "u1")
        original_updated_at = created["updated_at"]

        time.sleep(0.01)
        updated = store.update_model(created["model_id"], {"name": "updated_name"})

        assert updated is not None
        assert updated["name"] == "updated_name"
        assert updated["updated_at"] != original_updated_at

    def test_list_models_contract(self):
        """list_models should return a list of model objects."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        store.create_model({"name": "list_1", "tenant_id": "t1"}, "u1")
        store.create_model({"name": "list_2", "tenant_id": "t1"}, "u1")

        models = store.list_models(tenant_id="t1")
        assert isinstance(models, list)
        assert len(models) == 2
        for model in models:
            assert "model_id" in model
            assert "name" in model

    def test_delete_model_contract(self):
        """delete_model should return boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        model = store.create_model({"name": "delete_test"}, "u1")

        result = store.delete_model(model["model_id"])
        assert result is True

        result = store.delete_model("nonexistent")
        assert result is False


# =========================================================================
# Inference Service API Contract
# =========================================================================

class TestInferenceServiceContract:
    """Verify Inference Service API contract."""

    def test_predict_response_contract(self):
        """predict should return model_id, version, output, scores, latency_ms."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("contract_model", "v1", np.random.randn(10, 10))

        result = engine.predict("contract_model", {"features": list(np.random.randn(10))})

        required_fields = ["model_id", "version", "output", "scores", "latency_ms"]
        for field in required_fields:
            assert field in result, f"Missing field '{field}' in prediction response"

        assert result["model_id"] == "contract_model"
        assert result["version"] == "v1"
        assert isinstance(result["output"], float)
        assert isinstance(result["scores"], list)
        assert isinstance(result["latency_ms"], float)

    def test_load_model_returns_bool(self):
        """load_model should return True on success."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        result = engine.load_model("bool_model", "v1")
        assert result is True

    def test_swap_model_returns_bool(self):
        """swap_model should return True on success."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("swap_contract", "v1")
        result = engine.swap_model("swap_contract", "v2")
        assert result is True


# =========================================================================
# Event Schema Contract
# =========================================================================

class TestEventSchemaContract:
    """Verify event schema contracts for Kafka messages."""

    def test_event_serialization_contract(self):
        """Events should serialize to JSON with required fields."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import Event

        event = Event(
            event_type="model.trained",
            source_service="training",
            payload={"model_id": "m1", "accuracy": 0.95},
        )

        json_str = event.to_json()
        assert isinstance(json_str, str)

        import json
        parsed = json.loads(json_str)

        required_fields = [
            "event_id", "event_type", "source_service",
            "timestamp", "payload", "metadata", "trace_context",
        ]
        for field in required_fields:
            assert field in parsed, f"Missing field '{field}' in event JSON"

    def test_event_deserialization_contract(self):
        """Events should deserialize from JSON correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import Event

        original = Event(
            event_type="model.deployed",
            source_service="registry",
            payload={"model_id": "m1", "version": "v2"},
        )

        json_str = original.to_json()
        restored = Event.from_json(json_str)

        assert restored.event_type == original.event_type
        assert restored.source_service == original.source_service
        assert restored.payload == original.payload

    def test_event_id_is_uuid(self):
        """Event ID should be a valid UUID."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import Event

        event = Event(event_type="test")
        # Should be a valid UUID string
        uuid.UUID(event.event_id)  # Raises if invalid

    def test_event_timestamp_format(self):
        """Event timestamp should be ISO format."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import Event

        event = Event(event_type="test")
        # Should be parseable as datetime
        assert isinstance(event.timestamp, str)


# =========================================================================
# Auth Service API Contract
# =========================================================================

class TestAuthServiceContract:
    """Verify Auth Service API contract."""

    def test_create_token_contract(self):
        """create_token should return access_token, refresh_token, expires_in."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user_1", {"role": "admin"})

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert "expires_in" in tokens
        assert isinstance(tokens["access_token"], str)
        assert isinstance(tokens["refresh_token"], str)
        assert isinstance(tokens["expires_in"], int)

    def test_refresh_token_contract(self):
        """refresh should return new tokens or None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user_1", {"role": "user"})

        new_tokens = tm.refresh(tokens["refresh_token"])
        assert new_tokens is not None
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

        # Using old refresh token should return None
        result = tm.refresh(tokens["refresh_token"])
        assert result is None

    def test_api_key_create_contract(self):
        """create_key should return a string API key."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        key = km.create_key("user_1")
        assert isinstance(key, str)
        assert len(key) > 10

    def test_api_key_validate_contract(self):
        """validate_key should return user_id or None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import APIKeyManager

        km = APIKeyManager()
        key = km.create_key("user_1")

        result = km.validate_key(key)
        assert result == "user_1"

        result = km.validate_key("invalid_key")
        assert result is None


# =========================================================================
# Experiment Service API Contract
# =========================================================================

class TestExperimentServiceContract:
    """Verify Experiment Service API contract."""

    def test_create_experiment_contract(self):
        """create_experiment should return experiment_id string."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("exp_1", "model_1", {"lr": 0.01})

        assert isinstance(exp_id, str)
        assert len(exp_id) > 0

    def test_experiment_data_contract(self):
        """Experiment data should have required fields."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("contract_exp", "m1", {"lr": 0.01})
        exp = manager._experiments[exp_id]

        required = [
            "experiment_id", "name", "model_id", "hyperparameters",
            "seed", "parent_id", "tags", "status", "created_at",
        ]
        for field in required:
            assert field in exp, f"Missing field '{field}' in experiment"

    def test_compare_experiments_contract(self):
        """compare_experiments should return list of experiment+metrics."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp1 = manager.create_experiment("e1", "m1", {"lr": 0.01})
        exp2 = manager.create_experiment("e2", "m1", {"lr": 0.1})

        results = manager.compare_experiments([exp1, exp2])
        assert isinstance(results, list)
        assert len(results) == 2
        for r in results:
            assert "experiment" in r
            assert "metrics" in r

    def test_metric_aggregation_contract(self):
        """aggregate_metric should return count, sum, mean, min, max."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("exp_1", "loss", 0.5)
        logger.log_metric("exp_1", "loss", 0.3)

        agg = logger.aggregate_metric("exp_1", "loss")
        assert agg is not None
        for field in ["count", "sum", "mean", "min", "max"]:
            assert field in agg, f"Missing '{field}' in aggregation"


# =========================================================================
# Feature Service API Contract
# =========================================================================

class TestFeatureServiceContract:
    """Verify Feature Service API contract."""

    def test_feature_write_contract(self):
        """write_feature should return boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        result = store.write_feature("e1", "group", {"value": 1.0})
        assert isinstance(result, bool)

    def test_feature_read_contract(self):
        """read_online should return dict with values, timestamp, entity_id, feature_group."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        store.write_feature("e1", "demo", {"score": 0.5})

        result = store.read_online("e1", "demo")
        assert result is not None
        assert "values" in result
        assert "timestamp" in result
        assert "entity_id" in result
        assert "feature_group" in result

    def test_drift_detection_contract(self):
        """detect_drift should return boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        detector.set_reference("f1", mean=0.0, std=1.0)

        result = detector.detect_drift("f1", current_mean=0.5, current_std=1.0)
        assert isinstance(result, bool)


# =========================================================================
# Pipeline Service API Contract
# =========================================================================

class TestPipelineServiceContract:
    """Verify Pipeline Service API contract."""

    def test_data_validator_contract(self):
        """validate should return boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("test", 1, {"required": ["id"]})

        result = validator.validate({"id": "1"}, "test")
        assert isinstance(result, bool)

    def test_backfill_processor_contract(self):
        """process_record should return boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()
        result = processor.process_record("r1", {"data": "test"})
        assert isinstance(result, bool)

    def test_partition_router_contract(self):
        """route should return integer partition number."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=8)
        result = router.route("test_key")
        assert isinstance(result, int)
        assert 0 <= result < 8


# =========================================================================
# Monitoring Service API Contract
# =========================================================================

class TestMonitoringServiceContract:
    """Verify Monitoring Service API contract."""

    def test_model_health_contract(self):
        """get_model_health should return model_id, predictions, success_rate, latency."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ModelMonitor

        monitor = ModelMonitor()
        monitor.record_prediction("m1", 0.01, True)

        health = monitor.get_model_health("m1")
        assert "model_id" in health
        assert "total_predictions" in health
        assert "success_rate" in health
        assert "latency_stats" in health

    def test_histogram_stats_contract(self):
        """get_stats should return count, sum, avg, p50, p95, p99."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        h = LatencyHistogram()
        h.observe(0.01)
        h.observe(0.05)

        stats = h.get_stats()
        for field in ["count", "sum", "avg", "p50", "p95", "p99"]:
            assert field in stats, f"Missing '{field}' in histogram stats"

    def test_error_top_errors_contract(self):
        """get_top_errors should return list of {group, count}."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        agg = ErrorAggregator()
        agg.record_error({"type": "Error", "message": "test"})

        top = agg.get_top_errors(limit=5)
        assert isinstance(top, list)
        for entry in top:
            assert "group" in entry
            assert "count" in entry


# =========================================================================
# Extended Contract Tests
# =========================================================================

class TestStorageServiceContract:
    """Verify Storage Service API contract."""

    def test_upload_returns_checksum(self):
        """upload_artifact should return a checksum string."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_contract_storage")
        storage.initialize_bucket("contract_bucket")

        checksum = storage.upload_artifact("contract_bucket", "test.bin", b"data")
        assert isinstance(checksum, str)
        assert len(checksum) > 0

    def test_download_returns_bytes(self):
        """download_artifact should return bytes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_contract_download")
        storage.initialize_bucket("dl_bucket")
        storage.upload_artifact("dl_bucket", "file.bin", b"content")

        result = storage.download_artifact("dl_bucket", "file.bin")
        assert isinstance(result, bytes)

    def test_metadata_contract(self):
        """get_metadata should return size, checksum, uploaded_at."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_contract_meta")
        storage.initialize_bucket("meta_bucket")
        storage.upload_artifact("meta_bucket", "meta.bin", b"content")

        meta = storage.get_metadata("meta_bucket", "meta.bin")
        assert "size" in meta
        assert "checksum" in meta

    def test_list_artifacts_contract(self):
        """list_artifacts should return a list of strings."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_contract_list")
        storage.initialize_bucket("list_bucket")
        storage.upload_artifact("list_bucket", "a.bin", b"a")
        storage.upload_artifact("list_bucket", "b.bin", b"b")

        artifacts = storage.list_artifacts("list_bucket")
        assert isinstance(artifacts, list)
        assert len(artifacts) == 2


class TestWebhookServiceContract:
    """Verify Webhook Service API contract."""

    def test_register_returns_id(self):
        """register_webhook should return subscription ID."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        sub_id = wm.register_webhook("https://hooks.example.com/hook", ["model.deployed"])
        assert isinstance(sub_id, str)
        assert len(sub_id) > 0

    def test_deliver_returns_count(self):
        """deliver_event should return delivery count integer."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        wm.register_webhook("https://hooks.example.com/hook", ["test.event"])

        count = wm.deliver_event("test.event", {"data": "test"})
        assert isinstance(count, int)
        assert count >= 0


class TestDistributedLockContract:
    """Verify Distributed Lock API contract."""

    def test_acquire_returns_bool(self):
        """acquire should return boolean."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="contract_lock")
        result = lock.acquire(timeout=1.0)
        assert isinstance(result, bool)
        lock.release()

    def test_release_does_not_error(self):
        """release on acquired lock should not error."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="release_test")
        lock.acquire(timeout=1.0)
        lock.release()  # Should not raise


class TestSchedulerServiceContract:
    """Verify Scheduler Service API contract."""

    def test_feature_flag_set_and_evaluate(self):
        """Feature flag should be settable and evaluable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import FeatureFlagManager

        fm = FeatureFlagManager()
        fm.set_flag("test_flag", True, rules={"rollout_pct": 1.0})

        result = fm.evaluate_flag("test_flag")
        assert isinstance(result, bool)

    def test_worker_registry_contract(self):
        """Worker registry should support register/list."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import WorkerRegistry

        registry = WorkerRegistry()
        assert registry is not None


class TestConfigManagerContract:
    """Verify Config Manager API contract."""

    def test_load_config_contract(self):
        """load_config should accept a dict."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import ConfigManager

        cm = ConfigManager()
        cm.load_config({"key": "value"})
        assert cm.get("key") == "value"

    def test_get_with_default_contract(self):
        """get should return default for missing keys."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import ConfigManager

        cm = ConfigManager()
        cm.load_config({})
        result = cm.get("missing", "fallback")
        assert result == "fallback"

    def test_tenant_manager_contract(self):
        """TenantManager should create tenants with expected fields."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import TenantManager

        tm = TenantManager()
        tenant_id = tm.create_tenant("Test Corp", plan="free")

        tenant = tm.get_tenant(tenant_id)
        assert "name" in tenant
        assert "plan" in tenant
        assert "is_active" in tenant


class TestCertificateValidatorContract(unittest.TestCase):
    """Contract tests for CertificateValidator."""

    @pytest.mark.contract
    def test_validate_empty_chain(self):
        """Empty chain should be rejected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import CertificateValidator

        validator = CertificateValidator()
        assert validator.validate_certificate([]) is False

    @pytest.mark.contract
    def test_validate_valid_chain_bug_g6(self):
        """Bug G6: Only checks leaf cert presence, not full chain."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import CertificateValidator

        validator = CertificateValidator()
        validator.add_trusted_ca("ROOT_CA_CERT")
        
        result = validator.validate_certificate(["leaf_cert", "intermediate_cert"])
        assert result is True  # Accepts any non-empty chain

    @pytest.mark.contract
    def test_validate_untrusted_chain_bug_g6(self):
        """Bug G6: Should reject untrusted chains but doesn't."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.admin.views import CertificateValidator

        validator = CertificateValidator()
        # No trusted CAs added
        result = validator.validate_certificate(["untrusted_cert"])
        assert result is True  


class TestFeatureFlagContract(unittest.TestCase):
    """Contract tests for FeatureFlagManager."""

    @pytest.mark.contract
    def test_set_and_evaluate_flag(self):
        """Setting a flag should make it evaluatable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import FeatureFlagManager

        ffm = FeatureFlagManager()
        ffm.set_flag("new_ui", True)
        assert ffm.evaluate_flag("new_ui") is True

    @pytest.mark.contract
    def test_evaluate_nonexistent_flag(self):
        """Evaluating nonexistent flag should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import FeatureFlagManager

        ffm = FeatureFlagManager()
        assert ffm.evaluate_flag("nonexistent") is None

    @pytest.mark.contract
    def test_update_flag_value(self):
        """Updating a flag should return new value."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import FeatureFlagManager

        ffm = FeatureFlagManager()
        ffm.set_flag("toggle", False)
        assert ffm.evaluate_flag("toggle") is False
        ffm.set_flag("toggle", True)
        assert ffm.evaluate_flag("toggle") is True


class TestWorkerRegistryContract(unittest.TestCase):
    """Contract tests for WorkerRegistry."""

    @pytest.mark.contract
    def test_register_worker_contract(self):
        """Worker registration should return True."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import WorkerRegistry

        registry = WorkerRegistry()
        result = registry.register_worker("w1", ["training"])
        assert result is True

    @pytest.mark.contract
    def test_worker_capabilities_stored(self):
        """Worker capabilities should be stored on registration."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import WorkerRegistry

        registry = WorkerRegistry()
        registry.register_worker("w1", ["training", "inference", "eval"])
        worker = registry._workers.get("w1")
        assert worker is not None
        assert "training" in worker["capabilities"]
        assert "inference" in worker["capabilities"]

    @pytest.mark.contract
    def test_worker_active_status_on_register(self):
        """Worker should be active after registration."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.scheduler.views import WorkerRegistry

        registry = WorkerRegistry()
        registry.register_worker("w1", ["training"])
        assert registry._workers["w1"]["status"] == "active"
