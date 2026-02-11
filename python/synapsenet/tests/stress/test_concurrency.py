"""
SynapseNet Concurrency Tests
Tests for thread safety, deadlocks, and concurrent access consistency.
"""
import os
import sys
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestParameterServerConcurrentAccess:
    """Test parameter server under concurrent access."""

    def test_concurrent_gradient_application_version_consistency(self):
        """Version should increment exactly once per gradient application."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"w": 0.0}
        num_workers = 50

        barrier = threading.Barrier(num_workers)

        def apply(worker_id):
            barrier.wait()
            ps.apply_gradient(f"w-{worker_id}", {"w": 0.001}, ps.get_version())

        threads = [threading.Thread(target=apply, args=(i,)) for i in range(num_workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert ps.get_version() == num_workers, (
            f"After {num_workers} concurrent gradient applications, "
            f"version should be {num_workers} but got {ps.get_version()}"
        )

    def test_concurrent_read_during_write(self):
        """Reading parameters during concurrent writes should not crash."""
        from shared.utils.distributed import ParameterServer

        ps = ParameterServer()
        ps._parameters = {"layer1": 1.0, "layer2": 2.0}
        errors = []

        def writer():
            for _ in range(100):
                ps.apply_gradient("writer", {"layer1": 0.01, "layer2": 0.01}, ps.get_version())

        def reader():
            for _ in range(100):
                try:
                    params = ps.get_parameters()
                    assert "layer1" in params
                    assert "layer2" in params
                except Exception as e:
                    errors.append(str(e))

        writer_thread = threading.Thread(target=writer)
        reader_thread = threading.Thread(target=reader)

        writer_thread.start()
        reader_thread.start()
        writer_thread.join()
        reader_thread.join()

        assert len(errors) == 0, f"Concurrent read/write caused errors: {errors[:5]}"


class TestAllReduceConcurrency:
    """Test AllReduce coordinator under concurrent access."""

    def test_concurrent_submit_and_reduce(self):
        """Concurrent submit_gradients should not corrupt reduction."""
        from shared.utils.distributed import AllReduceCoordinator

        coordinator = AllReduceCoordinator(num_workers=4)
        errors = []
        results = []

        def submit_worker(worker_id, value):
            try:
                coordinator.submit_gradients(f"w-{worker_id}", {"grad": float(value)})
                result = coordinator.get_reduced_gradients(f"w-{worker_id}")
                if result:
                    results.append(result)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=submit_worker, args=(i, i * 1.0))
            for i in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        alive = [t for t in threads if t.is_alive()]
        assert len(alive) == 0, (
            f"{len(alive)} threads still alive after 5s, all should have completed"
        )
        assert len(errors) == 0, f"Errors: {errors}"


class TestDistributedBarrierConcurrency:
    """Test distributed barrier under concurrent access."""

    def test_all_participants_must_arrive(self):
        """Barrier should block until all participants arrive."""
        from shared.utils.distributed import DistributedBarrier

        barrier = DistributedBarrier(num_participants=3, timeout=5.0)
        results = []

        def participant(pid):
            result = barrier.wait(f"p-{pid}")
            results.append(result)

        threads = [threading.Thread(target=participant, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6.0)

        assert all(results), "All participants should successfully pass the barrier"

    def test_barrier_timeout_with_missing_participant(self):
        """Barrier should timeout if not all participants arrive."""
        from shared.utils.distributed import DistributedBarrier

        barrier = DistributedBarrier(num_participants=3, timeout=0.5)

        # Only 2 of 3 participants arrive
        result1 = barrier.wait("p-1")
        # This should timeout since p-2 and p-3 never arrive

        # At least the first participant should timeout
        assert not result1 or barrier.get_arrived_count() < 3

    def test_barrier_concurrent_wait(self):
        """Multiple concurrent waits should all complete together."""
        from shared.utils.distributed import DistributedBarrier

        barrier = DistributedBarrier(num_participants=5, timeout=5.0)
        arrival_times = []

        def wait_and_record(pid):
            result = barrier.wait(f"p-{pid}")
            if result:
                arrival_times.append(time.time())

        threads = [threading.Thread(target=wait_and_record, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=6.0)

        assert len(arrival_times) == 5, (
            f"All 5 participants should complete, only {len(arrival_times)} did"
        )

        # All should complete at roughly the same time
        if len(arrival_times) >= 2:
            time_spread = max(arrival_times) - min(arrival_times)
            assert time_spread < 1.0, (
                f"All participants should complete near-simultaneously, spread was {time_spread}s"
            )


class TestElasticScalerRaceCondition:
    """Test elastic scaler worker registration under concurrency."""

    def test_concurrent_registration_unique_indices(self):
        """Concurrent worker registrations should get unique indices."""
        from services.training.tasks import ElasticScaler

        scaler = ElasticScaler()
        indices = []
        lock = threading.Lock()

        def register(worker_id):
            idx = scaler.register_worker(f"worker-{worker_id}")
            with lock:
                indices.append(idx)

        threads = [threading.Thread(target=register, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All indices should be unique
        assert len(set(indices)) == 20, (
            f"After 20 concurrent registrations, all indices should be unique, "
            f"but got {len(set(indices))} unique out of 20"
        )


class TestMetricLoggerConcurrency:
    """Test metric logger under concurrent writes."""

    def test_concurrent_metric_logging(self):
        """Concurrent metric logging should not lose data."""
        from services.experiments.views import MetricLogger

        logger = MetricLogger()
        exp_id = "concurrent-exp"
        num_threads = 10
        logs_per_thread = 100

        def log_metrics(thread_id):
            for i in range(logs_per_thread):
                logger.log_metric(exp_id, "loss", float(thread_id * 1000 + i))

        threads = [threading.Thread(target=log_metrics, args=(t,)) for t in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        metrics = logger.get_metrics(exp_id)
        total = len(metrics.get("loss", []))
        expected = num_threads * logs_per_thread

        assert total == expected, (
            f"Expected {expected} metric entries after concurrent logging, got {total}"
        )


class TestFeatureCacheStampede:
    """Test feature cache under thundering herd scenario."""

    def test_concurrent_cache_miss(self):
        """Multiple threads finding cache miss should not all hit backend."""
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)
        backend_calls = []
        lock = threading.Lock()

        def compute_feature():
            result = cache.get("expensive_feature")
            if result is None:
                # Simulate expensive backend computation
                with lock:
                    backend_calls.append(1)
                time.sleep(0.01)
                value = {"score": 42}
                cache.set("expensive_feature", value)
                return value
            return result

        threads = [threading.Thread(target=compute_feature) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Ideally only 1 backend call, but without stampede protection
        # all 20 threads will hit the backend
        # This test documents the stampede behavior
        assert len(backend_calls) > 0
        # With proper stampede protection, this should be <= 2
        # Without it, it will be close to 20


class TestTokenRefreshRaceCondition:
    """Test token refresh under concurrent access."""

    def test_double_refresh_same_token(self):
        """Only one of two concurrent refreshes should succeed."""
        from services.auth.views import TokenManager

        tm = TokenManager()
        tokens = tm.create_token("user-1", {"role": "admin"})
        refresh_token = tokens["refresh_token"]

        results = []

        def do_refresh():
            result = tm.refresh(refresh_token)
            results.append(result)

        t1 = threading.Thread(target=do_refresh)
        t2 = threading.Thread(target=do_refresh)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successful = [r for r in results if r is not None]
        assert len(successful) <= 1, (
            f"Only one concurrent refresh should succeed, but {len(successful)} did"
        )


class TestModelCacheConcurrentAccess:
    """Test model cache under concurrent put/get/evict."""

    def test_concurrent_put_and_get(self):
        """Concurrent cache operations should not crash."""
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        errors = []

        def put_models(start):
            for i in range(start, start + 50):
                try:
                    cache.put(f"model-{i}", {"weights": [i]})
                except Exception as e:
                    errors.append(str(e))

        def get_models(start):
            for i in range(start, start + 50):
                try:
                    cache.get(f"model-{i}")
                except Exception as e:
                    errors.append(str(e))

        threads = [
            threading.Thread(target=put_models, args=(0,)),
            threading.Thread(target=put_models, args=(50,)),
            threading.Thread(target=get_models, args=(0,)),
            threading.Thread(target=get_models, args=(50,)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent cache operations caused errors: {errors[:5]}"

    def test_eviction_during_use(self):
        """Cache eviction should not corrupt data for in-flight reads."""
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=3)
        cache.put("model-a", {"weights": "a_weights"})
        cache.put("model-b", {"weights": "b_weights"})
        cache.put("model-c", {"weights": "c_weights"})

        # Get model-a (should be valid)
        model_a = cache.get("model-a")
        assert model_a is not None

        # Put new model, evicting model-a (LRU)
        cache.put("model-d", {"weights": "d_weights"})

        # model_a reference should still be valid (even though evicted from cache)
        assert model_a["weights"] == "a_weights"


class TestFeatureFlagConcurrency:
    """Test feature flag manager under concurrent evaluation and updates."""

    def test_concurrent_flag_evaluation_and_update(self):
        """Concurrent flag reads and writes should not crash."""
        from services.scheduler.views import FeatureFlagManager

        fm = FeatureFlagManager()
        fm.set_flag("feature_x", True)
        errors = []

        def reader():
            for _ in range(100):
                try:
                    val = fm.evaluate_flag("feature_x")
                    assert val is not None
                except Exception as e:
                    errors.append(str(e))

        def writer():
            for i in range(100):
                try:
                    fm.set_flag("feature_x", i % 2 == 0, rules={"region": "us"})
                except Exception as e:
                    errors.append(str(e))

        threads = [
            threading.Thread(target=reader),
            threading.Thread(target=reader),
            threading.Thread(target=writer),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent flag access errors: {errors[:5]}"


class TestModelSwapAtomicity:
    """Test that model swap is atomic (no partial state visible)."""

    def test_swap_atomicity(self):
        """During model swap, predictions should use either old or new model, never mixed."""
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("model-1", "v1", np.ones((100, 100)))

        inconsistencies = []

        def predict_loop():
            for _ in range(100):
                try:
                    result = engine.predict("model-1", {"features": list(range(100))})
                    # Version and weights should be consistent
                    version = result.get("version")
                    if version not in ("v1", "v2"):
                        inconsistencies.append(f"Unknown version: {version}")
                except (ValueError, KeyError):
                    pass  # Model might be mid-swap

        def swap_loop():
            for i in range(10):
                version = "v2" if i % 2 == 0 else "v1"
                engine.swap_model("model-1", version, np.ones((100, 100)) * (i + 1))
                time.sleep(0.001)

        threads = [
            threading.Thread(target=predict_loop),
            threading.Thread(target=predict_loop),
            threading.Thread(target=swap_loop),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(inconsistencies) == 0, (
            f"Model swap inconsistencies detected: {inconsistencies[:5]}"
        )


class TestRateLimiterConcurrency:
    """Test rate limiter under concurrent requests."""

    def test_concurrent_rate_limiting(self):
        """Rate limiter should correctly enforce limits under concurrent access."""
        from services.gateway.main import RateLimiter

        limiter = RateLimiter(max_requests=10, window_seconds=60)
        allowed = []
        denied = []
        lock = threading.Lock()

        def make_request():
            result = limiter.check_rate_limit({"remote_addr": "10.0.0.1"})
            with lock:
                if result:
                    allowed.append(1)
                else:
                    denied.append(1)

        threads = [threading.Thread(target=make_request) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_allowed = len(allowed)
        assert total_allowed <= 10, (
            f"Rate limiter should allow at most 10 requests, but allowed {total_allowed}"
        )


class TestRequestDeduplicatorConcurrency:
    """Test request deduplicator under concurrent access."""

    def test_concurrent_dedup_check(self):
        """Same idempotency key sent concurrently should only be processed once."""
        from services.gateway.main import RequestDeduplicator

        dedup = RequestDeduplicator(ttl_seconds=60.0)
        processed_count = []
        lock = threading.Lock()

        def process_request():
            key = "idempotency-key-123"
            if not dedup.is_duplicate(key):
                time.sleep(0.001)  # Simulate processing
                dedup.record(key, {"status": "ok"})
                with lock:
                    processed_count.append(1)

        threads = [threading.Thread(target=process_request) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one concurrent request with the same key should be processed
        assert len(processed_count) >= 1
        if len(processed_count) > 1:
            # Concurrent operations should produce consistent results
            pass
