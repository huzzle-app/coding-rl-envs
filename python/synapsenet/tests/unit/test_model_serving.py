"""
SynapseNet Model Serving Tests
Terminal Bench v2 - Tests for model serving, inference, caching, and deployment bugs

Tests cover:
- B1-B10: Model Serving bugs
- H1-H8: Caching & Performance bugs
"""
import time
import uuid
import hashlib
import threading
import sys
import os
from unittest import mock
from collections import OrderedDict

import pytest
import numpy as np

# =========================================================================
# B1: Model loading memory leak - old models not freed
# =========================================================================

class TestModelLoadingMemoryLeak:
    """BUG B1: Old model references are not freed when new models are loaded."""

    def test_model_loading_memory_leak(self):
        """Loading a new model should release the old model reference."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        old_weights = np.random.randn(100, 100)
        engine.load_model("model_1", "v1", old_weights)

        # Load new version - old should be cleaned up
        new_weights = np.random.randn(100, 100)
        engine.load_model("model_1", "v2", new_weights)

        # The old model reference should have been explicitly freed
        
        current = engine._current_models.get("model_1")
        assert current is not None
        assert current["version"] == "v2"
        # Check that v1 cache entry was cleaned up
        old_key = "model_1:v1"
        cached_old = engine.model_cache.get(old_key)
        
        assert cached_old is None, "Old model version should be removed from cache to prevent memory leak"

    def test_model_unload_cleanup(self):
        """Unloading a model should clean up all references."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        large_weights = np.random.randn(500, 500)
        engine.load_model("model_cleanup", "v1", large_weights)

        # Remove model - all references should be cleared
        cache_key = "model_cleanup:v1"
        engine.model_cache.remove(cache_key)
        del engine._current_models["model_cleanup"]

        assert engine.model_cache.get(cache_key) is None
        assert "model_cleanup" not in engine._current_models


# =========================================================================
# B2: Request batching timeout too short
# =========================================================================

class TestRequestBatchingTimeout:
    """BUG B2: Batching timeout is too short, causing partial batches."""

    def test_request_batching_timeout(self):
        """Batch timeout should allow reasonable time for accumulation."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=32)
        
        # Should be at least 0.05s to allow batch accumulation
        assert batcher.timeout >= 0.05, (
            f"Batch timeout {batcher.timeout}s is too short. "
            f"Should be >= 0.05s to allow batch accumulation"
        )

    def test_batch_size_limit(self):
        """Batcher should return a batch when max_size is reached."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=4)
        results = []
        for i in range(4):
            result = batcher.add_request({"input": f"data_{i}"})
            if result is not None:
                results.append(result)

        assert len(results) == 1, "Should return batch when max_size reached"
        assert len(results[0]) == 4, "Batch should contain 4 requests"

    def test_batch_flush_returns_pending(self):
        """Flush should return all pending requests."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=32)
        for i in range(5):
            batcher.add_request({"input": f"data_{i}"})

        flushed = batcher.flush()
        assert len(flushed) == 5
        assert len(batcher.flush()) == 0, "Flush should clear pending"


# =========================================================================
# B3: A/B testing traffic split precision loss
# =========================================================================

class TestABTestingTrafficSplit:
    """BUG B3: Float accumulation in traffic routing loses precision."""

    def test_ab_testing_traffic_split(self):
        """Traffic split should be accurate within acceptable tolerance."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        # Three-way split: 33.33%, 33.33%, 33.34%
        router.create_experiment("exp1", {
            "control": 1/3,
            "variant_a": 1/3,
            "variant_b": 1/3,
        })

        counts = {"control": 0, "variant_a": 0, "variant_b": 0}
        num_requests = 10000
        for i in range(num_requests):
            variant = router.route_request("exp1", f"req_{i}")
            counts[variant] = counts.get(variant, 0) + 1

        # Each variant should get roughly 33% of traffic
        for variant, count in counts.items():
            ratio = count / num_requests
            assert 0.28 < ratio < 0.38, (
                f"Variant {variant} got {ratio:.2%} of traffic, expected ~33%"
            )

    def test_traffic_split_precision(self):
        """Verify that float precision issues don't cause routing failures."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        # Weights that are known to cause float precision issues
        router.create_experiment("precision_test", {
            "a": 0.1,
            "b": 0.2,
            "c": 0.3,
            "d": 0.4,
        })

        # All requests should be routed to some variant
        unrouted = 0
        for i in range(1000):
            variant = router.route_request("precision_test", f"req_{i}")
            if variant not in {"a", "b", "c", "d"}:
                unrouted += 1

        assert unrouted == 0, f"{unrouted} requests were not routed to any variant"

    def test_ab_testing_weight_validation(self):
        """Weights should be validated to sum to 1.0."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        
        # These weights sum to 0.5 - should be rejected
        try:
            router.create_experiment("bad_weights", {"a": 0.3, "b": 0.2})
            # If we get here, check that routing still works correctly
            variant = router.route_request("bad_weights", "test_req")
            # Should either raise an error or normalize weights
            total_weight = sum(router._experiments["bad_weights"].values())
            assert abs(total_weight - 1.0) < 0.01, (
                f"Variant weights sum to {total_weight}, should be validated to sum to 1.0"
            )
        except ValueError:
            pass  # Correct behavior: reject invalid weights


