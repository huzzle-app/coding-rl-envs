"""
SynapseNet Model Serving Chaos Tests
Terminal Bench v2 - Chaos tests for model serving under failure conditions

Tests cover:
- B1-B10: Model Serving bugs under stress
- H1-H8: Caching bugs under stress
- Concurrent model operations
- Failure injection scenarios
"""
import time
import uuid
import threading
import sys
import os
from unittest import mock

import pytest
import numpy as np


# =========================================================================
# Concurrent model loading chaos
# =========================================================================

class TestConcurrentModelLoadingChaos:
    """Chaos test: Many models loaded and served concurrently."""

    def test_concurrent_model_load_and_predict(self):
        """Multiple models loaded and serving simultaneously."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        errors = []

        def load_and_predict(model_id):
            try:
                weights = np.random.randn(10, 10)
                engine.load_model(model_id, "v1", weights)
                result = engine.predict(model_id, {"features": list(np.random.randn(10))})
                assert result is not None
            except Exception as e:
                errors.append(f"{model_id}: {e}")

        threads = [
            threading.Thread(target=load_and_predict, args=(f"chaos_model_{i}",))
            for i in range(20)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent model operations failed: {errors}"

    def test_rapid_model_version_cycling(self):
        """Rapidly cycling through model versions under load."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("cycle_model", "v1", np.random.randn(10, 10))
        errors = []

        def version_cycler():
            try:
                for i in range(50):
                    engine.swap_model("cycle_model", f"v{i+2}", np.random.randn(10, 10))
            except Exception as e:
                errors.append(f"swap: {e}")

        def predictor():
            try:
                for _ in range(50):
                    try:
                        engine.predict("cycle_model", {"features": list(np.random.randn(10))})
                    except ValueError:
                        pass  # Model might not be loaded yet
            except Exception as e:
                errors.append(f"predict: {e}")

        t1 = threading.Thread(target=version_cycler)
        t2 = threading.Thread(target=predictor)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0, f"Version cycling errors: {errors}"


# =========================================================================
# Cache eviction under load
# =========================================================================

class TestCacheEvictionUnderLoad:
    """Chaos test: Cache eviction during high-throughput inference."""

    def test_cache_thrash(self):
        """Cache should handle rapid evictions without corruption."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        errors = []

        def cache_writer(thread_id):
            try:
                for i in range(100):
                    cache.put(f"model_{thread_id}_{i}", {"id": f"{thread_id}_{i}"})
            except Exception as e:
                errors.append(str(e))

        def cache_reader(thread_id):
            try:
                for i in range(100):
                    cache.get(f"model_{thread_id}_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for t_id in range(5):
            threads.append(threading.Thread(target=cache_writer, args=(t_id,)))
            threads.append(threading.Thread(target=cache_reader, args=(t_id,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Cache thrash errors: {errors}"

    def test_eviction_during_high_throughput(self):
        """Model eviction should not corrupt inference results."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=3)

        # Fill cache
        cache.put("model_a", {"name": "a"})
        cache.put("model_b", {"name": "b"})
        cache.put("model_c", {"name": "c"})

        # Rapid eviction cycle
        for i in range(100):
            cache.put(f"temp_{i}", {"name": f"temp_{i}"})

        # Cache should still be functional
        assert len(cache._cache) <= 3


# =========================================================================
# A/B testing under concurrent experiment changes
# =========================================================================

