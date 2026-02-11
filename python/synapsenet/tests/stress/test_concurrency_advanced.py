"""
SynapseNet Advanced Concurrency Tests
Tests for deeper concurrency issues: lock ordering, barrier races,
checkpoint consistency, and distributed coordination.
"""
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestDistributedLockOrdering:
    """Test distributed lock ABBA deadlock potential."""

    def test_no_deadlock_acquiring_multiple_locks(self):
        """Acquiring multiple locks should not deadlock."""
        from shared.utils.distributed import DistributedLock

        lock_a = DistributedLock(lock_name="resource_a", ttl=5)
        lock_b = DistributedLock(lock_name="resource_b", ttl=5)
        completed = []
        errors = []

        def task_ab():
            try:
                if lock_a.acquire(timeout=2.0):
                    time.sleep(0.01)
                    if lock_b.acquire(timeout=2.0):
                        completed.append("ab")
                        lock_b.release()
                    lock_a.release()
            except Exception as e:
                errors.append(f"ab: {e}")

        def task_ba():
            try:
                if lock_b.acquire(timeout=2.0):
                    time.sleep(0.01)
                    if lock_a.acquire(timeout=2.0):
                        completed.append("ba")
                        lock_a.release()
                    lock_b.release()
            except Exception as e:
                errors.append(f"ba: {e}")

        t1 = threading.Thread(target=task_ab)
        t2 = threading.Thread(target=task_ba)
        t1.start()
        t2.start()
        t1.join(timeout=5.0)
        t2.join(timeout=5.0)

        alive = sum(1 for t in [t1, t2] if t.is_alive())
        assert alive == 0, (
            f"{alive} threads still alive after 5s - all operations should complete within timeout"
        )

    def test_lock_context_manager_no_leak(self):
        """Lock should be properly released even on exception."""
        from shared.utils.distributed import DistributedLock

        lock = DistributedLock(lock_name="test", ttl=5)

        try:
            with lock:
                raise ValueError("test error")
        except ValueError:
            pass

        # Lock should be released and acquirable again
        acquired = lock.acquire(timeout=1.0)
        assert acquired, "Lock should be acquirable after exception in context manager"
        lock.release()