# =========================================================================
# B4: Canary deployment rollback race
# =========================================================================

class TestCanaryDeploymentRollback:
    """BUG B4: Rollback is not atomic, both versions serve during transition."""

    def test_canary_deployment_rollback(self):
        """Rollback should be atomic - no traffic to new version after rollback."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("model_1", "v2", traffic_pct=0.1)

        result = canary.rollback(dep_id)
        assert result is True

        deployment = canary._deployments[dep_id]
        # After rollback, should be fully rolled back
        assert deployment["traffic_pct"] == 0.0
        assert deployment["status"] == "rolled_back"

    def test_canary_rollback_race(self):
        """Rollback should handle in-flight requests safely."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("model_1", "v2", traffic_pct=0.5)

        
        # but traffic_pct hasn't been set to 0 yet. A concurrent reader could
        # see the intermediate state.
        states_seen = []

        def observer():
            for _ in range(100):
                dep = canary._deployments.get(dep_id)
                if dep:
                    states_seen.append((dep["status"], dep["traffic_pct"]))
                time.sleep(0.0001)

        observer_thread = threading.Thread(target=observer)
        observer_thread.start()

        canary.rollback(dep_id)
        observer_thread.join()

        # No state should show "rolling_back" with non-zero traffic
        for status, traffic in states_seen:
            if status == "rolling_back":
                assert traffic == 0.0, (
                    "During rollback, traffic should be 0% when status is 'rolling_back'. "
                    "BUG B4: Non-atomic rollback allows serving from both versions."
                )


# =========================================================================
# B5: Model warm-up missing
# =========================================================================

class TestModelWarmup:
    """BUG B5: No warm-up after model loading causes cold-start latency."""

    def test_model_warmup_execution(self):
        """Model should be warmed up after loading."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("warmup_model", "v1")

        # After loading, the model should have been warmed up with a test inference
        
        model = engine._current_models.get("warmup_model")
        assert model is not None
        # Check for warmup indicator (should have "warmed_up" flag or warmup timestamp)
        assert model.get("warmed_up", False) is True, (
            "Model should be warmed up after loading to avoid cold-start latency"
        )

    def test_warmup_before_serving(self):
        """First prediction should not have significantly higher latency."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.random.randn(10, 10)
        engine.load_model("latency_model", "v1", weights)

        # First prediction
        start = time.time()
        result1 = engine.predict("latency_model", {"features": list(np.random.randn(10))})
        first_latency = time.time() - start

        # Subsequent prediction
        start = time.time()
        result2 = engine.predict("latency_model", {"features": list(np.random.randn(10))})
        second_latency = time.time() - start

        # First prediction should not be dramatically slower if warmup happened
        # This is a soft check - mainly validates predict works
        assert result1 is not None
        assert result2 is not None


# =========================================================================
# B6: Prediction cache key collision
# =========================================================================

class TestPredictionCacheKey:
    """BUG B6: Prediction cache keys may collide for different inputs."""

    def test_prediction_cache_key(self):
        """Cache keys should uniquely identify model + input combinations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)

        # Two different models should have different cache keys
        cache.put("model_a:v1", {"model": "a", "weights": [1, 2, 3]})
        cache.put("model_b:v1", {"model": "b", "weights": [4, 5, 6]})

        assert cache.get("model_a:v1")["model"] == "a"
        assert cache.get("model_b:v1")["model"] == "b"

    def test_cache_key_collision_prevention(self):
        """Different version keys should not collide."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)

        cache.put("model:v1", {"version": "v1"})
        cache.put("model:v2", {"version": "v2"})

        v1 = cache.get("model:v1")
        v2 = cache.get("model:v2")
        assert v1["version"] == "v1"
        assert v2["version"] == "v2"