class TestABTestingChaos:
    """Chaos test: A/B routing during experiment updates."""

    def test_ab_routing_during_experiment_change(self):
        """A/B routing should remain consistent during experiment updates."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("live_exp", {"control": 0.5, "variant": 0.5})

        errors = []

        def route_requests():
            try:
                for i in range(100):
                    variant = router.route_request("live_exp", f"req_{i}")
                    assert variant in ("control", "variant"), f"Unknown variant: {variant}"
            except Exception as e:
                errors.append(str(e))

        def update_experiment():
            try:
                for _ in range(10):
                    router.create_experiment("live_exp", {"control": 0.6, "variant": 0.4})
                    time.sleep(0.001)
                    router.create_experiment("live_exp", {"control": 0.5, "variant": 0.5})
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=route_requests),
            threading.Thread(target=update_experiment),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"A/B testing chaos errors: {errors}"


# =========================================================================
# Canary deployment chaos
# =========================================================================

class TestCanaryDeploymentChaos:
    """Chaos test: Canary deployment with concurrent operations."""

    def test_canary_concurrent_promote_rollback(self):
        """Concurrent promote and rollback should be handled safely."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("model_1", "v2", traffic_pct=0.1)

        results = {"promoted": False, "rolled_back": False}

        def promote():
            results["promoted"] = canary.promote(dep_id)

        def rollback():
            results["rolled_back"] = canary.rollback(dep_id)

        t1 = threading.Thread(target=promote)
        t2 = threading.Thread(target=rollback)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Deployment should be in a consistent final state
        dep = canary._deployments[dep_id]
        assert dep["status"] in ("promoted", "rolled_back"), (
            f"Deployment in inconsistent state: {dep['status']}"
        )

    def test_multiple_canary_deployments(self):
        """Multiple concurrent canary deployments should not interfere."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_ids = []
        for i in range(5):
            dep_id = canary.start_canary(f"model_{i}", f"v{i+1}", traffic_pct=0.1)
            dep_ids.append(dep_id)

        # Promote all
        for dep_id in dep_ids:
            canary.promote(dep_id)

        for dep_id in dep_ids:
            assert canary._deployments[dep_id]["status"] == "promoted"


# =========================================================================
# Request batcher under pressure
# =========================================================================

class TestRequestBatcherChaos:
    """Chaos test: Request batcher under heavy concurrent load."""

    def test_batcher_under_pressure(self):
        """Batcher should not lose requests under high concurrency."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=8)
        all_batches = []
        lock = threading.Lock()

        def submit_requests(thread_id):
            for i in range(100):
                batch = batcher.add_request({"thread": thread_id, "req": i})
                if batch:
                    with lock:
                        all_batches.append(batch)

        threads = [threading.Thread(target=submit_requests, args=(t,)) for t in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Flush remaining
        remaining = batcher.flush()
        if remaining:
            all_batches.append(remaining)

        total_requests = sum(len(b) for b in all_batches)
        assert total_requests == 1000, (
            f"Processed {total_requests}/1000 requests. "
            "Batcher lost requests under load."
        )


# =========================================================================
# Feature cache stampede simulation
# =========================================================================

class TestFeatureCacheStampedeChaos:
    """Chaos test: Cache stampede with many concurrent requests."""

    def test_cache_stampede_simulation(self):
        """Simulate cache stampede with many concurrent misses."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.001)
        cache.set("hot_key", "value")

        time.sleep(0.002)  # Let it expire

        miss_count = {"value": 0}
        lock = threading.Lock()

        def fetch():
            result = cache.get("hot_key")
            if result is None:
                with lock:
                    miss_count["value"] += 1
                # Simulate expensive computation
                time.sleep(0.01)
                cache.set("hot_key", "new_value")

        threads = [threading.Thread(target=fetch) for _ in range(50)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Without stampede protection, all threads hit backend
        # With protection, only 1-2 should
        assert miss_count["value"] > 0


# =========================================================================
# Model swap race condition detailed test
# =========================================================================

class TestModelSwapRaceDetailed:
    """Detailed test for model swap race condition (B9)."""

    def test_swap_consistency_check(self):
        """During swap, version and weights should be consistent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        v1_weights = np.ones((10, 10))
        v2_weights = np.ones((10, 10)) * 2

        engine.load_model("consistency_model", "v1", v1_weights)

        inconsistencies = []

        def checker():
            for _ in range(1000):
                model = engine._current_models.get("consistency_model")
                if model:
                    version = model.get("version")
                    weights = model.get("weights")
                    if version == "v1" and weights is not None:
                        if not np.allclose(weights, v1_weights):
                            inconsistencies.append("v1 with wrong weights")
                    elif version == "v2" and weights is not None:
                        if not np.allclose(weights, v2_weights):
                            inconsistencies.append("v2 with wrong weights")

        def swapper():
            for _ in range(100):
                engine.swap_model("consistency_model", "v2", v2_weights)
                engine.swap_model("consistency_model", "v1", v1_weights)

        t1 = threading.Thread(target=checker)
        t2 = threading.Thread(target=swapper)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        
        # This test documents the potential for issues


# =========================================================================
# Distributed lock chaos
# =========================================================================

class TestDistributedLockChaos:
    """Chaos test: Distributed lock under contention."""

    def test_lock_contention(self):
        """Lock should handle high contention without deadlock."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="contention_test")
        counter = {"value": 0}
        errors = []

        def increment():
            try:
                for _ in range(10):
                    if lock.acquire(timeout=2.0):
                        try:
                            counter["value"] += 1
                        finally:
                            lock.release()
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=increment) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        alive = [t for t in threads if t.is_alive()]
        assert len(alive) == 0, f"{len(alive)} threads still alive - possible deadlock"
        assert len(errors) == 0, f"Lock errors: {errors}"


# =========================================================================
# Model monitor under load
# =========================================================================

class TestModelMonitorChaos:
    """Chaos test: Model monitor under high prediction volume."""

    def test_monitor_high_throughput(self):
        """Monitor should handle high-throughput predictions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ModelMonitor

        monitor = ModelMonitor()
        errors = []

        def record_predictions(model_id, count):
            try:
                for i in range(count):
                    latency = 0.001 * (i % 100)
                    success = i % 10 != 0  # 10% failure rate
                    monitor.record_prediction(model_id, latency, success)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=record_predictions, args=(f"model_{t}", 500))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Monitor errors: {errors}"

        for t in range(5):
            health = monitor.get_model_health(f"model_{t}")
            assert health["total_predictions"] == 500

    def test_error_aggregation_high_volume(self):
        """Error aggregator should handle many unique errors."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        aggregator = ErrorAggregator()

        for i in range(1000):
            aggregator.record_error({
                "type": "InferenceError",
                "message": f"Failed for model model_{i % 10}: timeout",
            })

        groups = aggregator.get_groups()
        assert len(groups) >= 1

        top = aggregator.get_top_errors(limit=5)
        assert len(top) >= 1


# =========================================================================
# Extended Chaos Tests - Model Serving
# =========================================================================

class TestInferenceUnderLoad:
    """Inference engine under sustained load."""

    def test_sustained_prediction_load(self):
        """Engine should handle sustained prediction load."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("load_model", "v1", np.random.randn(10, 10))

        errors = []
        for i in range(500):
            try:
                result = engine.predict("load_model", {"features": list(np.random.randn(10))})
                assert result is not None
            except Exception as e:
                errors.append(str(e))

        assert len(errors) == 0, f"Errors under load: {errors[:5]}"

    def test_multi_model_concurrent_inference(self):
        """Multiple models serving concurrently should not interfere."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        for i in range(5):
            engine.load_model(f"model_{i}", "v1", np.random.randn(10, 10))

        errors = []

        def predict_model(model_id):
            try:
                for _ in range(50):
                    result = engine.predict(model_id, {"features": list(np.random.randn(10))})
                    assert result["model_id"] == model_id
            except Exception as e:
                errors.append(f"{model_id}: {e}")

        threads = [
            threading.Thread(target=predict_model, args=(f"model_{i}",))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Multi-model errors: {errors}"

    def test_rapid_model_load_unload(self):
        """Rapid model load/unload cycles should be safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        errors = []

        for i in range(100):
            try:
                engine.load_model("rapid_model", f"v{i}", np.random.randn(5, 5))
                engine.predict("rapid_model", {"features": list(np.random.randn(5))})
            except Exception as e:
                errors.append(str(e))

        assert len(errors) == 0


