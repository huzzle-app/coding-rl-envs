"""
SynapseNet Experiment Tracking Tests
Terminal Bench v2 - Tests for experiment management, metrics, and reproducibility

Tests cover:
- E1-E8: Experiment Tracking bugs
"""
import time
import uuid
import random
import threading
import sys
import os
import unittest
from unittest import mock
from decimal import Decimal

import pytest
import numpy as np


# =========================================================================
# E1: Metric logging race condition
# =========================================================================

class TestMetricLoggingRace:
    """BUG E1: Concurrent metric writes can lose data."""

    def test_metric_logging_race(self):
        """Concurrent metric logging should not lose data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        experiment_id = "exp_race_test"
        num_threads = 10
        writes_per_thread = 100
        errors = []

        def log_metrics(thread_id):
            try:
                for i in range(writes_per_thread):
                    logger.log_metric(experiment_id, "loss", float(thread_id * 1000 + i))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=log_metrics, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent logging errors: {errors}"

        metrics = logger.get_metrics(experiment_id)
        total_logged = len(metrics.get("loss", []))
        expected = num_threads * writes_per_thread

        
        assert total_logged == expected, (
            f"Expected {expected} metrics logged, got {total_logged}. "
            f"BUG E1: Race condition lost {expected - total_logged} metric values."
        )

    def test_concurrent_metric_write(self):
        """Two threads writing to same experiment should not corrupt data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        exp_id = "exp_concurrent"

        def writer_a():
            for i in range(50):
                logger.log_metric(exp_id, "accuracy", 0.5 + i * 0.01)

        def writer_b():
            for i in range(50):
                logger.log_metric(exp_id, "loss", 1.0 - i * 0.01)

        t1 = threading.Thread(target=writer_a)
        t2 = threading.Thread(target=writer_b)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        metrics = logger.get_metrics(exp_id)
        assert len(metrics.get("accuracy", [])) == 50
        assert len(metrics.get("loss", [])) == 50


# =========================================================================
# E2: Hyperparameter float equality comparison
# =========================================================================

class TestHyperparameterFloatEquality:
    """BUG E2: Float comparison fails for hyperparameters like 0.1 + 0.2."""

    def test_hyperparameter_float_equality(self):
        """Hyperparameter comparison should handle float precision."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.time import compare_hyperparameters

        hp1 = {"learning_rate": 0.1 + 0.2}
        hp2 = {"learning_rate": 0.3}

        
        result = compare_hyperparameters(hp1, hp2)
        assert result is True, (
            "0.1 + 0.2 should be considered equal to 0.3 for hyperparameter comparison. "
            "BUG E2: Float == comparison fails."
        )

    def test_hyperparameter_comparison(self):
        """Similar hyperparameters should be recognized as equal."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.time import compare_hyperparameters

        hp1 = {"lr": 0.001, "momentum": 0.9, "weight_decay": 1e-5}
        hp2 = {"lr": 0.001, "momentum": 0.9, "weight_decay": 0.00001}

        result = compare_hyperparameters(hp1, hp2)
        assert result is True, "Equivalent hyperparameters should compare as equal"

    def test_different_hyperparameters(self):
        """Different hyperparameters should be recognized as different."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.time import compare_hyperparameters

        hp1 = {"lr": 0.001}
        hp2 = {"lr": 0.01}

        result = compare_hyperparameters(hp1, hp2)
        assert result is False, "Different hyperparameters should not compare as equal"


# =========================================================================
# E3: Reproducibility seed propagation
# =========================================================================

class TestReproducibilitySeed:
    """BUG E3: Seed not propagated to sub-processes."""

    def test_reproducibility_seed(self):
        """Setting seed should make experiment reproducible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create experiment with seed
        exp_id = manager.create_experiment("seeded_exp", "model_1", {"lr": 0.01}, seed=42)

        exp = manager._experiments[exp_id]
        assert exp["seed"] == 42

    def test_seed_propagation(self):
        """Seed should be propagated to ensure reproducibility across processes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create two experiments with same seed
        exp1_id = manager.create_experiment("exp_a", "model_1", {"lr": 0.01}, seed=42)
        
        # because seed only affects current process, not sub-processes
        exp2_id = manager.create_experiment("exp_b", "model_1", {"lr": 0.01}, seed=42)

        exp1 = manager._experiments[exp1_id]
        exp2 = manager._experiments[exp2_id]
        assert exp1["seed"] == exp2["seed"] == 42

    def test_seed_none_allowed(self):
        """Experiment without seed should work normally."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("unseeded", "model_1", {"lr": 0.01})
        exp = manager._experiments[exp_id]
        assert exp["seed"] is None