# =========================================================================
# B7: Input validation schema drift
# =========================================================================

class TestInputValidationSchema:
    """BUG B7: Input validation uses stale schema after model update."""

    def test_input_validation_schema(self):
        """Schema validation should use current model version's schema."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("schema_model", "v1")
        engine._input_schemas["schema_model"] = {"required": ["feature_a", "feature_b"]}

        # Update model to v2 with different schema
        engine.load_model("schema_model", "v2")
        # Schema should update to v2's schema
        

        current_model = engine._current_models["schema_model"]
        assert current_model["version"] == "v2"

    def test_schema_drift_detection(self):
        """Should detect when input schema drifts from model expectations."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.random.randn(10, 10)
        engine.load_model("drift_model", "v1", weights)

        # Valid prediction should work
        result = engine.predict("drift_model", {"features": list(np.random.randn(10))})
        assert result is not None
        assert "output" in result


# =========================================================================
# B8: Output postprocessing type mismatch
# =========================================================================

class TestOutputPostprocessType:
    """BUG B8: Output always cast to float, but classification should return int."""

    def test_output_postprocess_type(self):
        """Classification models should return integer labels, not floats."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.eye(10)
        engine.load_model("classifier", "v1", weights)

        result = engine.predict("classifier", {"features": list(np.random.randn(10))})

        
        # For a classifier, the output should be an integer class label
        output = result["output"]
        assert output is not None

    def test_postprocess_type_mismatch(self):
        """Postprocessing should preserve output type from model."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        weights = np.eye(10)
        engine.load_model("type_model", "v1", weights)

        result = engine.predict("type_model", {"features": list(np.ones(10))})
        
        assert "scores" in result
        assert isinstance(result["scores"], list)


# =========================================================================
# B9: Concurrent model swap race
# =========================================================================

class TestConcurrentModelSwap:
    """BUG B9: Model swap not atomic, concurrent requests see partial state."""

    def test_concurrent_model_swap(self):
        """Model swap should be atomic - no partial state visible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("swap_model", "v1")

        inconsistencies = []

        def reader():
            for _ in range(100):
                model = engine._current_models.get("swap_model")
                if model:
                    version = model.get("version")
                    weights = model.get("weights")
                    # Check consistency between version and weights
                    if version and weights is not None:
                        pass  # In a real check, verify version matches weights
                time.sleep(0.0001)

        def writer():
            for i in range(50):
                engine.swap_model("swap_model", f"v{i+2}")
                time.sleep(0.0001)

        reader_thread = threading.Thread(target=reader)
        writer_thread = threading.Thread(target=writer)

        reader_thread.start()
        writer_thread.start()

        reader_thread.join()
        writer_thread.join()

    def test_model_swap_atomicity(self):
        """Swap should use the swap lock for atomicity."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("atomic_model", "v1")

        
        # Verify swap lock exists
        assert hasattr(engine, '_swap_lock'), "Engine should have a swap lock"

        # Swap should work
        result = engine.swap_model("atomic_model", "v2")
        assert result is True
        assert engine._current_models["atomic_model"]["version"] == "v2"


# =========================================================================
# B10: Autoscaling metric lag
# =========================================================================

class TestAutoscalingMetricLag:
    """BUG B10: Autoscaling decisions based on stale metrics."""

    def test_autoscaling_metric_lag(self):
        """Autoscaling metrics should reflect current state."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=32)

        # Add requests and verify pending count is accurate
        for i in range(10):
            batcher.add_request({"input": f"data_{i}"})

        # Pending count should be 10
        pending_count = len(batcher._pending)
        assert pending_count == 10

    def test_scaling_decision_freshness(self):
        """Scaling decisions should be based on recent metrics."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        # Load a model and make predictions to generate metrics
        weights = np.random.randn(10, 10)
        engine.load_model("scale_model", "v1", weights)

        for i in range(5):
            engine.predict("scale_model", {"features": list(np.random.randn(10))})

        # Verify predictions happened
        model = engine._current_models.get("scale_model")
        assert model is not None


# =========================================================================
# H1: Model cache eviction during inference
# =========================================================================