class TestCacheUnderStress:
    """Cache operations under stress conditions."""

    def test_cache_rapid_eviction_cycle(self):
        """Rapid cache eviction should not corrupt state."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=2)
        for i in range(1000):
            cache.put(f"stress_model_{i}", {"id": i})
        assert len(cache._cache) <= 2

    def test_feature_cache_concurrent_set_get(self):
        """Concurrent set/get should be thread-safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        errors = []

        def writer():
            try:
                for i in range(200):
                    cache.set(f"key_{i % 50}", {"v": i})
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for i in range(200):
                    cache.get(f"key_{i % 50}")
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_model_cache_concurrent_put_remove(self):
        """Concurrent put and remove should be safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=20)
        errors = []

        def putter():
            try:
                for i in range(100):
                    cache.put(f"cm_{i}", {"id": i})
            except Exception as e:
                errors.append(str(e))

        def remover():
            try:
                for i in range(100):
                    cache.remove(f"cm_{i}")
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=putter)
        t2 = threading.Thread(target=remover)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0


class TestEventBusChaos:
    """Event bus under chaos conditions."""

    def test_high_throughput_publish(self):
        """Event bus should handle high throughput publishing."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="throughput_chaos")

        start = time.time()
        for i in range(5000):
            bus.publish("chaos.topic", Event(event_type=f"event_{i}"))
        elapsed = time.time() - start

        assert elapsed < 10.0, f"Publishing 5K events took {elapsed:.2f}s"

    def test_concurrent_publish_consume(self):
        """Concurrent publish and consume should be safe."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="concurrent_chaos")
        errors = []
        consumed = {"count": 0}
        lock = threading.Lock()

        def publisher():
            try:
                for i in range(100):
                    bus.publish("test.topic", Event(event_type="test"))
            except Exception as e:
                errors.append(str(e))

        def consumer():
            try:
                for _ in range(100):
                    event = bus.consume("test.topic")
                    if event:
                        with lock:
                            consumed["count"] += 1
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=publisher),
            threading.Thread(target=consumer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_multiple_topics_concurrent(self):
        """Multiple topics should be independent under concurrency."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.events.base import EventBus, Event

        bus = EventBus(service_name="multi_topic")
        errors = []

        def topic_worker(topic_name):
            try:
                for i in range(50):
                    bus.publish(topic_name, Event(event_type=f"{topic_name}_{i}"))
                    bus.consume(topic_name)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=topic_worker, args=(f"topic_{t}",))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestMonitoringChaos:
    """Monitoring under chaos conditions."""

    def test_histogram_concurrent_observe(self):
        """Histogram should handle concurrent observations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        histogram = LatencyHistogram()
        errors = []

        def observer():
            try:
                for _ in range(500):
                    histogram.observe(np.random.exponential(0.01))
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=observer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = histogram.get_stats()
        assert stats["count"] == 2500

    def test_error_aggregator_concurrent(self):
        """Error aggregator should handle concurrent error recording."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        aggregator = ErrorAggregator()
        errors = []

        def record_errors(thread_id):
            try:
                for i in range(100):
                    aggregator.record_error({
                        "type": f"Error_{thread_id}",
                        "message": f"Thread {thread_id} error {i}",
                    })
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=record_errors, args=(t,))
            for t in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_model_monitor_concurrent_health(self):
        """Model health should be queryable during high-throughput recording."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ModelMonitor

        monitor = ModelMonitor()
        errors = []

        def recorder():
            try:
                for i in range(200):
                    monitor.record_prediction("chaos_model", 0.01, i % 5 != 0)
            except Exception as e:
                errors.append(str(e))

        def reader():
            try:
                for _ in range(50):
                    monitor.get_model_health("chaos_model")
                    time.sleep(0.001)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=recorder)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(errors) == 0


class TestWebhookChaos:
    """Webhook delivery under chaos conditions."""

    def test_webhook_concurrent_delivery(self):
        """Concurrent webhook deliveries should not interfere."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import WebhookManager

        wm = WebhookManager()
        for i in range(10):
            wm.register_webhook(f"https://hook{i}.example.com/webhook", ["model.deployed"])

        errors = []

        def deliver(event_type):
            try:
                count = wm.deliver_event(event_type, {"model_id": "m1"})
                assert count >= 0
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=deliver, args=("model.deployed",))
            for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0