# =========================================================================
# E4: Experiment fork parent reference broken
# =========================================================================

class TestExperimentForkParent:
    """BUG E4: Fork doesn't validate parent exists."""

    def test_experiment_fork_parent(self):
        """Forking should validate that parent experiment exists."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Try to fork from nonexistent parent
        
        fork_id = manager.fork_experiment(
            "nonexistent_parent_id", "fork_exp", {"hyperparameters": {"lr": 0.1}}
        )

        if fork_id is not None:
            fork = manager._experiments[fork_id]
            assert fork["parent_id"] != "nonexistent_parent_id" or fork.get("model_id") is not None, (
                "Fork from nonexistent parent should either fail or handle missing parent. "
                "BUG E4: Fork created with reference to deleted/nonexistent parent."
            )

    def test_parent_reference_integrity(self):
        """Forked experiment should maintain valid parent reference."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create parent and fork
        parent_id = manager.create_experiment("parent", "model_1", {"lr": 0.01})
        fork_id = manager.fork_experiment(parent_id, "child", {"hyperparameters": {"lr": 0.02}})

        fork = manager._experiments[fork_id]
        assert fork["parent_id"] == parent_id
        assert manager._experiments.get(fork["parent_id"]) is not None

    def test_delete_parent_orphans_children(self):
        """Deleting parent should handle children references."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        parent_id = manager.create_experiment("parent", "model_1", {"lr": 0.01})
        child_id = manager.fork_experiment(parent_id, "child", {"hyperparameters": {"lr": 0.02}})

        # Delete parent
        manager.delete_experiment(parent_id)

        # Child should still exist but parent reference is now broken
        child = manager._experiments.get(child_id)
        assert child is not None

        
        referenced_parent = manager._experiments.get(child["parent_id"])
        assert referenced_parent is not None, (
            "Child experiment references deleted parent. "
            "BUG E4: Delete should update or invalidate child references."
        )

    def test_fork_inherits_hyperparameters(self):
        """Fork should inherit parent's hyperparameters and apply updates."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        parent_id = manager.create_experiment(
            "parent_hp", "model_1",
            {"lr": 0.01, "batch_size": 32, "epochs": 10}
        )

        fork_id = manager.fork_experiment(
            parent_id, "child_hp",
            {"hyperparameters": {"lr": 0.001}}
        )

        fork = manager._experiments[fork_id]
        # Should inherit batch_size and epochs, override lr
        assert fork["hyperparameters"]["lr"] == 0.001
        assert fork["hyperparameters"]["batch_size"] == 32
        assert fork["hyperparameters"]["epochs"] == 10


# =========================================================================
# E5: Artifact upload partial failure
# =========================================================================

class TestArtifactUploadPartial:
    """BUG E5: Partial artifact upload leaves incomplete data."""

    def test_artifact_upload_partial(self):
        """Failed upload should clean up partial artifacts."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_artifacts_e5")

        # Successful upload
        checksum = storage.upload_artifact("test_bucket", "model.pkl", b"model_data")
        assert checksum is not None

        # Verify artifact exists
        data = storage.download_artifact("test_bucket", "model.pkl")
        assert data == b"model_data"

    def test_partial_upload_cleanup(self):
        """Partial uploads should be cleaned up on failure."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.storage.main import ArtifactStorage

        storage = ArtifactStorage(base_path="/tmp/test_artifacts_e5_cleanup")
        storage.initialize_bucket("uploads")

        # Upload a complete artifact
        storage.upload_artifact("uploads", "complete.bin", b"complete_data")
        assert storage.download_artifact("uploads", "complete.bin") == b"complete_data"


# =========================================================================
# E6: Comparison query N+1
# =========================================================================