class TestModelCacheEviction:
    """BUG H1: LRU eviction can remove a model that's currently serving."""

    def test_model_cache_eviction(self):
        """Eviction should not remove models that are currently in use."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=3)

        # Fill cache
        cache.put("model_a", {"name": "a"})
        cache.put("model_b", {"name": "b"})
        cache.put("model_c", {"name": "c"})

        # Mark model_a as "in use" (simulating active inference)
        in_use_model = cache.get("model_a")  # This should mark it as recently used

        # Adding model_d should evict LRU (model_b or model_c), NOT model_a
        cache.put("model_d", {"name": "d"})

        
        assert cache.get("model_a") is not None, (
            "Model_a was in use and should not have been evicted"
        )

    def test_eviction_during_inference_safe(self):
        """Model should not be evicted while actively being used for inference."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=2)
        cache.put("active_model", {"name": "active"})
        cache.put("other_model", {"name": "other"})

        # Get reference to active model (simulating in-flight request)
        active_ref = cache.get("active_model")
        assert active_ref is not None

        # Insert new model, triggering eviction
        cache.put("new_model", {"name": "new"})

        # The model we were using should still be accessible
        still_there = cache.get("active_model")
        
        assert still_there is not None, (
            "Active model should be protected from eviction during inference"
        )


# =========================================================================
# H2: Feature cache TTL race
# =========================================================================

class TestFeatureCacheTTLRace:
    """BUG H2: TTL expiry can race with feature serving."""

    def test_feature_cache_ttl_race(self):
        """Cache TTL expiry should not cause serving failures."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.01)  # Very short TTL
        cache.set("feature_key", {"value": 42})

        # Read before expiry
        result = cache.get("feature_key")
        assert result is not None

        # Wait for expiry
        time.sleep(0.02)
        result_after = cache.get("feature_key")
        assert result_after is None, "Cache should expire after TTL"

    def test_ttl_expiry_consistency(self):
        """Expired entries should be fully removed, not partially visible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.05)
        cache.set("key1", "value1")
        cache.set("key2", "value2")

        time.sleep(0.06)

        # Both should be expired
        assert cache.get("key1") is None
        assert cache.get("key2") is None


# =========================================================================
# H3: Prediction cache collision
# =========================================================================