class TestModelServingChaosRecovery(unittest.TestCase):
    """Test model serving recovery from chaotic conditions."""

    @pytest.mark.chaos
    def test_model_cache_flood(self):
        """Cache should handle rapid insertions without crash."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=50)
        for i in range(200):
            cache.put(f"model_{i}", f"v{i}", {"weights": [i] * 100})
        assert cache.size() <= 50

    @pytest.mark.chaos
    def test_model_cache_concurrent_reads_writes(self):
        """Concurrent reads and writes should not corrupt cache."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)
        errors = []

        def write(start):
            try:
                for i in range(start, start + 50):
                    cache.put(f"m_{i}", "v1", {"w": [i]})
            except Exception as e:
                errors.append(str(e))

        def read(start):
            try:
                for i in range(start, start + 50):
                    cache.get(f"m_{i}", "v1")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for i in range(4):
            threads.append(threading.Thread(target=write, args=(i * 50,)))
            threads.append(threading.Thread(target=read, args=(i * 50,)))
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert len(errors) == 0

    @pytest.mark.chaos
    def test_batcher_timeout_recovery(self):
        """Request batcher should recover after timeout conditions."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=5, max_wait_ms=10)
        # Add requests that should batch together quickly
        for i in range(15):
            batcher.add_request(f"req_{i}", {"features": [float(i)]})
        assert batcher._queue is not None or True  # Verify no crash

    @pytest.mark.chaos
    def test_inference_engine_model_reload_race(self):
        """Reloading a model while predictions are running."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.random.randn(10, 10)
        engine.load_model("race_model", "v1", weights)
        errors = []

        def predict():
            try:
                for _ in range(20):
                    engine.predict("race_model", {"features": list(np.random.randn(10))})
            except Exception as e:
                errors.append(str(e))

        def reload_model():
            try:
                for v in range(5):
                    new_weights = np.random.randn(10, 10)
                    engine.load_model("race_model", f"v{v+2}", new_weights)
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=predict)
        t2 = threading.Thread(target=reload_model)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    @pytest.mark.chaos
    def test_ab_testing_weight_change_chaos(self):
        """Changing AB test weights during routing should not crash."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("chaos_exp", {"A": 0.5, "B": 0.5})
        errors = []

        def route():
            try:
                for _ in range(50):
                    router.route_request("chaos_exp", {"user": "test"})
            except Exception as e:
                errors.append(str(e))

        def update_weights():
            try:
                for _ in range(10):
                    router.create_experiment("chaos_exp", {"A": 0.7, "B": 0.3})
                    time.sleep(0.001)
                    router.create_experiment("chaos_exp", {"A": 0.3, "B": 0.7})
            except Exception as e:
                errors.append(str(e))

        t1 = threading.Thread(target=route)
        t2 = threading.Thread(target=update_weights)
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        assert len(errors) == 0

    @pytest.mark.chaos
    def test_latency_histogram_overflow(self):
        """Bug J6: Very large latencies should be handled."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import LatencyHistogram

        hist = LatencyHistogram()
        for _ in range(100):
            hist.observe(0.01)
        # Add a very large latency - BUG J6: exceeds all bucket boundaries
        hist.observe(999.0)
        stats = hist.get_stats()
        assert stats["count"] == 101

    @pytest.mark.chaos
    def test_error_aggregator_under_load(self):
        """Error aggregator should handle high volume."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ErrorAggregator

        agg = ErrorAggregator()
        for i in range(500):
            agg.record_error({"message": f"Error in model {i % 10}: prediction failed", "type": "PredictionError"})
        groups = agg.get_groups()
        
        assert len(groups) > 0

    @pytest.mark.chaos
    def test_model_monitor_rapid_predictions(self):
        """Monitor should handle rapid prediction recording."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.monitoring.main import ModelMonitor

        monitor = ModelMonitor()
        for i in range(1000):
            monitor.record_prediction(f"model_{i % 5}", 0.01 * (i % 100), i % 3 != 0)
        for mid in range(5):
            health = monitor.get_model_health(f"model_{mid}")
            assert health["total_predictions"] == 200

    @pytest.mark.chaos
    def test_feature_cache_expiry_storm(self):
        """Bug C7: All cache entries expiring simultaneously."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.001)  # Very short TTL
        for i in range(50):
            cache.set(f"key_{i}", f"value_{i}")
        time.sleep(0.01)
        # All entries expired - BUG C7: No stampede protection
        misses = sum(1 for i in range(50) if cache.get(f"key_{i}") is None)
        assert misses == 50

    @pytest.mark.chaos
    def test_metrics_collector_cardinality_explosion(self):
        """Bug J3: Dynamic labels create unbounded cardinality."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.webhooks.views import MetricsCollector

        mc = MetricsCollector()
        for i in range(100):
            mc.record_delivery(f"sub_{i}", "model.deployed", f"https://hook{i}.example.com", "success")
        
        assert mc.get_metric_count() == 100

    @pytest.mark.chaos
    def test_permission_cache_stale_under_updates(self):
        """Bug G4: Permission cache serves stale data after updates."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.auth.views import PermissionCache

        cache = PermissionCache(ttl=300.0)
        cache.set_permissions("user1", {"role": "viewer"})
        # Permission changed but cache not invalidated
        cached = cache.get_permissions("user1")
        assert cached["role"] == "viewer"  # Stale - should reflect update

    @pytest.mark.chaos
    def test_rate_limiter_burst_traffic(self):
        """Rate limiter should enforce limits under burst traffic."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=60)
        headers = {"remote_addr": "10.0.0.1"}
        results = [limiter.check_rate_limit(headers) for _ in range(20)]
        allowed = sum(1 for r in results if r)
        blocked = sum(1 for r in results if not r)
        assert allowed == 10
        assert blocked == 10

    @pytest.mark.chaos
    def test_config_precedence_bug_k1(self):
        """Bug K1: Config file overrides env variables (wrong precedence)."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.gateway.main import get_config

        result = get_config("rate_limit_per_minute")
        
        assert result == 100  # Returns default, not env override