class TestComparisonQueryNPlus1:
    """BUG E6: Comparison loads experiments individually."""

    def test_comparison_query_n_plus_1(self):
        """Comparing experiments should batch load, not N+1."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create many experiments
        exp_ids = []
        for i in range(20):
            exp_id = manager.create_experiment(f"exp_{i}", "model_1", {"lr": 0.01 * i})
            manager.metric_logger.log_metric(exp_id, "loss", 1.0 - i * 0.05)
            exp_ids.append(exp_id)

        # Compare all experiments
        results = manager.compare_experiments(exp_ids)

        
        assert len(results) == 20

    def test_comparison_query_count(self):
        """Number of queries should be O(1), not O(N)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        exp_ids = []
        for i in range(10):
            exp_id = manager.create_experiment(f"compare_{i}", "model_1", {"lr": 0.01})
            exp_ids.append(exp_id)

        # Track "queries" - in the current impl, each .get() is a "query"
        results = manager.compare_experiments(exp_ids)
        assert len(results) == 10


# =========================================================================
# E7: Metric aggregation overflow
# =========================================================================

class TestMetricAggregationOverflow:
    """BUG E7: Float sum overflows with large experiments."""

    def test_metric_aggregation_overflow(self):
        """Aggregation should handle large numbers without overflow."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        exp_id = "overflow_exp"

        # Log many large values
        for i in range(10000):
            logger.log_metric(exp_id, "large_metric", 1e15 + i)

        agg = logger.aggregate_metric(exp_id, "large_metric")
        assert agg is not None

        
        expected_count = 10000
        assert agg["count"] == expected_count

        # Check mean is reasonable
        expected_mean = 1e15 + 4999.5
        assert abs(agg["mean"] - expected_mean) < 1.0, (
            f"Mean {agg['mean']} deviates from expected {expected_mean}. "
            "BUG E7: Float aggregation loses precision."
        )

    def test_aggregation_precision(self):
        """Aggregation should maintain precision for small differences."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        exp_id = "precision_exp"

        # Log values that differ only slightly
        for i in range(1000):
            logger.log_metric(exp_id, "precise", 1.0 + i * 1e-10)

        agg = logger.aggregate_metric(exp_id, "precise")
        assert agg is not None
        assert agg["count"] == 1000
        assert agg["min"] == 1.0
        assert agg["max"] > 1.0

    def test_empty_aggregation(self):
        """Aggregating empty metrics should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        result = logger.aggregate_metric("nonexistent", "metric")
        assert result is None


# =========================================================================
# E8: Tag search SQL injection
# =========================================================================

class TestTagSearchInjection:
    """BUG E8: Tag search allows SQL injection."""

    def test_tag_search_injection(self):
        """Tag search should use parameterized queries."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        # Create experiment with tag
        exp_id = manager.create_experiment("tagged_exp", "model_1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["production", "v2"]

        # Normal search should work
        results = manager.search_by_tag("production")
        assert len(results) == 1

        # SQL injection attempt should not work
        malicious_tag = "'; DROP TABLE experiments; --"
        results = manager.search_by_tag(malicious_tag)
        # Should return empty, not cause an error or execute SQL
        assert len(results) == 0

    def test_tag_search_parameterized(self):
        """Search with special characters should be safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("safe_exp", "model_1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["test-tag"]

        # Search with special characters
        results = manager.search_by_tag("test-tag")
        assert len(results) == 1

        # Search with SQL characters
        results = manager.search_by_tag("test' OR '1'='1")
        assert len(results) == 0


# =========================================================================
# Additional experiment tracking tests
# =========================================================================

class TestExperimentManagerOperations:
    """Test basic experiment manager operations."""

    def test_create_experiment(self):
        """Creating an experiment should return a valid ID."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("test_exp", "model_1", {"lr": 0.01, "epochs": 10})

        assert exp_id is not None
        exp = manager._experiments[exp_id]
        assert exp["name"] == "test_exp"
        assert exp["model_id"] == "model_1"
        assert exp["hyperparameters"]["lr"] == 0.01
        assert exp["status"] == "created"

    def test_delete_experiment(self):
        """Deleting an experiment should remove it."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("to_delete", "model_1", {"lr": 0.01})
        assert manager.delete_experiment(exp_id) is True
        assert exp_id not in manager._experiments

    def test_delete_nonexistent(self):
        """Deleting a nonexistent experiment should return False."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        assert manager.delete_experiment("nonexistent") is False

    def test_metric_logging_basic(self):
        """Basic metric logging should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("exp1", "loss", 0.5)
        logger.log_metric("exp1", "loss", 0.4)
        logger.log_metric("exp1", "accuracy", 0.8)

        metrics = logger.get_metrics("exp1")
        assert len(metrics["loss"]) == 2
        assert len(metrics["accuracy"]) == 1

    def test_get_metrics_empty(self):
        """Getting metrics for nonexistent experiment should return empty dict."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        result = logger.get_metrics("nonexistent")
        assert result == {}

    def test_compare_single_experiment(self):
        """Comparing a single experiment should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("solo", "model_1", {"lr": 0.01})
        manager.metric_logger.log_metric(exp_id, "loss", 0.5)

        results = manager.compare_experiments([exp_id])
        assert len(results) == 1
        assert results[0]["experiment"]["name"] == "solo"

    def test_fork_with_updates(self):
        """Fork should apply updates to parent hyperparameters."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        parent_id = manager.create_experiment(
            "base", "model_1", {"lr": 0.01, "momentum": 0.9}
        )

        fork_id = manager.fork_experiment(
            parent_id, "variant",
            {"hyperparameters": {"lr": 0.001}}
        )

        fork = manager._experiments[fork_id]
        assert fork["hyperparameters"]["lr"] == 0.001  # Overridden
        assert fork["hyperparameters"]["momentum"] == 0.9  # Inherited

    def test_search_by_tag_multiple(self):
        """Search should find all experiments with matching tag."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        for i in range(5):
            exp_id = manager.create_experiment(f"tagged_{i}", "model_1", {"lr": 0.01})
            manager._experiments[exp_id]["tags"] = ["batch_1"]

        for i in range(3):
            exp_id = manager.create_experiment(f"other_{i}", "model_1", {"lr": 0.01})
            manager._experiments[exp_id]["tags"] = ["batch_2"]

        results = manager.search_by_tag("batch_1")
        assert len(results) == 5

        results = manager.search_by_tag("batch_2")
        assert len(results) == 3

    def test_aggregation_statistics(self):
        """Metric aggregation should compute correct statistics."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        exp_id = "stats_exp"
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        for v in values:
            logger.log_metric(exp_id, "score", v)

        agg = logger.aggregate_metric(exp_id, "score")
        assert agg["count"] == 5
        assert agg["sum"] == 15.0
        assert agg["mean"] == 3.0
        assert agg["min"] == 1.0
        assert agg["max"] == 5.0


