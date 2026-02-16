"""
SynapseNet Performance Tests
Terminal Bench v2 - Tests for inference latency, throughput, and resource usage

Tests cover:
- B2: Request batching performance
- B5: Model warm-up latency
- H1-H8: Cache performance
- Throughput benchmarks
"""
import time
import uuid
import threading
import sys
import os
import unittest
from unittest import mock

import pytest
import numpy as np


# =========================================================================
# Inference latency tests
# =========================================================================

class TestInferenceLatency:
    """Test inference latency is within acceptable bounds."""

    @pytest.mark.performance
    def test_single_inference_latency(self):
        """Single inference should complete within 100ms."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.random.randn(100, 100)
        engine.load_model("latency_model", "v1", weights)

        # Warm up
        engine.predict("latency_model", {"features": list(np.random.randn(100))})

        # Measure latency
        latencies = []
        for _ in range(100):
            start = time.time()
            engine.predict("latency_model", {"features": list(np.random.randn(100))})
            latencies.append(time.time() - start)

        avg_latency = np.mean(latencies)
        p99_latency = np.percentile(latencies, 99)

        assert avg_latency < 0.1, f"Average latency {avg_latency:.4f}s exceeds 100ms"
        assert p99_latency < 0.5, f"P99 latency {p99_latency:.4f}s exceeds 500ms"

    @pytest.mark.performance
    def test_cold_start_latency(self):
        """First inference after model load should not be excessively slow."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.random.randn(50, 50)
        engine.load_model("cold_model", "v1", weights)

        # First inference (cold start)
        start = time.time()
        engine.predict("cold_model", {"features": list(np.random.randn(50))})
        cold_latency = time.time() - start

        # Subsequent inference (warm)
        start = time.time()
        engine.predict("cold_model", {"features": list(np.random.randn(50))})
        warm_latency = time.time() - start

        # Cold start should not be more than 10x warm
        ratio = cold_latency / max(warm_latency, 1e-6)
        
        assert ratio < 10, (
            f"Cold/warm ratio is {ratio:.1f}x. "
            "Cold start should not be more than 10x slower."
        )


# =========================================================================
# Batching throughput tests
# =========================================================================

class TestBatchingThroughput:
    """Test request batching throughput."""

    @pytest.mark.performance
    def test_batch_vs_individual_throughput(self):
        """Batching should improve throughput over individual requests."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=32)

        # Measure batch collection throughput
        start = time.time()
        batches_collected = 0
        for i in range(1000):
            batch = batcher.add_request({"input": f"data_{i}"})
            if batch:
                batches_collected += 1
        remaining = batcher.flush()
        if remaining:
            batches_collected += 1
        batch_time = time.time() - start

        assert batches_collected > 0
        assert batch_time < 1.0, f"Batching 1000 requests took {batch_time:.2f}s"

    @pytest.mark.performance
    def test_batch_timeout_behavior(self):
        """Batch timeout should flush partial batches."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=100)

        # Add fewer requests than batch size
        for i in range(10):
            batcher.add_request({"input": f"data_{i}"})

        
        # But since we're not using async timeout, we manually flush
        flushed = batcher.flush()
        assert len(flushed) == 10


# =========================================================================
# Cache performance tests
# =========================================================================