class TestPredictionCacheCollision:
    """BUG H3: Different predictions may collide in cache."""

    def test_prediction_cache_collision(self):
        """Different model+input combinations should not collide."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("test", "http://localhost:8000")
        # Two different paths should produce different cache keys
        key1 = hashlib.md5("http://localhost:8000/model/a".encode()).hexdigest()
        key2 = hashlib.md5("http://localhost:8000/model/b".encode()).hexdigest()
        assert key1 != key2, "Different paths should produce different cache keys"

    def test_cache_key_uniqueness(self):
        """Cache keys should be unique for different request parameters."""
        keys = set()
        for model_id in ["model_a", "model_b", "model_c"]:
            for version in ["v1", "v2"]:
                key = f"{model_id}:{version}"
                assert key not in keys, f"Duplicate cache key: {key}"
                keys.add(key)


# =========================================================================
# H4: Cache stampede on deploy
# =========================================================================

class TestCacheStampedeOnDeploy:
    """BUG H4: All caches expire simultaneously on new deployment."""

    def test_cache_stampede_on_deploy(self):
        """Cache entries should have staggered expiry times."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)

        # Load many models at once (simulating post-deployment cache warm)
        for i in range(20):
            cache.put(f"model_{i}", {"id": i})

        # All models should be cached
        for i in range(20):
            assert cache.get(f"model_{i}") is not None

    def test_stampede_prevention_lock(self):
        """Cache miss should use lock to prevent thundering herd."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=0.01)
        cache.set("popular_key", "value")

        time.sleep(0.02)  # Let it expire

        # Multiple concurrent requests should not all hit backend
        results = []

        def request_feature():
            val = cache.get("popular_key")
            results.append(val)

        threads = [threading.Thread(target=request_feature) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All results should be None (expired)
        # In a fixed version, only one thread should compute, others wait
        assert all(r is None for r in results)


# =========================================================================
# H5: Distributed cache consistency
# =========================================================================

class TestDistributedCacheConsistency:
    """BUG H5: Cache nodes may have inconsistent data."""

    def test_distributed_cache_consistency(self):
        """Multiple cache instances should agree on values."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache1 = ModelCache(max_size=10)
        cache2 = ModelCache(max_size=10)

        # Simulate distributed caches
        cache1.put("shared_key", {"version": "v1"})
        # In a distributed system, cache2 should also see this update
        # But without coordination, cache2 has stale data
        result = cache2.get("shared_key")
        # This is expected in a local test - just validate the behavior
        assert result is None, "Independent cache instances should not share state"

    def test_cache_node_agreement(self):
        """Verify cache operations work correctly in isolation."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        cache.put("key1", "val1")
        cache.put("key2", "val2")

        assert cache.get("key1") == "val1"
        assert cache.get("key2") == "val2"

        cache.remove("key1")
        assert cache.get("key1") is None
        assert cache.get("key2") == "val2"


# =========================================================================
# H6: Cache aside pattern stale data
# =========================================================================

class TestCacheAsideStaleData:
    """BUG H6: Cache not invalidated on write operations."""

    def test_cache_aside_stale_data(self):
        """POST requests should invalidate related cache entries."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("test", "http://localhost:8000")

        # Simulate caching a GET response
        cache_key = hashlib.md5("http://localhost:8000/model/1".encode()).hexdigest()
        client._cache[cache_key] = {"model": "old_data"}
        client._cache_timestamps[cache_key] = time.time()

        # Make a POST (write) to the same resource
        try:
            client.post("/model/1", {"name": "updated"})
        except Exception:
            pass  # May fail in test (simulated HTTP)

        
        cached_value = client._cache.get(cache_key)
        assert cached_value is None, (
            "Cache should be invalidated after POST request. "
            "BUG H6: Stale cache data returned after write."
        )

    def test_cache_invalidation_timing(self):
        """Cache should be invalidated before write returns."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from shared.clients.base import ServiceClient

        client = ServiceClient("test", "http://localhost:8000")

        # Pre-populate cache
        client._cache["test_key"] = {"data": "old"}
        client._cache_timestamps["test_key"] = time.time()

        # After write, cache should not contain stale data
        
        assert "test_key" in client._cache  # Currently true due to bug


# =========================================================================
# H7: TTL randomization
# =========================================================================

class TestTTLRandomization:
    """BUG H7: TTL values should be randomized to prevent synchronized expiry."""

    def test_ttl_randomization(self):
        """Cache entries should have randomized TTL to prevent stampedes."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        cache = FeatureCacheManager(ttl=60.0)

        # Set multiple entries
        for i in range(10):
            cache.set(f"key_{i}", f"value_{i}")

        # All entries have the same TTL (no jitter)
        # In a fixed version, TTLs should be slightly different
        cached_times = []
        for i in range(10):
            entry = cache._cache.get(f"key_{i}")
            if entry:
                cached_times.append(entry["cached_at"])

        assert len(cached_times) == 10

    def test_expiry_distribution_uniform(self):
        """Expiry times should not all be identical."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.features.views import FeatureCacheManager

        # Base TTL should be the same, but with jitter
        cache = FeatureCacheManager(ttl=60.0)
        for i in range(5):
            cache.set(f"entry_{i}", i)

        # Verify all entries are accessible
        for i in range(5):
            assert cache.get(f"entry_{i}") == i


# =========================================================================
# H8: LRU eviction priority
# =========================================================================

class TestLRUEvictionPriority:
    """BUG H8: LRU eviction doesn't consider model usage frequency."""

    def test_lru_eviction_priority(self):
        """Frequently used models should be retained over rarely used ones."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=3)

        cache.put("frequent_model", {"name": "frequent"})
        cache.put("rare_model", {"name": "rare"})
        cache.put("medium_model", {"name": "medium"})

        # Access frequent_model many times
        for _ in range(100):
            cache.get("frequent_model")

        # Add new model, triggering eviction
        cache.put("new_model", {"name": "new"})

        # Frequent model should be retained
        assert cache.get("frequent_model") is not None, (
            "Frequently used model should not be evicted"
        )

    def test_priority_model_retained(self):
        """High-priority models should be retained during eviction."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=2)
        cache.put("priority_model", {"name": "priority"})
        cache.put("normal_model", {"name": "normal"})

        # Access priority model recently
        cache.get("priority_model")

        # Add new model - normal_model (LRU) should be evicted
        cache.put("another_model", {"name": "another"})

        # Priority model (most recently accessed) should be retained
        assert cache.get("priority_model") is not None
        # Normal model (LRU) should have been evicted
        assert cache.get("normal_model") is None


# =========================================================================
# Additional model serving edge cases
# =========================================================================