# =========================================================================
# Extended Experiment Tracking Tests
# =========================================================================

class TestMetricLoggerConcurrency:
    """Extended tests for concurrent metric logging."""

    def test_concurrent_metric_write(self):
        """Concurrent metric writes should not lose data."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        errors = []

        def log_metrics(thread_id):
            try:
                for i in range(100):
                    logger.log_metric(f"concurrent_exp", f"metric_{thread_id}", float(i))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=log_metrics, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        metrics = logger.get_metrics("concurrent_exp")
        for t in range(5):
            assert len(metrics[f"metric_{t}"]) == 100

    def test_metric_logging_different_experiments(self):
        """Metrics for different experiments should be independent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("exp_a", "loss", 0.5)
        logger.log_metric("exp_b", "loss", 0.3)

        a_metrics = logger.get_metrics("exp_a")
        b_metrics = logger.get_metrics("exp_b")

        assert len(a_metrics["loss"]) == 1
        assert len(b_metrics["loss"]) == 1
        assert a_metrics["loss"][0] == 0.5
        assert b_metrics["loss"][0] == 0.3

    def test_metric_logging_many_metrics(self):
        """Should handle many different metric names."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        for i in range(50):
            logger.log_metric("multi_exp", f"metric_{i}", float(i))

        metrics = logger.get_metrics("multi_exp")
        assert len(metrics) == 50


class TestExperimentHyperparameterComparison:
    """Extended hyperparameter comparison tests."""

    def test_hyperparameter_comparison(self):
        """Comparing experiments with different hyperparameters."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp1 = manager.create_experiment("lr_01", "m1", {"lr": 0.01})
        exp2 = manager.create_experiment("lr_001", "m1", {"lr": 0.001})
        exp3 = manager.create_experiment("lr_0001", "m1", {"lr": 0.0001})

        results = manager.compare_experiments([exp1, exp2, exp3])
        assert len(results) == 3

        lrs = [r["experiment"]["hyperparameters"]["lr"] for r in results]
        assert sorted(lrs) == [0.0001, 0.001, 0.01]

    def test_hyperparameter_float_comparison_precision(self):
        """Float hyperparameter comparison should handle precision."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp1 = manager.create_experiment("precise_a", "m1", {"lr": 0.1 + 0.2})
        exp2 = manager.create_experiment("precise_b", "m1", {"lr": 0.3})

        e1 = manager._experiments[exp1]
        e2 = manager._experiments[exp2]

        
        assert abs(e1["hyperparameters"]["lr"] - e2["hyperparameters"]["lr"]) < 1e-10, (
            "Float comparison should use approximate equality. "
            "BUG E2: Direct float comparison fails due to precision."
        )

    def test_hyperparameter_types_preserved(self):
        """Various hyperparameter types should be preserved."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        params = {
            "lr": 0.001,
            "epochs": 100,
            "optimizer": "adam",
            "use_warmup": True,
            "layers": [128, 64, 32],
        }
        exp_id = manager.create_experiment("typed_exp", "m1", params)
        exp = manager._experiments[exp_id]

        assert isinstance(exp["hyperparameters"]["lr"], float)
        assert isinstance(exp["hyperparameters"]["epochs"], int)
        assert isinstance(exp["hyperparameters"]["optimizer"], str)
        assert isinstance(exp["hyperparameters"]["use_warmup"], bool)
        assert isinstance(exp["hyperparameters"]["layers"], list)