class TestAllReduceBarrierRace:
    """Test AllReduce barrier count under high contention."""

    def test_barrier_count_accuracy(self):
        """Barrier count should exactly equal number of submitting workers."""
        from shared.utils.distributed import AllReduceCoordinator

        for trial in range(5):
            num_workers = 8
            coordinator = AllReduceCoordinator(num_workers=num_workers)
            barrier = threading.Barrier(num_workers)

            def submit(wid):
                barrier.wait()
                coordinator.submit_gradients(f"w-{wid}", {"g": float(wid)})

            threads = [threading.Thread(target=submit, args=(i,)) for i in range(num_workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=5.0)

            # After all workers submit, barrier should have reset to 0
            assert coordinator._barrier_count == 0, (
                f"Trial {trial}: barrier should reset after all workers submit, "
                f"got {coordinator._barrier_count}"
            )


class TestCheckpointConcurrentWriteRead:
    """Test checkpoint save/load under concurrent access."""

    def test_concurrent_checkpoint_save(self):
        """Concurrent checkpoint saves should not corrupt the file."""
        import tempfile
        import json
        from shared.ml.model_loader import ModelLoader

        loader = ModelLoader(storage_path=tempfile.mkdtemp())
        errors = []

        def save_checkpoint(thread_id):
            try:
                weights = {"layer": [float(thread_id)] * 100}
                path = loader.save_checkpoint(
                    f"model-concurrent", f"v{thread_id}", weights,
                    {"thread": thread_id}
                )
                # Verify the saved checkpoint is valid JSON
                loaded = loader.load_checkpoint(path)
                assert "weights" in loaded
                assert loaded["version"] == f"v{thread_id}"
            except (json.JSONDecodeError, AssertionError) as e:
                errors.append(f"Thread {thread_id}: {e}")

        threads = [threading.Thread(target=save_checkpoint, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Without the save lock, concurrent writes can corrupt JSON
        if errors:
            pytest.fail(
                f"Concurrent checkpoint saves produced corrupted files: {errors[:3]}. "
                f"concurrent saves should not produce corrupted files"
            )


class TestRingAllReduceNodeFailure:
    """Test ring allreduce handles node failure correctly."""

    def test_reduce_with_all_workers(self):
        """Reduce with all workers present should succeed."""
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w-0", "w-1", "w-2"])
        ring.submit("w-0", np.array([1.0, 2.0]))
        ring.submit("w-1", np.array([3.0, 4.0]))
        ring.submit("w-2", np.array([5.0, 6.0]))

        result = ring.reduce()
        assert result is not None
        expected = np.array([3.0, 4.0])  # Average
        assert np.allclose(result, expected), (
            f"Ring reduce average should be {expected}, got {result}"
        )

    def test_reduce_after_node_removal(self):
        """After removing a node, ring should still function with remaining workers."""
        from services.training.tasks import RingAllReduce

        ring = RingAllReduce(["w-0", "w-1", "w-2"])
        ring.remove_worker("w-1")

        ring.submit("w-0", np.array([2.0, 4.0]))
        ring.submit("w-2", np.array([6.0, 8.0]))

        result = ring.reduce()
        assert result is not None, (
            "reduce should work with remaining workers"
        )

        if result is not None:
            expected = np.array([4.0, 6.0])
            assert np.allclose(result, expected), (
                f"Average of [2,4] and [6,8] should be [4,6], got {result}"
            )


class TestGradientAccumulationOverflow:
    """Test gradient accumulation handles extreme values."""

    def test_large_gradient_accumulation(self):
        """Very large gradients should not produce inf/NaN after accumulation."""
        from shared.ml.model_loader import GradientAccumulator

        acc = GradientAccumulator(accumulation_steps=4)

        large_grad = {"layer": np.array([1e30, -1e30, 1e30])}
        for _ in range(4):
            acc.accumulate(large_grad)

        result = acc.get_accumulated()
        assert not np.any(np.isinf(result["layer"])), (
            f"Accumulated gradients should not overflow to inf. Got {result['layer']}"
        )
        assert not np.any(np.isnan(result["layer"])), (
            f"Accumulated gradients should not produce NaN. Got {result['layer']}"
        )

    def test_mixed_precision_nan_propagation(self):
        """Mixed precision accumulation should not propagate NaN."""
        from shared.ml.model_loader import GradientAccumulator

        acc = GradientAccumulator(accumulation_steps=2, use_mixed_precision=True)

        # With loss_scale=1.0 (the bug), this works fine
        # With proper loss_scale=65536, these values would overflow
        grad = {"layer": np.array([1e3, -1e3])}
        acc.accumulate(grad)
        acc.accumulate(grad)

        result = acc.get_accumulated()
        assert not np.any(np.isnan(result["layer"])), (
            "Mixed precision accumulation should not produce NaN"
        )


class TestCheckpointBarrierTimeout:
    """Test checkpoint barrier handles slow workers."""

    def test_barrier_with_slow_worker(self):
        """Barrier should handle one slow worker gracefully."""
        from services.training.tasks import CheckpointBarrier

        # Timeout of 1.0s is too short (bug A6)
        barrier = CheckpointBarrier(num_workers=3, timeout=1.0)
        results = []

        def fast_worker(wid):
            results.append(("fast", barrier.arrive(f"fast-{wid}")))

        def slow_worker():
            time.sleep(2.0)  # Arrives after timeout
            results.append(("slow", barrier.arrive("slow")))

        threads = [
            threading.Thread(target=fast_worker, args=(0,)),
            threading.Thread(target=fast_worker, args=(1,)),
            threading.Thread(target=slow_worker),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        # With timeout=1.0, fast workers will timeout before slow worker arrives
        fast_results = [r for name, r in results if name == "fast"]
        # At least one fast worker should timeout since slow worker is too slow
        assert False in fast_results or len(results) < 3, (
            "barrier should handle slow workers"
        )


class TestConsistentHashConcurrentModification:
    """Test consistent hash ring under concurrent node changes."""

    def test_concurrent_add_remove(self):
        """Concurrent add/remove should not corrupt the ring."""
        from shared.utils.distributed import ConsistentHashRing

        ring = ConsistentHashRing(["node-1", "node-2", "node-3"])
        errors = []

        def add_nodes():
            for i in range(10):
                try:
                    ring.add_node(f"new-node-{i}")
                except Exception as e:
                    errors.append(f"add: {e}")

        def remove_nodes():
            for i in range(10):
                try:
                    ring.remove_node(f"new-node-{i}")
                except Exception as e:
                    errors.append(f"remove: {e}")

        def lookup_keys():
            for i in range(100):
                try:
                    ring.get_node(f"key-{i}")
                except Exception as e:
                    errors.append(f"lookup: {e}")

        threads = [
            threading.Thread(target=add_nodes),
            threading.Thread(target=remove_nodes),
            threading.Thread(target=lookup_keys),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent hash ring operations failed: {errors[:5]}"


class TestAnomalyDetectorConcurrency:
    """Test anomaly detector under concurrent observations."""

    def test_concurrent_observations(self):
        """Concurrent observations should not corrupt statistics."""
        from services.monitoring.main import AnomalyDetector

        detector = AnomalyDetector(window_size=100)
        errors = []

        def observe_normal(metric, offset):
            np.random.seed(42 + offset)
            for _ in range(100):
                try:
                    detector.observe(metric, float(np.random.normal(50, 5)))
                except Exception as e:
                    errors.append(str(e))

        threads = [
            threading.Thread(target=observe_normal, args=("latency", i))
            for i in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Concurrent anomaly detection errors: {errors[:5]}"

        # Baseline should still be reasonable
        baseline = detector.get_baseline("latency")
        assert baseline is not None
        assert 40 < baseline["mean"] < 60, (
            f"Mean should be around 50 after normal observations, got {baseline['mean']}"
        )


class TestAlertThrottlerConcurrency:
    """Test alert throttler under concurrent alert generation."""

    def test_concurrent_alert_throttling(self):
        """Concurrent alerts should be properly throttled."""
        from services.monitoring.main import AlertThrottler

        throttler = AlertThrottler(window_seconds=60.0, max_alerts_per_window=5)
        allowed = []
        lock = threading.Lock()

        def generate_alerts():
            for _ in range(10):
                result = throttler.should_alert("high_latency")
                with lock:
                    allowed.append(result)

        threads = [threading.Thread(target=generate_alerts) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        total_allowed = sum(1 for a in allowed if a)
        assert total_allowed <= 5, (
            f"Throttler allowed {total_allowed} alerts with max_per_window=5. "
            f"concurrent alerts should respect the throttle limit"
        )