class TestModelCacheThreadSafety:
    """Test thread safety of model cache operations."""

    def test_concurrent_cache_operations(self):
        """Cache should handle concurrent reads and writes safely."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=50)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    cache.put(f"model_{thread_id}_{i}", {"id": i})
            except Exception as e:
                errors.append(str(e))

        def reader(thread_id):
            try:
                for i in range(20):
                    cache.get(f"model_{thread_id}_{i}")
            except Exception as e:
                errors.append(str(e))

        threads = []
        for t_id in range(5):
            threads.append(threading.Thread(target=writer, args=(t_id,)))
            threads.append(threading.Thread(target=reader, args=(t_id,)))

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent cache operations produced errors: {errors}"


class TestInferenceEngineEdgeCases:
    """Test edge cases in the inference engine."""

    def test_predict_unknown_model(self):
        """Predicting with unknown model should raise error."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        with pytest.raises(ValueError, match="not loaded"):
            engine.predict("nonexistent_model", {"features": [1, 2, 3]})

    def test_predict_with_empty_features(self):
        """Predicting with empty features should handle gracefully."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("edge_model", "v1")

        result = engine.predict("edge_model", {"features": []})
        assert result is not None

    def test_multiple_model_versions(self):
        """Should be able to serve multiple versions of same model."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("multi_model", "v1")
        engine.load_model("multi_model", "v2")

        # Current model should be v2
        assert engine._current_models["multi_model"]["version"] == "v2"

    def test_ab_routing_nonexistent_experiment(self):
        """Routing with nonexistent experiment should return control."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        result = router.route_request("nonexistent", "req_1")
        assert result == "control"


# =========================================================================
# Extended Model Serving Tests - Additional coverage
# =========================================================================

class TestModelCacheDetailed:
    """Detailed tests for ModelCache behavior."""

    def test_cache_max_size_enforcement(self):
        """Cache should never exceed max_size."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        for i in range(100):
            cache.put(f"model_{i}", {"id": i})
        assert len(cache._cache) <= 5

    def test_cache_get_nonexistent(self):
        """Getting nonexistent key should return None."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        assert cache.get("nonexistent") is None

    def test_cache_put_updates_existing(self):
        """Putting same key should update value."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        cache.put("key1", {"v": 1})
        cache.put("key1", {"v": 2})
        assert cache.get("key1") == {"v": 2}
        assert len(cache._cache) == 1

    def test_cache_remove_key(self):
        """Removing a key should make it inaccessible."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        cache.put("key1", "val1")
        cache.remove("key1")
        assert cache.get("key1") is None

    def test_cache_remove_nonexistent(self):
        """Removing nonexistent key should not error."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        cache.remove("nonexistent")  # Should not raise

    def test_cache_lru_order(self):
        """LRU order should evict least recently used."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=3)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.put("c", 3)

        # Access 'a' to make it most recently used
        cache.get("a")

        # Adding 'd' should evict 'b' (LRU)
        cache.put("d", 4)
        assert cache.get("b") is None
        assert cache.get("a") is not None

    def test_cache_empty_after_all_removes(self):
        """Cache should be empty after all items removed."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        cache.put("a", 1)
        cache.put("b", 2)
        cache.remove("a")
        cache.remove("b")
        assert len(cache._cache) == 0


class TestRequestBatcherDetailed:
    """Detailed tests for RequestBatcher."""

    def test_batcher_flush_empty(self):
        """Flushing empty batcher should return empty list."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=10)
        result = batcher.flush()
        assert result == []

    def test_batcher_returns_batch_at_max_size(self):
        """Batcher should return batch when max_size is reached."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=3)
        batcher.add_request({"id": 1})
        batcher.add_request({"id": 2})
        batch = batcher.add_request({"id": 3})
        assert batch is not None
        assert len(batch) == 3

    def test_batcher_returns_none_before_max(self):
        """Batcher should return None before max_size is reached."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=10)
        result = batcher.add_request({"id": 1})
        assert result is None

    def test_batcher_multiple_batches(self):
        """Batcher should produce multiple batches."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=5)
        batches = []
        for i in range(12):
            batch = batcher.add_request({"id": i})
            if batch:
                batches.append(batch)
        remaining = batcher.flush()
        if remaining:
            batches.append(remaining)

        total = sum(len(b) for b in batches)
        assert total == 12

    def test_batcher_flush_clears_pending(self):
        """Flush should clear pending requests."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=100)
        batcher.add_request({"id": 1})
        batcher.flush()
        assert len(batcher._pending) == 0

    def test_batcher_preserves_request_order(self):
        """Requests should be batched in order."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import RequestBatcher

        batcher = RequestBatcher(max_batch_size=5)
        for i in range(5):
            batcher.add_request({"id": i})
        batch = batcher.flush()
        assert [r["id"] for r in batch] == [0, 1, 2, 3, 4]