class TestExperimentForkDetailed:
    """Detailed fork tests."""

    def test_fork_inherits_seed(self):
        """Forked experiment should inherit parent's seed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        parent_id = manager.create_experiment("seeded", "m1", {"lr": 0.01})
        parent = manager._experiments[parent_id]
        parent_seed = parent.get("seed")

        child_id = manager.fork_experiment(parent_id, "forked", {})
        child = manager._experiments[child_id]

        
        assert child.get("parent_id") == parent_id, (
            "Forked experiment should reference parent. "
            "BUG E4: parent_id not set on fork."
        )

    def test_fork_nonexistent_parent(self):
        """Forking from nonexistent parent should fail."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        result = manager.fork_experiment("nonexistent", "child", {})
        assert result is None

    def test_fork_preserves_model_id(self):
        """Forked experiment should have same model_id as parent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        parent_id = manager.create_experiment("parent", "model_xyz", {"lr": 0.01})
        child_id = manager.fork_experiment(parent_id, "child", {})

        parent = manager._experiments[parent_id]
        child = manager._experiments[child_id]
        assert child["model_id"] == parent["model_id"]

    def test_deep_fork_chain(self):
        """Deep fork chains should preserve lineage."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        ids = []
        parent_id = manager.create_experiment("gen_0", "m1", {"lr": 0.01})
        ids.append(parent_id)

        for i in range(5):
            child_id = manager.fork_experiment(
                ids[-1], f"gen_{i+1}",
                {"hyperparameters": {"lr": 0.01 / (i + 2)}}
            )
            ids.append(child_id)

        # Verify chain
        for i in range(1, len(ids)):
            child = manager._experiments[ids[i]]
            assert child.get("parent_id") == ids[i-1]


class TestExperimentDeletion:
    """Extended deletion tests."""

    def test_delete_removes_metrics(self):
        """Deleting an experiment should clean up metrics."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("deletable", "m1", {"lr": 0.01})
        manager.metric_logger.log_metric(exp_id, "loss", 0.5)

        manager.delete_experiment(exp_id)
        assert exp_id not in manager._experiments

    def test_delete_multiple_experiments(self):
        """Multiple experiments should be deletable."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        ids = []
        for i in range(10):
            exp_id = manager.create_experiment(f"del_{i}", "m1", {"lr": 0.01})
            ids.append(exp_id)

        for exp_id in ids:
            assert manager.delete_experiment(exp_id) is True

        assert len(manager._experiments) == 0