class TestCachePerformance:
    """Test cache hit rate and performance."""

    @pytest.mark.performance
    def test_cache_hit_rate(self):
        """Cache should have high hit rate for repeated accesses."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)

        # Populate cache
        for i in range(50):
            cache.put(f"model_{i}", {"id": i, "weights": np.random.randn(10)})

        # Access pattern: 80% hits on cached models, 20% misses
        hits = 0
        misses = 0
        for _ in range(1000):
            if np.random.random() < 0.8:
                key = f"model_{np.random.randint(0, 50)}"
            else:
                key = f"model_{np.random.randint(50, 200)}"

            result = cache.get(key)
            if result is not None:
                hits += 1
            else:
                misses += 1

        hit_rate = hits / (hits + misses)
        assert hit_rate > 0.7, f"Cache hit rate {hit_rate:.2%} is too low"

    @pytest.mark.performance
    def test_cache_operation_speed(self):
        """Cache operations should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=1000)

        # Write performance
        start = time.time()
        for i in range(1000):
            cache.put(f"perf_model_{i}", {"id": i})
        write_time = time.time() - start

        # Read performance
        start = time.time()
        for i in range(1000):
            cache.get(f"perf_model_{i}")
        read_time = time.time() - start

        assert write_time < 1.0, f"1000 cache writes took {write_time:.2f}s"
        assert read_time < 0.5, f"1000 cache reads took {read_time:.2f}s"

    @pytest.mark.performance
    def test_feature_cache_performance(self):
        """Feature cache should serve requests quickly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)

        # Populate
        for i in range(100):
            cache.set(f"feature_{i}", {"score": np.random.random()})

        # Measure read latency
        start = time.time()
        for _ in range(10000):
            key = f"feature_{np.random.randint(0, 100)}"
            cache.get(key)
        read_time = time.time() - start

        avg_read_us = (read_time / 10000) * 1e6
        assert avg_read_us < 100, f"Average read latency {avg_read_us:.1f}us exceeds 100us"


# =========================================================================
# Model loading performance
# =========================================================================

class TestModelLoadingPerformance:
    """Test model loading performance."""

    @pytest.mark.performance
    def test_model_load_time(self):
        """Model loading should complete quickly."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()

        # Measure load time for various model sizes
        sizes = [10, 100, 500]
        for size in sizes:
            weights = np.random.randn(size, size)
            start = time.time()
            engine.load_model(f"model_{size}", "v1", weights)
            load_time = time.time() - start

            assert load_time < 1.0, (
                f"Loading {size}x{size} model took {load_time:.2f}s"
            )

    @pytest.mark.performance
    def test_model_swap_time(self):
        """Model swap should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("swap_perf", "v1", np.random.randn(100, 100))

        start = time.time()
        for i in range(100):
            engine.swap_model("swap_perf", f"v{i+2}", np.random.randn(100, 100))
        swap_time = time.time() - start

        avg_swap = swap_time / 100
        assert avg_swap < 0.01, f"Average swap time {avg_swap:.4f}s exceeds 10ms"


# =========================================================================
# Histogram performance
# =========================================================================

class TestHistogramPerformance:
    """Test histogram observation performance."""

    @pytest.mark.performance
    def test_histogram_observation_speed(self):
        """Histogram should handle high-frequency observations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        histogram = LatencyHistogram()

        start = time.time()
        for i in range(100000):
            histogram.observe(np.random.exponential(0.01))
        observe_time = time.time() - start

        assert observe_time < 5.0, (
            f"100K observations took {observe_time:.2f}s"
        )

        stats = histogram.get_stats()
        assert stats["count"] == 100000

    @pytest.mark.performance
    def test_histogram_percentile_speed(self):
        """Percentile computation should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        histogram = LatencyHistogram()
        for _ in range(10000):
            histogram.observe(np.random.exponential(0.05))

        start = time.time()
        for _ in range(1000):
            histogram.get_percentile(50)
            histogram.get_percentile(95)
            histogram.get_percentile(99)
        percentile_time = time.time() - start

        assert percentile_time < 1.0


# =========================================================================
# Concurrent throughput tests
# =========================================================================

class TestConcurrentThroughput:
    """Test system throughput under concurrent load."""

    @pytest.mark.performance
    def test_concurrent_prediction_throughput(self):
        """System should handle many concurrent predictions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("throughput_model", "v1", np.random.randn(10, 10))

        predictions = {"count": 0}
        lock = threading.Lock()
        errors = []

        def predictor():
            try:
                for _ in range(100):
                    engine.predict("throughput_model", {"features": list(np.random.randn(10))})
                    with lock:
                        predictions["count"] += 1
            except Exception as e:
                errors.append(str(e))

        start = time.time()
        threads = [threading.Thread(target=predictor) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.time() - start

        assert len(errors) == 0, f"Throughput test errors: {errors}"
        assert predictions["count"] == 1000

        throughput = predictions["count"] / elapsed
        assert throughput > 100, (
            f"Throughput {throughput:.0f} predictions/s is too low"
        )

    @pytest.mark.performance
    def test_event_bus_throughput(self):
        """Event bus should handle high message rates."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="throughput_test")

        start = time.time()
        for i in range(10000):
            event = Event(event_type="benchmark")
            bus.publish("benchmark.topic", event)
        publish_time = time.time() - start

        assert publish_time < 5.0, (
            f"Publishing 10K events took {publish_time:.2f}s"
        )


# =========================================================================
# Memory usage tests
# =========================================================================

class TestMemoryUsage:
    """Test memory usage patterns."""

    @pytest.mark.performance
    def test_model_cache_memory_bound(self):
        """Model cache should respect max_size."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=10)

        # Insert more than max_size
        for i in range(100):
            cache.put(f"model_{i}", {"id": i, "data": np.random.randn(100)})

        # Cache should not exceed max_size
        assert len(cache._cache) <= 10, (
            f"Cache has {len(cache._cache)} entries, max is 10"
        )

    @pytest.mark.performance
    def test_event_bus_memory(self):
        """Event bus should not accumulate unbounded messages."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="memory_test")

        # Publish and consume to prevent accumulation
        for i in range(1000):
            bus.publish("memory.topic", Event(event_type="test"))

        # Consume all
        while bus.consume("memory.topic"):
            pass

        assert len(bus._published_events) == 0

    @pytest.mark.performance
    def test_metric_logger_memory(self):
        """Metric logger should handle large histories efficiently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()

        # Log many metrics
        for i in range(10000):
            logger.log_metric("exp_1", "loss", float(i))

        metrics = logger.get_metrics("exp_1")
        assert len(metrics["loss"]) == 10000

        # Aggregation should still work
        agg = logger.aggregate_metric("exp_1", "loss")
        assert agg["count"] == 10000


# =========================================================================
# Distributed lock performance
# =========================================================================

class TestDistributedLockPerformance:
    """Test distributed lock acquisition performance."""

    @pytest.mark.performance
    def test_lock_acquisition_speed(self):
        """Lock acquisition should be fast when uncontested."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        latencies = []
        for i in range(100):
            lock = DistributedLock(lock_name=f"perf_lock_{i}")
            start = time.time()
            lock.acquire(timeout=1.0)
            latencies.append(time.time() - start)
            lock.release()

        avg_latency = np.mean(latencies)
        assert avg_latency < 0.01, (
            f"Average lock acquisition {avg_latency*1000:.1f}ms exceeds 10ms"
        )

    @pytest.mark.performance
    def test_lock_throughput(self):
        """Lock should support high throughput acquire/release cycles."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="throughput_lock")

        start = time.time()
        for _ in range(1000):
            lock.acquire(timeout=1.0)
            lock.release()
        elapsed = time.time() - start

        throughput = 1000 / elapsed
        assert throughput > 1000, (
            f"Lock throughput {throughput:.0f} ops/s is too low"
        )


# =========================================================================
# Extended Performance Tests
# =========================================================================

class TestFeatureStorePerformance:
    """Performance tests for feature store operations."""

    @pytest.mark.performance
    def test_feature_write_throughput(self):
        """Feature writes should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()

        start = time.time()
        for i in range(1000):
            store.write_feature(f"entity_{i}", "group", {"score": float(i)})
        write_time = time.time() - start

        assert write_time < 2.0, f"1000 feature writes took {write_time:.2f}s"

    @pytest.mark.performance
    def test_feature_read_throughput(self):
        """Feature reads should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureStore

        store = FeatureStore()
        for i in range(100):
            store.write_feature(f"entity_{i}", "group", {"score": float(i)})

        start = time.time()
        for i in range(1000):
            store.read_online(f"entity_{i % 100}", "group")
        read_time = time.time() - start

        assert read_time < 1.0, f"1000 feature reads took {read_time:.2f}s"

    @pytest.mark.performance
    def test_drift_detection_speed(self):
        """Drift detection should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.1)
        for i in range(100):
            detector.set_reference(f"feature_{i}", mean=0.0, std=1.0)

        start = time.time()
        for _ in range(10000):
            detector.detect_drift(
                f"feature_{np.random.randint(0, 100)}",
                current_mean=np.random.randn(),
                current_std=abs(np.random.randn()) + 0.1,
            )
        detect_time = time.time() - start

        assert detect_time < 2.0, f"10K drift detections took {detect_time:.2f}s"


class TestExperimentPerformance:
    """Performance tests for experiment tracking."""

    @pytest.mark.performance
    def test_metric_logging_throughput(self):
        """Metric logging should handle high throughput."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import MetricLogger

        logger = MetricLogger()

        start = time.time()
        for i in range(10000):
            logger.log_metric("perf_exp", "loss", float(i))
        log_time = time.time() - start

        assert log_time < 2.0, f"10K metric logs took {log_time:.2f}s"

    @pytest.mark.performance
    def test_experiment_creation_speed(self):
        """Experiment creation should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()

        start = time.time()
        for i in range(500):
            manager.create_experiment(f"exp_{i}", "model_1", {"lr": 0.01 * i})
        create_time = time.time() - start

        assert create_time < 2.0, f"500 experiment creations took {create_time:.2f}s"

    @pytest.mark.performance
    def test_experiment_comparison_speed(self):
        """Comparing many experiments should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.experiments.views import ExperimentManager

        manager = ExperimentManager()
        exp_ids = []
        for i in range(50):
            exp_id = manager.create_experiment(f"compare_{i}", "m1", {"lr": 0.01})
            manager.metric_logger.log_metric(exp_id, "loss", float(i))
            exp_ids.append(exp_id)

        start = time.time()
        results = manager.compare_experiments(exp_ids)
        compare_time = time.time() - start

        assert len(results) == 50
        assert compare_time < 1.0, f"Comparing 50 experiments took {compare_time:.2f}s"


class TestPipelinePerformance:
    """Performance tests for data pipeline."""

    @pytest.mark.performance
    def test_partition_routing_speed(self):
        """Partition routing should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import PartitionRouter

        router = PartitionRouter(num_partitions=16)

        start = time.time()
        for i in range(100000):
            router.route(f"key_{i}")
        route_time = time.time() - start

        assert route_time < 5.0, f"100K partition routes took {route_time:.2f}s"

    @pytest.mark.performance
    def test_validation_speed(self):
        """Data validation should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import DataValidator

        validator = DataValidator()
        validator.register_schema("perf_schema", 1, {"required": ["id", "name", "value"]})

        start = time.time()
        for i in range(10000):
            validator.validate(
                {"id": str(i), "name": f"item_{i}", "value": float(i)},
                "perf_schema",
            )
        validate_time = time.time() - start

        assert validate_time < 2.0, f"10K validations took {validate_time:.2f}s"

    @pytest.mark.performance
    def test_backfill_processing_speed(self):
        """Backfill processing should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.pipeline.main import BackfillProcessor

        processor = BackfillProcessor()

        start = time.time()
        for i in range(1000):
            processor.process_record(f"record_{i}", {"data": f"value_{i}"})
        process_time = time.time() - start

        assert process_time < 2.0, f"1000 backfill records took {process_time:.2f}s"


class TestModelMetadataPerformance:
    """Performance tests for model metadata."""

    @pytest.mark.performance
    def test_model_creation_speed(self):
        """Model creation should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()

        start = time.time()
        for i in range(500):
            store.create_model({"name": f"perf_model_{i}"}, f"user_{i}")
        create_time = time.time() - start

        assert create_time < 2.0, f"500 model creations took {create_time:.2f}s"

    @pytest.mark.performance
    def test_model_listing_speed(self):
        """Model listing should be fast even with many models."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.models.main import ModelMetadata

        store = ModelMetadata()
        for i in range(200):
            store.create_model(
                {"name": f"list_model_{i}", "tenant_id": f"t_{i % 10}"},
                f"user_{i}",
            )

        start = time.time()
        for t in range(10):
            store.list_models(tenant_id=f"t_{t}")
        list_time = time.time() - start

        assert list_time < 1.0, f"10 list operations took {list_time:.2f}s"


class TestDriftDetectionPerformance(unittest.TestCase):
    """Performance tests for drift detection operations."""

    @pytest.mark.performance
    def test_drift_detection_many_features(self):
        """Drift detection should be fast for many features."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector(threshold=0.05)
        for i in range(500):
            detector.set_reference(f"feature_{i}", float(i), 1.0)

        start = time.time()
        features = {f"feature_{i}": (float(i) + 0.1, 1.0) for i in range(500)}
        detector.detect_multivariate_drift(features)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"500-feature drift detection took {elapsed:.2f}s"

    @pytest.mark.performance
    def test_drift_detection_repeated(self):
        """Repeated drift checks should be consistently fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import DriftDetector

        detector = DriftDetector()
        detector.set_reference("f1", 100.0, 10.0)

        start = time.time()
        for _ in range(10000):
            detector.detect_drift("f1", 101.0, 10.0)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"10000 drift checks took {elapsed:.2f}s"


class TestFeatureTransformPerformance(unittest.TestCase):
    """Performance tests for feature transformation pipeline."""

    @pytest.mark.performance
    def test_large_pipeline_execution(self):
        """Pipeline with many transforms should execute efficiently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        for i in range(100):
            pipeline.add_transform(
                f"transform_{i}",
                lambda x, idx=i: x.get(f"f_{idx}", 0) + 1,
                [f"f_{i}"],
                f"out_{i}",
            )

        features = {f"f_{i}": float(i) for i in range(100)}
        start = time.time()
        for _ in range(100):
            pipeline.execute(features)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"100 pipeline executions took {elapsed:.2f}s"

    @pytest.mark.performance
    def test_pipeline_with_heavy_transforms(self):
        """Pipeline with compute-heavy transforms should complete."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.ml.feature_utils import FeatureTransformPipeline

        pipeline = FeatureTransformPipeline()
        pipeline.add_transform(
            "heavy",
            lambda x: sum(range(1000)),
            ["val"],
            "heavy_result",
        )
        features = {"val": 1.0}
        start = time.time()
        for _ in range(500):
            pipeline.execute(features)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"500 heavy transform executions took {elapsed:.2f}s"


class TestCachePerformance(unittest.TestCase):
    """Performance tests for feature caching."""

    @pytest.mark.performance
    def test_cache_write_throughput(self):
        """Cache writes should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        start = time.time()
        for i in range(5000):
            cache.set(f"key_{i}", {"value": i, "scores": [0.1, 0.2]})
        elapsed = time.time() - start
        assert elapsed < 1.0, f"5000 cache writes took {elapsed:.2f}s"

    @pytest.mark.performance
    def test_cache_read_throughput(self):
        """Cache reads should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        for i in range(1000):
            cache.set(f"key_{i}", {"value": i})

        start = time.time()
        for i in range(10000):
            cache.get(f"key_{i % 1000}")
        elapsed = time.time() - start
        assert elapsed < 1.0, f"10000 cache reads took {elapsed:.2f}s"

    @pytest.mark.performance
    def test_cache_mixed_operations(self):
        """Mixed read/write operations should maintain throughput."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        start = time.time()
        for i in range(5000):
            cache.set(f"key_{i % 500}", {"value": i})
            cache.get(f"key_{(i + 100) % 500}")
        elapsed = time.time() - start
        assert elapsed < 1.5, f"5000 mixed ops took {elapsed:.2f}s"


class TestHistogramPerformance(unittest.TestCase):
    """Performance tests for latency histogram."""

    @pytest.mark.performance
    def test_histogram_high_volume(self):
        """Histogram should handle high volume observations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        hist = LatencyHistogram()
        start = time.time()
        for i in range(50000):
            hist.observe(0.001 * (i % 100))
        elapsed = time.time() - start
        assert elapsed < 2.0, f"50000 observations took {elapsed:.2f}s"
        stats = hist.get_stats()
        assert stats["count"] == 50000

    @pytest.mark.performance
    def test_histogram_percentile_speed(self):
        """Percentile calculations should be fast."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        hist = LatencyHistogram()
        for i in range(10000):
            hist.observe(0.001 * (i % 500))

        start = time.time()
        for _ in range(10000):
            hist.get_percentile(50)
            hist.get_percentile(95)
            hist.get_percentile(99)
        elapsed = time.time() - start
        assert elapsed < 2.0, f"30000 percentile calcs took {elapsed:.2f}s"


class TestErrorAggregatorPerformance(unittest.TestCase):
    """Performance tests for error aggregation."""

    @pytest.mark.performance
    def test_error_recording_throughput(self):
        """Error recording should be fast at high volume."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        agg = ErrorAggregator()
        start = time.time()
        for i in range(10000):
            agg.record_error({"message": f"Error in model_{i % 20}: failed", "type": "PredictionError"})
        elapsed = time.time() - start
        assert elapsed < 2.0, f"10000 error recordings took {elapsed:.2f}s"

    @pytest.mark.performance
    def test_top_errors_speed(self):
        """Getting top errors should be fast even with many groups."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        agg = ErrorAggregator()
        for i in range(5000):
            agg.record_error({"message": f"Error {i % 100}: detail {i}", "type": "TypeError"})

        start = time.time()
        for _ in range(100):
            agg.get_top_errors(10)
        elapsed = time.time() - start
        assert elapsed < 1.0, f"100 top_errors queries took {elapsed:.2f}s"