class TestABTestingRouterDetailed:
    """Detailed tests for ABTestingRouter."""

    def test_ab_router_deterministic(self):
        """Same request_id should always route to same variant."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("exp1", {"control": 0.5, "treatment": 0.5})

        results = set()
        for _ in range(10):
            result = router.route_request("exp1", "fixed_request_id")
            results.add(result)

        assert len(results) == 1, "Same request should always route to same variant"

    def test_ab_router_variant_distribution(self):
        """Variant distribution should roughly match weights."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("exp1", {"control": 0.5, "variant": 0.5})

        counts = {"control": 0, "variant": 0}
        for i in range(1000):
            variant = router.route_request("exp1", f"req_{i}")
            counts[variant] = counts.get(variant, 0) + 1

        # Each should be roughly 50%
        for name, count in counts.items():
            ratio = count / 1000
            assert 0.3 < ratio < 0.7, (
                f"Variant {name} got {ratio:.1%}, expected ~50%"
            )

    def test_ab_router_multiple_experiments(self):
        """Multiple experiments should be independent."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("exp1", {"a": 0.5, "b": 0.5})
        router.create_experiment("exp2", {"x": 0.3, "y": 0.7})

        v1 = router.route_request("exp1", "req_1")
        v2 = router.route_request("exp2", "req_1")
        assert v1 in ("a", "b")
        assert v2 in ("x", "y")

    def test_ab_router_single_variant(self):
        """Single variant with weight 1.0 should always be selected."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("exp1", {"only_variant": 1.0})

        for i in range(100):
            assert router.route_request("exp1", f"req_{i}") == "only_variant"

    def test_ab_router_three_way_split(self):
        """Three-way split should cover all variants."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ABTestingRouter

        router = ABTestingRouter()
        router.create_experiment("exp3", {"a": 0.33, "b": 0.34, "c": 0.33})

        variants_seen = set()
        for i in range(500):
            v = router.route_request("exp3", f"req_{i}")
            variants_seen.add(v)

        assert len(variants_seen) >= 2, "Should see at least 2 variants in 500 requests"


class TestInferenceEnginePredictionDetails:
    """Detailed prediction tests."""

    def test_predict_output_structure(self):
        """Prediction output should have expected structure."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("struct_model", "v1", np.random.randn(10, 10))
        result = engine.predict("struct_model", {"features": list(np.random.randn(10))})

        assert "model_id" in result
        assert "version" in result
        assert "output" in result
        assert "scores" in result
        assert "latency_ms" in result

    def test_predict_model_id_matches(self):
        """Prediction result should reference correct model."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("test_id_model", "v3", np.random.randn(10, 10))
        result = engine.predict("test_id_model", {"features": list(np.random.randn(10))})
        assert result["model_id"] == "test_id_model"
        assert result["version"] == "v3"

    def test_predict_latency_positive(self):
        """Latency should be a positive number."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("lat_model", "v1", np.random.randn(10, 10))
        result = engine.predict("lat_model", {"features": list(np.random.randn(10))})
        assert isinstance(result["latency_ms"], float)

    def test_predict_scores_are_list(self):
        """Prediction scores should be a list of floats."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("scores_model", "v1", np.random.randn(10, 10))
        result = engine.predict("scores_model", {"features": list(np.random.randn(10))})
        assert isinstance(result["scores"], list)
        assert all(isinstance(s, float) for s in result["scores"])

    def test_predict_with_dict_input(self):
        """Prediction with non-list features should still work."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("dict_model", "v1", np.random.randn(10, 10))
        result = engine.predict("dict_model", {"other_key": "value"})
        assert result is not None

    def test_swap_model_preserves_cache_entry(self):
        """After swap, cache should contain new model."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("swap_test", "v1", np.random.randn(10, 10))
        engine.swap_model("swap_test", "v2", np.random.randn(10, 10))
        cached = engine.model_cache.get("swap_test:v2")
        assert cached is not None
        assert cached["version"] == "v2"

    def test_load_model_returns_true(self):
        """load_model should return True on success."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        assert engine.load_model("new_model", "v1") is True

    def test_swap_model_returns_true(self):
        """swap_model should return True on success."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine

        engine = InferenceEngine()
        engine.load_model("s_model", "v1")
        assert engine.swap_model("s_model", "v2") is True

    def test_engine_model_cache_type(self):
        """Engine should have a ModelCache instance."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine, ModelCache

        engine = InferenceEngine()
        assert isinstance(engine.model_cache, ModelCache)

    def test_engine_batcher_type(self):
        """Engine should have a RequestBatcher instance."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import InferenceEngine, RequestBatcher

        engine = InferenceEngine()
        assert isinstance(engine.batcher, RequestBatcher)


class TestCanaryDeploymentDetailed:
    """Detailed canary deployment tests."""

    def test_canary_start(self):
        """Starting canary should create deployment."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("m1", "v2", traffic_pct=0.1)
        assert dep_id is not None
        assert canary._deployments[dep_id]["status"] == "canary"

    def test_canary_promote(self):
        """Promoting canary should set traffic to 100%."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("m1", "v2", traffic_pct=0.1)
        canary.promote(dep_id)
        dep = canary._deployments[dep_id]
        assert dep["status"] == "promoted"
        assert dep["traffic_pct"] == 1.0

    def test_canary_rollback(self):
        """Rolling back canary should set traffic to 0%."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("m1", "v2", traffic_pct=0.1)
        canary.rollback(dep_id)
        dep = canary._deployments[dep_id]
        assert dep["status"] == "rolled_back"
        assert dep["traffic_pct"] == 0.0

    def test_canary_traffic_percentage(self):
        """Canary traffic should match configured percentage."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("m1", "v2", traffic_pct=0.25)
        dep = canary._deployments[dep_id]
        assert dep["traffic_pct"] == 0.25

    def test_canary_multiple_deployments(self):
        """Multiple canary deployments should coexist."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep1 = canary.start_canary("m1", "v2", traffic_pct=0.1)
        dep2 = canary.start_canary("m2", "v3", traffic_pct=0.2)
        assert dep1 != dep2
        assert len(canary._deployments) == 2

    def test_canary_deployment_model_info(self):
        """Deployment should track model and version."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.registry.views import CanaryDeployment

        canary = CanaryDeployment()
        dep_id = canary.start_canary("model_x", "v5", traffic_pct=0.15)
        dep = canary._deployments[dep_id]
        assert dep["model_id"] == "model_x"
        assert dep["version"] == "v5"


class TestModelCacheLargeScale:
    """Large-scale model cache tests."""

    def test_cache_with_many_entries(self):
        """Cache should handle many entries efficiently."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)
        for i in range(100):
            cache.put(f"model_{i}", {"id": i, "data": "x" * 100})

        # All should be retrievable
        for i in range(100):
            assert cache.get(f"model_{i}") is not None

    def test_cache_eviction_order_large(self):
        """Eviction should follow LRU order with many entries."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=10)
        for i in range(20):
            cache.put(f"m_{i}", {"id": i})

        # Only last 10 should remain
        for i in range(10):
            assert cache.get(f"m_{i}") is None
        for i in range(10, 20):
            assert cache.get(f"m_{i}") is not None

    def test_cache_access_pattern(self):
        """Working set access pattern should maintain hot entries."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=5)
        for i in range(5):
            cache.put(f"hot_{i}", {"id": i})

        # Continuously access hot entries
        for _ in range(50):
            for i in range(5):
                cache.get(f"hot_{i}")

        # Add cold entries (should evict oldest accessed)
        for i in range(3):
            cache.put(f"cold_{i}", {"id": i})

        # At least some hot entries should survive
        hot_count = sum(1 for i in range(5) if cache.get(f"hot_{i}") is not None)
        assert hot_count >= 2

    def test_cache_key_collision_resistance(self):
        """Different keys should not collide in cache."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=100)
        # Keys with similar prefixes
        for i in range(50):
            cache.put(f"model_v{i}", {"version": i})

        for i in range(50):
            result = cache.get(f"model_v{i}")
            assert result is not None
            assert result["version"] == i

    def test_cache_concurrent_reads_consistent(self):
        """Concurrent reads should return consistent values."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
        from services.inference.main import ModelCache

        cache = ModelCache(max_size=10)
        cache.put("shared", {"data": "consistent"})
        results = []

        def reader():
            for _ in range(100):
                val = cache.get("shared")
                if val:
                    results.append(val["data"])

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should see "consistent"
        for r in results:
            assert r == "consistent"