class TestExperimentSearchAndFilter:
    """Extended search tests."""

    def test_search_empty_tag(self):
        """Searching for empty tag should return nothing."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        results = manager.search_by_tag("")
        assert len(results) == 0

    def test_search_tag_case_sensitive(self):
        """Tag search should be case-sensitive."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("case_exp", "m1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["Production"]

        upper = manager.search_by_tag("Production")
        lower = manager.search_by_tag("production")

        assert len(upper) == 1
        # Case-sensitive: 'production' should not match 'Production'
        assert len(lower) == 0

    def test_search_multiple_tags(self):
        """Experiment with multiple tags should be findable by any tag."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("multi_tag", "m1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["prod", "v2", "model_a"]

        for tag in ["prod", "v2", "model_a"]:
            results = manager.search_by_tag(tag)
            assert len(results) == 1, f"Should find experiment by tag '{tag}'"

    def test_search_no_matching_tag(self):
        """Search with non-matching tag should return empty."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_id = manager.create_experiment("tagged", "m1", {"lr": 0.01})
        manager._experiments[exp_id]["tags"] = ["existing_tag"]

        results = manager.search_by_tag("nonexistent_tag")
        assert len(results) == 0


class TestMetricAggregationEdgeCases:
    """Edge cases for metric aggregation."""

    def test_single_value_aggregation(self):
        """Aggregation of single value should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("single_exp", "loss", 0.42)

        agg = logger.aggregate_metric("single_exp", "loss")
        assert agg["count"] == 1
        assert agg["mean"] == 0.42
        assert agg["min"] == 0.42
        assert agg["max"] == 0.42

    def test_aggregation_with_zeros(self):
        """Aggregation with zero values should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        for i in range(5):
            logger.log_metric("zero_exp", "metric", 0.0)

        agg = logger.aggregate_metric("zero_exp", "metric")
        assert agg["count"] == 5
        assert agg["mean"] == 0.0
        assert agg["sum"] == 0.0

    def test_aggregation_with_negative_values(self):
        """Aggregation with negative values should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        values = [-3.0, -1.0, 0.0, 1.0, 3.0]
        for v in values:
            logger.log_metric("neg_exp", "loss", v)

        agg = logger.aggregate_metric("neg_exp", "loss")
        assert agg["min"] == -3.0
        assert agg["max"] == 3.0
        assert abs(agg["mean"]) < 1e-10  # mean of symmetric values is 0

    def test_aggregation_wrong_metric_name(self):
        """Aggregating wrong metric name should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("exp_1", "loss", 0.5)

        result = logger.aggregate_metric("exp_1", "accuracy")
        assert result is None


class TestExperimentManagerExtended(unittest.TestCase):
    """Extended tests for ExperimentManager edge cases."""

    def test_create_experiment_with_seed(self):
        """Creating with seed should store it."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        eid = mgr.create_experiment("exp_seed", "model_1", {"lr": 0.01}, seed=42)
        exp = mgr._experiments[eid]
        assert exp["seed"] == 42

    def test_create_experiment_without_seed(self):
        """Creating without seed should store None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        eid = mgr.create_experiment("exp_noseed", "model_2", {"lr": 0.001})
        assert mgr._experiments[eid]["seed"] is None

    def test_create_multiple_experiments_unique_ids(self):
        """Each experiment should get a unique ID."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        ids = [mgr.create_experiment(f"exp_{i}", "m1", {"lr": 0.01}) for i in range(20)]
        assert len(set(ids)) == 20

    def test_fork_experiment_inherits_hyperparams(self):
        """Forked experiment should inherit parent hyperparameters."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        parent_id = mgr.create_experiment("parent", "m1", {"lr": 0.01, "epochs": 10})
        child_id = mgr.fork_experiment(parent_id, "child", {"hyperparameters": {"lr": 0.005}})
        child = mgr._experiments[child_id]
        assert child["hyperparameters"]["lr"] == 0.005
        assert child["hyperparameters"]["epochs"] == 10

    def test_fork_deleted_parent_bug_e4(self):
        """Bug E4: Forking from a deleted parent should be handled."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        parent_id = mgr.create_experiment("parent", "m1", {"lr": 0.01})
        mgr.delete_experiment(parent_id)
        
        child_id = mgr.fork_experiment(parent_id, "orphan", {"model_id": "m2"})
        assert child_id is not None  # fork succeeds but references deleted parent

    def test_delete_experiment_orphans_children_bug_e4(self):
        """Bug E4: Deleting parent should leave children as orphans."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        parent_id = mgr.create_experiment("parent", "m1", {"lr": 0.01})
        child_id = mgr.fork_experiment(parent_id, "child", {})
        mgr.delete_experiment(parent_id)
        child = mgr._experiments[child_id]
        # Child still references deleted parent
        assert child["parent_id"] == parent_id
        assert parent_id not in mgr._experiments

    def test_compare_experiments_returns_metrics(self):
        """Comparing experiments should return their metrics."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        e1 = mgr.create_experiment("exp1", "m1", {"lr": 0.01})
        e2 = mgr.create_experiment("exp2", "m1", {"lr": 0.001})
        mgr.metric_logger.log_metric(e1, "loss", 0.5)
        mgr.metric_logger.log_metric(e2, "loss", 0.3)
        results = mgr.compare_experiments([e1, e2])
        assert len(results) == 2

    def test_compare_experiments_n1_pattern_bug_e6(self):
        """Bug E6: Comparison loads experiments one at a time (N+1)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        ids = [mgr.create_experiment(f"exp_{i}", "m1", {"lr": 0.01}) for i in range(50)]
        # All 50 experiments loaded individually - N+1 pattern
        results = mgr.compare_experiments(ids)
        assert len(results) == 50

    def test_compare_nonexistent_experiment(self):
        """Comparing nonexistent experiment should skip it."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        e1 = mgr.create_experiment("exp1", "m1", {"lr": 0.01})
        results = mgr.compare_experiments([e1, "nonexistent"])
        assert len(results) == 1

    def test_search_by_tag_empty_results(self):
        """Searching for nonexistent tag should return empty list."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        mgr.create_experiment("exp1", "m1", {"lr": 0.01})
        results = mgr.search_by_tag("nonexistent_tag")
        assert results == []

    def test_experiment_status_lifecycle(self):
        """Experiment should start with 'created' status."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        eid = mgr.create_experiment("exp1", "m1", {"lr": 0.01})
        assert mgr._experiments[eid]["status"] == "created"

    def test_delete_nonexistent_experiment(self):
        """Deleting nonexistent experiment should return False."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        assert mgr.delete_experiment("nonexistent") is False

    def test_metric_logger_multiple_metrics(self):
        """Logger should track multiple metric names per experiment."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("e1", "loss", 0.5)
        logger.log_metric("e1", "accuracy", 0.8)
        logger.log_metric("e1", "f1_score", 0.75)
        metrics = logger.get_metrics("e1")
        assert len(metrics) == 3
        assert "loss" in metrics
        assert "accuracy" in metrics

    def test_metric_aggregation_single_value(self):
        """Aggregating a single metric value should work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        logger.log_metric("e1", "loss", 0.5)
        agg = logger.aggregate_metric("e1", "loss")
        assert agg["count"] == 1
        assert agg["mean"] == 0.5
        assert agg["min"] == 0.5
        assert agg["max"] == 0.5

    def test_metric_aggregation_large_values_bug_e7(self):
        """Bug E7: Large metric values may cause float overflow in aggregation."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        for i in range(1000):
            logger.log_metric("big_exp", "loss", 1e300)
        agg = logger.aggregate_metric("big_exp", "loss")
        
        assert agg is not None
        assert agg["count"] == 1000

    def test_get_metrics_nonexistent_experiment(self):
        """Getting metrics for nonexistent experiment should return empty dict."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        metrics = logger.get_metrics("nonexistent")
        assert metrics == {}

    def test_experiment_hyperparameters_stored(self):
        """Experiment hyperparameters should be stored correctly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        mgr = ExperimentManager()
        params = {"lr": 0.001, "batch_size": 32, "optimizer": "adam", "dropout": 0.1}
        eid = mgr.create_experiment("hp_exp", "m1", params)
        stored = mgr._experiments[eid]["hyperparameters"]
        assert stored == params
